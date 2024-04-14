from enum import Enum, IntEnum, unique
from pickle import HIGHEST_PROTOCOL, dumps, loads
from typing import TypeVar

from mlib.core.logger import parse2str


@unique
class Encoding(Enum):
    UTF_8 = "utf-8"
    UTF_16_LE = "utf-16-le"
    SHIFT_JIS = "shift-jis"
    CP932 = "cp932"


@unique
class FileType(Enum):
    """ファイル種別"""

    VMD_VPD = "VMD/VPDファイル (*.vmd, *.vpd)|*.vmd;*.vpd|すべてのファイル (*.*)|*.*"
    VMD = "VMDファイル (*.vmd)|*.vmd|すべてのファイル (*.*)|*.*"
    PMX = "PMXファイル (*.pmx)|*.pmx|すべてのファイル (*.*)|*.*"
    CSV = "CSVファイル (*.csv)|*.csv|すべてのファイル (*.*)|*.*"
    VRM = "VRMファイル (*.vrm)|*.vrm|すべてのファイル (*.*)|*.*"
    IMAGE = "画像ファイル (*.png, *.jpg, *.bmp)|*.png;*.jpg;*.jpeg;*.bmp|すべてのファイル (*.*)|*.*"


@unique
class VecAxis(IntEnum):
    """軸"""

    X = 0
    Y = 1
    Z = 2


TBaseModel = TypeVar("TBaseModel", bound="BaseModel")


class BaseModel:
    """基底クラス"""

    def __init__(self) -> None:
        pass

    def __str__(self) -> str:
        return parse2str(self)

    def copy(self: TBaseModel) -> TBaseModel:
        return loads(dumps(self, protocol=HIGHEST_PROTOCOL))
