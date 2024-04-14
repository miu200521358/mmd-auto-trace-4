import os
import struct
from enum import Enum
from io import BufferedWriter
from math import isinf, isnan
from typing import Tuple

from mlib.core.base import BaseModel
from mlib.core.logger import MLogger
from mlib.pmx.bone_setting import BoneFlg
from mlib.pmx.pmx_collection import PmxModel
from mlib.pmx.pmx_part import (
    Bdef1,
    Bdef2,
    Bdef4,
    Bone,
    BoneMorphOffset,
    GroupMorphOffset,
    MaterialMorphOffset,
    Sdef,
    ToonSharing,
    UvMorphOffset,
    VertexMorphOffset,
)

logger = MLogger(os.path.basename(__file__))


class PmxBinaryType(str, Enum):
    FLOAT = "f"
    BOOL = "c"
    BYTE = "<b"
    UNSIGNED_BYTE = "<B"
    SHORT = "<h"
    UNSIGNED_SHORT = "<H"
    INT = "<i"
    UNSIGNED_INT = "<I"
    LONG = "<l"
    UNSIGNED_LONG = "<L"


class PmxWriter(BaseModel):
    def __init__(
        self, model: PmxModel, output_path: str, include_system: bool = False
    ) -> None:
        super().__init__()
        self.model = model
        self.output_path = output_path
        self.include_system = include_system

    def save(self) -> None:
        if not self.include_system:
            for bone in self.model.bones:
                if bone.is_system:
                    self.model.remove_bone(bone.name)

        with open(self.output_path, "wb") as fout:
            target_bones = (
                [b for b in self.model.bones if b.index >= 0]
                if self.include_system
                else self.model.bones.writable()
            )

            # シグニチャ
            fout.write(b"PMX ")
            self.write_number(fout, PmxBinaryType.FLOAT, float(2))
            # 後続するデータ列のバイトサイズ  PMX2.0は 8 で固定
            self.write_byte(fout, 8)
            # エンコード方式  | 0:UTF16
            self.write_byte(fout, 0)
            # 追加UV数
            self.write_byte(fout, self.model.extended_uv_count)
            # 頂点Indexサイズ | 1,2,4 のいずれか
            vertex_idx_size, vertex_idx_type = self.define_write_index(
                len(self.model.vertices), is_vertex=True
            )
            self.write_byte(fout, vertex_idx_size)
            # テクスチャIndexサイズ | 1,2,4 のいずれか
            texture_idx_size, texture_idx_type = self.define_write_index(
                len(self.model.textures), is_vertex=False
            )
            self.write_byte(fout, texture_idx_size)
            # 材質Indexサイズ | 1,2,4 のいずれか
            material_idx_size, material_idx_type = self.define_write_index(
                len(self.model.materials), is_vertex=False
            )
            self.write_byte(fout, material_idx_size)
            # ボーンIndexサイズ | 1,2,4 のいずれか
            bone_idx_size, bone_idx_type = self.define_write_index(
                len(target_bones), is_vertex=False
            )
            self.write_byte(fout, bone_idx_size)
            # モーフIndexサイズ | 1,2,4 のいずれか
            morph_idx_size, morph_idx_type = self.define_write_index(
                len(self.model.morphs), is_vertex=False
            )
            self.write_byte(fout, morph_idx_size)
            # 剛体Indexサイズ | 1,2,4 のいずれか
            rigidbody_idx_size, rigidbody_idx_type = self.define_write_index(
                len(self.model.rigidbodies), is_vertex=False
            )
            self.write_byte(fout, rigidbody_idx_size)

            # モデル名(日本語)
            self.write_text(fout, self.model.name, "Pmx Model")
            # モデル名(英語)
            self.write_text(fout, self.model.english_name, "Pmx Model")
            # コメント(日本語)
            self.write_text(fout, self.model.comment, "")
            # コメント(英語)
            self.write_text(fout, self.model.english_comment, "")

            # 頂点出力
            self.write_vertices(fout, bone_idx_type)

            # 頂点出力
            self.write_faces(fout, vertex_idx_type)

            # テクスチャ出力
            self.write_textures(fout)

            # 材質出力
            self.write_materials(fout, texture_idx_type)

            # ボーン出力
            self.write_bones(fout, bone_idx_type, target_bones)

            # モーフ出力
            self.write_morphs(
                fout, vertex_idx_type, bone_idx_type, material_idx_type, morph_idx_type
            )

            # 表示枠出力
            self.write_display_slots(fout, bone_idx_type, morph_idx_type)

            # 剛体出力
            self.write_rigidbodies(fout, bone_idx_type)

            # ジョイント出力
            self.write_joints(fout, rigidbody_idx_type)

    def write_vertices(self, fout: BufferedWriter, bone_idx_type: PmxBinaryType):
        """
        頂点出力

        Parameters
        ----------
        model : PmxModel
        fout : BufferedWriter
        bone_idx_type : str

        Returns
        -------
        PmxModel
        """

        self.write_number(
            fout, PmxBinaryType.INT, len(self.model.vertices), is_positive_only=True
        )

        # 頂点データ
        for vertex in self.model.vertices:
            logger.count(
                "頂点データ出力",
                index=vertex.index,
                total_index_count=len(self.model.vertices),
                display_block=10000,
            )

            # position
            self.write_number(fout, PmxBinaryType.FLOAT, float(vertex.position.x))
            self.write_number(fout, PmxBinaryType.FLOAT, float(vertex.position.y))
            self.write_number(fout, PmxBinaryType.FLOAT, float(vertex.position.z))
            # normal
            self.write_number(fout, PmxBinaryType.FLOAT, float(vertex.normal.x))
            self.write_number(fout, PmxBinaryType.FLOAT, float(vertex.normal.y))
            self.write_number(fout, PmxBinaryType.FLOAT, float(vertex.normal.z))
            # uv
            self.write_number(fout, PmxBinaryType.FLOAT, float(vertex.uv.x))
            self.write_number(fout, PmxBinaryType.FLOAT, float(vertex.uv.y))
            # 追加uv
            for uv in vertex.extended_uvs:
                self.write_number(fout, PmxBinaryType.FLOAT, float(uv.x))
                self.write_number(fout, PmxBinaryType.FLOAT, float(uv.y))
                self.write_number(fout, PmxBinaryType.FLOAT, float(uv.z))
                self.write_number(fout, PmxBinaryType.FLOAT, float(uv.w))
            for _ in range(len(vertex.extended_uvs), self.model.extended_uv_count):
                # 追加UVが個数より足りない場合、0で埋める
                self.write_number(fout, PmxBinaryType.FLOAT, 0.0)
                self.write_number(fout, PmxBinaryType.FLOAT, 0.0)
                self.write_number(fout, PmxBinaryType.FLOAT, 0.0)
                self.write_number(fout, PmxBinaryType.FLOAT, 0.0)

            # deform
            if type(vertex.deform) is Bdef1:
                self.write_byte(fout, 0)
                self.write_number(fout, bone_idx_type, vertex.deform.indexes[0])
            elif type(vertex.deform) is Bdef2:
                self.write_byte(fout, 1)
                self.write_number(fout, bone_idx_type, vertex.deform.indexes[0])
                self.write_number(fout, bone_idx_type, vertex.deform.indexes[1])

                self.write_number(
                    fout,
                    PmxBinaryType.FLOAT,
                    vertex.deform.weights[0],
                    is_positive_only=True,
                )
            elif type(vertex.deform) is Bdef4:
                self.write_byte(fout, 2)
                self.write_number(fout, bone_idx_type, vertex.deform.indexes[0])
                self.write_number(fout, bone_idx_type, vertex.deform.indexes[1])
                self.write_number(fout, bone_idx_type, vertex.deform.indexes[2])
                self.write_number(fout, bone_idx_type, vertex.deform.indexes[3])

                self.write_number(
                    fout,
                    PmxBinaryType.FLOAT,
                    vertex.deform.weights[0],
                    is_positive_only=True,
                )
                self.write_number(
                    fout,
                    PmxBinaryType.FLOAT,
                    vertex.deform.weights[1],
                    is_positive_only=True,
                )
                self.write_number(
                    fout,
                    PmxBinaryType.FLOAT,
                    vertex.deform.weights[2],
                    is_positive_only=True,
                )
                self.write_number(
                    fout,
                    PmxBinaryType.FLOAT,
                    vertex.deform.weights[3],
                    is_positive_only=True,
                )
            elif type(vertex.deform) is Sdef:
                self.write_byte(fout, 3)
                self.write_number(fout, bone_idx_type, vertex.deform.indexes[0])
                self.write_number(fout, bone_idx_type, vertex.deform.indexes[1])
                self.write_number(
                    fout,
                    PmxBinaryType.FLOAT,
                    vertex.deform.weights[0],
                    is_positive_only=True,
                )
                self.write_number(
                    fout, PmxBinaryType.FLOAT, float(vertex.deform.sdef_c.x)
                )
                self.write_number(
                    fout, PmxBinaryType.FLOAT, float(vertex.deform.sdef_c.y)
                )
                self.write_number(
                    fout, PmxBinaryType.FLOAT, float(vertex.deform.sdef_c.z)
                )
                self.write_number(
                    fout, PmxBinaryType.FLOAT, float(vertex.deform.sdef_r0.x)
                )
                self.write_number(
                    fout, PmxBinaryType.FLOAT, float(vertex.deform.sdef_r0.y)
                )
                self.write_number(
                    fout, PmxBinaryType.FLOAT, float(vertex.deform.sdef_r0.z)
                )
                self.write_number(
                    fout, PmxBinaryType.FLOAT, float(vertex.deform.sdef_r1.x)
                )
                self.write_number(
                    fout, PmxBinaryType.FLOAT, float(vertex.deform.sdef_r1.y)
                )
                self.write_number(
                    fout, PmxBinaryType.FLOAT, float(vertex.deform.sdef_r1.z)
                )
            else:
                logger.error("頂点deformなし: {vertex}", vertex=str(vertex))

            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(vertex.edge_factor),
                is_positive_only=True,
            )

        logger.debug("-- 頂点データ出力終了({c})", c=len(self.model.vertices))

    def write_faces(self, fout: BufferedWriter, vertex_idx_type: PmxBinaryType):
        """
        面出力

        Parameters
        ----------
        model : PmxModel
        fout : BufferedWriter
        vertex_idx_type : str

        Returns
        -------
        PmxModel
        """

        # 面の数
        self.write_number(
            fout, PmxBinaryType.INT, len(self.model.faces) * 3, is_positive_only=True
        )

        # 面データ
        for face in self.model.faces:
            logger.count(
                "面データ出力",
                index=face.index,
                total_index_count=len(self.model.faces),
                display_block=10000,
            )

            for vidx in face.vertices:
                self.write_number(fout, vertex_idx_type, vidx, is_positive_only=True)

        logger.debug("-- 面データ出力終了({c})", c=len(self.model.faces))

    def write_textures(self, fout: BufferedWriter):
        """
        テクスチャ出力

        Parameters
        ----------
        model : PmxModel
        fout : BufferedWriter

        Returns
        -------
        PmxModel
        """
        # テクスチャの数
        self.write_number(
            fout, PmxBinaryType.INT, len(self.model.textures), is_positive_only=True
        )

        # テクスチャデータ
        for texture in self.model.textures:
            self.write_text(fout, texture.name, "")

        logger.debug("-- テクスチャデータ出力終了({c})", c=len(self.model.textures))

    def write_materials(self, fout: BufferedWriter, texture_idx_type: PmxBinaryType):
        """
        材質出力

        Parameters
        ----------
        model : PmxModel
        fout : BufferedWriter
        texture_idx_type : str

        Returns
        -------
        PmxModel
        """
        # 材質の数
        self.write_number(
            fout, PmxBinaryType.INT, len(self.model.materials), is_positive_only=True
        )

        # 材質データ
        for midx, material in enumerate(self.model.materials):
            # 材質名
            self.write_text(fout, material.name, f"Material {midx}")
            self.write_text(fout, material.english_name, f"Material {midx}")
            # Diffuse
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(material.diffuse.x),
                is_positive_only=True,
            )
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(material.diffuse.y),
                is_positive_only=True,
            )
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(material.diffuse.z),
                is_positive_only=True,
            )
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(material.diffuse.w),
                is_positive_only=True,
            )
            # Specular
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(material.specular.x),
                is_positive_only=True,
            )
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(material.specular.y),
                is_positive_only=True,
            )
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(material.specular.z),
                is_positive_only=True,
            )
            # Specular係数
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(material.specular_factor),
                is_positive_only=True,
            )
            # Ambient
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(material.ambient.x),
                is_positive_only=True,
            )
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(material.ambient.y),
                is_positive_only=True,
            )
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(material.ambient.z),
                is_positive_only=True,
            )
            # 描画フラグ(8bit)
            self.write_byte(fout, material.draw_flg.value)
            # エッジ色 (R,G,B,A)
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(material.edge_color.x),
                is_positive_only=True,
            )
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(material.edge_color.y),
                is_positive_only=True,
            )
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(material.edge_color.z),
                is_positive_only=True,
            )
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(material.edge_color.w),
                is_positive_only=True,
            )
            # エッジサイズ
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(material.edge_size),
                is_positive_only=True,
            )
            # 通常テクスチャ
            self.write_number(fout, texture_idx_type, material.texture_index)
            # スフィアテクスチャ
            self.write_number(fout, texture_idx_type, material.sphere_texture_index)
            # スフィアモード
            self.write_byte(fout, material.sphere_mode)
            # 共有Toonフラグ
            self.write_byte(fout, material.toon_sharing_flg)
            if material.toon_sharing_flg == ToonSharing.INDIVIDUAL.value:
                # 個別Toonテクスチャ
                self.write_number(fout, texture_idx_type, material.toon_texture_index)
            else:
                # 共有Toonテクスチャ[0～9]
                self.write_byte(fout, material.toon_texture_index)
            # コメント
            self.write_text(fout, material.comment, "")
            # 材質に対応する面(頂点)数
            self.write_number(fout, PmxBinaryType.INT, material.vertices_count)

        logger.debug("-- 材質データ出力終了({c})", c=len(self.model.materials))

    def write_bones(
        self,
        fout: BufferedWriter,
        bone_idx_type: PmxBinaryType,
        target_bones: list[Bone],
    ):
        """
        ボーン出力

        Parameters
        ----------
        model : PmxModel
        fout : BufferedWriter
        bone_idx_type : str

        Returns
        -------
        PmxModel
        """
        # ボーンの数(マイナスは常に出力しない)
        self.write_number(
            fout, PmxBinaryType.INT, len(target_bones), is_positive_only=True
        )

        for bidx, bone in enumerate(target_bones):
            logger.count(
                "ボーンデータ出力",
                index=bone.index,
                total_index_count=len(target_bones),
                display_block=100,
            )

            # ボーン名
            self.write_text(fout, bone.name, f"Bone {bidx}")
            self.write_text(fout, bone.english_name, f"Bone {bidx}")
            # position
            self.write_number(fout, PmxBinaryType.FLOAT, float(bone.position.x))
            self.write_number(fout, PmxBinaryType.FLOAT, float(bone.position.y))
            self.write_number(fout, PmxBinaryType.FLOAT, float(bone.position.z))
            # 親ボーンのボーンIndex
            self.write_number(fout, bone_idx_type, bone.parent_index)
            # 変形階層
            self.write_number(
                fout, PmxBinaryType.INT, bone.layer, is_positive_only=True
            )
            # ボーンフラグ(システムフラグを除く)
            fout.write(
                struct.pack(
                    PmxBinaryType.SHORT.value, (bone.bone_flg & ~BoneFlg.NOTHING).value
                )
            )

            if bone.is_tail_bone:
                # 接続先ボーンのボーンIndex
                self.write_number(fout, bone_idx_type, bone.tail_index)
            else:
                # 接続先位置
                self.write_number(
                    fout, PmxBinaryType.FLOAT, float(bone.tail_position.x)
                )
                self.write_number(
                    fout, PmxBinaryType.FLOAT, float(bone.tail_position.y)
                )
                self.write_number(
                    fout, PmxBinaryType.FLOAT, float(bone.tail_position.z)
                )

            if bone.is_external_translation or bone.is_external_rotation:
                # 付与親指定ありの場合
                self.write_number(fout, bone_idx_type, bone.effect_index)
                self.write_number(fout, PmxBinaryType.FLOAT, bone.effect_factor)

            if bone.has_fixed_axis:
                # 軸制限先
                self.write_number(fout, PmxBinaryType.FLOAT, float(bone.fixed_axis.x))
                self.write_number(fout, PmxBinaryType.FLOAT, float(bone.fixed_axis.y))
                self.write_number(fout, PmxBinaryType.FLOAT, float(bone.fixed_axis.z))

            if bone.has_local_coordinate:
                # ローカルX
                self.write_number(
                    fout, PmxBinaryType.FLOAT, float(bone.local_x_vector.x)
                )
                self.write_number(
                    fout, PmxBinaryType.FLOAT, float(bone.local_x_vector.y)
                )
                self.write_number(
                    fout, PmxBinaryType.FLOAT, float(bone.local_x_vector.z)
                )
                # ローカルZ
                self.write_number(
                    fout, PmxBinaryType.FLOAT, float(bone.local_z_vector.x)
                )
                self.write_number(
                    fout, PmxBinaryType.FLOAT, float(bone.local_z_vector.y)
                )
                self.write_number(
                    fout, PmxBinaryType.FLOAT, float(bone.local_z_vector.z)
                )

            if bone.is_external_parent_deform:
                self.write_number(fout, PmxBinaryType.INT, bone.external_key)

            if bone.is_ik:
                # IKボーン
                # n  : ボーンIndexサイズ  | IKターゲットボーンのボーンIndex
                self.write_number(fout, bone_idx_type, bone.ik.bone_index)
                # 4  : int  	| IKループ回数
                self.write_number(fout, PmxBinaryType.INT, bone.ik.loop_count)
                # 4  : float	| IKループ計算時の1回あたりの制限角度 -> ラジアン角
                self.write_number(
                    fout, PmxBinaryType.FLOAT, bone.ik.unit_rotation.radians.x
                )
                # 4  : int  	| IKリンク数 : 後続の要素数
                self.write_number(fout, PmxBinaryType.INT, len(bone.ik.links))

                for link in bone.ik.links:
                    # n  : ボーンIndexサイズ  | リンクボーンのボーンIndex
                    self.write_number(fout, bone_idx_type, link.bone_index)
                    # 1  : byte	| 角度制限 0:OFF 1:ON
                    self.write_byte(fout, int(link.angle_limit))

                    if link.angle_limit:
                        self.write_number(
                            fout,
                            PmxBinaryType.FLOAT,
                            float(link.min_angle_limit.radians.x),
                        )
                        self.write_number(
                            fout,
                            PmxBinaryType.FLOAT,
                            float(link.min_angle_limit.radians.y),
                        )
                        self.write_number(
                            fout,
                            PmxBinaryType.FLOAT,
                            float(link.min_angle_limit.radians.z),
                        )

                        self.write_number(
                            fout,
                            PmxBinaryType.FLOAT,
                            float(link.max_angle_limit.radians.x),
                        )
                        self.write_number(
                            fout,
                            PmxBinaryType.FLOAT,
                            float(link.max_angle_limit.radians.y),
                        )
                        self.write_number(
                            fout,
                            PmxBinaryType.FLOAT,
                            float(link.max_angle_limit.radians.z),
                        )

        logger.debug("-- ボーンデータ出力終了({c})", c=len(self.model.bones))

    def write_morphs(
        self,
        fout: BufferedWriter,
        vertex_idx_type: PmxBinaryType,
        bone_idx_type: PmxBinaryType,
        material_idx_type: PmxBinaryType,
        morph_idx_type: PmxBinaryType,
    ):
        """
        モーフ出力

        Parameters
        ----------
        model : PmxModel
        fout : BufferedWriter
        vertex_idx_type : str
        bone_idx_type : str
        material_idx_type : str
        morph_idx_type : str

        Returns
        -------
        PmxModel
        """
        # モーフの数
        target_morphs = (
            self.model.morphs.data.values()
            if self.include_system
            else self.model.morphs.writable()
        )
        self.write_number(
            fout, PmxBinaryType.INT, len(target_morphs), is_positive_only=True
        )

        for midx, morph in enumerate(target_morphs):
            # モーフ名
            self.write_text(fout, morph.name, f"Morph {midx}")
            self.write_text(fout, morph.english_name, f"Morph {midx}")
            # 操作パネル (PMD:カテゴリ) 1:眉(左下) 2:目(左上) 3:口(右上) 4:その他(右下)  | 0:システム予約
            self.write_byte(fout, morph.panel.value)
            # モーフ種類 - 0:グループ, 1:頂点, 2:ボーン, 3:UV, 4:追加UV1, 5:追加UV2, 6:追加UV3, 7:追加UV4, 8:材質
            self.write_byte(fout, morph.morph_type.value)
            # モーフのオフセット数 : 後続の要素数
            self.write_number(fout, PmxBinaryType.INT, len(morph.offsets))

            for offset in morph.offsets:
                if type(offset) is VertexMorphOffset:
                    # 頂点モーフ
                    self.write_number(fout, vertex_idx_type, offset.vertex_index)
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.position.x)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.position.y)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.position.z)
                    )
                elif type(offset) is UvMorphOffset:
                    # UVモーフ
                    self.write_number(fout, vertex_idx_type, offset.vertex_index)
                    self.write_number(fout, PmxBinaryType.FLOAT, float(offset.uv.x))
                    self.write_number(fout, PmxBinaryType.FLOAT, float(offset.uv.y))
                    self.write_number(fout, PmxBinaryType.FLOAT, float(offset.uv.z))
                    self.write_number(fout, PmxBinaryType.FLOAT, float(offset.uv.w))
                elif type(offset) is BoneMorphOffset:
                    # ボーンモーフ
                    self.write_number(fout, bone_idx_type, offset.bone_index)
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.position.x)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.position.y)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.position.z)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.rotation.qq.x)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.rotation.qq.y)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.rotation.qq.z)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.rotation.qq.scalar)
                    )
                elif type(offset) is MaterialMorphOffset:
                    # 材質モーフ
                    self.write_number(fout, material_idx_type, offset.material_index)
                    self.write_byte(fout, offset.calc_mode.value)
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.diffuse.x)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.diffuse.y)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.diffuse.z)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.diffuse.w)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.specular.x)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.specular.y)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.specular.z)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.specular_factor)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.ambient.x)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.ambient.y)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.ambient.z)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.edge_color.x)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.edge_color.y)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.edge_color.z)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.edge_color.w)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.edge_size)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.texture_factor.x)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.texture_factor.y)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.texture_factor.z)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.texture_factor.w)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.sphere_texture_factor.x)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.sphere_texture_factor.y)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.sphere_texture_factor.z)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.sphere_texture_factor.w)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.toon_texture_factor.x)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.toon_texture_factor.y)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.toon_texture_factor.z)
                    )
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.toon_texture_factor.w)
                    )
                elif type(offset) is GroupMorphOffset:
                    # グループモーフ
                    self.write_number(fout, morph_idx_type, offset.morph_index)
                    self.write_number(
                        fout, PmxBinaryType.FLOAT, float(offset.morph_factor)
                    )

        logger.debug("-- モーフデータ出力終了({c})", c=len(self.model.morphs))

    def write_display_slots(
        self,
        fout: BufferedWriter,
        bone_idx_type: PmxBinaryType,
        morph_idx_type: PmxBinaryType,
    ):
        """
        表示枠出力

        Parameters
        ----------
        model : PmxModel
        fout : BufferedWriter
        bone_idx_type : str
        morph_idx_type : str

        Returns
        -------
        PmxModel
        """

        # 表示枠の数
        self.write_number(
            fout,
            PmxBinaryType.INT,
            len(self.model.display_slots),
            is_positive_only=True,
        )

        target_display_slots = (
            self.model.display_slots.data.values()
            if self.include_system
            else self.model.display_slots.writable()
        )

        for didx, display_slot in enumerate(target_display_slots):
            # 表示枠名
            self.write_text(fout, display_slot.name, f"Display {didx}")
            self.write_text(fout, display_slot.english_name, f"Display {didx}")
            # 特殊枠フラグ - 0:通常枠 1:特殊枠
            self.write_byte(fout, display_slot.special_flg.value)
            # 枠内要素数
            self.write_number(fout, PmxBinaryType.INT, len(display_slot.references))
            # ボーンの場合
            for reference in display_slot.references:
                # 要素対象 0:ボーン 1:モーフ
                self.write_byte(fout, reference.display_type.value)
                if 0 == reference.display_type:
                    # ボーンIndex
                    self.write_number(fout, bone_idx_type, reference.display_index)
                else:
                    # モーフIndex
                    self.write_number(fout, morph_idx_type, reference.display_index)

        logger.debug("-- 表示枠データ出力終了({c})", c=len(self.model.display_slots))

    def write_rigidbodies(self, fout: BufferedWriter, bone_idx_type: PmxBinaryType):
        """
        剛体出力

        Parameters
        ----------
        model : PmxModel
        fout : BufferedWriter
        bone_idx_type : str

        Returns
        -------
        PmxModel
        """

        # 剛体の数
        self.write_number(fout, PmxBinaryType.INT, len(list(self.model.rigidbodies)))

        for ridx, rigidbody in enumerate(self.model.rigidbodies):
            # 剛体名
            self.write_text(fout, rigidbody.name, f"Rigidbody {ridx}")
            self.write_text(fout, rigidbody.english_name, f"Rigidbody {ridx}")
            # ボーンIndex
            self.write_number(fout, bone_idx_type, rigidbody.bone_index)
            # 1  : byte	| グループ
            self.write_byte(fout, rigidbody.collision_group)
            # 2  : ushort	| 非衝突グループフラグ
            fout.write(
                struct.pack(
                    PmxBinaryType.UNSIGNED_SHORT, rigidbody.no_collision_group.value
                )
            )
            # 1  : byte	| 形状 - 0:球 1:箱 2:カプセル
            self.write_byte(fout, rigidbody.shape_type)
            # 12 : float3	| サイズ(x,y,z)
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(rigidbody.shape_size.x),
                is_positive_only=True,
            )
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(rigidbody.shape_size.y),
                is_positive_only=True,
            )
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(rigidbody.shape_size.z),
                is_positive_only=True,
            )
            # 12 : float3	| 位置(x,y,z)
            self.write_number(
                fout, PmxBinaryType.FLOAT, float(rigidbody.shape_position.x)
            )
            self.write_number(
                fout, PmxBinaryType.FLOAT, float(rigidbody.shape_position.y)
            )
            self.write_number(
                fout, PmxBinaryType.FLOAT, float(rigidbody.shape_position.z)
            )
            # 12 : float3	| 回転(x,y,z)
            self.write_number(
                fout, PmxBinaryType.FLOAT, float(rigidbody.shape_rotation.radians.x)
            )
            self.write_number(
                fout, PmxBinaryType.FLOAT, float(rigidbody.shape_rotation.radians.y)
            )
            self.write_number(
                fout, PmxBinaryType.FLOAT, float(rigidbody.shape_rotation.radians.z)
            )
            # 4  : float	| 質量
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(rigidbody.param.mass),
                is_positive_only=True,
            )
            # 4  : float	| 移動減衰
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(rigidbody.param.linear_damping),
                is_positive_only=True,
            )
            # 4  : float	| 回転減衰
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(rigidbody.param.angular_damping),
                is_positive_only=True,
            )
            # 4  : float	| 反発力
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(rigidbody.param.restitution),
                is_positive_only=True,
            )
            # 4  : float	| 摩擦力
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(rigidbody.param.friction),
                is_positive_only=True,
            )
            # 1  : byte	| 剛体の物理演算 - 0:ボーン追従(static) 1:物理演算(dynamic) 2:物理演算 + Bone位置合わせ
            self.write_byte(fout, rigidbody.mode)

        logger.debug("-- 剛体データ出力終了({c})", c=len(self.model.rigidbodies))

    def write_joints(self, fout: BufferedWriter, rigidbody_idx_type: PmxBinaryType):
        """
        ジョイント出力

        Parameters
        ----------
        model : PmxModel
        fout : BufferedWriter
        rigidbody_idx_type : str

        Returns
        -------
        PmxModel
        """

        # ジョイントの数
        self.write_number(fout, PmxBinaryType.INT, len(list(self.model.joints)))

        for jidx, joint in enumerate(self.model.joints):
            # ジョイント名
            self.write_text(fout, joint.name, f"Joint {jidx}")
            self.write_text(fout, joint.english_name, f"Joint {jidx}")
            # 1  : byte	| Joint種類 - 0:スプリング6DOF   | PMX2.0では 0 のみ(拡張用)
            self.write_byte(fout, joint.joint_type)
            # n  : 剛体Indexサイズ  | 関連剛体AのIndex - 関連なしの場合は-1
            self.write_number(fout, rigidbody_idx_type, joint.rigidbody_index_a)
            # n  : 剛体Indexサイズ  | 関連剛体BのIndex - 関連なしの場合は-1
            self.write_number(fout, rigidbody_idx_type, joint.rigidbody_index_b)
            # 12 : float3	| 位置(x,y,z)
            self.write_number(fout, PmxBinaryType.FLOAT, float(joint.position.x))
            self.write_number(fout, PmxBinaryType.FLOAT, float(joint.position.y))
            self.write_number(fout, PmxBinaryType.FLOAT, float(joint.position.z))
            # 12 : float3	| 回転(x,y,z) -> ラジアン角
            self.write_number(
                fout, PmxBinaryType.FLOAT, float(joint.rotation.radians.x)
            )
            self.write_number(
                fout, PmxBinaryType.FLOAT, float(joint.rotation.radians.y)
            )
            self.write_number(
                fout, PmxBinaryType.FLOAT, float(joint.rotation.radians.z)
            )
            # 12 : float3	| 移動制限-下限(x,y,z)
            self.write_number(
                fout, PmxBinaryType.FLOAT, float(joint.param.translation_limit_min.x)
            )
            self.write_number(
                fout, PmxBinaryType.FLOAT, float(joint.param.translation_limit_min.y)
            )
            self.write_number(
                fout, PmxBinaryType.FLOAT, float(joint.param.translation_limit_min.z)
            )
            # 12 : float3	| 移動制限-上限(x,y,z)
            self.write_number(
                fout, PmxBinaryType.FLOAT, float(joint.param.translation_limit_max.x)
            )
            self.write_number(
                fout, PmxBinaryType.FLOAT, float(joint.param.translation_limit_max.y)
            )
            self.write_number(
                fout, PmxBinaryType.FLOAT, float(joint.param.translation_limit_max.z)
            )
            # 12 : float3	| 回転制限-下限(x,y,z) -> ラジアン角
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(joint.param.rotation_limit_min.radians.x),
            )
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(joint.param.rotation_limit_min.radians.y),
            )
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(joint.param.rotation_limit_min.radians.z),
            )
            # 12 : float3	| 回転制限-上限(x,y,z) -> ラジアン角
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(joint.param.rotation_limit_max.radians.x),
            )
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(joint.param.rotation_limit_max.radians.y),
            )
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(joint.param.rotation_limit_max.radians.z),
            )
            # 12 : float3	| バネ定数-移動(x,y,z)
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(joint.param.spring_constant_translation.x),
            )
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(joint.param.spring_constant_translation.y),
            )
            self.write_number(
                fout,
                PmxBinaryType.FLOAT,
                float(joint.param.spring_constant_translation.z),
            )
            # 12 : float3	| バネ定数-回転(x,y,z)
            self.write_number(
                fout, PmxBinaryType.FLOAT, float(joint.param.spring_constant_rotation.x)
            )
            self.write_number(
                fout, PmxBinaryType.FLOAT, float(joint.param.spring_constant_rotation.y)
            )
            self.write_number(
                fout, PmxBinaryType.FLOAT, float(joint.param.spring_constant_rotation.z)
            )

        logger.debug("-- ジョイントデータ出力終了({c})", c=len(self.model.joints))

    def define_write_index(
        self, size: int, is_vertex: bool
    ) -> Tuple[int, PmxBinaryType]:
        """
        個数による書き込みサイズの判定

        Parameters
        ----------
        size : int
            該当要素の個数
        is_vertex : bool
            頂点であるか否か

        Returns
        -------
        tuple[int, PmxBinaryType]
            実際に書き込むサイズとバイナリタイプ
        """

        if is_vertex:
            if 256 > size:
                return 1, PmxBinaryType.UNSIGNED_BYTE
            elif 256 <= size <= 65535:
                return 2, PmxBinaryType.UNSIGNED_SHORT
        else:
            if 128 > size:
                return 1, PmxBinaryType.BYTE
            elif 128 <= size <= 32767:
                return 2, PmxBinaryType.SHORT

        return 4, PmxBinaryType.INT

    def write_text(
        self,
        fout: BufferedWriter,
        text: str,
        default_text: str,
        type: PmxBinaryType = PmxBinaryType.INT,
    ):
        """
        文字列出力

        Parameters
        ----------
        fout : BufferedWriter
        text : str
            出力文字列
        default_text : str
            出力文字列が書き込めなかった場合のデフォルト文字列
        type : PmxBinaryType, optional
            バイナリサイズ, by default PmxBinaryType.INT
        """
        try:
            btxt = text.encode("utf-16-le")
        except Exception:
            btxt = default_text.encode("utf-16-le")
        fout.write(struct.pack(type.value, len(btxt)))
        fout.write(btxt)

    def write_number(
        self,
        fout: BufferedWriter,
        val_type: PmxBinaryType,
        val: float,
        default_value: float = 0.0,
        is_positive_only: bool = False,
    ):
        """
        数値出力

        Parameters
        ----------
        fout : BufferedWriter
        val_type : PmxBinaryType
        val : float
            出力数字
        is_positive_only : bool, optional
            正の数値しか出力しないか, by default False
        """
        try:
            if val is None or isnan(val) or isinf(val):
                # 正常な値を強制設定
                val = 0
            val = max(0, val) if is_positive_only else val

            # INT型の場合、INT変換
            if val_type == PmxBinaryType.FLOAT:
                fout.write(struct.pack(val_type.value, float(val)))
            else:
                fout.write(struct.pack(val_type.value, int(val)))
        except Exception as e:
            logger.error("val_type in [float]: %s", val_type in [PmxBinaryType.FLOAT])
            logger.error(
                "self.write_number失敗: type: %s, val: %s",
                e,
                val_type,
                val,
            )
            try:
                if val_type == PmxBinaryType.FLOAT:
                    fout.write(struct.pack(val_type.value, float(default_value)))
                else:
                    fout.write(struct.pack(val_type.value, int(default_value)))
            finally:
                pass

    def write_byte(
        self, fout: BufferedWriter, val: int, is_unsigned: bool = False
    ) -> None:
        """
        バイト文字の出力

        Parameters
        ----------
        fout : BufferedWriter
        val : int
        is_unsigned : bool, optional
            True の場合、符号なしBYTEで出力
        """
        if is_unsigned:
            fout.write(struct.pack(PmxBinaryType.UNSIGNED_BYTE.value, int(val)))
        else:
            fout.write(struct.pack(PmxBinaryType.BYTE.value, int(val)))
