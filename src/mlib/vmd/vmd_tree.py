from itertools import product
from typing import Iterator, Optional

import numpy as np

from mlib.core.math import MMatrix4x4, MQuaternion, MVector3D


class VmdBoneFrameTree:
    __slots__ = (
        "fno",
        "bone_index",
        "bone_name",
        "global_matrix_ary",
        "local_matrix_ary",
        "frame_position_matrix_ary",
        "frame_rotation_matrix_ary",
        "frame_fk_rotation_matrix_ary",
        "cache_global_matrix",
        "cache_local_matrix",
        "cache_global_matrix_no_scale",
        "cache_local_matrix_no_scale",
        "cache_position",
        "cache_frame_position",
        "cache_frame_rotation",
        "cache_frame_fk_rotation",
    )

    def __init__(
        self,
        fno: int,
        bone_index: int,
        bone_name: str,
        global_matrix_ary: np.ndarray,
        local_matrix_ary: np.ndarray,
        frame_position_matrix_ary: np.ndarray,
        frame_rotation_matrix_ary: np.ndarray,
        frame_fk_rotation_matrix_ary: np.ndarray,
    ) -> None:
        self.fno = fno
        self.bone_index = bone_index
        self.bone_name = bone_name
        self.global_matrix_ary = global_matrix_ary
        self.local_matrix_ary = local_matrix_ary
        self.frame_position_matrix_ary = frame_position_matrix_ary
        self.frame_rotation_matrix_ary = frame_rotation_matrix_ary
        self.frame_fk_rotation_matrix_ary = frame_fk_rotation_matrix_ary
        self.cache_global_matrix: Optional[MMatrix4x4] = None
        self.cache_local_matrix: Optional[MMatrix4x4] = None
        self.cache_global_matrix_no_scale: Optional[MMatrix4x4] = None
        self.cache_local_matrix_no_scale: Optional[MMatrix4x4] = None
        self.cache_position: Optional[MVector3D] = None
        self.cache_frame_position: Optional[MVector3D] = None
        self.cache_frame_rotation: Optional[MQuaternion] = None
        self.cache_frame_fk_rotation: Optional[MQuaternion] = None

    @property
    def global_matrix(self) -> MMatrix4x4:
        if self.cache_global_matrix is not None:
            return self.cache_global_matrix
        self.cache_global_matrix = MMatrix4x4(self.global_matrix_ary)
        return self.cache_global_matrix

    @property
    def local_matrix(self) -> MMatrix4x4:
        if self.cache_local_matrix is not None:
            return self.cache_local_matrix
        self.cache_local_matrix = MMatrix4x4(self.local_matrix_ary)
        return self.cache_local_matrix

    @property
    def global_matrix_no_scale(self) -> MMatrix4x4:
        if self.cache_global_matrix_no_scale is not None:
            return self.cache_global_matrix_no_scale

        global_matrix = self.global_matrix

        rot = global_matrix.to_quaternion()
        pos = global_matrix.to_position()

        no_scale_mat = MMatrix4x4()
        no_scale_mat.translate(pos)
        no_scale_mat.rotate(rot)
        self.cache_global_matrix_no_scale = no_scale_mat
        return self.cache_global_matrix_no_scale

    @property
    def local_matrix_no_scale(self) -> MMatrix4x4:
        if self.cache_local_matrix_no_scale is not None:
            return self.cache_local_matrix_no_scale

        local_matrix = self.local_matrix

        rot = local_matrix.to_quaternion()
        pos = local_matrix.to_position()

        no_scale_mat = MMatrix4x4()
        no_scale_mat.translate(pos)
        no_scale_mat.rotate(rot)
        self.cache_local_matrix_no_scale = no_scale_mat
        return self.cache_local_matrix_no_scale

    @property
    def position(self) -> MVector3D:
        if self.cache_position is not None:
            return self.cache_position
        self.cache_position = MVector3D(*self.global_matrix_ary[:3, 3])
        return self.cache_position

    @property
    def frame_position(self) -> MVector3D:
        if self.cache_frame_position is not None:
            return self.cache_frame_position
        self.cache_frame_position = MVector3D(*self.frame_position_matrix_ary[:3, 3])
        return self.cache_frame_position

    @property
    def frame_rotation(self) -> MQuaternion:
        if self.cache_frame_rotation is not None:
            return self.cache_frame_rotation

        self.cache_frame_rotation = MMatrix4x4(
            self.frame_rotation_matrix_ary
        ).to_quaternion()
        return self.cache_frame_rotation

    @property
    def frame_fk_rotation(self) -> MQuaternion:
        if self.cache_frame_fk_rotation is not None:
            return self.cache_frame_fk_rotation

        self.cache_frame_fk_rotation = MMatrix4x4(
            self.frame_fk_rotation_matrix_ary
        ).to_quaternion()
        return self.cache_frame_fk_rotation


class VmdBoneFrameTrees:
    __slots__ = (
        "_names",
        "_name_indexes",
        "_indexes",
        "_result_global_matrixes",
        "_result_matrixes",
        "_motion_bone_poses",
        "_motion_bone_qqs",
        "_motion_bone_fk_qqs",
        "_cache_frames",
    )

    def __init__(
        self,
        bone_dict: dict[str, int],
        fnos: list[int],
        result_global_matrixes: np.ndarray,
        result_matrixes: np.ndarray,
        motion_bone_poses: np.ndarray,
        motion_bone_qqs: np.ndarray,
        motion_bone_fk_qqs: np.ndarray,
    ) -> None:
        """
        ボーン変形行列生成

        Parameters
        ----------
        bone_names : list[str]
            ボーン名
        fnos : list[int]
            キーフレ番号リスト
        result_global_matrixes : np.ndarray
            自身のボーン位置を加味したグローバル行列
        result_matrixes : np.ndarray
            自身のボーン位置を加味しないローカル行列
        motion_bone_poses : np.ndarray
            キーフレ時点の位置
        motion_bone_qqs : np.ndarray
            キーフレ時点の回転（FK・IK・付与）
        """
        self._names = bone_dict
        self._name_indexes: dict[int, str] = dict(
            [(idx, name) for name, idx in bone_dict.items()]
        )
        self._indexes: dict[int, int] = dict(
            [(fno, fidx) for fidx, fno in enumerate(fnos)]
        )
        self._result_global_matrixes = result_global_matrixes
        self._result_matrixes = result_matrixes
        self._motion_bone_poses = motion_bone_poses
        self._motion_bone_qqs = motion_bone_qqs
        self._motion_bone_fk_qqs = motion_bone_fk_qqs
        self._cache_frames: dict[tuple[int, int], VmdBoneFrameTree] = {}

    def __getitem__(self, key: tuple[str, int]) -> VmdBoneFrameTree:
        bone_name, fno = key
        bone_index = self._names[bone_name]
        fidx = self._indexes[fno]

        if (bone_index, fidx) in self._cache_frames:
            return self._cache_frames[(bone_index, fidx)]

        vbf = VmdBoneFrameTree(
            fno,
            bone_index,
            bone_name,
            self._result_global_matrixes[fidx, bone_index],
            self._result_matrixes[fidx, bone_index],
            self._motion_bone_poses[fidx, bone_index],
            self._motion_bone_qqs[fidx, bone_index],
            self._motion_bone_fk_qqs[fidx, bone_index],
        )
        self._cache_frames[(bone_index, fidx)] = vbf

        return vbf

    def exists(self, bone_name: str, fno: int) -> bool:
        """既に該当ボーンの情報が登録されているか"""
        return bone_name in self._names and fno in self._indexes

    def __len__(self) -> int:
        return len(self._indexes)

    def __iter__(self) -> Iterator[VmdBoneFrameTree]:
        return iter(
            self[self._name_indexes[bone_index], fno]
            for bone_index, fno in product(
                sorted(self._names.values()), self._indexes.keys()
            )
        )

    @property
    def indexes(self) -> list[int]:
        return sorted(self._indexes.keys())

    @property
    def names(self) -> list[str]:
        return list(self._names.keys())
