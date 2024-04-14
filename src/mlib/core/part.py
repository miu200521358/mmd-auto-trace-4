from enum import Enum, unique
from typing import Optional, TypeVar

import numpy as np

from mlib.core.base import BaseModel
from mlib.core.math import MQuaternion, MVector3D


@unique
class Switch(Enum):
    """ON/OFFスイッチ"""

    OFF = 0
    ON = 1


class BaseRotationModel(BaseModel):
    __slots__ = (
        "_radians",
        "_degrees",
        "_qq",
    )

    def __init__(self, v_radians: Optional[MVector3D] = None) -> None:
        super().__init__()
        self._radians = MVector3D()
        self._degrees = MVector3D()
        self._qq = MQuaternion()
        self.radians = v_radians or MVector3D()

    @property
    def qq(self) -> MQuaternion:
        """
        回転情報をクォータニオンとして受け取る
        """
        return self._qq

    @qq.setter
    def qq(self, v: MQuaternion) -> None:
        """
        クォータニオンを回転情報として設定する

        Parameters
        ----------
        v : MQuaternion
            クォータニオン
        """
        self._qq = v
        self._degrees = v.to_euler_degrees()
        self._radians = MVector3D(*np.radians(self._degrees.vector))

    @property
    def radians(self) -> MVector3D:
        """
        回転情報をラジアンとして受け取る
        """
        return self._radians

    @radians.setter
    def radians(self, v: MVector3D) -> None:
        """
        ラジアンを回転情報として設定する

        Parameters
        ----------
        v : MVector3D
            ラジアン
        """
        self._radians = v
        self._degrees = MVector3D(*np.degrees(v.vector))
        self._qq = MQuaternion.from_euler_degrees(self.degrees)

    @property
    def degrees(self) -> MVector3D:
        """
        回転情報を度として受け取る
        """
        return self._degrees

    @degrees.setter
    def degrees(self, v: MVector3D) -> None:
        """
        度を回転情報として設定する

        Parameters
        ----------
        v : MVector3D
            度
        """
        self._degrees = v
        self._radians = MVector3D(*np.radians(v.vector))
        self._qq = MQuaternion.from_euler_degrees(v)


TBaseIndexModel = TypeVar("TBaseIndexModel", bound="BaseIndexModel")


class BaseIndexModel(BaseModel):
    """
    INDEXを持つ基底クラス
    """

    def __init__(self, index: int = -1) -> None:
        """
        初期化

        Parameters
        ----------
        index : int, optional
            INDEX, by default -1
        """
        self.index = index

    def __bool__(self) -> bool:
        return 0 <= self.index

    def __iadd__(self: TBaseIndexModel, v: TBaseIndexModel) -> None:
        raise NotImplementedError()

    def __add__(self: TBaseIndexModel, v: TBaseIndexModel) -> TBaseIndexModel:
        raise NotImplementedError()


TBaseIndexNameModel = TypeVar("TBaseIndexNameModel", bound="BaseIndexNameModel")


class BaseIndexNameModel(BaseModel):
    """
    INDEXと名前を持つ基底クラス
    """

    def __init__(self, index: int = -1, name: str = "", english_name: str = "") -> None:
        """
        初期化

        Parameters
        ----------
        index : int, optional
            INDEX, by default -1
        name : str, optional
            名前, by default ""
        english_name : str, optional
            英語名, by default ""
        """
        self.index: int = index
        self.name: str = name
        self.english_name: str = english_name

    def __bool__(self) -> bool:
        return 0 <= self.index and 0 <= len(self.name)

    def __iadd__(self: TBaseIndexNameModel, v: TBaseIndexNameModel) -> None:
        raise NotImplementedError()

    def __add__(
        self: TBaseIndexNameModel, v: TBaseIndexNameModel
    ) -> TBaseIndexNameModel:
        raise NotImplementedError()
