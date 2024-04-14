from typing import Iterator, Optional

from mlib.core.base import BaseModel
from mlib.core.interpolation import Interpolation, evaluate
from mlib.core.math import MQuaternion, MVector3D
from mlib.core.part import BaseIndexNameModel, BaseRotationModel


class BaseVmdNameFrame(BaseIndexNameModel):
    """
    VMD用基底クラス(名前あり)

    Parameters
    ----------
    index : int, optional
        キーフレ, by default None
    name : str, optional
        名前, by default None
    register : bool, optional
        登録対象か否か, by default None
    read : bool, optional
        VMDデータから読み込んだデータか, by default None
    """

    def __init__(
        self,
        index: int = -1,
        name: str = "",
        register: bool = False,
        read: bool = False,
    ) -> None:
        super().__init__(index, name)
        self.register = register
        self.read = read


# https://hariganep.seesaa.net/article/201103article_1.html
class BoneInterpolations(BaseModel):
    """
    ボーンキーフレ用補間曲線

    Parameters
    ----------
    translation_x : Interpolation, optional
        移動X, by default None
    translation_y : Interpolation, optional
        移動Y, by default None
    translation_z : Interpolation, optional
        移動Z, by default None
    rotation : Interpolation, optional
        回転, by default None
    """

    __slots__ = (
        "translation_x",
        "translation_y",
        "translation_z",
        "rotation",
        "vals",
    )

    def __init__(self) -> None:
        self.translation_x = Interpolation()
        self.translation_y = Interpolation()
        self.translation_z = Interpolation()
        self.rotation = Interpolation()
        self.vals = [
            20,
            20,
            0,
            0,
            20,
            20,
            20,
            20,
            107,
            107,
            107,
            107,
            107,
            107,
            107,
            107,
            20,
            20,
            20,
            20,
            20,
            20,
            20,
            107,
            107,
            107,
            107,
            107,
            107,
            107,
            107,
            0,
            20,
            20,
            20,
            20,
            20,
            20,
            107,
            107,
            107,
            107,
            107,
            107,
            107,
            107,
            0,
            0,
            20,
            20,
            20,
            20,
            20,
            107,
            107,
            107,
            107,
            107,
            107,
            107,
            107,
            0,
            0,
            0,
        ]

    def __str__(self) -> str:
        return (
            f"translation_x[{self.translation_x}], translation_y[{self.translation_y}], "
            + f"translation_z[{self.translation_z}], rotation[{self.rotation}]"
        )

    def evaluate(
        self, prev_index: int, index: int, next_index: int
    ) -> tuple[float, float, float, float]:
        # 補間結果Yは、FKキーフレ内で計算する
        _, ry, _ = evaluate(self.rotation, prev_index, index, next_index)
        _, xy, _ = evaluate(self.translation_x, prev_index, index, next_index)
        _, yy, _ = evaluate(self.translation_y, prev_index, index, next_index)
        _, zy, _ = evaluate(self.translation_z, prev_index, index, next_index)

        return ry, xy, yy, zy

    def merge(self) -> list[int]:
        return [
            int(self.translation_x.start.x),
            self.vals[1],
            self.vals[2],
            self.vals[3],
            int(self.translation_x.start.y),
            self.vals[5],
            self.vals[6],
            self.vals[7],
            int(self.translation_x.end.x),
            self.vals[9],
            self.vals[10],
            self.vals[11],
            int(self.translation_x.end.y),
            self.vals[13],
            self.vals[14],
            self.vals[15],
            int(self.translation_y.start.x),
            self.vals[17],
            self.vals[18],
            self.vals[19],
            int(self.translation_y.start.y),
            self.vals[21],
            self.vals[22],
            self.vals[23],
            int(self.translation_y.end.x),
            self.vals[25],
            self.vals[26],
            self.vals[27],
            int(self.translation_y.end.y),
            self.vals[29],
            self.vals[30],
            self.vals[31],
            int(self.translation_z.start.x),
            self.vals[33],
            self.vals[34],
            self.vals[35],
            int(self.translation_z.start.y),
            self.vals[37],
            self.vals[38],
            self.vals[39],
            int(self.translation_z.end.x),
            self.vals[41],
            self.vals[42],
            self.vals[43],
            int(self.translation_z.end.y),
            self.vals[45],
            self.vals[46],
            self.vals[47],
            int(self.rotation.start.x),
            self.vals[49],
            self.vals[50],
            self.vals[51],
            int(self.rotation.start.y),
            self.vals[53],
            self.vals[54],
            self.vals[55],
            int(self.rotation.end.x),
            self.vals[57],
            self.vals[58],
            self.vals[59],
            int(self.rotation.end.y),
            self.vals[61],
            self.vals[62],
            self.vals[63],
        ]

    def __iter__(self) -> Iterator[Interpolation]:
        return iter(
            [self.translation_x, self.translation_y, self.translation_z, self.rotation]
        )

    def __getitem__(self, index: int) -> Interpolation:
        if index == 0:
            return self.translation_x
        elif index == 1:
            return self.translation_y
        elif index == 2:
            return self.translation_z
        elif index == 3:
            return self.rotation
        raise IndexError(f"Interpolation index [{index}]")

    def __setitem__(self, index: int, value: Interpolation) -> None:
        if index == 0:
            self.translation_x = value
        elif index == 1:
            self.translation_y = value
        elif index == 2:
            self.translation_z = value
        elif index == 3:
            self.rotation = value


class VmdBoneFrame(BaseVmdNameFrame):
    """
    VMDのボーン1フレーム

    Parameters
    ----------
    name : str, optional
        ボーン名, by default None
    index : int, optional
        キーフレ, by default None
    position : MVector3D, optional
        位置, by default None
    rotation : MQuaternion, optional
        回転, by default None
    scale : MVector3D, optional
        グローバルスケール, by default None
    local_position : MVector3D, optional
        ローカル位置（グローバルの後にかける）, by default None
    local_rotation : MQuaternion, optional
        ローカル回転（グローバルの後にかける）, by default None
    local_scale : MVector3D, optional
        ローカルスケール（グローバルの後にかける）, by default None
    interpolations : Interpolations, optional
        補間曲線, by default None
    register : bool, optional
        登録対象か否か, by default None
    read : bool, optional
        VMDデータから読み込んだデータか, by default None
    """

    __slots__ = (
        "name",
        "index",
        "register",
        "read",
        "position",
        "local_position",
        "rotation",
        "local_rotation",
        "scale",
        "local_scale",
        "interpolations",
        "ik_rotation",
        "corrected_rotation",
        "corrected_position",
    )

    def __init__(
        self,
        index: int = -1,
        name: str = "",
        register: bool = False,
        read: bool = False,
    ) -> None:
        super().__init__(index, name, register, read)
        self.position = MVector3D()
        self.local_position = MVector3D()
        self.rotation = MQuaternion()
        self.local_rotation = MQuaternion()
        self.scale = MVector3D()
        self.local_scale = MVector3D()
        self.interpolations = BoneInterpolations()
        self.ik_rotation: Optional[MQuaternion] = None
        self.corrected_position: Optional[MVector3D] = None
        self.corrected_rotation: Optional[MQuaternion] = None

    def __iadd__(self, v: "VmdBoneFrame"):
        self.position += v.position
        self.local_position += v.local_position
        self.rotation *= v.rotation
        self.local_rotation *= v.local_rotation
        self.scale += v.scale
        self.local_scale += v.local_scale

        if v.ik_rotation:
            if self.ik_rotation is None:
                self.ik_rotation = MQuaternion()
            self.ik_rotation *= v.ik_rotation

        if v.corrected_position:
            if self.corrected_position is None:
                self.corrected_position = MVector3D()
            self.corrected_position += v.corrected_position

        if v.corrected_rotation:
            if self.corrected_rotation is None:
                self.corrected_rotation = MQuaternion()
            self.corrected_rotation *= v.corrected_rotation
        return self

    def __add__(self, v: "VmdBoneFrame"):
        vv = self.copy()

        vv.position += v.position
        vv.local_position += v.local_position
        vv.rotation *= v.rotation
        vv.local_rotation *= v.local_rotation
        vv.scale += v.scale
        vv.local_scale += v.local_scale

        if v.ik_rotation:
            if vv.ik_rotation is None:
                vv.ik_rotation = MQuaternion()
            vv.ik_rotation *= v.ik_rotation

        if v.corrected_position:
            if vv.corrected_position is None:
                vv.corrected_position = MVector3D()
            vv.corrected_position += v.corrected_position

        if v.corrected_rotation:
            if vv.corrected_rotation is None:
                vv.corrected_rotation = MQuaternion()
            vv.corrected_rotation *= v.corrected_rotation
        return vv


class VmdMorphFrame(BaseVmdNameFrame):
    """
    VMDのモーフ1フレーム

    Parameters
    ----------
    name : str, optional
        モーフ名, by default None
    index : int, optional
        キーフレ, by default None
    ratio : float, optional
        変化量, by default None
    register : bool, optional
        登録対象か否か, by default None
    read : bool, optional
        VMDデータから読み込んだデータか, by default None
    """

    __slots__ = (
        "name",
        "index",
        "register",
        "read",
        "ratio",
    )

    def __init__(
        self,
        index: int = -1,
        name: str = "",
        ratio: float = 0.0,
        register: bool = False,
        read: bool = False,
    ) -> None:
        super().__init__(index, name, register, read)
        self.ratio = ratio

    def __iadd__(self, v: "VmdMorphFrame"):
        self.ratio += v.ratio
        return self

    def __add__(self, v: "VmdMorphFrame"):
        vv = self.copy()
        vv.ratio += v.ratio
        return vv


class CameraInterpolations(BaseModel):
    """
    カメラ補間曲線

    Parameters
    ----------
    translation_x : Interpolation, optional
        移動X, by default None
    translation_y : Interpolation, optional
        移動Y, by default None
    translation_z : Interpolation, optional
        移動Z, by default None
    rotation : Interpolation, optional
        回転, by default None
    distance : Interpolation, optional
        距離, by default None
    viewing_angle : Interpolation, optional
        視野角, by default None
    """

    __slots__ = (
        "translation_x",
        "translation_y",
        "translation_z",
        "rotation",
        "distance",
        "viewing_angle",
    )

    def __init__(
        self,
        translation_x: Optional[Interpolation] = None,
        translation_y: Optional[Interpolation] = None,
        translation_z: Optional[Interpolation] = None,
        rotation: Optional[Interpolation] = None,
        distance: Optional[Interpolation] = None,
        viewing_angle: Optional[Interpolation] = None,
    ) -> None:
        self.translation_x = translation_x or Interpolation()
        self.translation_y = translation_y or Interpolation()
        self.translation_z = translation_z or Interpolation()
        self.rotation = rotation or Interpolation()
        self.distance = distance or Interpolation()
        self.viewing_angle = viewing_angle or Interpolation()

    def merge(self) -> list[int]:
        return [
            int(self.translation_x.start.x),
            int(self.translation_y.start.x),
            int(self.translation_z.start.x),
            int(self.rotation.start.x),
            int(self.distance.start.x),
            int(self.viewing_angle.start.x),
            int(self.translation_x.start.y),
            int(self.translation_y.start.y),
            int(self.translation_z.start.y),
            int(self.rotation.start.y),
            int(self.distance.start.y),
            int(self.viewing_angle.start.y),
            int(self.translation_x.end.x),
            int(self.translation_y.end.x),
            int(self.translation_z.end.x),
            int(self.rotation.end.x),
            int(self.distance.end.x),
            int(self.viewing_angle.end.x),
            int(self.translation_x.end.y),
            int(self.translation_y.end.y),
            int(self.translation_z.end.y),
            int(self.rotation.end.y),
            int(self.distance.end.y),
            int(self.viewing_angle.end.y),
        ]


class VmdCameraFrame(BaseVmdNameFrame):
    """
    カメラキーフレ

    Parameters
    ----------
    index : int, optional
        キーフレ, by default None
    position : MVector3D, optional
        位置, by default None
    rotation : BaseRotationModel, optional
        回転, by default None
    distance : float, optional
        距離, by default None
    viewing_angle : int, optional
        視野角, by default None
    perspective : bool, optional
        パース, by default None
    interpolations : CameraInterpolations, optional
        補間曲線, by default None
    register : bool, optional
        登録対象か否か, by default None
    read : bool, optional
        VMDデータから読み込んだデータか, by default None
    """

    __slots__ = (
        "index",
        "register",
        "read",
        "position",
        "rotation",
        "distance",
        "viewing_angle",
        "perspective",
        "interpolations",
    )

    def __init__(
        self,
        index: int = -1,
        position: Optional[MVector3D] = None,
        rotation: Optional[BaseRotationModel] = None,
        distance: float = 0.0,
        viewing_angle: int = 0,
        perspective: bool = False,
        interpolations: Optional[CameraInterpolations] = None,
        register: bool = False,
        read: bool = False,
    ) -> None:
        super().__init__(index, "カメラ", register, read)
        self.position = position or MVector3D()
        self.rotation = rotation or BaseRotationModel()
        self.distance = distance
        self.viewing_angle = viewing_angle
        self.perspective = perspective
        self.interpolations = interpolations or CameraInterpolations()


class VmdLightFrame(BaseVmdNameFrame):
    """
    照明キーフレ

    Parameters
    ----------
    index : int, optional
        キーフレ, by default None
    color : MVector3D, optional
        色, by default None
    position : MVector3D, optional
        位置, by default None
    register : bool, optional
        登録対象か否か, by default None
    read : bool, optional
        VMDデータから読み込んだデータか, by default None
    """

    __slots__ = (
        "index",
        "register",
        "read",
        "color",
        "position",
    )

    def __init__(
        self,
        index: int = -1,
        color: Optional[MVector3D] = None,
        position: Optional[MVector3D] = None,
        register: bool = False,
        read: bool = False,
    ) -> None:
        super().__init__(index, "照明", register, read)
        self.color = color or MVector3D()
        self.position = position or MVector3D()


class VmdShadowFrame(BaseVmdNameFrame):
    """
    セルフ影キーフレ

    Parameters
    ----------
    index : int, optional
        キーフレ, by default None
    mode : int, optional
        セルフ影モード, by default None
    distance : float, optional
        影範囲距離, by default None
    register : bool, optional
        登録対象か否か, by default None
    read : bool, optional
        VMDデータから読み込んだデータか, by default None
    """

    __slots__ = (
        "index",
        "register",
        "read",
        "type",
        "distance",
    )

    def __init__(
        self,
        index: int = -1,
        mode: int = 0,
        distance: float = 0.0,
        register: bool = False,
        read: bool = False,
    ) -> None:
        super().__init__(index, "セルフ影", register, read)
        self.type = mode
        self.distance = distance


class VmdIkOnOff(BaseModel):
    """
    IKのONOFF

    Parameters
    ----------
    name : str, optional
        IK名, by default None
    onoff : bool, optional
        ON,OFF, by default None
    """

    __slots__ = (
        "name",
        "onoff",
    )

    def __init__(
        self,
        name: str = "",
        onoff: bool = True,
    ) -> None:
        super().__init__()
        self.name = name
        self.onoff = onoff


class VmdShowIkFrame(BaseVmdNameFrame):
    """
    IKキーフレ

    Parameters
    ----------
    index : int, optional
        キーフレ, by default None
    show : bool, optional
        表示有無, by default None
    iks : list[VmdIk], optional
        IKリスト, by default None
    register : bool, optional
        登録対象か否か, by default None
    read : bool, optional
        VMDデータから読み込んだデータか, by default None
    """

    __slots__ = (
        "index",
        "register",
        "read",
        "show",
        "iks",
    )

    def __init__(
        self,
        index: int = -1,
        show: bool = True,
        iks: Optional[list[VmdIkOnOff]] = None,
        register: bool = False,
        read: bool = False,
    ) -> None:
        super().__init__(index, "IK", register, read)
        self.show = show
        self.iks = iks or []
