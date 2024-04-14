import os
from abc import ABC, abstractmethod
from enum import Flag, IntEnum, unique
from typing import Any, Optional, Union

import numpy as np
import OpenGL.GL as gl
from PIL import Image, ImageOps

from mlib.core.base import BaseModel
from mlib.core.exception import MViewerException
from mlib.core.math import MMatrix4x4, MQuaternion, MVector2D, MVector3D, MVector4D
from mlib.core.part import BaseIndexModel, BaseIndexNameModel, BaseRotationModel, Switch
from mlib.pmx.bone_setting import STANDARD_BONE_NAMES, BoneFlg


@unique
class DeformType(IntEnum):
    """ウェイト変形方式"""

    BDEF1 = 0
    """0:BDEF1"""
    BDEF2 = 1
    """1:BDEF2"""
    BDEF4 = 2
    """2:BDEF4"""
    SDEF = 3
    """3:SDEF"""


class Deform(BaseModel, ABC):
    """
    デフォーム基底クラス

    Parameters
    ----------
    indexes : list[int]
        ボーンINDEXリスト
    weights : list[float]
        ウェイトリスト
    count : int
        デフォームボーン個数
    """

    __slots__ = (
        "indexes",
        "weights",
        "count",
    )

    def __init__(self, indexes: list[int], weights: list[float], count: int):
        super().__init__()
        self.indexes = np.array(indexes, dtype=np.int64)
        self.weights = np.array(weights, dtype=np.float32)
        self.count: int = count

    def get_indexes(self, weight_threshold: float = 0) -> np.ndarray:
        """
        デフォームボーンINDEXリスト取得

        Parameters
        ----------
        weight_threshold : float, optional
            ウェイト閾値, by default 0
            指定された場合、このweight以上のウェイトを持っているINDEXのみを取得する

        Returns
        -------
        np.ndarray
            デフォームボーンINDEXリスト
        """
        return self.indexes[self.weights >= weight_threshold]

    def get_weights(self, weight_threshold: float = 0) -> np.ndarray:
        """
        デフォームウェイトリスト取得

        Parameters
        ----------
        weight_threshold : float, optional
            ウェイト閾値, by default 0
            指定された場合、このweight以上のウェイトを持っているウェイトのみを取得する

        Returns
        -------
        np.ndarray
            デフォームウェイトリスト
        """
        return self.weights[self.weights >= weight_threshold]

    def normalize(self, align=False) -> None:
        """
        ウェイト正規化

        Parameters
        ----------
        align : bool, optional
            countのボーン数に揃えるか, by default False
        """
        if align:
            # ウェイトを統合する
            index_weights: dict[int, float] = {}
            for n in range(len(self.indexes)):
                if self.indexes[n] not in index_weights:
                    index_weights[self.indexes[n]] = 0.0
                index_weights[self.indexes[n]] += self.weights[n]

            # 揃える必要がある場合
            # 数が足りるよう、かさ増しする
            ilist = np.array(list(index_weights.keys()) + [0, 0, 0, 0], dtype=np.int64)
            wlist = np.array(
                list(index_weights.values()) + [0, 0, 0, 0], dtype=np.float32
            )
            # 正規化
            wlist /= wlist.sum(axis=0, keepdims=True)

            # ウェイトの大きい順に指定個数までを対象とする
            self.indexes = ilist[np.argsort(-wlist)][: self.count]
            self.weights = wlist[np.argsort(-wlist)][: self.count]

        # ウェイト正規化
        self.weights /= self.weights.sum(axis=0, keepdims=True)

    def normalized_deform(self) -> list[float]:
        """
        ウェイト正規化して4つのボーンINDEXとウェイトを返す（合計8個）
        """
        # 揃える必要がある場合
        # ウェイトを統合する
        index_weights: dict[int, float] = {}
        for n in range(len(self.indexes)):
            if self.indexes[n] not in index_weights:
                index_weights[self.indexes[n]] = 0.0
            index_weights[self.indexes[n]] += self.weights[n]

        # 揃える必要がある場合
        # 数が足りるよう、かさ増しする
        ilist = np.array(list(index_weights.keys()) + [0, 0, 0, 0], dtype=np.float32)
        wlist = np.array(list(index_weights.values()) + [0, 0, 0, 0], dtype=np.float32)
        # 正規化
        wlist /= wlist.sum(axis=0, keepdims=True)

        # ウェイトの大きい順に指定個数までを対象とする
        indexes = ilist[np.argsort(-wlist)][:4]
        weights = wlist[np.argsort(-wlist)][:4]

        # ウェイト正規化
        weights /= weights.sum(axis=0, keepdims=True)

        normalized_deform = []
        normalized_deform.extend(indexes.tolist())
        normalized_deform.extend(weights.tolist())

        return normalized_deform

    @abstractmethod
    def type(self) -> int:
        """
        デフォームタイプ
        """
        return -1


class Bdef1(Deform):
    def __init__(self, index0: int):
        super().__init__([index0], [1.0], 1)

    def type(self) -> int:
        return 0


class Bdef2(Deform):
    def __init__(self, index0: int, index1: int, weight0: float):
        super().__init__([index0, index1], [weight0, 1 - weight0], 2)

    def type(self) -> int:
        return 1


class Bdef4(Deform):
    def __init__(
        self,
        index0: int,
        index1: int,
        index2: int,
        index3: int,
        weight0: float,
        weight1: float,
        weight2: float,
        weight3: float,
    ):
        super().__init__(
            [index0, index1, index2, index3], [weight0, weight1, weight2, weight3], 4
        )

    def type(self) -> int:
        return 2


class Sdef(Deform):
    __slots__ = (
        "indexes",
        "weights",
        "count",
        "sdef_c",
        "sdef_r0",
        "sdef_r1",
    )

    def __init__(
        self,
        index0: int,
        index1: int,
        weight0: float,
        sdef_c_x: float,
        sdef_c_y: float,
        sdef_c_z: float,
        sdef_r0_x: float,
        sdef_r0_y: float,
        sdef_r0_z: float,
        sdef_r1_x: float,
        sdef_r1_y: float,
        sdef_r1_z: float,
    ):
        super().__init__([index0, index1], [weight0, 1 - weight0], 2)
        self.sdef_c = MVector3D(sdef_c_x, sdef_c_y, sdef_c_z)
        self.sdef_r0 = MVector3D(sdef_r0_x, sdef_r0_y, sdef_r0_z)
        self.sdef_r1 = MVector3D(sdef_r1_x, sdef_r1_y, sdef_r1_z)

    def type(self) -> int:
        return 3


class Vertex(BaseIndexModel):
    """
    頂点

    Parameters
    ----------
    position : MVector3D, optional
        頂点位置, by default MVector3D()
    normal : MVector3D, optional
        頂点法線, by default MVector3D()
    uv : MVector2D, optional
        UV, by default MVector2D()
    extended_uvs : list[MVector4D], optional
        追加UV, by default []
    deform_type: DeformType, optional
        ウェイト変形方式 0:BDEF1 1:BDEF2 2:BDEF4 3:SDEF, by default DeformType.BDEF1
    deform : Deform, optional
        デフォーム, by default Deform([], [], 0)
    edge_factor : float, optional
        エッジ倍率, by default 0
    """

    __slots__ = (
        "index",
        "position",
        "normal",
        "uv",
        "extended_uvs",
        "deform_type",
        "deform",
        "edge_factor",
    )

    def __init__(
        self,
        index: int = -1,
    ):
        super().__init__(index=index)
        self.position = MVector3D()
        self.normal = MVector3D()
        self.uv = MVector2D()
        self.extended_uvs: list[MVector4D] = []
        self.deform_type = DeformType.BDEF1
        self.deform: Union[Bdef1, Bdef2, Bdef4, Sdef] = Bdef1(-1)
        self.edge_factor = 0.0


class Face(BaseIndexModel):
    """
    面データ

    Parameters
    ----------
    vertex_index0 : int
        頂点0
    vertex_index1 : int
        頂点1
    vertex_index2 : int
        頂点2
    """

    __slots__ = (
        "index",
        "vertices",
    )

    def __init__(
        self,
        index: int = -1,
        vertex_index0: int = -1,
        vertex_index1: int = -1,
        vertex_index2: int = -1,
    ):
        super().__init__(index=index)
        self.vertices = [vertex_index0, vertex_index1, vertex_index2]


@unique
class TextureType(IntEnum):
    TEXTURE = 0
    TOON = 1
    SPHERE = 2


class Texture(BaseIndexNameModel):
    """
    テクスチャ
        for_draw: 描画初期化済みであるか否か
        image: テクスチャイメージ
        texture_type: TextureType
        texture_id: GL生成テクスチャバッファID
        texture_idx: TextureTypeごとのテクスチャ展開先番号
        valid: テクスチャパスが有効であるか否か
    """

    __slots__ = (
        "index",
        "name",
        "for_draw",
        "for_sub_draw",
        "image",
        "texture_type",
        "texture_id",
        "texture_idx",
        "valid",
        "path",
    )

    def __init__(self, index: int = -1, name: str = ""):
        super().__init__(index=index, name=name)
        self.for_draw = False
        self.for_sub_draw = False
        self.image = None
        self.texture_id: Optional[Any] = None
        self.sub_texture_id: Optional[Any] = None
        self.texture_type: Optional[TextureType] = None
        self.texture_idx = None
        self.valid = True
        self.path = ""

    def delete_draw(self) -> None:
        if self.texture_id is not None:
            try:
                gl.glDeleteTextures(1, [self.texture_id])
            except Exception as e:
                raise MViewerException(
                    f"IBO glDeleteBuffers Failure\n{self.texture_id}", e
                )

            error_code = gl.glGetError()
            if error_code != gl.GL_NO_ERROR:
                raise MViewerException(
                    f"glDeleteTextures Failure\n{self.name}: {error_code}"
                )

        if self.sub_texture_id is not None:
            try:
                gl.glDeleteTextures(1, [self.sub_texture_id])
            except Exception as e:
                raise MViewerException(
                    f"IBO glDeleteBuffers Failure\n{self.sub_texture_id}", e
                )

            error_code = gl.glGetError()
            if error_code != gl.GL_NO_ERROR:
                raise MViewerException(
                    f"glDeleteTextures Failure\n{self.name}: {error_code}"
                )

        self.texture_id = None
        self.for_draw = False
        self.sub_texture_id = None
        self.for_sub_draw = False

    def init_draw(
        self,
        model_path: str,
        texture_type: TextureType,
        is_individual: bool = True,
        is_sub: bool = False,
    ) -> None:
        if (not is_sub and self.for_draw) or (is_sub and self.for_sub_draw):
            # 既にフラグが立ってたら描画初期化済み
            return

        # global texture
        if is_individual:
            tex_path = os.path.abspath(
                os.path.join(os.path.dirname(model_path), self.name)
            )
        else:
            tex_path = self.name

        # テクスチャがちゃんとある場合のみ初期化処理実施
        self.valid = os.path.exists(tex_path) & os.path.isfile(tex_path)
        if self.valid:
            self.path = tex_path
            try:
                self.image = Image.open(tex_path).convert("RGBA")
                self.image = ImageOps.flip(self.image)
            except Exception:
                self.valid = False

            if self.valid:
                self.texture_type = texture_type

                if is_sub:
                    # テクスチャオブジェクト生成
                    try:
                        self.sub_texture_id = gl.glGenTextures(1)
                    except Exception as e:
                        raise MViewerException(f"glGenTextures Failure\n{self.name}", e)

                    error_code = gl.glGetError()
                    if error_code != gl.GL_NO_ERROR:
                        raise MViewerException(
                            f"glGenTextures Failure\n{self.name}: {error_code}"
                        )
                else:
                    # テクスチャオブジェクト生成
                    try:
                        self.texture_id = gl.glGenTextures(1)
                    except Exception as e:
                        raise MViewerException(f"glGenTextures Failure\n{self.name}", e)

                    error_code = gl.glGetError()
                    if error_code != gl.GL_NO_ERROR:
                        raise MViewerException(
                            f"glGenTextures Failure\n{self.name}: {error_code}"
                        )

                self.texture_idx = (
                    gl.GL_TEXTURE0
                    if texture_type == TextureType.TEXTURE
                    else gl.GL_TEXTURE1
                    if texture_type == TextureType.TOON
                    else gl.GL_TEXTURE2
                )
                self.set_texture(is_sub)

        # 描画初期化
        self.for_draw = True

    def set_texture(self, is_sub: bool) -> None:
        if self.image:
            self.bind(is_sub)

            try:
                gl.glTexImage2D(
                    gl.GL_TEXTURE_2D,
                    0,
                    gl.GL_RGBA,
                    self.image.size[0],
                    self.image.size[1],
                    0,
                    gl.GL_RGBA,
                    gl.GL_UNSIGNED_BYTE,
                    self.image.tobytes(),
                )
            except Exception as e:
                raise MViewerException(f"Texture set_texture Failure\n{self.name}", e)

            error_code = gl.glGetError()
            if error_code != gl.GL_NO_ERROR:
                raise MViewerException(
                    f"Texture set_texture Failure\n{self.name}: {error_code}"
                )

            self.unbind()

    def bind(self, is_sub: bool) -> None:
        gl.glActiveTexture(self.texture_idx)
        if is_sub:
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.sub_texture_id)
        else:
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)

        if self.texture_type == TextureType.TOON:
            gl.glTexParameteri(
                gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE
            )
            gl.glTexParameteri(
                gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE
            )

        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAX_LEVEL, 0)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)

    def unbind(self) -> None:
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)


@unique
class SphereMode(IntEnum):
    """スフィアモード"""

    INVALID = 0
    """0:無効"""
    MULTIPLICATION = 1
    """1:乗算(sph)"""
    ADDITION = 2
    """2:加算(spa)"""
    SUBTEXTURE = 3
    """3:サブテクスチャ(追加UV1のx,yをUV参照して通常テクスチャ描画を行う)"""


@unique
class DrawFlg(Flag):
    """描画フラグ"""

    NONE = 0x0000
    """"初期値"""
    DOUBLE_SIDED_DRAWING = 0x0001
    """0x01:両面描画"""
    GROUND_SHADOW = 0x0002
    """0x02:地面影"""
    DRAWING_ON_SELF_SHADOW_MAPS = 0x0004
    """0x04:セルフシャドウマップへの描画"""
    DRAWING_SELF_SHADOWS = 0x0008
    """0x08:セルフシャドウの描画"""
    DRAWING_EDGE = 0x0010
    """0x10:エッジ描画"""


@unique
class ToonSharing(IntEnum):
    """スフィアモード"""

    INDIVIDUAL = 0
    """0:継続値は個別Toon"""
    SHARING = 1
    """1:継続値は共有Toon"""


class Material(BaseIndexNameModel):
    """
    材質

    Parameters
    ----------
    name : str, optional
        材質名, by default ""
    english_name : str, optional
        材質名英, by default ""
    diffuse_color : MVector4D, optional
        Diffuse (R,G,B,A)(拡散色＋非透過度), by default MVector4D()
    specular_color : MVector3D, optional
        Specular (R,G,B)(反射色), by default MVector3D()
    specular_factor : float, optional
        Specular係数(反射強度), by default 0
    ambient_color : MVector3D, optional
        Ambient (R,G,B)(環境色), by default MVector3D()
    draw_flg : DrawFlg, optional
        描画フラグ(8bit) - 各bit 0:OFF 1:ON
        0x01:両面描画, 0x02:地面影, 0x04:セルフシャドウマップへの描画, 0x08:セルフシャドウの描画, 0x10:エッジ描画, by default DrawFlg.NONE
    edge_color : MVector4D, optional
        エッジ色 (R,G,B,A), by default MVector4D()
    edge_size : float, optional
        エッジサイズ, by default 0
    texture_index : int, optional
        通常テクスチャINDEX, by default -1
    sphere_texture_index : int, optional
        スフィアテクスチャINDEX, by default -1
    sphere_mode : SphereMode, optional
        スフィアモード 0:無効 1:乗算(sph) 2:加算(spa) 3:サブテクスチャ(追加UV1のx,yをUV参照して通常テクスチャ描画を行う), by default INVALID
    toon_sharing_flg : Switch, optional
        共有Toonフラグ 0:継続値は個別Toon 1:継続値は共有Toon, by default OFF
    toon_texture_index : int, optional
        ToonテクスチャINDEX, by default -1
    comment : str, optional
        メモ, by default ""
    vertices_count : int, optional
        材質に対応する面(頂点)数 (必ず3の倍数になる), by default 0
    """

    __slots__ = (
        "index",
        "name",
        "english_name",
        "diffuse",
        "specular",
        "specular_factor",
        "ambient",
        "draw_flg",
        "edge_color",
        "edge_size",
        "texture_index",
        "sphere_texture_index",
        "sphere_mode",
        "toon_sharing_flg",
        "toon_texture_index",
        "comment",
        "vertices_count",
    )

    def __init__(
        self,
        index: int = -1,
        name: str = "",
        english_name: str = "",
    ):
        super().__init__(index=index, name=name, english_name=english_name)
        self.diffuse = MVector4D()
        self.specular = MVector3D()
        self.specular_factor = 0.0
        self.ambient = MVector3D()
        self.draw_flg = DrawFlg.NONE
        self.edge_color = MVector4D()
        self.edge_size = 0.0
        self.texture_index = -1
        self.sphere_texture_index = -1
        self.sphere_mode = SphereMode.INVALID
        self.toon_sharing_flg = ToonSharing.SHARING
        self.toon_texture_index = -1
        self.comment = ""
        self.vertices_count = 0


class IkLink(BaseModel):
    """
    IKリンク

    Parameters
    ----------
    bone_index : int, optional
        リンクボーンのボーンIndex, by default -1
    angle_limit : bool, optional
        角度制限 0:OFF 1:ON, by default False
    min_angle_limit : MVector3D, optional
        下限 (x,y,z) -> ラジアン角, by default MVector3D()
    max_angle_limit : MVector3D, optional
        上限 (x,y,z) -> ラジアン角, by default MVector3D()
    """

    __slots__ = (
        "bone_index",
        "angle_limit",
        "min_angle_limit",
        "max_angle_limit",
        "local_angle_limit",
        "local_min_angle_limit",
        "local_max_angle_limit",
    )

    def __init__(
        self,
    ) -> None:
        super().__init__()
        self.bone_index = -1
        self.angle_limit = False
        self.min_angle_limit = BaseRotationModel()
        self.max_angle_limit = BaseRotationModel()
        self.local_angle_limit = False
        self.local_min_angle_limit = BaseRotationModel()
        self.local_max_angle_limit = BaseRotationModel()

    def __bool__(self) -> bool:
        return 0 <= self.bone_index


class Ik(BaseModel):
    """
    IK

    Parameters
    ----------
    bone_index : int, optional
        IKターゲットボーンのボーンIndex, by default -1
    loop_count : int, optional
        IKループ回数 (最大255), by default 0
    unit_rotation : float, optional
        IKループ計算時の1回あたりの制限角度 -> ラジアン角, by default 0
        unit_rotation の x に値が入っている
    links : list[IkLink], optional
        IKリンクリスト, by default []
    """

    __slots__ = (
        "bone_index",
        "loop_count",
        "unit_rotation",
        "links",
    )

    def __init__(self) -> None:
        super().__init__()
        self.bone_index = -1
        self.loop_count = 0
        self.unit_rotation = BaseRotationModel()
        self.links: list[IkLink] = []

    def __bool__(self) -> bool:
        return 0 <= self.bone_index


class Bone(BaseIndexNameModel):
    """
    ボーン

    Parameters
    ----------
    name : str, optional
        ボーン名, by default ""
    english_name : str, optional
        ボーン名英, by default ""
    position : MVector3D, optional
        位置, by default MVector3D()
    parent_index : int, optional
        親ボーンのボーンIndex, by default -1
    layer : int, optional
        変形階層, by default 0
    bone_flg : BoneFlg, optional
        ボーンフラグ(16bit) 各bit 0:OFF 1:ON, by default BoneFlg.NONE
    tail_position : MVector3D, optional
        接続先:0 の場合 座標オフセット, ボーン位置からの相対分, by default MVector3D()
    tail_index : int, optional
        接続先:1 の場合 接続先ボーンのボーンIndex, by default -1
    effect_index : int, optional
        回転付与:1 または 移動付与:1 の場合 付与親ボーンのボーンIndex, by default -1
    effect_factor : float, optional
        付与率, by default 0
    fixed_axis : MVector3D, optional
        軸固定:1 の場合 軸の方向ベクトル, by default MVector3D()
    local_x_vector : MVector3D, optional
        ローカル軸:1 の場合 X軸の方向ベクトル, by default MVector3D()
    corrected_local_y_vector
        ローカル軸:1 の場合 Y軸の方向ベクトル, by default MVector3D()
    local_z_vector : MVector3D, optional
        ローカル軸:1 の場合 Z軸の方向ベクトル, by default MVector3D()
    corrected_local_z_vector:
        再計算したZ軸の方向ベクトル
    external_key : int, optional
        外部親変形:1 の場合 Key値, by default -1
    ik : Optional[Ik], optional
        IK:1 の場合 IKデータを格納, by default None
    is_system : bool, optional
        システム計算用追加ボーン, by default False

    local_axis: ローカル軸
    parent_relative_position: 親ボーンからの相対位置
    tail_relative_position: 表示先ボーンの相対位置（表示先がボーンの場合、そのボーンとの差分）

    tree_indexes: ボーンINDEXリスト（自分のINDEXが末端にある）
    parent_revert_matrix: 逆オフセット行列(親ボーンからの相対位置分を戻す)
    offset_matrix: オフセット行列 (自身の位置を原点に戻す行列)

    relative_bone_indexes: 関連ボーンINDEX一覧（付与親とかIKとか）
    child_bone_indexes: 自分を親として登録しているボーンINDEX一覧
    """

    __slots__ = (
        "index",
        "name",
        "english_name",
        "position",
        "parent_index",
        "layer",
        "bone_flg",
        "tail_position",
        "tail_index",
        "effect_index",
        "effect_factor",
        "fixed_axis",
        "local_x_vector",
        "local_z_vector",
        "external_key",
        "ik",
        "display_slot",
        "is_system",
        "corrected_local_y_vector",
        "corrected_local_z_vector",
        "corrected_local_x_vector",
        "local_axis",
        "local_matrix",
        "ik_link_indexes",
        "ik_target_indexes",
        "parent_relative_position",
        "tail_relative_position",
        "corrected_fixed_axis",
        "tree_indexes",
        "parent_revert_matrix",
        "offset_matrix",
        "relative_bone_indexes",
        "child_bone_indexes",
        "effective_target_indexes",
        "angle_limit",
        "min_angle_limit",
        "max_angle_limit",
        "local_angle_limit",
        "local_min_angle_limit",
        "local_max_angle_limit",
    )

    SYSTEM_ROOT_NAME = "SYSTEM_ROOT"

    def __init__(
        self,
        index: int = -1,
        name: str = "",
        english_name: str = "",
    ):
        super().__init__(index=index, name=name, english_name=english_name)
        self.position = MVector3D()
        self.parent_index = -1
        self.layer = 0
        self.bone_flg = BoneFlg.NONE
        self.tail_position = MVector3D()
        self.tail_index = -1
        self.effect_index = -1
        self.effect_factor = 0.0
        self.fixed_axis = MVector3D(1, 0, 0)
        self.local_x_vector = MVector3D(1, 0, 0)
        self.local_z_vector = MVector3D(0, 0, -1)
        self.external_key = -1
        self.ik: Ik = Ik()
        self.display_slot: int = -1
        self.is_system: bool = False
        self.ik_link_indexes: list[int] = []
        self.ik_target_indexes: list[int] = []
        self.effective_target_indexes: list[int] = []
        self.angle_limit = False
        self.min_angle_limit = BaseRotationModel()
        self.max_angle_limit = BaseRotationModel()
        self.local_angle_limit = False
        self.local_min_angle_limit = BaseRotationModel()
        self.local_max_angle_limit = BaseRotationModel()

        self.corrected_local_x_vector = self.local_x_vector.copy()
        self.corrected_local_y_vector = self.local_z_vector.cross(
            self.corrected_local_x_vector
        )
        self.corrected_local_z_vector = self.corrected_local_x_vector.cross(
            self.corrected_local_y_vector
        )
        self.corrected_fixed_axis = self.fixed_axis.copy()

        self.parent_relative_position = MVector3D()
        self.tail_relative_position = MVector3D()
        self.local_axis = MVector3D(1, 0, 0)
        self.local_matrix = MMatrix4x4()

        self.tree_indexes: list[int] = []
        self.offset_matrix = np.eye(4)
        self.parent_revert_matrix = np.eye(4)

        self.relative_bone_indexes: list[int] = []
        self.child_bone_indexes: list[int] = []

    def correct_fixed_axis(self, corrected_fixed_axis: MVector3D):
        self.corrected_fixed_axis = corrected_fixed_axis.normalized()

    def correct_local_vector(self, corrected_local_x_vector: MVector3D):
        self.corrected_local_x_vector = corrected_local_x_vector.normalized()
        self.corrected_local_y_vector = self.corrected_local_x_vector.cross(
            MVector3D(0, 0, -1)
        )
        self.corrected_local_z_vector = self.corrected_local_x_vector.cross(
            self.corrected_local_y_vector
        )

    @property
    def is_tail_bone(self) -> bool:
        """表示先がボーンであるか"""
        return BoneFlg.TAIL_IS_BONE in self.bone_flg

    @property
    def can_rotate(self) -> bool:
        """回転可能であるか"""
        return BoneFlg.CAN_ROTATE in self.bone_flg

    @property
    def can_translate(self) -> bool:
        """移動可能であるか"""
        return BoneFlg.CAN_TRANSLATE in self.bone_flg

    @property
    def is_visible(self) -> bool:
        """表示であるか"""
        return BoneFlg.IS_VISIBLE in self.bone_flg

    @property
    def can_manipulate(self) -> bool:
        """操作可であるか"""
        return BoneFlg.CAN_MANIPULATE in self.bone_flg

    @property
    def is_ik(self) -> bool:
        """IKであるか"""
        return BoneFlg.IS_IK in self.bone_flg

    @property
    def is_external_local(self) -> bool:
        """ローカル付与であるか"""
        return BoneFlg.IS_EXTERNAL_LOCAL in self.bone_flg

    @property
    def is_external_rotation(self) -> bool:
        """回転付与であるか"""
        return BoneFlg.IS_EXTERNAL_ROTATION in self.bone_flg

    @property
    def is_external_translation(self) -> bool:
        """移動付与であるか"""
        return BoneFlg.IS_EXTERNAL_TRANSLATION in self.bone_flg

    @property
    def has_fixed_axis(self) -> bool:
        """軸固定であるか"""
        return BoneFlg.HAS_FIXED_AXIS in self.bone_flg

    @property
    def has_local_coordinate(self) -> bool:
        """ローカル軸を持つか"""
        return BoneFlg.HAS_LOCAL_COORDINATE in self.bone_flg

    @property
    def is_after_physics_deform(self) -> bool:
        """物理後変形であるか"""
        return BoneFlg.IS_AFTER_PHYSICS_DEFORM in self.bone_flg

    @property
    def is_external_parent_deform(self) -> bool:
        """外部親変形であるか"""
        return BoneFlg.IS_EXTERNAL_PARENT_DEFORM in self.bone_flg

    @property
    def is_leg_d(self) -> bool:
        """足D系列であるか"""
        return self.name in [
            "左足D",
            "左ひざD",
            "左足首D",
            "右足D",
            "右ひざD",
            "右足首D",
        ]

    @property
    def is_shoulder_p(self) -> bool:
        """肩D系列であるか"""
        return self.name in [
            "左肩P",
            "左肩C",
            "右肩P",
            "右肩C",
        ]

    @property
    def is_leg_fk(self) -> bool:
        """足FK系列であるか"""
        return (
            self.name
            in [
                "左足",
                "左ひざ",
                "左足首",
                "左つま先",
                "右足",
                "右ひざ",
                "右足首",
                "右つま先",
            ]
            or self.is_leg_d
        )

    @property
    def is_ankle(self) -> bool:
        """足首から先であるか"""
        return (
            self.name
            in [
                "左足首",
                "左足首D",
                "左つま先",
                "左足先EX",
                "右足首",
                "右足首D",
                "右つま先",
                "右足先EX",
            ]
            or self.is_leg_d
        )

    @property
    def is_twist(self) -> bool:
        """捩りボーンであるか"""
        return "捩" in self.name

    @property
    def is_arm(self) -> bool:
        """腕系ボーンであるか(指は含まない)"""
        return self.name in [
            "左腕",
            "左腕捩",
            "左腕捩1",
            "左腕捩2",
            "左腕捩3",
            "左腕捩4",
            "左腕捩5",
            "左ひじ",
            "左手捩",
            "左手捩1",
            "左手捩2",
            "左手捩3",
            "左手捩4",
            "左手捩5",
            "左手首",
            "右腕",
            "右腕捩",
            "右腕捩1",
            "右腕捩2",
            "右腕捩3",
            "右腕捩4",
            "右腕捩5",
            "右ひじ",
            "右手捩",
            "右手捩1",
            "右手捩2",
            "右手捩3",
            "右手捩4",
            "右手捩5",
            "右手首",
        ]

    @property
    def is_finger(self) -> bool:
        """指系ボーンであるか"""
        return self.name in [
            "左親指０",
            "左親指１",
            "左親指２",
            "左親指先",
            "左人指１",
            "左人指２",
            "左人指３",
            "左人指先",
            "左中指１",
            "左中指２",
            "左中指３",
            "左中指先",
            "左薬指１",
            "左薬指２",
            "左薬指３",
            "左薬指先",
            "左小指１",
            "左小指２",
            "左小指３",
            "左小指先",
            "右親指０",
            "右親指１",
            "右親指２",
            "右親指先",
            "右人指１",
            "右人指２",
            "右人指３",
            "右人指先",
            "右中指１",
            "右中指２",
            "右中指３",
            "右中指先",
            "右薬指１",
            "右薬指２",
            "右薬指３",
            "右薬指先",
            "右小指１",
            "右小指２",
            "右小指３",
            "右小指先",
        ]

    @property
    def is_standard_extend(self) -> bool:
        """準標準の拡張ボーンであるか"""
        if f"{self.name}先" in STANDARD_BONE_NAMES or (
            self.name[:-1] in STANDARD_BONE_NAMES and self.name[-1] in ("先", "端")
        ):
            return True
        return False

    @property
    def is_head(self) -> bool:
        """準標準ボーン：頭系であるか"""
        return self.name in (
            "首",
            "頭",
            "左目",
            "右目",
            "両目",
        )

    @property
    def is_lower(self) -> bool:
        """準標準ボーン：下半身系であるか"""
        return (
            self.name
            in (
                "下半身",
                "腰キャンセル左",
                "腰キャンセル右",
                "左足IK親",
                "左足ＩＫ",
                "右足IK親",
                "右足ＩＫ",
                "左つま先ＩＫ",
                "右つま先ＩＫ",
            )
            or self.is_leg_fk
            or self.is_leg_d
        )

    @property
    def is_upper(self) -> bool:
        """準標準ボーン：上半身系であるか"""
        return (
            self.name
            in (
                "上半身",
                "上半身2",
                "首根元",
            )
            or self.is_head
            or self.is_finger
            or self.is_arm
        )

    @property
    def is_not_local_cancel(self) -> bool:
        """
        ローカル軸行列計算で親のキャンセルをさせないボーン
        準標準だけど捩り・指・足先EXは親を伝播させる
        """
        return self.is_twist or self.is_finger or "足先EX" in self.name

    @property
    def is_standard(self) -> bool:
        """準標準であるか"""
        return self.name in STANDARD_BONE_NAMES


class MorphOffset(BaseModel):
    """モーフオフセット基底クラス"""

    def __init__(self) -> None:
        super().__init__()


class VertexMorphOffset(MorphOffset):
    """
    頂点モーフ

    Parameters
    ----------
    vertex_index : int
        頂点INDEX
    position : MVector3D
        座標オフセット量(x,y,z)
    """

    __slots__ = ("vertex_index", "position")

    def __init__(self, vertex_index: int, position: MVector3D):
        super().__init__()
        self.vertex_index = vertex_index
        self.position = position


class UvMorphOffset(MorphOffset):
    """
    UVモーフ

    Parameters
    ----------
    vertex_index : int
        頂点INDEX
    uv : MVector4D
        UVオフセット量(x,y,z,w) ※通常UVはz,wが不要項目になるがモーフとしてのデータ値は記録しておく
    """

    __slots__ = ("vertex_index", "uv")

    def __init__(self, vertex_index: int, uv: MVector4D):
        super().__init__()
        self.vertex_index = vertex_index
        self.uv = uv


class BoneMorphOffset(MorphOffset):
    """
    ボーンモーフ

    Parameters
    ----------
    bone_index : int
        ボーンIndex
    position : MVector3D
        グローバル移動量(x,y,z)
    qq : MQuaternion
        グローバル回転量-クォータニオン(x,y,z,w)
    scale : MVector3D
        グローバル縮尺量(x,y,z) ※システム独自
    local_position : MVector3D
        ローカル軸に沿った移動量(x,y,z) ※システム独自
    local_qq : MQuaternion
        ローカル軸に沿った回転量-クォータニオン(x,y,z,w) ※システム独自
    local_scale : MVector3D
        ローカル軸に沿った縮尺量(x,y,z) ※システム独自
    """

    __slots__ = (
        "bone_index",
        "position",
        "rotation",
        "scale",
        "local_position",
        "local_rotation",
        "local_scale",
    )

    def __init__(
        self,
        bone_index: int,
        position: Optional[MVector3D] = None,
        qq: Optional[MQuaternion] = None,
        scale: Optional[MVector3D] = None,
        local_position: Optional[MVector3D] = None,
        local_qq: Optional[MQuaternion] = None,
        local_scale: Optional[MVector3D] = None,
    ):
        super().__init__()
        self.bone_index = bone_index
        self.position = position or MVector3D()
        self.rotation = BaseRotationModel()
        if qq:
            self.rotation.qq = qq
        self.scale = scale or MVector3D()
        self.local_position = local_position or MVector3D()
        self.local_rotation = BaseRotationModel()
        if local_qq:
            self.local_rotation.qq = local_qq
        self.local_scale = local_scale or MVector3D()

    def clear(self):
        self.position = MVector3D()
        self.rotation = BaseRotationModel()
        self.scale = MVector3D()
        self.local_position = MVector3D()
        self.local_rotation = BaseRotationModel()
        self.local_scale = MVector3D()


class GroupMorphOffset(MorphOffset):
    """
    グループモーフ

    Parameters
    ----------
    morph_index : int
        モーフINDEX
    morph_factor : float
        モーフ変動量
    """

    __slots__ = ("morph_index", "morph_factor")

    def __init__(self, morph_index: int, morph_factor: float):
        super().__init__()
        self.morph_index = morph_index
        self.morph_factor = morph_factor


@unique
class MaterialMorphCalcMode(IntEnum):
    """材質モーフ：計算モード"""

    MULTIPLICATION = 0
    """0:乗算"""
    ADDITION = 1
    """1:加算"""


class MaterialMorphOffset(MorphOffset):
    """
    材質モーフ

    Parameters
    ----------
    material_index : int
        材質Index -> -1:全材質対象
    calc_mode : CalcMode
        0:乗算, 1:加算
    diffuse : MVector4D
        Diffuse (R,G,B,A)
    specular : MVector3D
        Specular (R,G,B)
    specular_factor : float
        Specular係数
    ambient : MVector3D
        Ambient (R,G,B)
    edge_color : MVector4D
        エッジ色 (R,G,B,A)
    edge_size : float
        エッジサイズ
    texture_factor : MVector4D
        テクスチャ係数 (R,G,B,A)
    sphere_texture_factor : MVector4D
        スフィアテクスチャ係数 (R,G,B,A)
    toon_texture_factor : MVector4D
        Toonテクスチャ係数 (R,G,B,A)
    """

    __slots__ = (
        "material_index",
        "calc_mode",
        "diffuse",
        "specular",
        "specular_factor",
        "ambient",
        "edge_color",
        "edge_size",
        "texture_factor",
        "sphere_texture_factor",
        "toon_texture_factor",
    )

    def __init__(
        self,
        material_index: int,
        calc_mode: MaterialMorphCalcMode,
        diffuse: MVector4D,
        specular: MVector3D,
        specular_factor: float,
        ambient: MVector3D,
        edge_color: MVector4D,
        edge_size: float,
        texture_factor: MVector4D,
        sphere_texture_factor: MVector4D,
        toon_texture_factor: MVector4D,
    ):
        super().__init__()
        self.material_index = material_index
        self.calc_mode = calc_mode
        self.diffuse = diffuse
        self.specular = specular
        self.specular_factor = specular_factor
        self.ambient = ambient
        self.edge_color = edge_color
        self.edge_size = edge_size
        self.texture_factor = texture_factor
        self.sphere_texture_factor = sphere_texture_factor
        self.toon_texture_factor = toon_texture_factor


class ShaderMaterial:
    """
    材質モーフを加味したシェーダー用材質情報
    """

    __slots__ = (
        "light_ambient4",
        "material",
        "texture_factor_vector",
        "sphere_texture_factor_vector",
        "toon_texture_factor_vector",
    )

    def __init__(
        self,
        material: Material,
        light_ambient4: MVector4D,
        texture_factor: Optional[MVector4D] = None,
        toon_texture_factor: Optional[MVector4D] = None,
        sphere_texture_factor: Optional[MVector4D] = None,
    ):
        super().__init__()
        self.light_ambient4 = light_ambient4
        self.material = material.copy()
        self.texture_factor_vector = texture_factor or MVector4D()
        self.sphere_texture_factor_vector = toon_texture_factor or MVector4D()
        self.toon_texture_factor_vector = sphere_texture_factor or MVector4D()

    @property
    def diffuse(self) -> np.ndarray:
        return np.array(
            [
                *(
                    self.material.diffuse.xyz * self.light_ambient4.xyz
                    + MVector3D(
                        self.material.ambient.x,
                        self.material.ambient.y,
                        self.material.ambient.z,
                    )
                ).vector,
                self.material.diffuse.w,
            ]
        )

    @property
    def ambient(self) -> np.ndarray:
        return (self.material.diffuse.xyz * self.light_ambient4.xyz).vector

    @property
    def specular(self) -> np.ndarray:
        return np.array(
            [
                *(self.material.specular * self.light_ambient4.xyz).vector,
                self.material.specular_factor,
            ]
        )

    @property
    def edge_color(self) -> np.ndarray:
        edge_color = self.material.edge_color.vector
        edge_color[-1] *= self.material.diffuse.w
        return edge_color

    @property
    def edge_size(self) -> float:
        return self.material.edge_size

    @property
    def texture_factor(self) -> np.ndarray:
        return self.texture_factor_vector.vector

    @property
    def sphere_texture_factor(self) -> np.ndarray:
        return self.sphere_texture_factor_vector.vector

    @property
    def toon_texture_factor(self) -> np.ndarray:
        return self.toon_texture_factor_vector.vector

    def __imul__(self, v: Union[float, int, "ShaderMaterial"]):
        if isinstance(v, (float, int)):
            self.material.diffuse *= v
            self.material.ambient *= v
            self.material.specular *= v
            self.material.edge_color *= v
            self.material.edge_size *= v
            self.texture_factor_vector *= v
            self.sphere_texture_factor_vector *= v
            self.toon_texture_factor_vector *= v
        else:
            self.material.diffuse *= v.material.diffuse
            self.material.ambient *= v.material.ambient
            self.material.specular *= v.material.specular
            self.material.edge_color *= v.material.edge_color
            self.material.edge_size *= v.material.edge_size
            self.texture_factor_vector *= v.texture_factor_vector
            self.sphere_texture_factor_vector *= v.sphere_texture_factor_vector
            self.toon_texture_factor_vector *= v.toon_texture_factor_vector
        return self

    def __iadd__(self, v: Union[float, int, "ShaderMaterial"]):
        if isinstance(v, (float, int)):
            self.material.diffuse += v
            self.material.ambient += v
            self.material.specular += v
            self.material.edge_color += v
            self.material.edge_size += v
            self.texture_factor_vector += v
            self.sphere_texture_factor_vector += v
            self.toon_texture_factor_vector += v
        else:
            self.material.diffuse += v.material.diffuse
            self.material.ambient += v.material.ambient
            self.material.specular += v.material.specular
            self.material.edge_color += v.material.edge_color
            self.material.edge_size += v.material.edge_size
            self.texture_factor_vector += v.texture_factor_vector
            self.sphere_texture_factor_vector += v.sphere_texture_factor_vector
            self.toon_texture_factor_vector += v.toon_texture_factor_vector
        return self


@unique
class MorphPanel(IntEnum):
    """操作パネル"""

    SYSTEM = 0
    """0:システム予約"""
    EYEBROW_LOWER_LEFT = 1
    """1:眉(左下)"""
    EYE_UPPER_LEFT = 2
    """2:目(左上)"""
    LIP_UPPER_RIGHT = 3
    """3:口(右上)"""
    OTHER_LOWER_RIGHT = 4
    """4:その他(右下)"""

    @property
    def panel_name(self):
        if 1 == self.value:
            return "眉"
        elif 2 == self.value:
            return "目"
        elif 3 == self.value:
            return "口"
        elif 4 == self.value:
            return "他"
        else:
            return "システム"


@unique
class MorphType(IntEnum):
    """モーフ種類"""

    GROUP = 0
    """0:グループ"""
    VERTEX = 1
    """1:頂点"""
    BONE = 2
    """2:ボーン"""
    UV = 3
    """3:UV"""
    EXTENDED_UV1 = 4
    """4:追加UV1"""
    EXTENDED_UV2 = 5
    """5:追加UV2"""
    EXTENDED_UV3 = 6
    """6:追加UV3"""
    EXTENDED_UV4 = 7
    """7:追加UV4"""
    MATERIAL = 8
    """"8:材質"""
    AFTER_VERTEX = 91
    """91:ボーン変形後頂点"""


class Morph(BaseIndexNameModel):
    """
    _summary_

    Parameters
    ----------
    name : str, optional
        モーフ名, by default ""
    english_name : str, optional
        モーフ名英, by default ""
    panel : MorphPanel, optional
        モーフパネル, by default MorphPanel.UPPER_LEFT_EYE
    morph_type : MorphType, optional
        モーフ種類, by default MorphType.GROUP
    offsets : list[TMorphOffset], optional
        モーフオフセット
    is_system: ツール側で追加したモーフ
    """

    __slots__ = (
        "index",
        "name",
        "english_name",
        "panel",
        "morph_type",
        "offsets",
        "is_system",
        "display_slot",
    )

    def __init__(
        self,
        index: int = -1,
        name: str = "",
        english_name: str = "",
    ):
        super().__init__(index=index, name=name, english_name=english_name)
        self.panel = MorphPanel.EYE_UPPER_LEFT
        self.morph_type = MorphType.GROUP
        self.offsets: list[
            VertexMorphOffset
            | UvMorphOffset
            | BoneMorphOffset
            | GroupMorphOffset
            | MaterialMorphOffset
        ] = []
        self.is_system = False
        self.display_slot = -1


@unique
class DisplayType(IntEnum):
    """表示枠要素タイプ"""

    BONE = 0
    """0:ボーン"""
    MORPH = 1
    """1:モーフ"""


class DisplaySlotReference(BaseModel):
    """
    表示枠要素

    Parameters
    ----------
    display_type : DisplayType, optional
        要素対象 0:ボーン 1:モーフ, by default DisplayType.BONE
    display_index : int, optional
        ボーンIndex or モーフIndex, by default -1
    """

    __slots__ = ("display_type", "display_index")

    def __init__(
        self,
        display_type: DisplayType = DisplayType.BONE,
        display_index: int = -1,
    ):
        super().__init__()
        self.display_type = display_type
        self.display_index = display_index


class DisplaySlot(BaseIndexNameModel):
    """
    表示枠

    Parameters
    ----------
    name : str, optional
        枠名, by default ""
    english_name : str, optional
        枠名英, by default ""
    special_flg : Switch, optional
        特殊枠フラグ - 0:通常枠 1:特殊枠, by default Switch.OFF
    references : list[DisplaySlotReference], optional
        表示枠要素, by default []
    is_system: ツール側で追加した表示枠
    """

    __slots__ = (
        "index",
        "name",
        "english_name",
        "special_flg",
        "references",
        "is_system",
    )

    def __init__(
        self,
        index: int = -1,
        name: str = "",
        english_name: str = "",
    ):
        super().__init__(index=index, name=name, english_name=english_name)
        self.special_flg = Switch.OFF
        self.references: list[DisplaySlotReference] = []
        self.is_system: bool = False


class RigidBodyParam(BaseModel):
    """
    剛体パラ

    Parameters
    ----------
    mass : float, optional
        質量, by default 0
    linear_damping : float, optional
        移動減衰, by default 0
    angular_damping : float, optional
        回転減衰, by default 0
    restitution : float, optional
        反発力, by default 0
    friction : float, optional
        摩擦力, by default 0
    """

    __slots__ = (
        "mass",
        "linear_damping",
        "angular_damping",
        "restitution",
        "friction",
    )

    def __init__(
        self,
        mass: float = 0,
        linear_damping: float = 0,
        angular_damping: float = 0,
        restitution: float = 0,
        friction: float = 0,
    ) -> None:
        super().__init__()
        self.mass = mass
        self.linear_damping = linear_damping
        self.angular_damping = angular_damping
        self.restitution = restitution
        self.friction = friction


@unique
class RigidBodyShape(IntEnum):
    """剛体の形状"""

    SPHERE = 0
    """0:球"""
    BOX = 1
    """1:箱"""
    CAPSULE = 2
    """2:カプセル"""


@unique
class RigidBodyMode(IntEnum):
    """剛体物理の計算モード"""

    STATIC = 0
    """0:ボーン追従(static)"""
    DYNAMIC = 1
    """1:物理演算(dynamic)"""
    DYNAMIC_BONE = 2
    """2:物理演算 + Bone位置合わせ"""


@unique
class RigidBodyCollisionGroup(Flag):
    """剛体の衝突グループ"""

    NONE = 0x0000
    """0:グループなし"""
    GROUP01 = 0x0001
    GROUP02 = 0x0002
    GROUP03 = 0x0004
    GROUP04 = 0x0008
    GROUP05 = 0x0010
    GROUP06 = 0x0020
    GROUP07 = 0x0040
    GROUP08 = 0x0080
    GROUP09 = 0x0100
    GROUP10 = 0x0200
    GROUP11 = 0x0400
    GROUP12 = 0x0800
    GROUP13 = 0x1000
    GROUP14 = 0x2000
    GROUP15 = 0x4000
    GROUP16 = 0x8000


class RigidBody(BaseIndexNameModel):
    """
    剛体

    Parameters
    ----------
    name : str, optional
        剛体名, by default ""
    english_name : str, optional
        剛体名英, by default ""
    bone_index : int, optional
        関連ボーンIndex, by default -1
    collision_group : int, optional
        グループ, by default 0
    no_collision_group : RigidBodyCollisionGroup, optional
        非衝突グループフラグ, by default 0
    shape_type : RigidBodyShape, optional
        形状, by default RigidBodyShape.SPHERE
    shape_size : MVector3D, optional
        サイズ(x,y,z), by default MVector3D()
    shape_position : MVector3D, optional
        位置(x,y,z), by default MVector3D()
    shape_rotation_radians : MVector3D, optional
        回転(x,y,z) -> ラジアン角, by default MVector3D()
    mass : float, optional
        質量, by default 0
    linear_damping : float, optional
        移動減衰, by default 0
    angular_damping : float, optional
        回転減衰, by default 0
    restitution : float, optional
        反発力, by default 0
    friction : float, optional
        摩擦力, by default 0
    mode : RigidBodyMode, optional
        剛体の物理演算, by default RigidBodyMode.STATIC
    """

    __slots__ = (
        "index",
        "name",
        "english_name",
        "bone_index",
        "collision_group",
        "no_collision_group",
        "shape_type",
        "shape_size",
        "shape_position",
        "shape_rotation",
        "param",
        "mode",
        "x_direction",
        "y_direction",
        "z_direction",
        "is_system",
    )

    def __init__(
        self,
        index: int = -1,
        name: str = "",
        english_name: str = "",
    ) -> None:
        super().__init__(index=index, name=name, english_name=english_name)
        self.bone_index = -1
        self.collision_group = 0
        self.no_collision_group = RigidBodyCollisionGroup.NONE
        self.shape_type = RigidBodyShape.SPHERE
        self.shape_size = MVector3D()
        self.shape_position = MVector3D()
        self.shape_rotation = BaseRotationModel()
        self.param = RigidBodyParam()
        self.mode = RigidBodyMode.STATIC
        # 軸方向
        self.x_direction = MVector3D(1, 0, 0)
        self.y_direction = MVector3D(0, 1, 0)
        self.z_direction = MVector3D(0, 0, -1)
        self.is_system = False


class JointLimitParam(BaseModel):
    """
    ジョイント制限パラメーター

    Parameters
    ----------
    limit_min : MVector3D, optional
        制限最小角度, by default MVector3D()
    limit_max : MVector3D, optional
        制限最大角度, by default MVector3D()
    """

    __slots__ = ("limit_min", "limit_max")

    def __init__(
        self,
        limit_min: MVector3D,
        limit_max: MVector3D,
    ) -> None:
        super().__init__()
        self.limit_min = limit_min or MVector3D()
        self.limit_max = limit_max or MVector3D()


class JointParam(BaseModel):
    """
    ジョイントパラメーター

    Parameters
    ----------
    translation_limit_min : MVector3D, optional
        移動制限-下限(x,y,z), by default MVector3D()
    translation_limit_max : MVector3D, optional
        移動制限-上限(x,y,z), by default MVector3D()
    rotation_limit_min : BaseRotationModel, optional
        回転制限-下限(x,y,z) -> ラジアン角, by default BaseRotationModel()
    rotation_limit_max : BaseRotationModel, optional
        回転制限-上限(x,y,z) -> ラジアン角, by default BaseRotationModel()
    spring_constant_translation : MVector3D, optional
        バネ定数-移動(x,y,z), by default MVector3D()
    spring_constant_rotation : MVector3D, optional
        バネ定数-回転(x,y,z), by default MVector3D()
    """

    __slots__ = (
        "translation_limit_min",
        "translation_limit_max",
        "rotation_limit_min",
        "rotation_limit_max",
        "spring_constant_translation",
        "spring_constant_rotation",
    )

    def __init__(
        self,
    ) -> None:
        super().__init__()
        self.translation_limit_min = MVector3D()
        self.translation_limit_max = MVector3D()
        self.rotation_limit_min = BaseRotationModel()
        self.rotation_limit_max = BaseRotationModel()
        self.spring_constant_translation = MVector3D()
        self.spring_constant_rotation = MVector3D()


class Joint(BaseIndexNameModel):
    """
    ジョイント

    Parameters
    ----------
    name : str, optional
        Joint名, by default ""
    english_name : str, optional
        Joint名英, by default ""
    joint_type : int, optional
        Joint種類, by default 0
    rigidbody_index_a : int, optional
        関連剛体AのIndex, by default -1
    rigidbody_index_b : int, optional
        関連剛体BのIndex, by default -1
    position : MVector3D, optional
        位置(x,y,z), by default MVector3D()
    rotation : BaseRotationModel, optional
        回転(x,y,z) -> ラジアン角, by default BaseRotationModel()
    translation_limit_min : MVector3D, optional
        移動制限-下限(x,y,z), by default MVector3D()
    translation_limit_max : MVector3D, optional
        移動制限-上限(x,y,z), by default MVector3D()
    rotation_limit_min : BaseRotationModel, optional
        回転制限-下限(x,y,z) -> ラジアン角, by default BaseRotationModel()
    rotation_limit_max : BaseRotationModel, optional
        回転制限-上限(x,y,z) -> ラジアン角, by default BaseRotationModel()
    spring_constant_translation : MVector3D, optional
        バネ定数-移動(x,y,z), by default MVector3D()
    spring_constant_rotation : MVector3D, optional
        バネ定数-回転(x,y,z), by default MVector3D()
    """

    __slots__ = (
        "index",
        "name",
        "english_name",
        "joint_type",
        "rigidbody_index_a",
        "rigidbody_index_b",
        "position",
        "rotation",
        "param",
        "is_system",
    )

    def __init__(
        self,
        index: int = -1,
        name: str = "",
        english_name: str = "",
    ) -> None:
        super().__init__(index=index, name=name, english_name=english_name)
        self.joint_type = 0
        self.rigidbody_index_a = -1
        self.rigidbody_index_b = -1
        self.position = MVector3D()
        self.rotation = BaseRotationModel()
        self.param = JointParam()
        self.is_system = False
