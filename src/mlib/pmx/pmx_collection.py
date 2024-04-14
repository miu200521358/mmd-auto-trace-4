import os
from glob import glob
from typing import Iterable, Optional

import numpy as np
import OpenGL.GL as gl

from mlib.core.collection import (
    BaseHashModel,
    BaseIndexDictModel,
    BaseIndexNameDictModel,
)
from mlib.core.exception import MViewerException
from mlib.core.logger import MLogger
from mlib.core.math import MMatrix4x4, MMatrix4x4List, MVector3D, MVectorDict
from mlib.core.part import Switch
from mlib.pmx.bone_setting import STANDARD_BONE_NAMES, BoneFlg, BoneSettings
from mlib.pmx.mesh import IBO, VAO, VBO, Mesh
from mlib.pmx.pmx_part import (
    Bdef1,
    Bdef2,
    Bone,
    BoneMorphOffset,
    DisplaySlot,
    DisplaySlotReference,
    DisplayType,
    DrawFlg,
    Face,
    Joint,
    Material,
    Morph,
    MorphPanel,
    MorphType,
    RigidBody,
    ShaderMaterial,
    Texture,
    TextureType,
    ToonSharing,
    Vertex,
)
from mlib.pmx.pmx_tree import BoneTree, BoneTrees
from mlib.pmx.shader import MShader, ProgramType, VsLayout
from mlib.vmd.vmd_tree import VmdBoneFrameTrees

logger = MLogger(os.path.basename(__file__))
__ = logger.get_text


class Vertices(BaseIndexDictModel[Vertex]):
    """
    頂点リスト
    """

    def __init__(self) -> None:
        super().__init__()


class Faces(BaseIndexDictModel[Face]):
    """
    面リスト
    """

    def __init__(self) -> None:
        super().__init__()


class Textures(BaseIndexNameDictModel[Texture]):
    """
    テクスチャリスト
    """

    def __init__(self) -> None:
        super().__init__()


class ToonTextures(BaseIndexNameDictModel[Texture]):
    """
    共有テクスチャ辞書
    """

    def __init__(self) -> None:
        super().__init__()


class Materials(BaseIndexNameDictModel[Material]):
    """
    材質リスト
    """

    def __init__(self) -> None:
        super().__init__()


class Bones(BaseIndexNameDictModel[Bone]):
    """
    ボーンリスト
    """

    __slots__ = (
        "name",
        "data",
        "cache",
        "indexes",
        "_names",
        "is_bone_not_local_cancels",
        "local_axises",
        "parent_revert_matrixes",
        "bone_link_indexes",
    )

    def __init__(self) -> None:
        super().__init__()
        self.is_bone_not_local_cancels: list[bool] = [False]
        self.local_axises: list[MVector3D] = [MVector3D()]
        self.parent_revert_matrixes: np.ndarray = np.full((1, 4, 4), np.eye(4))
        self.bone_link_indexes: list[int] = []

    def setup(self) -> None:
        self.is_bone_not_local_cancels = [
            bone.is_not_local_cancel for bone in self.data.values()
        ]
        self.local_axises = [bone.local_axis for bone in self.data.values()]
        self.parent_revert_matrixes = np.array(
            [bone.parent_revert_matrix for bone in self.data.values()]
        )
        self.bone_link_indexes = [
            bidx
            for (_, bidx) in sorted(
                [(bone.layer, bone.index) for bone in self.data.values()]
            )
        ]

    def writable(self) -> list[Bone]:
        """出力対象となるボーン一覧を取得する"""
        bones: list[Bone] = []
        for b in self:
            if b.is_system:
                continue
            bones.append(b)
        return bones

    def create_bone_trees(self) -> BoneTrees:
        """
        ボーンツリー一括生成

        Returns
        -------
        BoneTrees
        """
        # ボーンツリー
        bone_trees = BoneTrees()
        total_index_count = len(self)

        # 計算ボーンリスト
        for i, end_bone in enumerate(self):
            if 0 > end_bone.index:
                continue
            # レイヤー込みのINDEXリスト取得を末端ボーンをキーとして保持
            end_bone.tree_indexes = []
            bone_tree = BoneTree(name=end_bone.name)
            for _, bidx in sorted(self.create_bone_link_indexes(end_bone.index)):
                bone_tree.append(self.data[bidx].copy())
                end_bone.tree_indexes.append(bidx)
            bone_trees.append(bone_tree, name=end_bone.name)

            logger.count(
                "モデルセットアップ：ボーンツリー",
                index=i,
                total_index_count=total_index_count,
                display_block=500,
            )

        return bone_trees

    @property
    def tail_bone_names(self) -> list[str]:
        """
        親ボーンとして登録されていないボーン名リストを取得する
        """
        tail_bone_names = []
        parent_bone_indexes = []
        for end_bone in self:
            parent_bone_indexes.append(end_bone.parent_index)

        for end_bone in self:
            if end_bone.index not in parent_bone_indexes:
                tail_bone_names.append(end_bone.name)

        return tail_bone_names

    def create_bone_link_indexes(
        self, child_idx: int, bone_link_indexes=None, loop=0
    ) -> list[tuple[int, int]]:
        """
        指定ボーンの親ボーンを繋げてく

        Parameters
        ----------
        child_idx : int
            指定ボーンINDEX
        bone_link_indexes : _type_, optional
            既に構築済みの親ボーンリスト, by default None

        Returns
        -------
        親ボーンリスト
        """
        if 0 > child_idx:
            return []

        # 階層＞リスト順（＞FK＞IK＞付与）
        if not bone_link_indexes:
            bone_link_indexes = [
                (self.data[child_idx].layer, self.data[child_idx].index)
            ]

        for b in reversed(self.data.values()):
            if (
                b.index == self.data[child_idx].parent_index
                and 0 <= b.index
                and loop < len(self.data)
                and (b.layer, b.index) not in bone_link_indexes
            ):
                bone_link_indexes.append((b.layer, b.index))
                return self.create_bone_link_indexes(
                    b.index, bone_link_indexes, loop + 1
                )

        return bone_link_indexes

    def get_tail_relative_position(self, bone_index: int) -> MVector3D:
        """
        末端位置を取得

        Parameters
        ----------
        bone_index : int
            ボーンINDEX

        Returns
        -------
        ボーンの末端位置（グローバル位置）
        """
        if bone_index not in self:
            return MVector3D()

        bone = self[bone_index]
        to_pos = MVector3D()

        from_pos = bone.position
        bone_setting = STANDARD_BONE_NAMES.get(bone.name)
        if bone_setting:
            for tail_bone_name in bone_setting.tails:
                if tail_bone_name in self:
                    return self[tail_bone_name].position - from_pos

        # 合致するのがなければ通常の表示先から検出
        if bone.is_tail_bone and 0 <= bone.tail_index and bone.tail_index in self:
            # 表示先が指定されているの場合、保持
            to_pos = self[bone.tail_index].position
        elif not bone.is_tail_bone and 0 < bone.tail_position.length():
            # 表示先が相対パスの場合、保持
            to_pos = from_pos + bone.tail_position
        else:
            # 表示先がない場合、とりあえず親ボーンからの向きにする
            from_pos = self[bone.parent_index].position
            to_pos = self[bone_index].position

        return to_pos - from_pos

    def get_parent_relative_position(self, bone_index: int) -> MVector3D:
        """親ボーンから見た相対位置"""
        bone = self[bone_index]
        return bone.position - (
            MVector3D()
            if bone.index < 0 or bone.parent_index not in self
            else self[bone.parent_index].position
        )

    def get_mesh_matrix(
        self, fidx: int, matrixes: MMatrix4x4List, bone_index: int, matrix: np.ndarray
    ) -> np.ndarray:
        """
        スキンメッシュアニメーション用ボーン変形行列を作成する

        Parameters
        ----------
        fidx : int
            フレームINDEX（キーフレ番号とは違う）
        matrixes : MMatrix4x4List
            座標変換行列
        bone_index : int
            処理対象ボーンINDEX
        matrix : Optional[MMatrix4x4], optional
            計算元行列, by default None

        Returns
        -------
        ボーン変形行列
        """
        bone = self[bone_index]

        # 自身の姿勢をかける
        # 座標変換行列
        matrix = matrixes.vector[fidx, bone_index] @ matrix
        # 逆BOf行列(初期姿勢行列)
        matrix = bone.parent_revert_matrix @ matrix

        if 0 <= bone.index and 0 <= bone.parent_index and bone.parent_index in self:
            # 親ボーンがある場合、遡る
            matrix = self.get_mesh_matrix(fidx, matrixes, bone.parent_index, matrix)

        return matrix

    def exists(self, bone_names: Iterable[str]) -> bool:
        """指定されたボーン名がすべて存在しているか"""
        for bone_name in bone_names:
            if bone_name not in self.names:
                return False
        return True


class Morphs(BaseIndexNameDictModel[Morph]):
    """
    モーフリスト
    """

    def __init__(self) -> None:
        super().__init__()

    def filter_by_type(self, *keys: MorphType) -> list[Morph]:
        """モーフ種別にあったモーフリスト"""
        return [v for v in self.data.values() if v.morph_type in keys]

    def filter_by_panel(self, *keys: MorphPanel) -> list[Morph]:
        """表示枠にあったモーフリスト"""
        return [v for v in self.data.values() if v.panel in keys]

    def writable(self) -> list[Morph]:
        """出力対象となるモーフ一覧を取得する"""
        morphs: list[Morph] = []
        for m in self:
            if m.is_system:
                continue
            morphs.append(m)
        return morphs


class DisplaySlots(BaseIndexNameDictModel[DisplaySlot]):
    """
    表示枠リスト
    """

    def __init__(self) -> None:
        super().__init__()

    def writable(self) -> list[DisplaySlot]:
        """出力対象となる表示枠一覧を取得する"""
        display_slots: list[DisplaySlot] = []
        for d in self:
            if d.is_system:
                continue
            display_slots.append(d)
        return display_slots


class RigidBodies(BaseIndexNameDictModel[RigidBody]):
    """
    剛体リスト
    """

    def __init__(self) -> None:
        super().__init__()

    def get_by_index(self, index: int) -> RigidBody:
        if index == -1:
            return RigidBody()
        return super().get_by_index(index)


class Joints(BaseIndexNameDictModel[Joint]):
    """
    ジョイントリスト
    """

    def __init__(self) -> None:
        super().__init__()

    def get_by_index(self, index: int) -> Joint:
        if index == -1:
            return Joint()
        return super().get_by_index(index)


class PmxModel(BaseHashModel):
    """
    Pmxモデルデータ

    Parameters
    ----------
    path : str, optional
        パス, by default ""
    signature : str, optional
        signature, by default ""
    version : float, optional
        バージョン, by default 0.0
    extended_uv_count : int, optional
        追加UV数, by default 0
    vertex_count : int, optional
        頂点数, by default 0
    texture_count : int, optional
        テクスチャ数, by default 0
    material_count : int, optional
        材質数, by default 0
    bone_count : int, optional
        ボーン数, by default 0
    morph_count : int, optional
        モーフ数, by default 0
    rigidbody_count : int, optional
        剛体数, by default 0
    name : str, optional
        モデル名, by default ""
    english_name : str, optional
        モデル名英, by default ""
    comment : str, optional
        コメント, by default ""
    english_comment : str, optional
        コメント英, by default ""
    json_data : dict, optional
        JSONデータ（vroidデータ用）, by default {}
    """

    __slots__ = (
        "path",
        "digest",
        "signature",
        "version",
        "extended_uv_count",
        "vertex_count",
        "texture_count",
        "material_count",
        "bone_count",
        "morph_count",
        "rigidbody_count",
        "model_name",
        "english_name",
        "comment",
        "english_comment",
        "vertices",
        "faces",
        "textures" "toon_textures",
        "materials",
        "bones",
        "bone_trees",
        "morphs",
        "display_slots",
        "rigidbodies",
        "joints",
        "for_draw",
        "meshes",
        "textures",
        "toon_textures",
        "vertices_by_materials",
        "vertices_by_bones",
        "faces_by_materials",
        "for_sub_draw",
        "sub_meshes",
    )

    def __init__(
        self,
        path: str = "",
    ):
        super().__init__(path=path or "")
        self.signature: str = ""
        self.version: float = 0.0
        self.extended_uv_count: int = 0
        self.vertex_count: int = 0
        self.texture_count: int = 0
        self.material_count: int = 0
        self.bone_count: int = 0
        self.morph_count: int = 0
        self.rigidbody_count: int = 0
        self.model_name: str = ""
        self.english_name: str = ""
        self.comment: str = ""
        self.english_comment: str = ""
        self.vertices: Vertices = Vertices()
        self.faces: Faces = Faces()
        self.textures: Textures = Textures()
        self.toon_textures: ToonTextures = ToonTextures()
        self.materials: Materials = Materials()
        self.bones: Bones = Bones()
        self.bone_trees: BoneTrees = BoneTrees()
        self.morphs: Morphs = Morphs()
        self.display_slots: DisplaySlots = DisplaySlots()
        self.rigidbodies: RigidBodies = RigidBodies()
        self.joints: Joints = Joints()
        self.for_draw = False
        self.meshes: Optional[Meshes] = None
        self.for_sub_draw = False
        self.sub_meshes: Optional[Meshes] = None
        self.vertices_by_bones: dict[int, list[int]] = {}
        self.vertices_by_materials: dict[int, list[int]] = {}
        self.faces_by_materials: dict[int, list[int]] = {}

    @property
    def name(self) -> str:
        return self.model_name

    def initialize_display_slots(self) -> None:
        d01 = DisplaySlot(name="Root", english_name="Root")
        d01.special_flg = Switch.ON
        self.display_slots.append(d01)
        d02 = DisplaySlot(name="表情", english_name="Exp")
        d02.special_flg = Switch.ON
        self.display_slots.append(d02)

    def get_weighted_vertex_scale(self) -> dict[int, dict[int, MVector3D]]:
        vertex_bone_scales: dict[int, dict[int, MVector3D]] = {}
        total_index_count = len(self.vertices)
        for vertex in self.vertices:
            indexes = vertex.deform.get_indexes()
            weights = vertex.deform.get_weights()
            for bone_index in indexes:
                if bone_index not in vertex_bone_scales:
                    vertex_bone_scales[bone_index] = {}
                vertex_bone_scales[bone_index][vertex.index] = MVector3D(
                    *(vertex.normal.vector * weights[indexes == bone_index][0])
                )

            logger.count(
                "ウェイトボーン分布",
                index=vertex.index,
                total_index_count=total_index_count,
                display_block=5000,
            )
        return vertex_bone_scales

    def update_vertices_by_bone(self) -> None:
        """ボーン別頂点INDEXリストの更新"""
        self.vertices_by_bones = {}
        total_index_count = len(self.vertices)
        for vertex in self.vertices:
            for bone_index in vertex.deform.get_indexes():
                if bone_index not in self.vertices_by_bones:
                    self.vertices_by_bones[bone_index] = []
                self.vertices_by_bones[bone_index].append(vertex.index)

            logger.count(
                "ウェイトボーン分布",
                index=vertex.index,
                total_index_count=total_index_count,
                display_block=5000,
            )

    def update_vertices_by_material(self) -> None:
        """材質別頂点INDEXリストの更新"""
        prev_face_count = 0
        self.vertices_by_materials = {}
        self.faces_by_materials = {}
        for material in self.materials:
            vertices: list[int] = []
            self.faces_by_materials[material.index] = []
            face_count = material.vertices_count // 3
            for face_index in range(prev_face_count, prev_face_count + face_count):
                vertices.extend(self.faces[face_index].vertices)
                self.faces_by_materials[material.index].append(face_index)
            self.vertices_by_materials[material.index] = list(set(vertices))
            prev_face_count += face_count

    def init_draw(self, is_sub: bool) -> None:
        if (not is_sub and self.for_draw) or (is_sub and self.for_sub_draw):
            # 既にフラグが立ってたら描画初期化済み
            return

        # 共有Toon読み込み
        for tidx, tpath in enumerate(
            glob(
                os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "..",
                    "resources",
                    "share_toon",
                    "*.bmp",
                )
            )
        ):
            self.toon_textures.append(Texture(tidx, os.path.abspath(tpath)))

        if is_sub:
            self.sub_meshes = Meshes(self, is_sub)
            # 描画初期化
            self.for_sub_draw = True
        else:
            self.meshes = Meshes(self, is_sub)
            # 描画初期化
            self.for_draw = True

    def delete_draw(self) -> None:
        if not self.for_draw or not self.meshes:
            # 描画初期化してなければスルー
            return

        self.meshes.delete_draw()
        self.for_draw = False

    def draw(
        self,
        shader: MShader,
        bone_matrixes: np.ndarray,
        vertex_morph_poses: np.ndarray,
        after_vertex_morph_poses: np.ndarray,
        uv_morph_poses: np.ndarray,
        uv1_morph_poses: np.ndarray,
        material_morphs: list[ShaderMaterial],
        is_alpha: bool,
        is_show_bone_weight: bool,
        show_bone_indexes: list[int],
        is_sub: bool,
    ) -> None:
        if is_sub:
            if not self.for_sub_draw or not self.sub_meshes:
                return
            self.sub_meshes.draw(
                shader,
                bone_matrixes,
                vertex_morph_poses,
                after_vertex_morph_poses,
                uv_morph_poses,
                uv1_morph_poses,
                material_morphs,
                is_alpha,
                is_show_bone_weight,
                show_bone_indexes,
                is_sub,
            )
        else:
            if not self.for_draw or not self.meshes:
                return
            self.meshes.draw(
                shader,
                bone_matrixes,
                vertex_morph_poses,
                after_vertex_morph_poses,
                uv_morph_poses,
                uv1_morph_poses,
                material_morphs,
                is_alpha,
                is_show_bone_weight,
                show_bone_indexes,
                is_sub,
            )

    def draw_bone(
        self,
        shader: MShader,
        bone_matrixes: np.ndarray,
        select_bone_color: np.ndarray,
        unselect_bone_color: np.ndarray,
        selected_bone_indexes: np.ndarray,
        is_sub: bool,
    ) -> None:
        if is_sub:
            if not self.for_sub_draw or not self.sub_meshes:
                return
            self.sub_meshes.draw_bone(
                shader,
                bone_matrixes,
                select_bone_color,
                unselect_bone_color,
                selected_bone_indexes,
                is_sub,
            )
        else:
            if not self.for_draw or not self.meshes:
                return
            self.meshes.draw_bone(
                shader,
                bone_matrixes,
                select_bone_color,
                unselect_bone_color,
                selected_bone_indexes,
                is_sub,
            )

    # def draw_axis(
    #     self,
    #     axis_matrixes: np.ndarray,
    #     axis_color: np.ndarray,
    # ) -> None:
    #     if not self.for_draw or not self.meshes:
    #         return
    #     self.meshes.draw_axis(axis_matrixes, axis_color)

    def setup(self) -> None:
        self.delete_draw()
        total_index_count = len(self.bones)

        # システム用ボーン追加
        if "右腕" in self.bones and "左腕" in self.bones and "上半身" in self.bones:
            neck_root_position = (
                self.bones["右腕"].position + self.bones["左腕"].position
            ) / 2

            if "首根元" in self.bones:
                self.bones["首根元"].position = neck_root_position.copy()
                self.bones["左肩根元"].position = neck_root_position.copy()
                self.bones["右肩根元"].position = neck_root_position.copy()
            else:
                parent_bone_name = (
                    "上半身3"
                    if "上半身3" in self.bones
                    else "上半身2"
                    if "上半身2" in self.bones
                    else "上半身"
                )
                parent_bone = self.bones[parent_bone_name]

                # 首根元を追加
                neck_root_bone = Bone(name="首根元")
                neck_root_bone.is_system = True
                neck_root_bone.parent_index = parent_bone.index
                neck_root_bone.index = parent_bone.index + 1
                neck_root_bone.position = neck_root_position.copy()
                if "首" in self.bones:
                    neck_root_bone.local_axis = (
                        self.bones["首"].position - neck_root_bone.position
                    ).normalized()
                else:
                    neck_root_bone.local_axis = MVector3D(0, 1, 0)
                self.insert_bone(neck_root_bone)

                # 肩根元を追加
                right_shoulder_root = Bone(name="右肩根元", index=neck_root_bone.index + 1)
                right_shoulder_root.parent_index = neck_root_bone.index
                right_shoulder_root.is_system = True
                right_shoulder_root.position = neck_root_position.copy()
                if "右肩" in self.bones:
                    right_shoulder_root.tail_relative_position = (
                        self.bones["右肩"].position - right_shoulder_root.position
                    )
                    right_shoulder_root.local_axis = (
                        right_shoulder_root.tail_relative_position.normalized()
                    )
                else:
                    right_shoulder_root.tail_relative_position = (
                        right_shoulder_root.local_axis
                    ) = MVector3D(-1, 0, 0)
                self.insert_bone(right_shoulder_root)

                left_shoulder_root = Bone(name="左肩根元", index=neck_root_bone.index + 1)
                left_shoulder_root.parent_index = neck_root_bone.index
                left_shoulder_root.is_system = True
                left_shoulder_root.position = neck_root_position.copy()
                if "左肩" in self.bones:
                    left_shoulder_root.tail_relative_position = (
                        self.bones["左肩"].position - left_shoulder_root.position
                    )
                    left_shoulder_root.local_axis = (
                        left_shoulder_root.tail_relative_position.normalized()
                    )
                else:
                    left_shoulder_root.tail_relative_position = (
                        left_shoulder_root.local_axis
                    ) = MVector3D(1, 0, 0)
                self.insert_bone(left_shoulder_root)

                # 腕系で左右に分かれてるのは親を肩根元に置き換える
                for bone in self.bones:
                    if (
                        bone.parent_index == neck_root_bone.index
                        and "肩根元" not in bone.name
                    ):
                        if "右" in bone.name:
                            bone.parent_index = self.bones["右肩根元"].index
                        elif "左" in bone.name:
                            bone.parent_index = self.bones["左肩根元"].index

        if "右足" in self.bones and "左足" in self.bones and "下半身" in self.bones:
            if "足中心" in self.bones:
                self.bones["足中心"].position = (
                    self.bones["右足"].position + self.bones["左足"].position
                ) / 2
            else:
                leg_root_bone = Bone(name="足中心")
                leg_root_bone.parent_index = self.bones["下半身"].index
                leg_root_bone.index = self.bones["下半身"].index + 1
                leg_root_bone.position = (
                    self.bones["右足"].position + self.bones["左足"].position
                ) / 2
                leg_root_bone.is_system = True
                self.insert_bone(leg_root_bone)
                for replace_bone_name in (
                    "腰キャンセル右",
                    "腰キャンセル左",
                    "右足",
                    "左足",
                    "右足D",
                    "左足D",
                ):
                    if (
                        replace_bone_name in self.bones
                        and self.bones[replace_bone_name].parent_index
                        == self.bones["下半身"].index
                    ):
                        self.bones[replace_bone_name].parent_index = self.bones[
                            "足中心"
                        ].index

        logger.info("モデルセットアップ：システム用ボーン")

        for bone in self.bones:
            # 関係ボーンリストを一旦クリア
            bone.ik_link_indexes = []
            bone.ik_target_indexes = []
            bone.effective_target_indexes = []
            bone.child_bone_indexes = []

        for bone in self.bones:
            if bone.is_ik and bone.ik:
                # IKのリンクとターゲット
                for link in bone.ik.links:
                    if (
                        link.bone_index in self.bones
                        and bone.index
                        not in self.bones[link.bone_index].ik_link_indexes
                    ):
                        # リンクボーンにフラグを立てる
                        self.bones[link.bone_index].ik_link_indexes.append(bone.index)
                        # リンクの制限をコピーしておく
                        self.bones[link.bone_index].angle_limit = link.angle_limit
                        self.bones[
                            link.bone_index
                        ].min_angle_limit = link.min_angle_limit
                        self.bones[
                            link.bone_index
                        ].max_angle_limit = link.max_angle_limit
                        self.bones[
                            link.bone_index
                        ].local_angle_limit = link.local_angle_limit
                        self.bones[
                            link.bone_index
                        ].local_min_angle_limit = link.local_min_angle_limit
                        self.bones[
                            link.bone_index
                        ].local_max_angle_limit = link.local_max_angle_limit
                if (
                    bone.ik.bone_index in self.bones
                    and bone.index
                    not in self.bones[bone.ik.bone_index].ik_target_indexes
                ):
                    # ターゲットボーンにもフラグを立てる
                    self.bones[bone.ik.bone_index].ik_target_indexes.append(bone.index)
            if 0 <= bone.effect_index and bone.effect_index in self.bones:
                # 付与親の方に付与子情報を保持
                self.bones[bone.effect_index].effective_target_indexes.append(
                    bone.index
                )

        # ボーンツリー生成
        self.bone_trees = self.bones.create_bone_trees()

        # ボーン変形行列を計算するのに影響する全てのボーンINDEXのリストを取得する
        for bone in self.bones:
            # ボーンセットアップ
            self.setup_bone(bone)

            # 影響があるボーンINDEXリスト
            bone.relative_bone_indexes = list(
                sorted(self.get_tree_relative_bone_indexes(bone.index, recursive=True))
            )

            if bone.parent_index in self.bones:
                # 親ボーンに子ボーンとして登録する
                self.bones[bone.parent_index].child_bone_indexes.append(bone.index)

            logger.count(
                "モデルセットアップ：ボーン",
                index=bone.index,
                total_index_count=total_index_count,
                display_block=100,
            )

        # ボーンリストセットアップ
        self.bones.setup()

        logger.info("モデルセットアップ：ボーンツリー")

    def get_tree_relative_bone_indexes(
        self, bone_index: int, recursive: bool = False
    ) -> set[int]:
        logger.debug(
            f"get_tree_relative_bone_indexes: {bone_index}({self.bones[bone_index].name})"
        )

        if 0 >= bone_index or bone_index not in self.bones.indexes:
            return set([])

        # 直接関係するボーンINDEXセット
        bone = self.bones[bone_index]
        relative_bone_indexes: set[int] = set(
            self.bone_trees[self.bones[bone_index].name].indexes[:-1]
        )
        # if 0 <= bone.parent_index:
        #     relative_bone_indexes |= {bone.parent_index}
        # if (bone.is_external_rotation or bone.is_external_translation) and 0 <= bone.effect_index:
        #     relative_bone_indexes |= {bone.effect_index}
        if bone.effective_target_indexes:
            relative_bone_indexes |= set(bone.effective_target_indexes)
        # if bone.ik:
        #     relative_bone_indexes |= {bone.ik.bone_index}
        #     for link in bone.ik.links:
        #         relative_bone_indexes |= {link.bone_index}
        # if bone.ik_link_indexes:
        #     relative_bone_indexes |= set(bone.ik_link_indexes)
        # if bone.ik_target_indexes:
        #     relative_bone_indexes |= set(bone.ik_target_indexes)

        tree_relative_bone_indexes: set[int] = set([])
        if recursive:
            for relative_index in relative_bone_indexes:
                for tree_index in self.bone_trees[
                    self.bones[relative_index].name
                ].indexes[1:]:
                    tree_relative_bone_indexes |= self.get_tree_relative_bone_indexes(
                        tree_index
                    )

        return tree_relative_bone_indexes | relative_bone_indexes | {bone_index}

    def setup_bone(self, bone: Bone):
        """各ボーンのセットアップ"""
        bone.parent_relative_position = self.bones.get_parent_relative_position(
            bone.index
        )
        # 末端ボーンの相対位置
        bone.tail_relative_position = self.bones.get_tail_relative_position(bone.index)
        # 各ボーンのローカル軸
        bone.local_axis = bone.tail_relative_position.normalized()
        bone.local_matrix = bone.local_axis.to_local_matrix4x4()
        if bone.has_fixed_axis:
            bone.correct_local_vector(bone.fixed_axis.normalized())
            bone.correct_fixed_axis(bone.fixed_axis.normalized())
        else:
            bone.correct_local_vector(bone.local_axis)

        # オフセット行列は自身の位置を原点に戻す行列
        bone.offset_matrix[:3, 3] = -bone.position.vector

        # 逆オフセット行列は親ボーンからの相対位置分
        bone.parent_revert_matrix[:3, 3] = bone.parent_relative_position.vector

    def remove_bone(self, bone_name: str) -> None:
        """ボーンの削除に伴う諸々のボーンINDEXの置き換え"""
        if bone_name not in self.bones:
            return

        bone = self.bones[bone_name]
        replaced_map = self.bones.remove(bone)

        # 自身のINDEXは親ボーンのINDEXで置き換える
        replaced_map[bone.index] = replaced_map[bone.parent_index]

        if not replaced_map:
            return

        for v in self.vertices:
            v.deform.indexes = np.vectorize(replaced_map.get)(v.deform.indexes)

        for b in self.bones:
            if b.index < 0:
                continue

            if b.parent_index in replaced_map:
                b.parent_index = replaced_map[b.parent_index]
            else:
                b.parent_index = replaced_map[bone.parent_index]

            if b.tail_index in replaced_map and b.name != bone_name:
                b.tail_index = replaced_map[b.tail_index]
            else:
                b.tail_index = replaced_map[bone.tail_index]

            if b.effect_index in replaced_map:
                b.effect_index = replaced_map[b.effect_index]
            else:
                b.effect_index = replaced_map[bone.effect_index]

            if b.is_ik:
                if b.ik.bone_index in replaced_map:
                    b.ik.bone_index = replaced_map[b.ik.bone_index]
                for link in b.ik.links:
                    if link.bone_index in replaced_map:
                        link.bone_index = replaced_map[link.bone_index]

        for m in self.morphs:
            if m.morph_type == MorphType.BONE:
                for offset in m.offsets:
                    if not isinstance(offset, BoneMorphOffset):
                        continue
                    if offset.bone_index in replaced_map:
                        offset.bone_index = replaced_map[offset.bone_index]

        for d in self.display_slots:
            for dr in d.references:
                if (
                    dr.display_type == DisplayType.BONE
                    and dr.display_index in replaced_map
                ):
                    dr.display_index = replaced_map[dr.display_index]

        for r in self.rigidbodies:
            if r.bone_index in replaced_map:
                r.bone_index = replaced_map[r.bone_index]

    def insert_bone(self, bone: Bone):
        """ボーンの追加に伴う諸々のボーンINDEXの置き換え"""
        # 挿入
        replaced_map = self.bones.insert(bone)

        if not replaced_map:
            if not bone.is_system and bone.is_visible:
                # 表示対象な場合、親と同じ表示枠に追加
                is_add_display = False
                for d in self.display_slots:
                    if d.special_flg == Switch.ON:
                        continue
                    for dr in d.references:
                        if (
                            dr.display_type == DisplayType.BONE
                            and bone.parent_index == dr.display_index
                        ):
                            d.references.append(
                                DisplaySlotReference(DisplayType.BONE, bone.index)
                            )
                            is_add_display = True
                            break
                    if is_add_display:
                        break

                if not is_add_display:
                    # 表示枠に追加できなかった場合、ボーン名の表示枠を作ってそこに追加する
                    display_slot = DisplaySlot(
                        name=bone.name, english_name=bone.english_name
                    )
                    display_slot.references.append(
                        DisplaySlotReference(DisplayType.BONE, display_index=bone.index)
                    )
                    self.display_slots.append(display_slot)

            return

        for v in self.vertices:
            v.deform.indexes = np.vectorize(replaced_map.get)(v.deform.indexes)

        for b in self.bones:
            if b.index < 0:
                continue

            if b.tail_index in replaced_map:
                b.tail_index = replaced_map[b.tail_index]

            if b.effect_index in replaced_map:
                b.effect_index = replaced_map[b.effect_index]

            if b.is_ik:
                if b.ik.bone_index in replaced_map:
                    b.ik.bone_index = replaced_map[b.ik.bone_index]
                for link in b.ik.links:
                    if link.bone_index in replaced_map:
                        link.bone_index = replaced_map[link.bone_index]

            if b.name != bone.name:
                # 左右が同じ方向であるか
                is_same_direction = True
                is_same_finger = True
                if bone.name[0] in ["右", "左"] or bone.name[-1] in ["右", "左"]:
                    is_same_direction = (
                        bone.name[-1] == b.name[0] and "腰キャンセル" in bone.name
                    ) or (bone.name[0] == b.name[0] and "腰キャンセル" not in bone.name)
                    if "指" == bone.name[:3][-1]:
                        is_same_finger = bone.name[:2][-1] == b.name[:2][-1]

                in_bone_tree = set(
                    self.bones.create_bone_link_indexes(replaced_map[b.parent_index])
                )
                in_standard = self.bone_trees.is_in_standard(b.name)
                if b.is_ik and len(b.ik.links):
                    # IKの場合リンクの起点をボーンツリーの基準とする
                    in_bone_tree = set(
                        self.bones.create_bone_link_indexes(b.index)
                    ) | set(
                        self.bones.create_bone_link_indexes(b.ik.links[-1].bone_index)
                    )
                    in_standard |= True in [
                        self.bone_trees.is_in_standard(b.name)
                        for b in self.bone_trees[
                            self.bones[b.ik.links[-1].bone_index].name
                        ]
                    ]
                in_bone_tree &= set(
                    self.bones.create_bone_link_indexes(replaced_map[bone.parent_index])
                )
                if b.parent_index <= 0:
                    in_bone_tree |= {(0, -1)}

                if (
                    b.parent_index == bone.index - 1
                    and is_same_direction
                    and in_bone_tree
                    and in_standard
                ):
                    if (
                        (b.name in ["右足", "左足"] and bone.name in ["右足D", "左足D"])
                        or not is_same_finger
                        or b.is_standard_extend
                    ):
                        # 足D・準標準の先ボーンは親に設定しない
                        b.parent_index = replaced_map[b.parent_index]
                    else:
                        b.parent_index = bone.index
                elif b.parent_index in replaced_map:
                    original_parent = self.bones[replaced_map[b.parent_index]]
                    original_parent_distance = b.position.distance(
                        original_parent.position
                    )
                    replaced_parent_distance = b.position.distance(bone.position)
                    if (
                        bone.parent_index == replaced_map[b.parent_index]
                        and is_same_direction
                        and original_parent_distance
                        and (
                            0.5 > replaced_parent_distance / original_parent_distance
                            or original_parent.position == bone.position
                        )
                        and "捩" not in b.name
                    ):
                        # 準標準ボーンの範囲外かつ挿入ボーンのと親子関係があり、距離が挿入ボーンの方が近いか全く同じ位置の場合、挿入ボーンで置き換える
                        b.parent_index = bone.index
                    else:
                        b.parent_index = replaced_map[b.parent_index]

        for m in self.morphs:
            if m.morph_type == MorphType.BONE:
                for offset in m.offsets:
                    if not isinstance(offset, BoneMorphOffset):
                        continue
                    if offset.bone_index in replaced_map:
                        offset.bone_index = replaced_map[offset.bone_index]

        for d in self.display_slots:
            for dr in d.references:
                if (
                    dr.display_type == DisplayType.BONE
                    and dr.display_index in replaced_map
                ):
                    dr.display_index = replaced_map[dr.display_index]

        for r in self.rigidbodies:
            if r.bone_index in replaced_map:
                original_parent = self.bones[replaced_map[r.bone_index]]
                original_parent_distance = r.shape_position.distance(
                    original_parent.position
                )
                replaced_parent_distance = r.shape_position.distance(bone.position)
                if (
                    bone.parent_index == replaced_map[r.bone_index]
                    and original_parent_distance
                    and 0.5 > replaced_parent_distance / original_parent_distance
                ):
                    r.bone_index = bone.index
                else:
                    r.bone_index = replaced_map[r.bone_index]

        if bone.is_visible and not bone.is_system:
            # ボーンツリーだけ再生成
            self.bone_trees = self.bones.create_bone_trees()

            # 親ボーンで表示枠に入ってるとこに入れる
            is_add_display_reference = False
            for tree_name in reversed(self.bone_trees[bone.name].names):
                for d in self.display_slots:
                    if d.special_flg == Switch.ON:
                        continue
                    for dr in d.references:
                        if (
                            dr.display_type == DisplayType.BONE
                            and self.bones[tree_name].index == dr.display_index
                        ):
                            d.references.append(
                                DisplaySlotReference(
                                    DisplayType.BONE, display_index=bone.index
                                )
                            )
                            is_add_display_reference = True
                            break
                    if is_add_display_reference:
                        break
                if is_add_display_reference:
                    break

            if not is_add_display_reference:
                # 最後まで追加されなかった場合、表示枠そのものを追加
                display_slot = DisplaySlot(
                    name=bone.name, english_name=bone.english_name
                )
                display_slot.references.append(
                    DisplaySlotReference(DisplayType.BONE, display_index=bone.index)
                )
                self.display_slots.append(display_slot)

    def insert_standard_bone(
        self, bone_name: str, bone_matrixes: VmdBoneFrameTrees
    ) -> bool:
        bone_setting = STANDARD_BONE_NAMES[bone_name]
        if bone_name in self.bones:
            # 既にある場合、作成しない
            return False
        if (
            bone_name != "全ての親"
            and not [bname for bname in bone_setting.tails if bname in self.bones]
            and "D" != bone_name[-1]
            and "EX" != bone_name[-2:]
        ):
            # 先に接続可能なボーンが無い場合、作成しない
            return False
        parent_names = [p for p in bone_setting.parents if p in self.bones.names]
        if bone_name != "全ての親" and not parent_names:
            # 全ての親以外で親ボーンが無い場合、作成しない
            return False
        if bone_name == "全ての親":
            # 親のひとつ下に作成する
            bone = Bone(name=bone_name, index=0)
            bone.parent_index = -1
        else:
            parent_bone = self.bones[parent_names[0]]
            # 親のひとつ下に作成する
            bone = Bone(name=bone_name, index=parent_bone.index + 1)
            bone.parent_index = parent_bone.index
            # 変形階層
            bone.layer = parent_bone.layer
        direction = bone.name[0]
        bone.bone_flg = bone_setting.flag
        if "足D" in bone.name:
            # 足D系列は変形階層を追加
            bone.layer += 1
            # 場所も出力対象の最後に持ってくる
            bone.index = max([b.index for b in self.bones if not b.is_system]) + 1
        # 位置
        local_y_vector = MVector3D(0, -1, 0)
        if "全ての親" == bone.name:
            bone.position = MVector3D()
        elif "グルーブ" == bone.name and "センター" in self.bones:
            bone.position = bone_matrixes["センター", 0].position * 1.025
        elif (bone.is_leg_d or "肩P" == bone.name[-2:]) and bone.name[:-1] in self.bones:
            bone.position = bone_matrixes[bone.name[:-1], 0].position.copy()
        elif "肩C" in bone.name and f"{direction}腕" in self.bones:
            bone.position = bone_matrixes[f"{direction}腕", 0].position.copy()
            bone.tail_position = MVector3D()
            bone.bone_flg &= ~BoneFlg.TAIL_IS_BONE
        elif "足IK親" in bone.name and f"{direction}足首" in self.bones:
            bone.position = bone_matrixes[f"{direction}足首", 0].position.copy()
            bone.position.y = 0
        elif "腰" == bone.name and "下半身" in self.bones and "足中心" in self.bones:
            bone.position = (
                bone_matrixes["下半身", 0].position + bone_matrixes["足中心", 0].position
            ) / 2
            bone.local_x_vector = (
                bone_matrixes["足中心", 0].position - bone_matrixes["下半身", 0].position
            ).normalized()
            bone.local_z_vector = local_y_vector.cross(bone.local_x_vector).normalized()
            bone.bone_flg |= BoneFlg.HAS_LOCAL_COORDINATE
        elif "上半身2" == bone.name and "上半身" in self.bones and "首" in self.bones:
            bone.position = (
                bone_matrixes["上半身", 0].position + bone_matrixes["首", 0].position
            ) / 2
            bone.position.z += (
                abs(
                    bone_matrixes["首", 0].position.z
                    - bone_matrixes["上半身", 0].position.z
                )
                * 0.5
            )
            bone.local_x_vector = (
                bone_matrixes["首", 0].position - bone_matrixes["上半身", 0].position
            ).normalized()
            bone.local_z_vector = local_y_vector.cross(bone.local_x_vector).normalized()
            bone.bone_flg |= BoneFlg.HAS_LOCAL_COORDINATE
        elif "上半身3" == bone.name and "上半身2" in self.bones and "上半身" in self.bones:
            if "首" in self.bones:
                bone.position = (
                    bone_matrixes["上半身2", 0].position + bone_matrixes["首", 0].position
                ) / 2
                bone.position.z += (
                    abs(
                        bone_matrixes["首", 0].position.z
                        - bone_matrixes["上半身2", 0].position.z
                    )
                    * 0.5
                )
                bone.local_x_vector = (
                    bone_matrixes["首", 0].position - bone_matrixes["上半身2", 0].position
                ).normalized()
            else:
                bone.position = bone_matrixes["上半身", 0].position + (
                    (
                        bone_matrixes["上半身2", 0].position
                        - bone_matrixes["上半身", 0].position
                    )
                    / 2
                )
                bone.position.z += (
                    abs(
                        bone_matrixes["上半身2", 0].position.z
                        - bone_matrixes["上半身", 0].position.z
                    )
                    * 0.5
                )
                bone.local_x_vector = (
                    bone_matrixes["上半身2", 0].position - bone_matrixes["上半身", 0].position
                ).normalized()
            bone.local_z_vector = local_y_vector.cross(bone.local_x_vector).normalized()
            bone.bone_flg |= BoneFlg.HAS_LOCAL_COORDINATE
        elif (
            "腕捩" in bone.name
            and f"{direction}腕" in self.bones
            and f"{direction}ひじ" in self.bones
        ):
            bone.position = MVector3D(
                *np.average(
                    [
                        bone_matrixes[f"{direction}腕", 0].position.vector,
                        bone_matrixes[f"{direction}ひじ", 0].position.vector,
                    ],
                    weights=[0.4, 0.6],
                    axis=0,
                )
            )
            bone.fixed_axis = (
                bone_matrixes[f"{direction}ひじ", 0].position
                - bone_matrixes[f"{direction}腕", 0].position
            ).normalized()
            bone.local_x_vector = (
                bone_matrixes[f"{direction}ひじ", 0].position
                - bone_matrixes[f"{direction}腕", 0].position
            ).normalized()
            bone.local_z_vector = local_y_vector.cross(bone.local_x_vector).normalized()
            bone.tail_position = MVector3D()
            bone.bone_flg &= ~BoneFlg.TAIL_IS_BONE
        elif (
            "手捩" in bone.name
            and f"{direction}ひじ" in self.bones
            and f"{direction}手首" in self.bones
        ):
            bone.position = MVector3D(
                *np.average(
                    [
                        bone_matrixes[f"{direction}ひじ", 0].position.vector,
                        bone_matrixes[f"{direction}手首", 0].position.vector,
                    ],
                    weights=[0.4, 0.6],
                    axis=0,
                )
            )
            bone.fixed_axis = (
                bone_matrixes[f"{direction}手首", 0].position
                - bone_matrixes[f"{direction}ひじ", 0].position
            ).normalized()
            bone.local_x_vector = (
                bone_matrixes[f"{direction}手首", 0].position
                - bone_matrixes[f"{direction}ひじ", 0].position
            ).normalized()
            bone.local_z_vector = local_y_vector.cross(bone.local_x_vector).normalized()
            bone.tail_position = MVector3D()
            bone.bone_flg &= ~BoneFlg.TAIL_IS_BONE
        elif (
            "足先EX" in bone.name
            and f"{direction}足首" in self.bones
            and f"{direction}つま先ＩＫ" in self.bones
            and self.bones[f"{direction}つま先ＩＫ"].ik
        ):
            toe_target_bone = self.bones[self.bones[f"{direction}つま先ＩＫ"].ik.bone_index]
            bone.position = MVector3D(
                *np.average(
                    [
                        bone_matrixes[f"{direction}足首", 0].position.vector,
                        bone_matrixes[toe_target_bone.name, 0].position.vector,
                    ],
                    weights=[0.35, 0.65],
                    axis=0,
                )
            )
            bone.local_x_vector = (
                bone_matrixes[toe_target_bone.name, 0].position
                - bone_matrixes[f"{direction}足首", 0].position
            ).normalized()
            bone.local_z_vector = local_y_vector.cross(bone.local_x_vector).normalized()
            bone.tail_position = MVector3D()
            bone.bone_flg &= ~BoneFlg.TAIL_IS_BONE
            bone.bone_flg |= BoneFlg.HAS_LOCAL_COORDINATE
        elif (
            "親指０" in bone.name
            and f"{direction}手首" in self.bones
            and f"{direction}親指１" in self.bones
        ):
            bone.position = MVector3D(
                *np.average(
                    [
                        bone_matrixes[f"{direction}手首", 0].position.vector,
                        bone_matrixes[f"{direction}親指１", 0].position.vector,
                    ],
                    weights=[0.2, 0.8],
                    axis=0,
                )
            )
            bone.local_x_vector = (
                bone_matrixes[f"{direction}親指１", 0].position
                - bone_matrixes[f"{direction}手首", 0].position
            ).normalized()
            bone.local_z_vector = local_y_vector.cross(bone.local_x_vector).normalized()
            bone.bone_flg |= BoneFlg.HAS_LOCAL_COORDINATE
        elif "両目" == bone.name and "左目" in self.bones and "右目" in self.bones:
            bone.position = (
                bone_matrixes["左目", 0].position + bone_matrixes["右目", 0].position
            ) / 2
        elif "親指先" in bone.name and f"{bone.name[0]}親指２":
            bone.position = bone_matrixes[f"{bone.name[0]}親指２", 0].position
        elif "指先" in bone.name and f"{bone.name[:2]}指３":
            bone.position = bone_matrixes[f"{bone.name[:2]}指３", 0].position
        else:
            return False

        # 表示先
        if isinstance(bone_setting.display_tail, MVector3D):
            if BoneFlg.TAIL_IS_BONE in bone.bone_flg:
                bone.tail_position = bone_setting.display_tail.copy()
        elif (
            isinstance(bone_setting.display_tail, list)
            and bone_setting.display_tail[0] in self.bones
        ):
            bone.tail_index = self.bones[bone_setting.display_tail[0]].index

        # 回転付与
        if "肩C" in bone.name and f"{direction}肩P" in self.bones:
            bone.effect_index = self.bones[f"{direction}肩P"].index
            bone.effect_factor = -1
        elif bone.is_leg_d:
            bone.effect_index = self.bones[bone.name[:-1]].index
            bone.effect_factor = 1

        # 一旦ボーンを挿入
        self.insert_bone(bone)

        if bone.is_twist:
            # 捩りの場合、分散用ボーンも追加する
            from_name = f"{direction}腕" if "腕捩" in bone.name else f"{direction}ひじ"
            to_name = f"{direction}ひじ" if "腕捩" in bone.name else f"{direction}手首"
            for no, zen_no, ratio, factor in (
                (1, "１", 0.3, 0.25),
                (2, "２", 0.5, 0.5),
                (3, "３", 0.7, 0.75),
            ):
                twist_bone_name = f"{bone.name}{no}"
                if (
                    twist_bone_name in self.bones
                    or f"{bone.name}{zen_no}" in self.bones
                ):
                    continue
                twist_bone = Bone(name=twist_bone_name, index=bone.index + no)
                twist_bone.position = MVector3D(
                    *np.average(
                        [
                            bone_matrixes[from_name, 0].position.vector,
                            bone_matrixes[to_name, 0].position.vector,
                        ],
                        weights=[1 - ratio, ratio],
                        axis=0,
                    )
                )
                # 親ボーンは捩りの親（腕ないしひじ）
                twist_bone.parent_index = bone.parent_index
                twist_bone.bone_flg = BoneFlg.CAN_ROTATE | BoneFlg.IS_EXTERNAL_ROTATION
                twist_bone.effect_index = bone.index
                twist_bone.effect_factor = factor

                self.insert_bone(twist_bone)

            # ひじの親は捩りボーンそのもの
            if "腕捩" in bone.name:
                self.bones[f"{direction}ひじ"].parent_index = bone.index
            elif "手捩" in bone.name:
                self.bones[f"{direction}手首"].parent_index = bone.index

        elif "肩P" in bone_name:
            # 肩Pの場合、肩Cも追加する
            self.insert_standard_bone(f"{bone_name[:2]}C", bone_matrixes)
        elif bone_name == "腰":
            # 腰の場合、腰キャンセルも追加する
            left_leg_bone = self.bones["左足"]
            waist_cancel_left_parent_bone = [
                self.bones[parent_name]
                for parent_name in BoneSettings.LEFT_WAIST_CANCEL.value.parents
                if parent_name in self.bones
            ][0]
            # 親のひとつ下
            waist_cancel_left_bone = Bone(
                name="腰キャンセル左", index=waist_cancel_left_parent_bone.index + 1
            )
            # 親ボーンは足中心 or 腰
            waist_cancel_left_bone.parent_index = waist_cancel_left_parent_bone.index

            waist_cancel_left_bone.position = bone_matrixes[
                left_leg_bone.name, 0
            ].position.copy()
            waist_cancel_left_bone.tail_position = MVector3D()
            waist_cancel_left_bone.bone_flg = BoneSettings.LEFT_WAIST_CANCEL.value.flag
            # 変形階層
            waist_cancel_left_bone.layer = parent_bone.layer
            # 付与親でキャンセル
            waist_cancel_left_bone.effect_index = bone.index
            waist_cancel_left_bone.effect_factor = -1
            # 腰キャンセル左を追加
            self.insert_bone(waist_cancel_left_bone)

            right_leg_bone = self.bones["右足"]
            waist_cancel_right_parent_bone = [
                self.bones[parent_name]
                for parent_name in BoneSettings.RIGHT_WAIST_CANCEL.value.parents
                if parent_name in self.bones
            ][0]
            # 親のひとつ下
            waist_cancel_right_bone = Bone(
                name="腰キャンセル右", index=waist_cancel_right_parent_bone.index + 1
            )
            # 親ボーンは足中心 or 腰
            waist_cancel_right_bone.parent_index = waist_cancel_right_parent_bone.index

            waist_cancel_right_bone.position = bone_matrixes[
                right_leg_bone.name, 0
            ].position.copy()
            waist_cancel_right_bone.tail_position = MVector3D()
            waist_cancel_right_bone.bone_flg = (
                BoneSettings.RIGHT_WAIST_CANCEL.value.flag
            )
            # 変形階層
            waist_cancel_right_bone.layer = parent_bone.layer
            # 付与親でキャンセル
            waist_cancel_right_bone.effect_index = bone.index
            waist_cancel_right_bone.effect_factor = -1
            # 腰キャンセル右を追加
            self.insert_bone(waist_cancel_right_bone)

            if "左足" in self.bones:
                self.bones["左足"].parent_index = waist_cancel_left_bone.index
            if "左足D" in self.bones:
                self.bones["左足D"].parent_index = waist_cancel_left_bone.index

            if "右足" in self.bones:
                self.bones["右足"].parent_index = waist_cancel_right_bone.index
            if "右足D" in self.bones:
                self.bones["右足D"].parent_index = waist_cancel_right_bone.index

        # 付与親の設定
        if "両目" == bone.name:
            self.bones["左目"].effect_index = self.bones["両目"].index
            self.bones["左目"].effect_factor = 1
            self.bones["右目"].effect_index = self.bones["両目"].index
            self.bones["右目"].effect_factor = 1

        # 表示先の切り替え
        if "上半身2" == bone.name:
            self.bones[bone.parent_index].tail_index = bone.index
            self.bones[bone.parent_index].bone_flg |= BoneFlg.TAIL_IS_BONE

        # 全親の場合、親が-1のものを子どもにする
        if bone_name == "全ての親":
            for b in self.bones:
                if 0 > b.parent_index and b.name != "全ての親":
                    b.parent_index = bone.index

        return True

    def replace_standard_weights(self, bone_names: list[str]) -> None:
        """準標準ボーンのウェイトの乗せ替え"""

        self.update_vertices_by_bone()
        upper_wait_bone_names = (
            ["上半身", "上半身2"] + ["上半身3"] if "上半身3" in self.bones else []
        )

        if "上半身2" in bone_names and self.bones.exists(("上半身", "上半身2")):
            tail_bone_name = (
                "上半身3" if "上半身3" in self.bones else "首" if "首" in self.bones else None
            )
            if tail_bone_name:
                self.separate_weights(
                    "上半身",
                    "上半身2",
                    tail_bone_name,
                    0.3,
                    0.5,
                    upper_wait_bone_names,
                    to_tail_pos=MVector3D(0, 1, 0),
                )
            else:
                self.separate_weights(
                    "上半身",
                    "上半身2",
                    "上半身2",
                    0.3,
                    0.5,
                    upper_wait_bone_names,
                    to_tail_pos=MVector3D(0, 1, 0),
                )
        if "上半身3" in bone_names and self.bones.exists(("上半身", "上半身2", "上半身3")):
            self.update_vertices_by_bone()
            if "首" in self.bones:
                self.separate_weights(
                    "上半身2",
                    "上半身3",
                    "首",
                    0.3,
                    0.0,
                    upper_wait_bone_names,
                    to_tail_pos=MVector3D(0, 1, 0),
                )
            else:
                self.separate_weights(
                    "上半身2",
                    "上半身3",
                    "上半身3",
                    0.3,
                    0.0,
                    upper_wait_bone_names,
                    to_tail_pos=MVector3D(0, 1, 0),
                )
        if "右足先EX" in bone_names and self.bones.exists(("右足首", "右足首D", "右足先EX")):
            to_tail_z = self.bones["右足先EX"].position.z - self.bones["右足首"].position.z
            self.separate_weights(
                "右足首",
                "右足先EX",
                "右足先EX",
                0.2,
                0.1,
                ("右足首", "右足首D", "右足先EX"),
                to_tail_pos=MVector3D(0, 0, to_tail_z),
            )
        if "左足先EX" in bone_names and self.bones.exists(("左足首", "左足首D", "左足先EX")):
            to_tail_z = self.bones["左足先EX"].position.z - self.bones["左足首"].position.z
            self.separate_weights(
                "左足首",
                "左足先EX",
                "左足先EX",
                0.2,
                0.1,
                ("左足首", "左足首D", "左足先EX"),
                to_tail_pos=MVector3D(0, 0, to_tail_z),
            )
        if "右肩" in bone_names and self.bones.exists(("上半身", "上半身2", "右肩", "右腕")):
            self.separate_weights(
                "上半身3" if "上半身3" in self.bones else "上半身2",
                "右肩",
                "右腕",
                0.1,
                0.5,
                (("上半身3" if "上半身3" in self.bones else "上半身2"), "右肩"),
                is_shoulder=True,
            )
        if "左肩" in bone_names and self.bones.exists(("上半身", "上半身2", "左肩", "左腕")):
            self.separate_weights(
                "上半身3" if "上半身3" in self.bones else "上半身2",
                "左肩",
                "左腕",
                0.1,
                0.5,
                (("上半身3" if "上半身3" in self.bones else "上半身2"), "左肩"),
                is_shoulder=True,
            )
        if "右親指０" in bone_names and self.bones.exists(("右手首", "右親指０", "右親指１")):
            self.separate_weights(
                "右手首",
                "右親指０",
                "右親指１",
                0.1,
                0.0,
                ("右手首", "右親指１"),
                is_thumb=True,
            )
        if "左親指０" in bone_names and self.bones.exists(("左手首", "左親指０", "左親指１")):
            self.separate_weights(
                "左手首",
                "左親指０",
                "左親指１",
                0.1,
                0.0,
                ("左手首", "左親指１"),
                is_thumb=True,
            )
        if "右腕捩" in bone_names and self.bones.exists(
            ("右腕", "右腕捩", "右腕捩1", "右腕捩2", "右腕捩3")
        ):
            self.separate_weights(
                "右腕",
                "右腕捩1",
                "右腕捩2",
                1.2,
                1.0,
                ("右腕", "右腕捩", "右腕捩1", "右腕捩2", "右腕捩3"),
                is_twist=True,
            )
            self.separate_weights(
                "右腕捩1",
                "右腕捩2",
                "右腕捩3",
                1.2,
                1.0,
                ("右腕", "右腕捩", "右腕捩1", "右腕捩2", "右腕捩3"),
                is_twist=True,
            )
            self.separate_weights(
                "右腕捩2",
                "右腕捩3",
                "右腕捩",
                1.2,
                1.0,
                ("右腕", "右腕捩", "右腕捩1", "右腕捩2", "右腕捩3"),
                is_twist=True,
            )
        if "左腕捩" in bone_names and self.bones.exists(
            ("左腕", "左腕捩", "左腕捩1", "左腕捩2", "左腕捩3")
        ):
            self.separate_weights(
                "左腕",
                "左腕捩1",
                "左腕捩2",
                1.2,
                1.0,
                ("左腕", "左腕捩", "左腕捩1", "左腕捩2", "左腕捩3"),
                is_twist=True,
            )
            self.separate_weights(
                "左腕捩1",
                "左腕捩2",
                "左腕捩3",
                1.2,
                1.0,
                ("左腕", "左腕捩", "左腕捩1", "左腕捩2", "左腕捩3"),
                is_twist=True,
            )
            self.separate_weights(
                "左腕捩2",
                "左腕捩3",
                "左腕捩",
                1.2,
                1.0,
                ("左腕", "左腕捩", "左腕捩1", "左腕捩2", "左腕捩3"),
                is_twist=True,
            )
        if "右手捩" in bone_names and self.bones.exists(
            ("右手", "右手捩", "右手捩1", "右手捩2", "右手捩3")
        ):
            self.separate_weights(
                "右ひじ",
                "右手捩1",
                "右手捩2",
                1.2,
                1.0,
                ("右ひじ", "右手捩", "右手捩1", "右手捩2", "右手捩3"),
                is_twist=True,
            )
            self.separate_weights(
                "右手捩1",
                "右手捩2",
                "右手捩3",
                1.2,
                1.0,
                ("右ひじ", "右手捩", "右手捩1", "右手捩2", "右手捩3"),
                is_twist=True,
            )
            self.separate_weights(
                "右手捩2",
                "右手捩3",
                "右手捩",
                1.2,
                1.0,
                ("右ひじ", "右手捩", "右手捩1", "右手捩2", "右手捩3"),
                is_twist=True,
            )
        if "左手捩" in bone_names and self.bones.exists(
            ("左手", "左手捩", "左手捩1", "左手捩2", "左手捩3")
        ):
            self.separate_weights(
                "左ひじ",
                "左手捩1",
                "左手捩2",
                1.2,
                1.0,
                ("左ひじ", "左手捩", "左手捩1", "左手捩2", "左手捩3"),
                is_twist=True,
            )
            self.separate_weights(
                "左手捩1",
                "左手捩2",
                "左手捩3",
                1.2,
                1.0,
                ("左ひじ", "左手捩", "左手捩1", "左手捩2", "左手捩3"),
                is_twist=True,
            )
            self.separate_weights(
                "左手捩2",
                "左手捩3",
                "左手捩",
                1.2,
                1.0,
                ("左ひじ", "左手捩", "左手捩1", "左手捩2", "左手捩3"),
                is_twist=True,
            )

        if True in [
            self.bones[bone_name].is_leg_d
            for bone_name in bone_names
            if bone_name in self.bones
        ]:
            # 足Dはそのまま置き換える
            replaced_map = dict([(b.index, b.index) for b in self.bones])
            target_vertex_indexes: list[int] = []
            for bone_name in bone_names:
                if bone_name not in self.bones:
                    continue
                bone = self.bones[bone_name]
                # ウェイトの一括置換
                if bone.is_leg_d and bone_name[:-1] in self.bones:
                    leg_fk_index = self.bones[bone_name[:-1]].index
                    replaced_map[leg_fk_index] = bone.index
                    target_vertex_indexes += self.vertices_by_bones.get(
                        leg_fk_index, []
                    )
            for v in self.vertices:
                v.deform.indexes = np.vectorize(replaced_map.get)(v.deform.indexes)

    def separate_weights(
        self,
        from_name: str,
        separate_name: str,
        to_name: str,
        from_ratio: float,
        to_ratio: float,
        weight_bone_names: Iterable[str] = [],
        to_tail_pos: MVector3D = MVector3D(),
        is_thumb: bool = False,
        is_shoulder: bool = False,
        is_twist: bool = False,
    ):
        """ウェイト置換"""
        from_bone = self.bones[from_name]
        separate_bone = self.bones[separate_name]
        to_bone = self.bones[to_name]

        # ウェイト乗せ替え対象頂点はFROMとTOの間
        vertex_indexes = set(
            [
                vertex_index
                for weight_bone_name in weight_bone_names
                if weight_bone_name in self.bones
                for vertex_index in self.vertices_by_bones.get(
                    self.bones[weight_bone_name].index, []
                )
            ]
        )

        if not vertex_indexes:
            return

        match_bone_indexes = [
            self.bones[weight_bone_name].index
            for weight_bone_name in weight_bone_names
            if weight_bone_name in self.bones
        ]

        if not to_tail_pos:
            # 先は分割したボーンの表示先
            to_tail_pos = self.bones.get_tail_relative_position(separate_bone.index)
            if np.isclose(to_tail_pos.length(), 0.0):
                # 表示先がない場合、表示先に類するボーンのうち最も遠いものを選ぶ
                bone_pos_dict = MVectorDict()
                # 分割ボーンの付与親ボーンの末端
                if (
                    separate_bone.is_external_translation
                    or separate_bone.is_external_rotation
                ) and 0 <= separate_bone.effect_index:
                    bone_pos_dict.append(
                        separate_bone.effect_index,
                        self.bones[separate_bone.effect_index].tail_relative_position,
                    )
                # 分割ボーンの親ボーン
                separate_parent_bone = self.bones[separate_bone.parent_index]
                # 分割ボーンの親ボーンの末端
                if (
                    separate_parent_bone.is_tail_bone
                    and separate_bone.tail_index in self.bones
                ):
                    bone_pos_dict.append(
                        separate_parent_bone.index,
                        self.bones[separate_parent_bone.index].tail_relative_position,
                    )
                if (
                    separate_parent_bone.is_external_translation
                    or separate_parent_bone.is_external_rotation
                ) and 0 <= separate_parent_bone.effect_index:
                    # 分割ボーンの親ボーンの付与親ボーンの末端
                    separate_parent_effect_bone = self.bones[
                        separate_parent_bone.effect_index
                    ]
                    bone_pos_dict.append(
                        separate_parent_effect_bone.index,
                        self.bones[
                            separate_parent_effect_bone.index
                        ].tail_relative_position,
                    )

                if not len(bone_pos_dict):
                    # 見つからない場合、親ボーンからの距離を加味する
                    to_tail_pos = from_bone.position - separate_bone.position
                else:
                    # 見つかった場合、そのうちに最も遠いものをTOターゲットにする
                    to_tail_pos = bone_pos_dict.farthest_value(MVector3D())
        else:
            to_tail_pos *= self.bones.get_tail_relative_position(
                separate_bone.index
            ).length()

        to_pos = separate_bone.position + to_tail_pos
        mat = MMatrix4x4()
        mat.translate(separate_bone.position)
        if is_shoulder:
            if "右" in separate_bone.name:
                mat = mat @ MVector3D(-1, 0, 0).to_local_matrix4x4()
            else:
                mat = mat @ MVector3D(1, 0, 0).to_local_matrix4x4()
        else:
            mat = mat @ to_tail_pos.to_local_matrix4x4()

        # ローカル位置
        local_from_pos = mat.inverse() * from_bone.position
        local_to_pos = mat.inverse() * to_pos

        for vertex_index in vertex_indexes:
            v = self.vertices[vertex_index]
            v.deform.normalize(align=True)
            to_separate_ratio = 0.0

            # 頂点のローカル位置
            local_vpos = mat.inverse() * v.position

            # 同じボーンINDEXで複数の欄にウェイトを持っている可能性があるので、matchで確認
            bone_matches = np.array([i in match_bone_indexes for i in v.deform.indexes])

            if is_thumb:
                # 親指の場合、親指の周囲だけウェイトを塗る
                if to_tail_pos.z > local_vpos.z or v.position.z > from_bone.position.z:
                    # FROMの一定距離より内側のボーン方向にある場合、スルー
                    continue
                else:
                    if 0 <= local_vpos.z:
                        # ウェイト割り当てボーンより外側にある場合、TO側で置換してスルー
                        v.deform.indexes = np.where(
                            bone_matches, separate_bone.index, v.deform.indexes
                        )
                        continue
                    else:
                        # 親指０より手首よりの場合、ウェイト計算
                        ratio = 1 - abs(local_vpos.z / to_tail_pos.z)
            elif is_shoulder:
                # 肩の場合、肩の周囲だけウェイトを塗る
                if np.sign(v.position.x) != np.sign(to_pos.x):
                    # 上半身より反対側の場合、スルー
                    continue

                if local_vpos.x <= local_to_pos.x * from_ratio * -1:
                    # 上半身寄りで、頂点のX位置が肩から腕の距離の一定割合より遠い場合、上半身に割り当ててスルー
                    v.deform.indexes = np.where(
                        bone_matches, from_bone.index, v.deform.indexes
                    )
                    continue
                elif local_vpos.x >= local_to_pos.x * to_ratio:
                    # 腕寄りで、頂点のX位置が肩から腕の距離の一定割合より遠い場合、腕に割り当ててスルー
                    v.deform.indexes = np.where(
                        bone_matches, to_bone.index, v.deform.indexes
                    )
                    continue

                if v.position.y < separate_bone.position.y + (
                    local_to_pos.x * from_ratio * 0.5
                ):
                    # Y方向的に肩より下の場合、上半身側に渡してスルー
                    v.deform.indexes = np.where(
                        bone_matches, from_bone.index, v.deform.indexes
                    )
                    continue

                ratio = (1 - abs(local_vpos.x / local_to_pos.x)) * 0.8
                if 0 < v.position.x:
                    # 腕側の場合のみ分割先に割り当てる
                    to_separate_ratio = (1 - ratio) * 0.8
            elif is_twist:
                if 0 > local_vpos.x:
                    ratio = (
                        1 - (local_vpos.x / (local_from_pos.x * from_ratio))
                        if from_ratio
                        else 1
                    )
                    if 1 <= ratio:
                        continue
                else:
                    if local_vpos.x <= local_to_pos.x * from_ratio * -1:
                        # FROM寄りで、頂点のX位置が捩りから遠い場合、スルー
                        continue

                    if local_vpos.x >= local_to_pos.x * to_ratio:
                        # TO寄りで、頂点のX位置が捩りから遠い場合、TOに割り当ててスルー
                        v.deform.indexes = np.where(
                            bone_matches, to_bone.index, v.deform.indexes
                        )
                        continue

                    ratio = 1 - (abs(local_vpos.x) / local_to_pos.x)
                    if 0 < local_vpos.x:
                        # 腕側の場合のみ分割先に割り当てる
                        to_separate_ratio = 1 - ratio
            else:
                if 0 > local_vpos.x:
                    ratio = (
                        1 - (local_vpos.x / (local_from_pos.x * from_ratio))
                        if from_ratio
                        else 1
                    )
                    if 1 <= ratio:
                        continue
                else:
                    if 0.0 == to_ratio or 0 <= local_vpos.x:
                        # 全部TOに乗せるのであれば、そのまま分割ボーンに乗せ替え
                        # TO寄りで、頂点のX位置がTOから遠い場合、分割ボーンに乗せ替え
                        v.deform.indexes = np.where(
                            bone_matches, separate_bone.index, v.deform.indexes
                        )
                        continue
                    else:
                        ratio = local_vpos.x / (local_to_pos.x * to_ratio)
                        if 1 <= ratio:
                            # TOボーンの一定距離よりさきの場合、分割ボーンに分配する
                            v.deform.indexes = np.where(
                                bone_matches, separate_bone.index, v.deform.indexes
                            )
                            continue
                        else:
                            ratio = 1 - ratio

            if 0 >= ratio:
                continue

            # # 分割先ボーンのウェイトは一旦元ボーンに載せ替える
            # v.deform.indexes = np.where(bone_matches, from_bone.index, v.deform.indexes)
            original_weight = np.sum(v.deform.weights[bone_matches])
            separate_weight = (
                original_weight * ratio / (np.count_nonzero(bone_matches) or 1)
            )
            to_weight = (
                original_weight
                * to_separate_ratio
                / (np.count_nonzero(bone_matches) or 1)
            )
            # 元ボーンは分割先ボーンの残り
            v.deform.weights = np.where(
                bone_matches,
                v.deform.weights - separate_weight - to_weight,
                v.deform.weights,
            )
            v.deform.weights[0.01 > v.deform.weights] = 0
            v.deform.weights = np.append(v.deform.weights, original_weight * ratio)
            v.deform.indexes = np.append(v.deform.indexes, separate_bone.index)
            if 0 < to_separate_ratio and to_bone.index in self.bones:
                v.deform.weights = np.append(
                    v.deform.weights, original_weight * to_separate_ratio
                )
                v.deform.indexes = np.append(v.deform.indexes, to_bone.index)
            # 一旦最大値で正規化
            v.deform.count = 4
            v.deform.normalize(align=True)
            if np.count_nonzero(v.deform.weights) == 0:
                # 念のためウェイトが割り当てられなかったら、元ボーンを割り当てとく
                v.deform = Bdef1(from_bone.index)
            elif np.count_nonzero(v.deform.weights) == 1:
                # Bdef1で再定義
                v.deform = Bdef1(int(v.deform.indexes[np.argmax(v.deform.weights)]))
            elif np.count_nonzero(v.deform.weights) == 2:
                # Bdef2で再定義
                v.deform = Bdef2(
                    int(v.deform.indexes[np.argsort(v.deform.weights)[-1]]),
                    int(v.deform.indexes[np.argsort(v.deform.weights)[-2]]),
                    float(np.max(v.deform.weights)),
                )
            v.deform.normalize(align=True)


class Meshes(BaseIndexDictModel[Mesh]):
    """
    メッシュリスト
    """

    __slots__ = (
        "data",
        "indexes",
        "model",
        "vertices",
        "faces",
        "vao",
        "vbo_components",
        "morph_pos_comps",
        "morph_uv_comps",
        "morph_uv1_comps",
        "vbo_vertices",
        "ibo_faces",
        "bones",
        "bone_hierarchies",
        "bone_vao",
        "bone_vbo_components",
        "bone_vbo_vertices",
        "bone_ibo_faces",
        "axises",
        "axis_hierarchies",
        "axis_vao",
        "axis_vbo_components",
        "axis_vbo_vertices",
        "axis_ibo_faces",
    )

    def __init__(self, model: PmxModel, is_sub: bool) -> None:
        super().__init__()

        self.model = model

        # 頂点情報
        self.vertices = np.array(
            [
                np.fromiter(
                    [
                        *v.position.gl.vector,
                        *v.normal.gl.vector,
                        v.uv.x,
                        1 - v.uv.y,
                        v.extended_uvs[0].x if 0 < len(v.extended_uvs) else 0.0,
                        1 - v.extended_uvs[0].y if 0 < len(v.extended_uvs) else 0.0,
                        v.edge_factor,
                        *v.deform.normalized_deform(),
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                    ],
                    dtype=np.float32,
                    count=33,
                )
                for v in model.vertices
            ],
        )

        face_dtype: type = (
            np.uint8
            if model.vertex_count == 1
            else np.uint16
            if model.vertex_count == 2
            else np.uint32
        )

        # 面情報
        self.faces: np.ndarray = np.array(
            [
                np.array(
                    [f.vertices[2], f.vertices[1], f.vertices[0]], dtype=face_dtype
                )
                for f in model.faces
            ],
        )

        prev_vertices_count = 0
        for material in model.materials:
            texture: Optional[Texture] = None
            if 0 <= material.texture_index:
                texture = model.textures[material.texture_index]
                texture.init_draw(model.path, TextureType.TEXTURE, is_sub=is_sub)

            toon_texture: Optional[Texture] = None
            if ToonSharing.SHARING == material.toon_sharing_flg:
                # 共有Toon
                toon_texture = model.toon_textures[material.toon_texture_index]
                toon_texture.init_draw(
                    model.path, TextureType.TOON, is_individual=False, is_sub=is_sub
                )
            elif (
                ToonSharing.INDIVIDUAL == material.toon_sharing_flg
                and 0 <= material.toon_texture_index
            ):
                # 個別Toon
                toon_texture = model.textures[material.toon_texture_index]
                toon_texture.init_draw(model.path, TextureType.TOON, is_sub=is_sub)

            sphere_texture: Optional[Texture] = None
            if 0 <= material.sphere_texture_index:
                sphere_texture = model.textures[material.sphere_texture_index]
                sphere_texture.init_draw(model.path, TextureType.SPHERE, is_sub=is_sub)

            self.append(
                Mesh(
                    material,
                    texture,
                    toon_texture,
                    sphere_texture,
                    prev_vertices_count,
                    face_dtype,
                )
            )

            prev_vertices_count += material.vertices_count

        # ---------------------

        # 頂点VAO
        self.vao = VAO(is_sub)
        self.vbo_components = {
            VsLayout.POSITION_ID.value: {"size": 3, "offset": 0},
            VsLayout.NORMAL_ID.value: {"size": 3, "offset": 3},
            VsLayout.UV_ID.value: {"size": 2, "offset": 6},
            VsLayout.EXTEND_UV_ID.value: {"size": 2, "offset": 8},
            VsLayout.EDGE_ID.value: {"size": 1, "offset": 10},
            VsLayout.BONE_ID.value: {"size": 4, "offset": 11},
            VsLayout.WEIGHT_ID.value: {"size": 4, "offset": 15},
            VsLayout.MORPH_POS_ID.value: {"size": 3, "offset": 19},
            VsLayout.MORPH_UV_ID.value: {"size": 4, "offset": 22},
            VsLayout.MORPH_UV1_ID.value: {"size": 4, "offset": 26},
            VsLayout.MORPH_AFTER_POS_ID.value: {"size": 3, "offset": 30},
        }
        self.morph_pos_comps = self.vbo_components[VsLayout.MORPH_POS_ID.value]
        self.morph_uv_comps = self.vbo_components[VsLayout.MORPH_UV_ID.value]
        self.morph_uv1_comps = self.vbo_components[VsLayout.MORPH_UV1_ID.value]
        self.morph_after_pos_comps = self.vbo_components[
            VsLayout.MORPH_AFTER_POS_ID.value
        ]
        self.vbo_vertices = VBO(
            self.vertices,
            self.vbo_components,
            is_sub,
        )
        self.ibo_faces = IBO(self.faces, is_sub)

        # ----------

        # ボーン位置
        self.bones = np.array(
            [
                np.array(
                    [
                        *b.position.gl.vector,
                        b.index / len(model.bones),
                        0.0,
                    ],
                    dtype=np.float32,
                )
                for b in model.bones
            ],
        )

        bone_face_dtype: type = (
            np.uint8
            if 256 > len(model.bones)
            else np.uint16
            if 65536 > len(model.bones)
            else np.uint32
        )

        # ボーン親子関係
        self.bone_hierarchies: np.ndarray = np.array(
            [
                np.array(
                    [
                        b.index,
                        b.parent_index,
                    ],
                    dtype=bone_face_dtype,
                )
                for b in model.bones
                if 0 <= b.parent_index
            ],
        )

        # ボーンVAO
        self.bone_vao = VAO(is_sub)
        self.bone_vbo_components = {
            0: {"size": 3, "offset": 0},
            1: {"size": 1, "offset": 3},
            2: {"size": 1, "offset": 4},
        }
        self.bone_vbo_vertices = VBO(
            self.bones,
            self.bone_vbo_components,
            is_sub,
        )
        self.bone_ibo_faces = IBO(self.bone_hierarchies, is_sub)

        # # ----------

        # # ローカル軸
        # self.axises = np.array(
        #     [
        #         np.array(
        #             [
        #                 *b.position.gl.vector,
        #                 b.index / len(model.bones) * 2,
        #             ],
        #             dtype=np.float32,
        #         )
        #         for b in model.bones
        #     ]
        #     + [
        #         np.array(
        #             [
        #                 *(b.position + b.local_axis).gl.vector,
        #                 b.index / len(model.bones) * 2,
        #             ],
        #             dtype=np.float32,
        #         )
        #         for b in model.bones
        #     ],
        # )

        # axis_face_dtype: type = np.uint8 if 256 > len(model.bones) * 2 else np.uint16 if 65536 > len(model.bones) * 2 else np.uint32

        # # ローカル軸親子関係
        # self.axis_hierarchies: np.ndarray = np.array(
        #     [
        #         np.array(
        #             [
        #                 b.index,
        #                 len(model.bones) + b.index,
        #             ],
        #             dtype=axis_face_dtype,
        #         )
        #         for b in model.bones
        #     ],
        # )

        # # ローカル軸VAO
        # self.axis_vao = VAO()
        # self.axis_vbo_components = {
        #     0: {"size": 3, "offset": 0},
        #     1: {"size": 1, "offset": 3},
        # }
        # self.axis_vbo_vertices = VBO(
        #     self.axises,
        #     self.axis_vbo_components,
        # )
        # self.axis_ibo_faces = IBO(self.axis_hierarchies)

    def draw(
        self,
        shader: MShader,
        bone_matrixes: np.ndarray,
        vertex_morph_poses: np.ndarray,
        after_vertex_morph_poses: np.ndarray,
        uv_morph_poses: np.ndarray,
        uv1_morph_poses: np.ndarray,
        material_morphs: list[ShaderMaterial],
        is_alpha: bool,
        is_show_bone_weight: bool,
        show_bone_indexes: list[int],
        is_sub: bool,
    ):
        # 隠面消去
        # https://learnopengl.com/Advanced-OpenGL/Depth-testing
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LEQUAL)

        # 頂点モーフ変動量を上書き設定してからバインド
        self.vbo_vertices.data[
            :,
            self.morph_pos_comps["offset"] : (
                self.morph_pos_comps["offset"] + self.morph_pos_comps["size"]
            ),
        ] = vertex_morph_poses
        self.vbo_vertices.data[
            :,
            self.morph_uv_comps["offset"] : (
                self.morph_uv_comps["offset"] + self.morph_uv_comps["size"]
            ),
        ] = uv_morph_poses
        self.vbo_vertices.data[
            :,
            self.morph_uv1_comps["offset"] : (
                self.morph_uv1_comps["offset"] + self.morph_uv1_comps["size"]
            ),
        ] = uv1_morph_poses
        self.vbo_vertices.data[
            :,
            self.morph_after_pos_comps["offset"] : (
                self.morph_after_pos_comps["offset"]
                + self.morph_after_pos_comps["size"]
            ),
        ] = after_vertex_morph_poses

        # 必ず50個渡すようにする（ただし該当しないボーンINDEXにしておく）
        limited_show_bone_indexes = (show_bone_indexes + [-2 for _ in range(50)])[:50]

        for mesh in self:
            self.vao.bind(is_sub)
            self.vbo_vertices.bind(is_sub)
            self.vbo_vertices.set_slot(VsLayout.POSITION_ID)
            self.vbo_vertices.set_slot(VsLayout.NORMAL_ID)
            self.vbo_vertices.set_slot(VsLayout.UV_ID)
            self.vbo_vertices.set_slot(VsLayout.EXTEND_UV_ID)
            self.vbo_vertices.set_slot(VsLayout.EDGE_ID)
            self.vbo_vertices.set_slot(VsLayout.BONE_ID)
            self.vbo_vertices.set_slot(VsLayout.WEIGHT_ID)
            self.vbo_vertices.set_slot(VsLayout.MORPH_POS_ID)
            self.vbo_vertices.set_slot(VsLayout.MORPH_UV_ID)
            self.vbo_vertices.set_slot(VsLayout.MORPH_UV1_ID)
            self.vbo_vertices.set_slot(VsLayout.MORPH_AFTER_POS_ID)
            self.ibo_faces.bind(is_sub)

            material_morph = material_morphs[mesh.material.index]

            if 0.0 >= material_morph.material.diffuse.w:
                # 非表示材質の場合、常に描写しない
                continue

            if (
                is_alpha
                and mesh.material.diffuse.w <= material_morph.material.diffuse.w
            ):
                # 半透明描写かつ非透過度が元々の非透過度以上の場合、スルー
                continue
            elif (
                not is_alpha
                and mesh.material.diffuse.w > material_morph.material.diffuse.w
            ):
                # 不透明描写かつ非透過度が元々の非透過度未満の場合スルー
                continue

            # アルファテストを有効にする
            gl.glEnable(gl.GL_ALPHA_TEST)

            # ブレンディングを有効にする
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

            # モデル描画
            shader.use(ProgramType.MODEL)
            mesh.draw_model(
                bone_matrixes,
                material_morph,
                shader,
                self.ibo_faces,
                is_show_bone_weight,
                limited_show_bone_indexes,
                is_sub,
            )
            shader.unuse()

            if (
                DrawFlg.DRAWING_EDGE in mesh.material.draw_flg
                and 0 < material_morph.material.diffuse.w
            ):
                # エッジ描画
                shader.use(ProgramType.EDGE)
                mesh.draw_edge(bone_matrixes, material_morph, shader, self.ibo_faces)
                shader.unuse()

            # ---------------

            self.ibo_faces.unbind()
            self.vbo_vertices.unbind()
            self.vao.unbind()

            gl.glDisable(gl.GL_BLEND)
            gl.glDisable(gl.GL_ALPHA_TEST)

        gl.glDisable(gl.GL_DEPTH_TEST)

    def draw_bone(
        self,
        shader: MShader,
        bone_matrixes: np.ndarray,
        select_bone_color: np.ndarray,
        unselect_bone_color: np.ndarray,
        selected_bone_indexes: np.ndarray,
        is_sub: bool,
    ):
        # ボーンをモデルメッシュの前面に描画するために深度テストを無効化
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_ALWAYS)

        # アルファテストを有効にする
        gl.glEnable(gl.GL_ALPHA_TEST)

        # ブレンディングを有効にする
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

        # 選択ボーンを切り替える
        self.bone_vbo_vertices.data[:, -1] = selected_bone_indexes

        self.bone_vao.bind(is_sub)
        self.bone_vbo_vertices.bind(is_sub)
        self.bone_vbo_vertices.set_slot_by_value(0)
        self.bone_vbo_vertices.set_slot_by_value(1)
        self.bone_vbo_vertices.set_slot_by_value(2)
        self.bone_ibo_faces.bind(is_sub)

        shader.use(ProgramType.BONE)

        gl.glUniform4f(
            shader.select_bone_color_uniform[ProgramType.BONE.value], *select_bone_color
        )
        gl.glUniform4f(
            shader.unselect_bone_color_uniform[ProgramType.BONE.value],
            *unselect_bone_color,
        )
        gl.glUniform1i(
            shader.bone_count_uniform[ProgramType.BONE.value], len(self.model.bones)
        )

        if self.model.meshes:
            self.model.meshes[0].bind_bone_matrixes(
                bone_matrixes, shader, ProgramType.BONE
            )

        try:
            gl.glDrawElements(
                gl.GL_LINES,
                self.bone_hierarchies.size,
                self.bone_ibo_faces.dtype,
                gl.ctypes.c_void_p(0),
            )
        except Exception as e:
            raise MViewerException("Meshes draw_bone Failure", e)

        error_code = gl.glGetError()
        if error_code != gl.GL_NO_ERROR:
            raise MViewerException(f"Meshes draw_bone Failure\n{error_code}")

        if self.model.meshes:
            self.model.meshes[0].unbind_bone_matrixes()

        self.bone_ibo_faces.unbind()
        self.bone_vbo_vertices.unbind()
        self.bone_vao.unbind()
        shader.unuse()

        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_ALPHA_TEST)
        gl.glDisable(gl.GL_DEPTH_TEST)

    def delete_draw(self) -> None:
        for material in self.model.materials:
            texture: Optional[Texture] = None
            if 0 <= material.texture_index:
                texture = self.model.textures[material.texture_index]
                texture.delete_draw()

            toon_texture: Optional[Texture] = None
            if ToonSharing.SHARING == material.toon_sharing_flg:
                # 共有Toon
                toon_texture = self.model.toon_textures[material.toon_texture_index]
                toon_texture.delete_draw()
            elif (
                ToonSharing.INDIVIDUAL == material.toon_sharing_flg
                and 0 <= material.toon_texture_index
            ):
                # 個別Toon
                toon_texture = self.model.textures[material.toon_texture_index]
                toon_texture.delete_draw()

            sphere_texture: Optional[Texture] = None
            if 0 <= material.sphere_texture_index:
                sphere_texture = self.model.textures[material.sphere_texture_index]
                sphere_texture.delete_draw()
        del self.vao
        del self.vbo_components
        del self.morph_pos_comps
        del self.morph_uv_comps
        del self.morph_uv1_comps
        del self.vbo_vertices
        del self.ibo_faces
