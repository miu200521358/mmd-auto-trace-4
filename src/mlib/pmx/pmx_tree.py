from typing import Optional

from mlib.core.collection import BaseIndexNameDictModel, BaseIndexNameDictWrapperModel
from mlib.core.math import MVector3D
from mlib.pmx.bone_setting import STANDARD_BONE_NAMES
from mlib.pmx.pmx_part import Bone


class BoneTree(BaseIndexNameDictModel[Bone]):
    """ボーンリンク"""

    def __init__(self, name: str = "") -> None:
        super().__init__(name)

    def get_relative_position(self, key: int) -> MVector3D:
        """
        該当ボーンの相対位置を取得

        Parameters
        ----------
        key : int
            ボーンINDEX

        Returns
        -------
        ボーンの親ボーンから見た相対位置
        """
        if key not in self:
            return MVector3D()

        bone = self[key]
        if bone.parent_index not in self:
            return bone.position

        return bone.position - self[bone.parent_index]

    def filter(
        self, start_bone_name: str, end_bone_name: Optional[str] = None
    ) -> "BoneTree":
        start_index = [
            i for i, b in enumerate(self.data.values()) if b.name == start_bone_name
        ][0]
        if end_bone_name:
            end_index = [
                i for i, b in enumerate(self.data.values()) if b.name == end_bone_name
            ][0]
        else:
            end_bone_name = self.last_name
            end_index = self.last_index
        new_tree = BoneTree(end_bone_name)
        for i, t in enumerate(self):
            if start_index <= i <= end_index:
                new_tree.append(t)
        return new_tree

    def get_standard(self) -> "BoneTree":
        """準標準ボーンのみを取得する"""

        new_tree = BoneTree(self.last_name)
        for t in self:
            if t.name in STANDARD_BONE_NAMES:
                new_tree.append(t)

        return new_tree


class BoneTrees(BaseIndexNameDictWrapperModel[BoneTree]):
    """
    BoneTreeリスト
    """

    def __init__(self) -> None:
        """モデル辞書"""
        super().__init__()

    def create(self, key: str) -> BoneTree:
        return BoneTree(key)

    def is_in_standard(self, name: str) -> bool:
        """準標準までのボーンツリーに含まれるボーンであるか否か"""
        # チェック対象ボーンが含まれるボーンツリー
        if name in STANDARD_BONE_NAMES:
            return True

        for bone_tree in [
            bt for bt in self.data.values() if name in bt.names and name != bt.last_name
        ]:
            bone_find_index = [i for i, b in enumerate(bone_tree) if b.name == name][0]
            is_parent_standard = False
            is_child_standard = False
            # 親系統、子系統どちらにも準標準ボーンが含まれている場合、TRUE
            for parent_name in bone_tree.names[:bone_find_index]:
                if parent_name in STANDARD_BONE_NAMES:
                    is_parent_standard = True
                    break
            for child_name in bone_tree.names[bone_find_index + 1 :]:
                if child_name in STANDARD_BONE_NAMES:
                    is_child_standard = True
                    break
            if is_parent_standard and is_child_standard:
                return True

        return False

    def has_standard_child(self, name: str) -> bool:
        """準標準の子どもをもつボーンであるか否か"""
        # チェック対象ボーンが含まれるボーンツリー
        if name in STANDARD_BONE_NAMES:
            return False

        for bone_tree in [
            bt for bt in self.data.values() if name in bt.names and name != bt.last_name
        ]:
            bone_find_index = [i for i, b in enumerate(bone_tree) if b.name == name][0]
            # 子系統に準標準ボーンが含まれている場合、TRUE
            for child_name in bone_tree.names[bone_find_index + 1 :]:
                if child_name in STANDARD_BONE_NAMES:
                    return True

        return False

    def get_standard_children(self, name: str) -> list[Bone]:
        """子ボーンの準標準ボーンを所得"""
        bones: list[Bone] = []
        for bone_tree in [
            bt for bt in self.data.values() if name in bt.names and name != bt.last_name
        ]:
            bone_find_index = [i for i, b in enumerate(bone_tree) if b.name == name][0]
            # 子系統に準標準ボーンが含まれている場合、TRUE
            for child_name in bone_tree.names[bone_find_index + 1 :]:
                if child_name in STANDARD_BONE_NAMES:
                    bones.append(bone_tree[child_name])

        return bones

    def is_standard_tail(self, name: str) -> bool:
        """準標準までのボーンツリーに含まれるボーンの表示先であるか否か"""
        if name in STANDARD_BONE_NAMES:
            # そもそも自分が準標準ボーンならばFalse
            return False

        bone_tree = self.data[name]
        bone_find_index = [i for i, b in enumerate(bone_tree) if b.name == name][0]
        if 1 > bone_find_index:
            # そもそも子でない場合、表示先にはなり得ない
            return False

        bone = bone_tree[bone_tree.names[bone_find_index]]
        parent_bone = bone_tree[bone_tree.names[bone_find_index - 1]]

        if not self.is_in_standard(parent_bone.name):
            # そもそも親ボーンが準標準ボーンの範囲外ならばFalse
            return False

        for bt in self.data.values():
            if bt[bt.last_name].parent_index == bone.index:
                # 自分が親ボーンとして登録されている場合、False
                return False

        # 自分が準標準ボーンの範囲内の親を持ち、子ボーンがいない場合、表示先とみなす
        return True

    def get_child_bone_names(self, bone_name: str, is_standard: bool) -> list[str]:
        """指定されたボーンを親に持つ子ボーンリストの取得"""
        child_bone_names: list[str] = []

        for bone_tree in [
            bt
            for bt in self.data.values()
            if bone_name in bt.names and bone_name != bt.last_name
        ]:
            bone_find_index = [
                i for i, b in enumerate(bone_tree) if b.name == bone_name
            ][0]
            # 自分を親に持つ子ボーン名のリストを保持
            for child_name in bone_tree.names[bone_find_index + 1 :]:
                if (
                    is_standard and child_name in STANDARD_BONE_NAMES
                ) or not is_standard:
                    child_bone_names.append(child_name)

        return child_bone_names
