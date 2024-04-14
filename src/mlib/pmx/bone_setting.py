from enum import Enum, Flag, unique
from typing import Iterable, Union

from mlib.core.math import MVector3D


@unique
class BoneFlg(Flag):
    """ボーンフラグ"""

    NONE = 0x0000
    """"初期値"""
    TAIL_IS_BONE = 0x0001
    """接続先(PMD子ボーン指定)表示方法 -> 0:座標オフセットで指定 1:ボーンで指定"""
    CAN_ROTATE = 0x0002
    """回転可能"""
    CAN_TRANSLATE = 0x0004
    """移動可能"""
    IS_VISIBLE = 0x0008
    """表示"""
    CAN_MANIPULATE = 0x0010
    """操作可"""
    IS_IK = 0x0020
    """IK"""
    IS_EXTERNAL_LOCAL = 0x0080
    """ローカル付与 | 付与対象 0:ユーザー変形値／IKリンク／多重付与 1:親のローカル変形量"""
    IS_EXTERNAL_ROTATION = 0x0100
    """回転付与"""
    IS_EXTERNAL_TRANSLATION = 0x0200
    """移動付与"""
    HAS_FIXED_AXIS = 0x0400
    """軸固定"""
    HAS_LOCAL_COORDINATE = 0x0800
    """ローカル軸"""
    IS_AFTER_PHYSICS_DEFORM = 0x1000
    """物理後変形"""
    IS_EXTERNAL_PARENT_DEFORM = 0x2000
    """外部親変形"""
    NOTHING = 0x4000
    """ボーンが実際には存在しない場合のフラグ(システム用)"""


class BoneSetting:
    """ボーン設定"""

    def __init__(
        self,
        name: str,
        parents: Iterable[str],
        display_tail: Union[MVector3D, Iterable[str]],
        tails: Iterable[str],
        flag: BoneFlg,
    ) -> None:
        """
        name : 準標準ボーン名
        parents : 親ボーン名候補リスト
        display_tail : 表示先ボーンもしくは表示先位置
            vector の場合はそのまま使う。名前リストの場合、該当ボーンの位置との相対位置
        tails : 末端ボーン名候補リスト
        flag : ボーンの特性
        """
        self.name = name
        self.parents = parents
        self.display_tail = display_tail
        self.tails = tails
        self.flag = flag


class BoneSettings(Enum):
    """準標準ボーン設定一覧"""

    ROOT = BoneSetting(
        name="全ての親",
        parents=[],
        display_tail=MVector3D(0, 1, 0),
        tails=("センター",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_TRANSLATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE,
    )
    CENTER = BoneSetting(
        name="センター",
        parents=("全ての親",),
        display_tail=MVector3D(0, 1, 0),
        tails=("上半身", "下半身"),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_TRANSLATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE,
    )
    GROOVE = BoneSetting(
        name="グルーブ",
        parents=("センター",),
        display_tail=MVector3D(0, -1, 0),
        tails=("上半身", "下半身"),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_TRANSLATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE,
    )
    WAIST = BoneSetting(
        name="腰",
        parents=("グルーブ", "センター"),
        display_tail=MVector3D(0, -1, 0),
        tails=("上半身", "下半身"),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_TRANSLATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE,
    )
    LOWER = BoneSetting(
        name="下半身",
        parents=("腰", "グルーブ", "センター"),
        display_tail=("足中心",),
        tails=("足中心",),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.CAN_MANIPULATE | BoneFlg.IS_VISIBLE,
    )
    LEG_CENTER = BoneSetting(
        name="足中心",
        parents=("下半身", "腰", "グルーブ", "センター"),
        display_tail=MVector3D(0, -1, 0),
        tails=[],
        flag=BoneFlg.CAN_ROTATE,
    )
    UPPER = BoneSetting(
        name="上半身",
        parents=("腰", "グルーブ", "センター"),
        display_tail=("上半身2",),
        tails=("上半身2",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    UPPER2 = BoneSetting(
        name="上半身2",
        parents=("上半身",),
        display_tail=("上半身3", "首根元"),
        tails=("上半身3", "首根元"),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    UPPER3 = BoneSetting(
        name="上半身3",
        parents=("上半身2",),
        display_tail=("首根元",),
        tails=("首根元",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    NECK_ROOT = BoneSetting(
        name="首根元",
        parents=("上半身3", "上半身2", "上半身"),
        display_tail=("首",),
        tails=("首",),
        flag=BoneFlg.CAN_ROTATE,
    )
    NECK = BoneSetting(
        name="首",
        parents=("首根元", "上半身2", "上半身"),
        display_tail=("頭",),
        tails=("頭",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    HEAD = BoneSetting(
        name="頭",
        parents=("首",),
        display_tail=MVector3D(0, 1, 0),
        tails=[],
        flag=BoneFlg.CAN_ROTATE | BoneFlg.CAN_MANIPULATE | BoneFlg.IS_VISIBLE,
    )
    EYES = BoneSetting(
        name="両目",
        parents=("頭",),
        display_tail=MVector3D(0, 1, 0),
        tails=("左目", "右目"),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.CAN_MANIPULATE | BoneFlg.IS_VISIBLE,
    )
    LEFT_EYE = BoneSetting(
        name="左目",
        parents=("頭",),
        display_tail=MVector3D(0, 1, 0),
        tails=[],
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.IS_EXTERNAL_ROTATION,
    )
    RIGHT_EYE = BoneSetting(
        name="右目",
        parents=("頭",),
        display_tail=MVector3D(0, 1, 0),
        tails=[],
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.IS_EXTERNAL_ROTATION,
    )

    RIGHT_BUST = BoneSetting(
        name="右胸",
        parents=("上半身3", "上半身2", "上半身"),
        display_tail=MVector3D(0, 0, -1),
        tails=[],
        flag=BoneFlg.CAN_ROTATE | BoneFlg.CAN_MANIPULATE | BoneFlg.IS_VISIBLE,
    )
    RIGHT_SHOULDER_ROOT = BoneSetting(
        name="右肩根元",
        parents=("首根元",),
        display_tail=MVector3D(0, 1, 0),
        tails=("右肩",),
        flag=BoneFlg.CAN_ROTATE,
    )
    RIGHT_SHOULDER_P = BoneSetting(
        name="右肩P",
        parents=("右肩根元", "首根元"),
        display_tail=MVector3D(0, 1, 0),
        tails=("右腕",),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.CAN_MANIPULATE | BoneFlg.IS_VISIBLE,
    )
    RIGHT_SHOULDER = BoneSetting(
        name="右肩",
        parents=("右肩P", "右肩根元"),
        display_tail=("右腕",),
        tails=("右腕",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_SHOULDER_C = BoneSetting(
        name="右肩C",
        parents=("右肩",),
        display_tail=MVector3D(0, 1, 0),
        tails=("右ひじ",),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.IS_EXTERNAL_ROTATION,
    )
    RIGHT_ARM = BoneSetting(
        name="右腕",
        parents=("右肩C", "右肩"),
        display_tail=("右腕捩", "右ひじ"),
        tails=("右腕捩", "右ひじ"),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_ARM_TWIST = BoneSetting(
        name="右腕捩",
        parents=("右腕",),
        display_tail=MVector3D(0, 1, 0),
        tails=("右ひじ",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.HAS_FIXED_AXIS,
    )
    RIGHT_ARM_TWIST1 = BoneSetting(
        name="右腕捩1",
        parents=("右腕",),
        display_tail=MVector3D(0, 1, 0),
        tails=("右ひじ",),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.HAS_FIXED_AXIS,
    )
    RIGHT_ARM_TWIST2 = BoneSetting(
        name="右腕捩2",
        parents=("右腕",),
        display_tail=MVector3D(0, 1, 0),
        tails=("右ひじ",),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.HAS_FIXED_AXIS,
    )
    RIGHT_ARM_TWIST3 = BoneSetting(
        name="右腕捩3",
        parents=("右腕",),
        display_tail=MVector3D(0, 1, 0),
        tails=("右ひじ",),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.HAS_FIXED_AXIS,
    )
    RIGHT_ELBOW = BoneSetting(
        name="右ひじ",
        parents=("右腕捩", "右腕"),
        display_tail=("右手捩", "右手首"),
        tails=("右手捩", "右手首"),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_HAND_TWIST = BoneSetting(
        name="右手捩",
        parents=("右ひじ",),
        display_tail=MVector3D(0, 1, 0),
        tails=("右手首",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.HAS_FIXED_AXIS,
    )
    RIGHT_HAND_TWIST1 = BoneSetting(
        name="右手捩1",
        parents=("右ひじ",),
        display_tail=MVector3D(0, 1, 0),
        tails=("右手首",),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.HAS_FIXED_AXIS,
    )
    RIGHT_HAND_TWIST2 = BoneSetting(
        name="右手捩2",
        parents=("右ひじ",),
        display_tail=MVector3D(0, 1, 0),
        tails=("右手首",),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.HAS_FIXED_AXIS,
    )
    RIGHT_HAND_TWIST3 = BoneSetting(
        name="右手捩3",
        parents=("右ひじ",),
        display_tail=MVector3D(0, 1, 0),
        tails=("右手首",),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.HAS_FIXED_AXIS,
    )
    RIGHT_WRIST = BoneSetting(
        name="右手首",
        parents=("右手捩", "右ひじ"),
        display_tail=MVector3D(-1, 0, 0),
        tails=("右中指１", "右人指１", "右薬指１", "右小指１"),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_THUMB0 = BoneSetting(
        name="右親指０",
        parents=("右手首",),
        display_tail=("右親指１",),
        tails=("右親指１",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_THUMB1 = BoneSetting(
        name="右親指１",
        parents=("右親指０",),
        display_tail=("右親指２",),
        tails=("右親指２",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_THUMB2 = BoneSetting(
        name="右親指２",
        parents=("右親指１",),
        display_tail=MVector3D(0, 1, 0),
        tails=("右親指先",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_THUMB_TAIL = BoneSetting(
        name="右親指先",
        parents=("右親指２",),
        display_tail=MVector3D(0, 1, 0),
        tails=[],
        flag=BoneFlg.CAN_ROTATE,
    )
    RIGHT_INDEX0 = BoneSetting(
        name="右人指１",
        parents=("右手首",),
        display_tail=("右人指２",),
        tails=("右人指３",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_INDEX1 = BoneSetting(
        name="右人指２",
        parents=("右人指１",),
        display_tail=("右人指３",),
        tails=("右人指３",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_INDEX2 = BoneSetting(
        name="右人指３",
        parents=("右人指２",),
        display_tail=MVector3D(0, 1, 0),
        tails=("右人指先",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_INDEX_TAIL = BoneSetting(
        name="右人指先",
        parents=("右人指３",),
        display_tail=MVector3D(0, 1, 0),
        tails=[],
        flag=BoneFlg.CAN_ROTATE,
    )
    RIGHT_MIDDLE0 = BoneSetting(
        name="右中指１",
        parents=("右手首",),
        display_tail=("右中指２",),
        tails=("右中指３",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_MIDDLE1 = BoneSetting(
        name="右中指２",
        parents=("右中指１",),
        display_tail=("右中指３",),
        tails=("右中指３",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_MIDDLE2 = BoneSetting(
        name="右中指３",
        parents=("右中指２",),
        display_tail=MVector3D(0, 1, 0),
        tails=("右中指先",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_MIDDLE_TAIL = BoneSetting(
        name="右中指先",
        parents=("右中指３",),
        display_tail=MVector3D(0, 1, 0),
        tails=[],
        flag=BoneFlg.CAN_ROTATE,
    )
    RIGHT_RING0 = BoneSetting(
        name="右薬指１",
        parents=("右手首",),
        display_tail=("右薬指２",),
        tails=("右薬指３",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_RING1 = BoneSetting(
        name="右薬指２",
        parents=("右薬指１",),
        display_tail=("右薬指３",),
        tails=("右薬指３",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_RING2 = BoneSetting(
        name="右薬指３",
        parents=("右薬指２",),
        display_tail=MVector3D(0, 1, 0),
        tails=("右薬指先",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_RING_TAIL = BoneSetting(
        name="右薬指先",
        parents=("右薬指３",),
        display_tail=MVector3D(0, 1, 0),
        tails=[],
        flag=BoneFlg.CAN_ROTATE,
    )
    RIGHT_PINKY0 = BoneSetting(
        name="右小指１",
        parents=("右手首",),
        display_tail=("右小指２",),
        tails=("右小指３",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_PINKY1 = BoneSetting(
        name="右小指２",
        parents=("右小指１",),
        display_tail=("右小指３",),
        tails=("右小指３",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_PINKY2 = BoneSetting(
        name="右小指３",
        parents=("右小指２",),
        display_tail=MVector3D(0, 1, 0),
        tails=("右小指先",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_PINKY_TAIL = BoneSetting(
        name="右小指先",
        parents=("右小指３",),
        display_tail=MVector3D(0, 1, 0),
        tails=[],
        flag=BoneFlg.CAN_ROTATE,
    )
    RIGHT_WAIST_CANCEL = BoneSetting(
        name="腰キャンセル右",
        parents=("足中心", "下半身"),
        display_tail=MVector3D(0, -1, 0),
        tails=("右足",),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.CAN_MANIPULATE | BoneFlg.IS_EXTERNAL_ROTATION,
    )
    RIGHT_LEG = BoneSetting(
        name="右足",
        parents=("腰キャンセル右", "足中心", "下半身"),
        display_tail=("右ひざ",),
        tails=("右ひざ",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_KNEE = BoneSetting(
        name="右ひざ",
        parents=("右足",),
        display_tail=("右足首",),
        tails=("右足首",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_ANKLE = BoneSetting(
        name="右足首",
        parents=("右ひざ",),
        display_tail=("右つま先",),
        tails=("右つま先",),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.CAN_MANIPULATE | BoneFlg.IS_VISIBLE,
    )
    RIGHT_TOE = BoneSetting(
        name="右つま先",
        parents=("右足首",),
        display_tail=MVector3D(0, -1, 0),
        tails=[],
        flag=BoneFlg.CAN_ROTATE | BoneFlg.CAN_MANIPULATE | BoneFlg.IS_VISIBLE,
    )
    RIGHT_LEG_D = BoneSetting(
        name="右足D",
        parents=("腰キャンセル右", "下半身"),
        display_tail=("右ひざD",),
        tails=("右ひざD",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.IS_EXTERNAL_ROTATION
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_KNEE_D = BoneSetting(
        name="右ひざD",
        parents=("右足D",),
        display_tail=("右足首D",),
        tails=("右足首D",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.IS_EXTERNAL_ROTATION
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_ANKLE_D = BoneSetting(
        name="右足首D",
        parents=("右ひざD",),
        display_tail=MVector3D(0, -1, 0),
        tails=("右足先EX",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.IS_EXTERNAL_ROTATION
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_TOE_EX = BoneSetting(
        name="右足先EX",
        parents=("右足首D",),
        display_tail=MVector3D(0, -1, 0),
        tails=[],
        flag=BoneFlg.CAN_ROTATE | BoneFlg.CAN_MANIPULATE | BoneFlg.IS_VISIBLE,
    )
    RIGHT_LEG_IK_PARENT = BoneSetting(
        name="右足IK親",
        parents=("全ての親",),
        display_tail=MVector3D(0, 1, 0),
        tails=("右足ＩＫ",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_TRANSLATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE,
    )
    RIGHT_LEG_IK = BoneSetting(
        name="右足ＩＫ",
        parents=("右足IK親", "全ての親"),
        display_tail=("右つま先ＩＫ",),
        tails=("右つま先ＩＫ",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_TRANSLATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.IS_IK
        | BoneFlg.TAIL_IS_BONE,
    )
    RIGHT_TOE_IK = BoneSetting(
        name="右つま先ＩＫ",
        parents=("右足ＩＫ",),
        display_tail=MVector3D(0, -1, 0),
        tails=[],
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_TRANSLATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.IS_IK,
    )

    LEFT_BUST = BoneSetting(
        name="左胸",
        parents=("上半身3", "上半身2", "上半身"),
        display_tail=MVector3D(0, 0, -1),
        tails=[],
        flag=BoneFlg.CAN_ROTATE | BoneFlg.CAN_MANIPULATE | BoneFlg.IS_VISIBLE,
    )
    LEFT_SHOULDER_ROOT = BoneSetting(
        name="左肩根元",
        parents=("首根元",),
        display_tail=MVector3D(0, 1, 0),
        tails=("左肩",),
        flag=BoneFlg.CAN_ROTATE,
    )
    LEFT_SHOULDER_P = BoneSetting(
        name="左肩P",
        parents=("左肩根元", "首根元"),
        display_tail=MVector3D(0, 1, 0),
        tails=("左腕",),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.CAN_MANIPULATE | BoneFlg.IS_VISIBLE,
    )
    LEFT_SHOULDER = BoneSetting(
        name="左肩",
        parents=("左肩P", "左肩根元"),
        display_tail=("左腕",),
        tails=("左腕",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_SHOULDER_C = BoneSetting(
        name="左肩C",
        parents=("左肩",),
        display_tail=MVector3D(0, 1, 0),
        tails=("左ひじ",),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.IS_EXTERNAL_ROTATION,
    )
    LEFT_ARM = BoneSetting(
        name="左腕",
        parents=("左肩C", "左肩"),
        display_tail=("左腕捩", "左ひじ"),
        tails=("左腕捩", "左ひじ"),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_ARM_TWIST = BoneSetting(
        name="左腕捩",
        parents=("左腕",),
        display_tail=MVector3D(0, 1, 0),
        tails=("左ひじ",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.HAS_FIXED_AXIS,
    )
    LEFT_ARM_TWIST1 = BoneSetting(
        name="左腕捩1",
        parents=("左腕",),
        display_tail=MVector3D(0, 1, 0),
        tails=("左ひじ",),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.HAS_FIXED_AXIS,
    )
    LEFT_ARM_TWIST2 = BoneSetting(
        name="左腕捩2",
        parents=("左腕",),
        display_tail=MVector3D(0, 1, 0),
        tails=("左ひじ",),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.HAS_FIXED_AXIS,
    )
    LEFT_ARM_TWIST3 = BoneSetting(
        name="左腕捩3",
        parents=("左腕",),
        display_tail=MVector3D(0, 1, 0),
        tails=("左ひじ",),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.HAS_FIXED_AXIS,
    )
    LEFT_ELBOW = BoneSetting(
        name="左ひじ",
        parents=("左腕捩", "左腕"),
        display_tail=("左手捩", "左手首"),
        tails=("左手捩", "左手首"),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_HAND_TWIST = BoneSetting(
        name="左手捩",
        parents=("左ひじ",),
        display_tail=MVector3D(0, 1, 0),
        tails=("左手首",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.HAS_FIXED_AXIS,
    )
    LEFT_HAND_TWIST1 = BoneSetting(
        name="左手捩1",
        parents=("左ひじ",),
        display_tail=MVector3D(0, 1, 0),
        tails=("左手首",),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.HAS_FIXED_AXIS,
    )
    LEFT_HAND_TWIST2 = BoneSetting(
        name="左手捩2",
        parents=("左ひじ",),
        display_tail=MVector3D(0, 1, 0),
        tails=("左手首",),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.HAS_FIXED_AXIS,
    )
    LEFT_HAND_TWIST3 = BoneSetting(
        name="左手捩3",
        parents=("左ひじ",),
        display_tail=MVector3D(0, 1, 0),
        tails=("左手首",),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.HAS_FIXED_AXIS,
    )
    LEFT_WRIST = BoneSetting(
        name="左手首",
        parents=("左手捩", "左ひじ"),
        display_tail=MVector3D(1, 0, 0),
        tails=("左中指１", "左人指１", "左薬指１", "左小指１"),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_THUMB0 = BoneSetting(
        name="左親指０",
        parents=("左手首",),
        display_tail=("左親指１",),
        tails=("左親指１",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_THUMB1 = BoneSetting(
        name="左親指１",
        parents=("左親指０",),
        display_tail=("左親指２",),
        tails=("左親指２",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_THUMB2 = BoneSetting(
        name="左親指２",
        parents=("左親指１",),
        display_tail=MVector3D(0, 1, 0),
        tails=("左親指先",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_THUMB_TAIL = BoneSetting(
        name="左親指先",
        parents=("左親指２",),
        display_tail=MVector3D(0, 1, 0),
        tails=[],
        flag=BoneFlg.CAN_ROTATE,
    )
    LEFT_INDEX0 = BoneSetting(
        name="左人指１",
        parents=("左手首",),
        display_tail=("左人指２",),
        tails=("左人指３",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_INDEX1 = BoneSetting(
        name="左人指２",
        parents=("左人指１",),
        display_tail=("左人指３",),
        tails=("左人指３",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_INDEX2 = BoneSetting(
        name="左人指３",
        parents=("左人指２",),
        display_tail=MVector3D(0, 1, 0),
        tails=("左人指先",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_INDEX_TAIL = BoneSetting(
        name="左人指先",
        parents=("左人指３",),
        display_tail=MVector3D(0, 1, 0),
        tails=[],
        flag=BoneFlg.CAN_ROTATE,
    )
    LEFT_MIDDLE0 = BoneSetting(
        name="左中指１",
        parents=("左手首",),
        display_tail=("左中指２",),
        tails=("左中指３",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_MIDDLE1 = BoneSetting(
        name="左中指２",
        parents=("左中指１",),
        display_tail=("左中指３",),
        tails=("左中指３",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_MIDDLE2 = BoneSetting(
        name="左中指３",
        parents=("左中指２",),
        display_tail=MVector3D(0, 1, 0),
        tails=("左中指先",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_MIDDLE_TAIL = BoneSetting(
        name="左中指先",
        parents=("左中指３",),
        display_tail=MVector3D(0, 1, 0),
        tails=[],
        flag=BoneFlg.CAN_ROTATE,
    )
    LEFT_RING0 = BoneSetting(
        name="左薬指１",
        parents=("左手首",),
        display_tail=("左薬指２",),
        tails=("左薬指３",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_RING1 = BoneSetting(
        name="左薬指２",
        parents=("左薬指１",),
        display_tail=("左薬指３",),
        tails=("左薬指３",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_RING2 = BoneSetting(
        name="左薬指３",
        parents=("左薬指２",),
        display_tail=MVector3D(0, 1, 0),
        tails=("左薬指先",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_RING_TAIL = BoneSetting(
        name="左薬指先",
        parents=("左薬指３",),
        display_tail=MVector3D(0, 1, 0),
        tails=[],
        flag=BoneFlg.CAN_ROTATE,
    )
    LEFT_PINKY0 = BoneSetting(
        name="左小指１",
        parents=("左手首",),
        display_tail=("左小指２",),
        tails=("左小指３",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_PINKY1 = BoneSetting(
        name="左小指２",
        parents=("左小指１",),
        display_tail=("左小指３",),
        tails=("左小指３",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_PINKY2 = BoneSetting(
        name="左小指３",
        parents=("左小指２",),
        display_tail=MVector3D(0, 1, 0),
        tails=("左小指先",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_PINKY_TAIL = BoneSetting(
        name="左小指先",
        parents=("左小指３",),
        display_tail=MVector3D(0, 1, 0),
        tails=[],
        flag=BoneFlg.CAN_ROTATE,
    )
    LEFT_WAIST_CANCEL = BoneSetting(
        name="腰キャンセル左",
        parents=("足中心", "下半身"),
        display_tail=MVector3D(0, -1, 0),
        tails=("左足",),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.CAN_MANIPULATE | BoneFlg.IS_EXTERNAL_ROTATION,
    )
    LEFT_LEG = BoneSetting(
        name="左足",
        parents=("腰キャンセル左", "足中心", "下半身"),
        display_tail=("左ひざ",),
        tails=("左ひざ",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_KNEE = BoneSetting(
        name="左ひざ",
        parents=("左足",),
        display_tail=("左足首",),
        tails=("左足首",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_ANKLE = BoneSetting(
        name="左足首",
        parents=("左ひざ",),
        display_tail=("左つま先",),
        tails=("左つま先",),
        flag=BoneFlg.CAN_ROTATE | BoneFlg.CAN_MANIPULATE | BoneFlg.IS_VISIBLE,
    )
    LEFT_TOE = BoneSetting(
        name="左つま先",
        parents=("左足首",),
        display_tail=MVector3D(0, -1, 0),
        tails=[],
        flag=BoneFlg.CAN_ROTATE | BoneFlg.CAN_MANIPULATE | BoneFlg.IS_VISIBLE,
    )
    LEFT_LEG_D = BoneSetting(
        name="左足D",
        parents=("腰キャンセル左", "下半身"),
        display_tail=("左ひざD",),
        tails=("左ひざD",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.IS_EXTERNAL_ROTATION
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_KNEE_D = BoneSetting(
        name="左ひざD",
        parents=("左足D",),
        display_tail=("左足首D",),
        tails=("左足首D",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.IS_EXTERNAL_ROTATION
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_ANKLE_D = BoneSetting(
        name="左足首D",
        parents=("左ひざD",),
        display_tail=MVector3D(0, -1, 0),
        tails=("左足先EX",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.IS_EXTERNAL_ROTATION
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_TOE_EX = BoneSetting(
        name="左足先EX",
        parents=("左足首D",),
        display_tail=MVector3D(0, -1, 0),
        tails=[],
        flag=BoneFlg.CAN_ROTATE | BoneFlg.CAN_MANIPULATE | BoneFlg.IS_VISIBLE,
    )
    LEFT_LEG_IK_PARENT = BoneSetting(
        name="左足IK親",
        parents=("全ての親",),
        display_tail=MVector3D(0, 1, 0),
        tails=("左足ＩＫ",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_TRANSLATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE,
    )
    LEFT_LEG_IK = BoneSetting(
        name="左足ＩＫ",
        parents=("左足IK親", "全ての親"),
        display_tail=("左つま先ＩＫ",),
        tails=("左つま先ＩＫ",),
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_TRANSLATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.IS_IK
        | BoneFlg.TAIL_IS_BONE,
    )
    LEFT_TOE_IK = BoneSetting(
        name="左つま先ＩＫ",
        parents=("左足ＩＫ",),
        display_tail=MVector3D(0, -1, 0),
        tails=[],
        flag=BoneFlg.CAN_ROTATE
        | BoneFlg.CAN_TRANSLATE
        | BoneFlg.CAN_MANIPULATE
        | BoneFlg.IS_VISIBLE
        | BoneFlg.IS_IK,
    )


STANDARD_BONE_NAMES: dict[str, BoneSetting] = dict(
    [(bs.value.name, bs.value) for bs in BoneSettings]
)
"""準標準ボーン名前とEnumのキーの辞書"""
