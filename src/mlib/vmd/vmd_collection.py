import math
import os
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from enum import IntEnum, auto
from functools import lru_cache
from itertools import product
from math import radians
from typing import Iterable, Optional, Union

import numpy as np
from numpy.linalg import inv

from mlib.core.collection import (
    BaseHashModel,
    BaseIndexNameDictModel,
    BaseIndexNameDictWrapperModel,
)
from mlib.core.interpolation import split_interpolation
from mlib.core.logger import MLogger
from mlib.core.math import (
    MMatrix4x4,
    MQuaternion,
    MQuaternionOrder,
    MVector3D,
    MVector4D,
    calc_list_by_ratio,
)
from mlib.pmx.pmx_collection import PmxModel
from mlib.pmx.pmx_part import (
    Bone,
    BoneMorphOffset,
    GroupMorphOffset,
    Material,
    MaterialMorphCalcMode,
    MaterialMorphOffset,
    MorphType,
    ShaderMaterial,
    UvMorphOffset,
    VertexMorphOffset,
)
from mlib.pmx.shader import MShader
from mlib.service.base_worker import verify_thread
from mlib.vmd.vmd_part import (
    VmdBoneFrame,
    VmdCameraFrame,
    VmdLightFrame,
    VmdMorphFrame,
    VmdShadowFrame,
    VmdShowIkFrame,
)
from mlib.vmd.vmd_tree import VmdBoneFrameTrees

logger = MLogger(os.path.basename(__file__))


class VmdAttributes(IntEnum):
    POSITION = auto()
    ROTATION = auto()
    SCALE = auto()
    LOCAL_POSITION = auto()
    LOCAL_ROTATION = auto()
    LOCAL_SCALE = auto()


class VmdBoneNameFrames(BaseIndexNameDictModel[VmdBoneFrame]):
    """
    ボーン名別キーフレ辞書
    """

    __slots__ = (
        "data",
        "name",
        "cache",
        "_names",
        "_indexes",
        "_ik_indexes",
        "_register_indexes",
    )

    def __init__(self, name: str = "") -> None:
        super().__init__(name)
        self._ik_indexes: list[int] = []
        self._register_indexes: list[int] = []

    def __getitem__(self, key: Union[int, str]) -> VmdBoneFrame:
        if isinstance(key, str):
            return VmdBoneFrame(name=key, index=0)

        # キーフレがない場合、生成したのを返す（保持はしない）
        prev_index, middle_index, next_index = self.range_indexes(
            key, indexes=self.register_indexes
        )

        if key in self.data:
            bf = self.get_by_index(key)
            return bf

        # prevとnextの範囲内である場合、補間曲線ベースで求め直す
        return self.calc(
            prev_index,
            middle_index,
            next_index,
        )

    def cache_clear(self) -> None:
        """キャッシュクリアとしてIK情報を削除"""
        super().cache_clear()

        for index in self.data.keys():
            self.data[index].ik_rotation = None
            self.data[index].corrected_position = None
            self.data[index].corrected_rotation = None

    def append(
        self, value: VmdBoneFrame, is_sort: bool = True, is_positive_index: bool = True
    ) -> None:
        if value.ik_rotation is not None and value.index not in self._ik_indexes:
            self._ik_indexes.append(value.index)
            self._ik_indexes.sort()
        super().append(value, is_sort, is_positive_index)

        if value.register and value.index not in self._register_indexes:
            self._register_indexes.append(value.index)
            self._register_indexes.sort()

    def insert(
        self, value: VmdBoneFrame, is_sort: bool = True, is_positive_index: bool = True
    ) -> dict[int, int]:
        if value.ik_rotation is not None and value.index not in self._ik_indexes:
            self._ik_indexes.append(value.index)
            self._ik_indexes.sort()

        prev_index, middle_index, next_index = self.range_indexes(
            value.index, indexes=self.register_indexes
        )

        replaced_map: dict[int, int] = {}
        super().append(value, is_sort, is_positive_index)

        if next_index > value.index:
            # 次のキーフレが自身より後の場合、自身のキーフレがないので補間曲線を分割する
            for i, next_interpolation in enumerate(
                self.data[next_index].interpolations
            ):
                (
                    split_target_interpolation,
                    split_next_interpolation,
                ) = split_interpolation(
                    next_interpolation, prev_index, middle_index, next_index
                )
                self.data[middle_index].interpolations[i] = split_target_interpolation
                self.data[next_index].interpolations[i] = split_next_interpolation

        if value.register and value.index not in self._register_indexes:
            self._register_indexes.append(value.index)
            self._register_indexes.sort()

        return replaced_map

    @verify_thread
    def calc(self, prev_index: int, index: int, next_index: int) -> VmdBoneFrame:
        if index in self.data:
            bf = self.data[index]
            return bf

        if index in self.cache:
            bf = self.cache[index]
        else:
            bf = VmdBoneFrame(name=self.name, index=index)
            self.cache[index] = bf

        if prev_index == next_index:
            if next_index == index:
                # 全くキーフレがない場合、そのまま返す
                return bf

            # FKのprevと等しい場合、指定INDEX以前がないので、その次のをコピーして返す
            next_bf = self.data[next_index]
            bf.position = next_bf.position.copy()
            bf.local_position = next_bf.local_position.copy()
            bf.rotation = next_bf.rotation.copy()
            bf.local_rotation = next_bf.local_rotation.copy()
            bf.scale = next_bf.scale.copy()
            bf.local_scale = next_bf.local_scale.copy()
            # IKとかの計算値はコピーしない
            return bf

        prev_bf = (
            self.data[prev_index]
            if prev_index in self
            else VmdBoneFrame(name=self.name, index=prev_index)
        )
        next_bf = (
            self.data[next_index]
            if next_index in self
            else VmdBoneFrame(name=self.name, index=next_index)
        )

        # 補間結果Yは、FKキーフレ内で計算する
        ry, xy, yy, zy = next_bf.interpolations.evaluate(prev_index, index, next_index)

        # # IK用回転
        # bf.ik_rotation = self.calc_ik(prev_index, index, next_index)

        # FK用回転
        bf.rotation = MQuaternion.slerp(prev_bf.rotation, next_bf.rotation, ry)

        # ローカル回転
        bf.local_rotation = MQuaternion.slerp(
            prev_bf.local_rotation, next_bf.local_rotation, ry
        )

        # 移動・スケール・ローカル移動・ローカルスケール　は一括で計算
        (
            bf.position.vector,
            bf.scale.vector,
            bf.local_position.vector,
            bf.local_scale.vector,
        ) = calc_list_by_ratio(
            tuple(
                [
                    tuple(prev_bf.position.vector.tolist()),
                    tuple(prev_bf.scale.vector.tolist()),
                    tuple(prev_bf.local_position.vector.tolist()),
                    tuple(prev_bf.local_scale.vector.tolist()),
                ]
            ),
            tuple(
                [
                    tuple(next_bf.position.vector.tolist()),
                    tuple(next_bf.scale.vector.tolist()),
                    tuple(next_bf.local_position.vector.tolist()),
                    tuple(next_bf.local_scale.vector.tolist()),
                ]
            ),
            tuple([xy, yy, zy]),
        )

        return bf

    @property
    def register_indexes(self) -> list[int]:
        return self._register_indexes


class VmdBoneFrames(BaseIndexNameDictWrapperModel[VmdBoneNameFrames]):
    """
    ボーンキーフレ辞書
    """

    def __init__(self) -> None:
        super().__init__()

    def create(self, key: str) -> VmdBoneNameFrames:
        return VmdBoneNameFrames(name=key)

    # 88.0f / 180.0f*3.14159265f
    GIMBAL_RAD = radians(88)
    GIMBAL2_RAD = radians(88 * 2)
    QUARTER_RAD = radians(90)
    HALF_RAD = radians(180)
    FULL_RAD = radians(360)

    EYE_MAT = np.eye(4)

    def is_non_identity_matrix(self, mat: np.ndarray) -> bool:
        """行列が恒等行列でないかどうかをチェックする"""
        return not np.all(mat == self.EYE_MAT)

    @property
    def max_fno(self) -> int:
        return max([max(self[bname].indexes + [0]) for bname in self.names] + [0])

    def cache_clear(self) -> None:
        for bname in self.data.keys():
            self.data[bname].cache_clear()

    def animate_bone_matrixes(
        self,
        fnos: list[int],
        model: PmxModel,
        morph_bone_frames: Optional["VmdBoneFrames"] = None,
        bone_names: Iterable[str] = [],
        is_calc_ik: bool = True,
        out_fno_log: bool = False,
        description: str = "",
        max_worker: int = 1,
    ) -> VmdBoneFrameTrees:
        # 処理対象ボーン名取得
        target_bone_names = self.get_animate_bone_names(model, bone_names)

        # 処理対象ボーンの行列取得
        bone_dict, bone_offset_matrixes, bone_pos_matrixes = self.create_bone_matrixes(
            model, target_bone_names
        )

        if out_fno_log:
            logger.info("ボーンモーフ計算[{d}]", d=description)

        # モーフボーン操作
        if morph_bone_frames is not None:
            (
                is_morph_identity_poses,
                is_morph_identity_qqs,
                is_morph_identity_scales,
                is_morph_identity_local_poses,
                is_morph_identity_local_qqs,
                is_morph_identity_local_scales,
                morph_bone_poses,
                morph_bone_qqs,
                morph_bone_scales,
                morph_bone_local_poses,
                morph_bone_local_qqs,
                morph_bone_local_scales,
                _,
            ) = morph_bone_frames.get_bone_matrixes(
                fnos,
                model,
                target_bone_names,
                out_fno_log=out_fno_log,
                description=description + "|Morph",
            )
        else:
            morph_row = len(fnos)
            morph_col = len(model.bones)
            is_morph_identity_poses = True
            is_morph_identity_qqs = True
            is_morph_identity_scales = True
            is_morph_identity_local_poses = True
            is_morph_identity_local_qqs = True
            is_morph_identity_local_scales = True
            morph_bone_poses = np.full((morph_row, morph_col, 4, 4), np.eye(4))
            morph_bone_qqs = np.full((morph_row, morph_col, 4, 4), np.eye(4))
            morph_bone_scales = np.full((morph_row, morph_col, 4, 4), np.eye(4))
            morph_bone_local_poses = np.full((morph_row, morph_col, 4, 4), np.eye(4))
            morph_bone_local_qqs = np.full((morph_row, morph_col, 4, 4), np.eye(4))
            morph_bone_local_scales = np.full((morph_row, morph_col, 4, 4), np.eye(4))

        if out_fno_log:
            logger.info("ボーンモーション計算[{d}]", d=description)

        if is_calc_ik:
            # IK計算
            self.calc_ik_rotations(
                fnos, model, target_bone_names, out_fno_log, description, max_worker
            )

        # モーションボーン操作
        if 1 < len(fnos) and 1 < max_worker:
            # 複数キーフレを並列で求められる条件である場合、並列処理で求める
            (
                is_motion_identity_poses,
                is_motion_identity_qqs,
                is_motion_identity_scales,
                is_motion_identity_local_poses,
                is_motion_identity_local_qqs,
                is_motion_identity_local_scales,
                motion_bone_poses,
                motion_bone_qqs,
                motion_bone_scales,
                motion_bone_local_poses,
                motion_bone_local_qqs,
                motion_bone_local_scales,
                motion_bone_fk_qqs,
            ) = self.get_bone_matrixes_parallel(
                fnos,
                model,
                target_bone_names,
                out_fno_log=out_fno_log,
                description=description + "|Bone",
                max_worker=max_worker,
            )
        else:
            (
                is_motion_identity_poses,
                is_motion_identity_qqs,
                is_motion_identity_scales,
                is_motion_identity_local_poses,
                is_motion_identity_local_qqs,
                is_motion_identity_local_scales,
                motion_bone_poses,
                motion_bone_qqs,
                motion_bone_scales,
                motion_bone_local_poses,
                motion_bone_local_qqs,
                motion_bone_local_scales,
                motion_bone_fk_qqs,
            ) = self.get_bone_matrixes(
                fnos,
                model,
                target_bone_names,
                out_fno_log=out_fno_log,
                description=description + "|Bone",
            )

        # ボーン変形行列
        matrixes = np.full(motion_bone_poses.shape, np.eye(4))

        # モーフの適用
        matrixes = self.calc_bone_matrixes_array(
            is_morph_identity_poses,
            is_morph_identity_qqs,
            is_morph_identity_scales,
            is_morph_identity_local_poses,
            is_morph_identity_local_qqs,
            is_morph_identity_local_scales,
            morph_bone_poses,
            morph_bone_qqs,
            morph_bone_scales,
            morph_bone_local_poses,
            morph_bone_local_qqs,
            morph_bone_local_scales,
            np.full(motion_bone_poses.shape, np.eye(4)),
        )

        return self.calc_bone_matrixes(
            fnos,
            model,
            bone_dict,
            bone_offset_matrixes,
            bone_pos_matrixes,
            is_motion_identity_poses,
            is_motion_identity_qqs,
            is_motion_identity_scales,
            is_motion_identity_local_poses,
            is_motion_identity_local_qqs,
            is_motion_identity_local_scales,
            motion_bone_poses,
            motion_bone_qqs,
            motion_bone_scales,
            motion_bone_local_poses,
            motion_bone_local_qqs,
            motion_bone_local_scales,
            motion_bone_fk_qqs,
            matrixes,
            out_fno_log,
            description,
        )

    def get_animate_bone_names(
        self, model: PmxModel, bone_names: list[str]
    ) -> list[str]:
        if not bone_names:
            return model.bones.names
        else:
            return [
                model.bones[bone_index].name
                for bone_index in sorted(
                    set(
                        [
                            bone_index
                            for bone_name in bone_names
                            for bone_index in model.bones[
                                bone_name
                            ].relative_bone_indexes
                        ]
                    )
                )
            ]

    def create_bone_matrixes(
        self,
        model: PmxModel,
        target_bone_names: list[str],
    ) -> tuple[dict[str, int], list[tuple[int, np.ndarray]], np.ndarray]:
        bone_offset_matrixes: list[tuple[int, np.ndarray]] = []
        bone_pos_matrixes = np.full((1, len(model.bones.indexes), 4, 4), np.eye(4))
        bone_dict: dict[str, int] = {}
        for bone_name in target_bone_names:
            bone = model.bones[bone_name]
            bone_pos_matrixes[0, bone.index, :3, 3] = bone.position.vector
            bone_offset_matrixes.append((bone.index, bone.offset_matrix))
            bone_dict[bone.name] = bone.index
        return bone_dict, bone_offset_matrixes, bone_pos_matrixes

    def calc_bone_matrixes_array(
        self,
        is_identity_poses: bool,
        is_identity_qqs: bool,
        is_identity_scales: bool,
        is_identity_local_poses: bool,
        is_identity_local_qqs: bool,
        is_identity_local_scales: bool,
        bone_poses: np.ndarray,
        bone_qqs: np.ndarray,
        bone_scales: np.ndarray,
        bone_local_poses: np.ndarray,
        bone_local_qqs: np.ndarray,
        bone_local_scales: np.ndarray,
        matrixes: np.ndarray = None,
    ) -> np.ndarray:
        if matrixes is None:
            matrixes = np.full(bone_poses.shape, np.eye(4))

        if not is_identity_poses:
            matrixes @= bone_poses
        if not is_identity_local_poses:
            matrixes @= bone_local_poses
        if not is_identity_qqs:
            matrixes @= bone_qqs
        if not is_identity_local_qqs:
            matrixes @= bone_local_qqs
        if not is_identity_scales:
            matrixes @= bone_scales
        if not is_identity_local_scales:
            matrixes @= bone_local_scales

        return matrixes

    def calc_bone_matrixes(
        self,
        fnos: list[int],
        model: PmxModel,
        bone_dict: dict[str, int],
        bone_offset_matrixes: list[tuple[int, np.ndarray]],
        bone_pos_matrixes: np.ndarray,
        is_motion_identity_poses: bool,
        is_motion_identity_qqs: bool,
        is_motion_identity_scales: bool,
        is_motion_identity_local_poses: bool,
        is_motion_identity_local_qqs: bool,
        is_motion_identity_local_scales: bool,
        motion_bone_poses: np.ndarray,
        motion_bone_qqs: np.ndarray,
        motion_bone_scales: np.ndarray,
        motion_bone_local_poses: np.ndarray,
        motion_bone_local_qqs: np.ndarray,
        motion_bone_local_scales: np.ndarray,
        motion_bone_fk_qqs: np.ndarray,
        matrixes: np.ndarray = None,
        out_fno_log: bool = False,
        description: str = "",
    ) -> VmdBoneFrameTrees:
        matrixes = self.calc_bone_matrixes_array(
            is_motion_identity_poses,
            is_motion_identity_qqs,
            is_motion_identity_scales,
            is_motion_identity_local_poses,
            is_motion_identity_local_qqs,
            is_motion_identity_local_scales,
            motion_bone_poses,
            motion_bone_qqs,
            motion_bone_scales,
            motion_bone_local_poses,
            motion_bone_local_qqs,
            motion_bone_local_scales,
            matrixes,
        )

        if out_fno_log:
            logger.info("ボーン行列計算[{d}]", d=description)

        # 各ボーンごとのボーン変形行列結果と逆BOf行列(初期姿勢行列)の行列積
        relative_matrixes = model.bones.parent_revert_matrixes @ matrixes

        if out_fno_log:
            logger.info("ボーン変形行列リストアップ[{d}]", d=description)

        # 行列積ボーン変形行列結果
        result_matrixes = np.full(motion_bone_poses.shape, np.eye(4))
        result_global_matrixes = np.full(motion_bone_poses.shape, np.eye(4))
        total_index_count = len(fnos) * len(bone_offset_matrixes)

        for i, (fidx, (bone_index, offset_matrix)) in enumerate(
            product(list(range(len(fnos))), bone_offset_matrixes)
        ):
            if out_fno_log:
                logger.count(
                    "ボーン変形行列積[{d}]",
                    d=description,
                    index=i,
                    total_index_count=total_index_count,
                    display_block=50000,
                )

            result_matrixes[fidx, bone_index] = offset_matrix.copy()
            # ボーンツリーINDEXリストごとのボーン変形行列リスト(子どもから親に遡る)
            for matrix in relative_matrixes[
                fidx, list(reversed(model.bones[bone_index].tree_indexes))
            ]:
                result_matrixes[fidx, bone_index] = (
                    matrix @ result_matrixes[fidx, bone_index]
                )

        # グローバル行列は最後にボーン位置に移動させる
        result_global_matrixes = result_matrixes @ bone_pos_matrixes

        return VmdBoneFrameTrees(
            bone_dict,
            fnos,
            result_global_matrixes,
            result_matrixes,
            motion_bone_poses,
            motion_bone_qqs,
            motion_bone_fk_qqs,
        )

    def get_bone_matrixes(
        self,
        fnos: list[int],
        model: PmxModel,
        target_bone_names: list[str],
        out_fno_log: bool = False,
        description: str = "",
    ) -> tuple[
        bool,
        bool,
        bool,
        bool,
        bool,
        bool,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
    ]:
        """ボーン変形行列を求める"""

        row = len(fnos)
        col = len(model.bones)
        poses = np.full((row, col, 4, 4), np.eye(4))
        qqs = np.full((row, col, 4, 4), np.eye(4))
        fk_qqs = np.full((row, col, 4, 4), np.eye(4))
        scales = np.full((row, col, 4, 4), np.eye(4))
        local_poses = np.full((row, col, 4, 4), np.eye(4))
        local_qqs = np.full((row, col, 4, 4), np.eye(4))
        local_scales = np.full((row, col, 4, 4), np.eye(4))
        is_identity_poses = True
        is_identity_qqs = True
        is_identity_scales = True
        is_identity_local_poses = True
        is_identity_local_qqs = True
        is_identity_local_scales = True

        total_count = len(fnos) * len(target_bone_names)

        for fidx, fno in enumerate(fnos):
            fno_poses: dict[int, MVector3D] = {}
            fno_scales: dict[int, MVector3D] = {}
            fno_local_poses: dict[int, MVector3D] = {}
            fno_local_qqs: dict[int, MQuaternion] = {}
            fno_local_scales: dict[int, MVector3D] = {}

            is_valid_local_pos = False
            is_valid_local_rot = False
            is_valid_local_scale = False

            for bidx, bone_name in enumerate(target_bone_names):
                if out_fno_log:
                    logger.count(
                        "ボーン計算[{d}]",
                        d=description,
                        index=fidx * len(target_bone_names) + bidx,
                        total_index_count=total_count,
                        display_block=10000,
                    )

                bone = model.bones[bone_name]
                if bone.index in fno_local_poses:
                    continue
                bf = self[bone.name][fno]
                fno_poses[bone.index] = bf.position
                fno_scales[bone.index] = bf.scale
                fno_local_poses[bone.index] = bf.local_position.effective()
                fno_local_qqs[bone.index] = bf.local_rotation.effective()
                fno_local_scales[bone.index] = bf.local_scale.effective()

                is_valid_local_pos = is_valid_local_pos or bool(bf.local_position)
                is_valid_local_rot = is_valid_local_rot or bool(bf.local_rotation)
                is_valid_local_scale = is_valid_local_scale or bool(bf.local_scale)

            for bone_name in target_bone_names:
                bone = model.bones[bone_name]

                is_parent_bone_not_local_cancels: list[bool] = []
                parent_local_poses: list[MVector3D] = []
                parent_local_qqs: list[MQuaternion] = []
                parent_local_scales: list[MVector3D] = []
                parent_local_axises: list[MVector3D] = []

                for parent_index in bone.tree_indexes[:-1]:
                    parent_bone = model.bones[parent_index]
                    if parent_bone.index not in fno_local_poses:
                        parent_bf = self[parent_bone.name][fno]
                        fno_local_poses[parent_bone.index] = (
                            parent_bf.local_position.effective()
                        )
                        fno_local_qqs[parent_bone.index] = (
                            parent_bf.local_rotation.effective()
                        )
                        fno_local_scales[parent_bone.index] = (
                            parent_bf.local_scale.effective()
                        )
                    is_parent_bone_not_local_cancels.append(
                        model.bones.is_bone_not_local_cancels[parent_bone.index]
                    )
                    parent_local_axises.append(
                        model.bones.local_axises[parent_bone.index]
                    )
                    parent_local_poses.append(fno_local_poses[parent_bone.index])
                    parent_local_qqs.append(fno_local_qqs[parent_bone.index])
                    parent_local_scales.append(fno_local_scales[parent_bone.index])

                _, _, _, poses[fidx, bone.index] = self.get_position(
                    fidx, fno, model, bone, fno_poses[bone.index]
                )
                if is_identity_poses and self.is_non_identity_matrix(
                    poses[fidx, bone.index]
                ):
                    is_identity_poses = False

                # モーションによるローカル移動量
                if is_valid_local_pos:
                    _, _, _, local_pos_mat = self.get_local_position(
                        fidx,
                        bone,
                        fno_local_poses,
                        is_parent_bone_not_local_cancels,
                        parent_local_poses,
                        parent_local_axises,
                    )
                    local_poses[fidx, bone.index] = local_pos_mat
                    is_identity_local_poses = False

                # FK(捩り) > IK(捩り) > 付与親(捩り)
                # ここではもうIKの回転結果は求まってるのでIK計算を追加では行わない
                _, _, _, (qq, fk_qq) = self.get_rotation(fidx, fno, model, bone)
                qqs[fidx, bone.index] = qq.to_matrix4x4().vector
                fk_qqs[fidx, bone.index] = fk_qq.to_matrix4x4().vector
                if is_identity_qqs and self.is_non_identity_matrix(
                    qqs[fidx, bone.index]
                ):
                    is_identity_qqs = False

                # ローカル回転
                if is_valid_local_rot:
                    _, _, _, local_rot_mat = self.get_local_rotation(
                        fidx,
                        bone,
                        fno_local_qqs,
                        is_parent_bone_not_local_cancels,
                        parent_local_qqs,
                        parent_local_axises,
                    )
                    local_qqs[fidx, bone.index] = local_rot_mat
                    is_identity_local_qqs = False

                # モーションによるスケール変化
                _, _, _, scale_mat = self.get_scale(
                    fidx, fno, model, bone, fno_scales[bone.index]
                )
                scales[fidx, bone.index] = scale_mat
                if is_identity_scales and self.is_non_identity_matrix(
                    scales[fidx, bone.index]
                ):
                    is_identity_scales = False

                # ローカルスケール
                if is_valid_local_scale:
                    _, _, _, local_scale_mat = self.get_local_scale(
                        fidx,
                        bone,
                        fno_local_scales,
                        is_parent_bone_not_local_cancels,
                        parent_local_scales,
                        parent_local_axises,
                    )
                    local_scales[fidx, bone.index] = local_scale_mat
                    is_identity_local_scales = False

        return (
            is_identity_poses,
            is_identity_qqs,
            is_identity_scales,
            is_identity_local_poses,
            is_identity_local_qqs,
            is_identity_local_scales,
            poses,
            qqs,
            scales,
            local_poses,
            local_qqs,
            local_scales,
            fk_qqs,
        )

    def get_bone_matrixes_parallel(
        self,
        fnos: list[int],
        model: PmxModel,
        target_bone_names: list[str],
        out_fno_log: bool = False,
        description: str = "",
        max_worker: int = 1,
    ) -> tuple[
        bool,
        bool,
        bool,
        bool,
        bool,
        bool,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
    ]:
        """ボーン変形行列を求める"""

        row = len(fnos)
        col = len(model.bones)
        poses = np.full((row, col, 4, 4), np.eye(4))
        qqs = np.full((row, col, 4, 4), np.eye(4))
        fk_qqs = np.full((row, col, 4, 4), np.eye(4))
        scales = np.full((row, col, 4, 4), np.eye(4))
        local_poses = np.full((row, col, 4, 4), np.eye(4))
        local_qqs = np.full((row, col, 4, 4), np.eye(4))
        local_scales = np.full((row, col, 4, 4), np.eye(4))
        is_identity_poses = True
        is_identity_qqs = True
        is_identity_scales = True
        is_identity_local_poses = True
        is_identity_local_qqs = True
        is_identity_local_scales = True

        total_count = len(fnos) * len(target_bone_names)

        with ThreadPoolExecutor(
            thread_name_prefix="bone_matrixes", max_workers=max_worker
        ) as executor:
            futures: list[Future] = []

            for fidx, fno in enumerate(fnos):
                fno_poses: dict[int, MVector3D] = {}
                fno_scales: dict[int, MVector3D] = {}
                fno_local_poses: dict[int, MVector3D] = {}
                fno_local_qqs: dict[int, MQuaternion] = {}
                fno_local_scales: dict[int, MVector3D] = {}

                is_valid_local_pos = False
                is_valid_local_rot = False
                is_valid_local_scale = False

                for bidx, bone_name in enumerate(target_bone_names):
                    if out_fno_log:
                        logger.count(
                            "ボーン計算[{d}]",
                            d=description,
                            index=fidx * len(target_bone_names) + bidx,
                            total_index_count=total_count,
                            display_block=50000,
                        )

                    bone = model.bones[bone_name]
                    if bone.index in fno_local_poses:
                        continue
                    bf = self[bone.name][fno]
                    fno_poses[bone.index] = bf.position
                    fno_scales[bone.index] = bf.scale
                    fno_local_poses[bone.index] = bf.local_position.effective()
                    fno_local_qqs[bone.index] = bf.local_rotation.effective()
                    fno_local_scales[bone.index] = bf.local_scale.effective()

                    is_valid_local_pos = is_valid_local_pos or bool(bf.local_position)
                    is_valid_local_rot = is_valid_local_rot or bool(bf.local_rotation)
                    is_valid_local_scale = is_valid_local_scale or bool(bf.local_scale)

                for bone_name in target_bone_names:
                    bone = model.bones[bone_name]

                    is_parent_bone_not_local_cancels: list[bool] = []
                    parent_local_poses: list[MVector3D] = []
                    parent_local_qqs: list[MQuaternion] = []
                    parent_local_scales: list[MVector3D] = []
                    parent_local_axises: list[MVector3D] = []

                    for parent_index in bone.tree_indexes[:-1]:
                        parent_bone = model.bones[parent_index]
                        if parent_bone.index not in fno_local_poses:
                            parent_bf = self[parent_bone.name][fno]
                            fno_local_poses[parent_bone.index] = (
                                parent_bf.local_position.effective()
                            )
                            fno_local_qqs[parent_bone.index] = (
                                parent_bf.local_rotation.effective()
                            )
                            fno_local_scales[parent_bone.index] = (
                                parent_bf.local_scale.effective()
                            )
                        is_parent_bone_not_local_cancels.append(
                            model.bones.is_bone_not_local_cancels[parent_bone.index]
                        )
                        parent_local_axises.append(
                            model.bones.local_axises[parent_bone.index]
                        )
                        parent_local_poses.append(fno_local_poses[parent_bone.index])
                        parent_local_qqs.append(fno_local_qqs[parent_bone.index])
                        parent_local_scales.append(fno_local_scales[parent_bone.index])

                    futures.append(
                        executor.submit(
                            self.get_position,
                            fidx,
                            fno,
                            model,
                            bone,
                            fno_poses[bone.index],
                        )
                    )

                    # モーションによるローカル移動量
                    if is_valid_local_pos:
                        futures.append(
                            executor.submit(
                                self.get_local_position,
                                fidx,
                                bone,
                                fno_local_poses,
                                is_parent_bone_not_local_cancels,
                                parent_local_poses,
                                parent_local_axises,
                            )
                        )

                    # FK(捩り) > IK(捩り) > 付与親(捩り)
                    # ここではもうIKの回転結果は求まってるのでIK計算を追加では行わない
                    futures.append(
                        executor.submit(
                            self.get_rotation,
                            fidx,
                            fno,
                            model,
                            bone,
                        )
                    )

                    # ローカル回転
                    if is_valid_local_rot:
                        futures.append(
                            executor.submit(
                                self.get_local_rotation,
                                fidx,
                                bone,
                                fno_local_qqs,
                                is_parent_bone_not_local_cancels,
                                parent_local_qqs,
                                parent_local_axises,
                            )
                        )

                    # モーションによるスケール変化
                    futures.append(
                        executor.submit(
                            self.get_scale,
                            fidx,
                            fno,
                            model,
                            bone,
                            fno_scales[bone.index],
                        )
                    )

                    # ローカルスケール
                    if is_valid_local_scale:
                        futures.append(
                            executor.submit(
                                self.get_local_scale,
                                fidx,
                                bone,
                                fno_local_scales,
                                is_parent_bone_not_local_cancels,
                                parent_local_scales,
                                parent_local_axises,
                            )
                        )

        for future in as_completed(futures):
            if future.exception():
                raise future.exception()

            fidx, bone_index, attr, mat = future.result()
            if attr == VmdAttributes.POSITION:
                poses[fidx, bone_index] = mat
                if is_identity_poses and self.is_non_identity_matrix(mat):
                    is_identity_poses = False

            elif attr == VmdAttributes.ROTATION:
                qq, fk_qq = mat
                qqs[fidx, bone_index] = qq.to_matrix4x4().vector
                fk_qqs[fidx, bone_index] = fk_qq.to_matrix4x4().vector
                if is_identity_qqs and self.is_non_identity_matrix(
                    qqs[fidx, bone_index]
                ):
                    is_identity_qqs = False

            elif attr == VmdAttributes.SCALE:
                scales[fidx, bone_index] = mat
                if is_identity_scales and self.is_non_identity_matrix(mat):
                    is_identity_scales = False

            elif attr == VmdAttributes.LOCAL_POSITION:
                local_poses[fidx, bone_index] = mat
                is_identity_local_poses = False

            elif attr == VmdAttributes.LOCAL_ROTATION:
                local_qqs[fidx, bone_index] = mat
                is_identity_local_qqs = False

            elif attr == VmdAttributes.LOCAL_SCALE:
                local_scales[fidx, bone_index] = mat
                is_identity_local_scales = False

        return (
            is_identity_poses,
            is_identity_qqs,
            is_identity_scales,
            is_identity_local_poses,
            is_identity_local_qqs,
            is_identity_local_scales,
            poses,
            qqs,
            scales,
            local_poses,
            local_qqs,
            local_scales,
            fk_qqs,
        )

    def get_position(
        self,
        fidx: int,
        fno: int,
        model: PmxModel,
        bone: Bone,
        position: MVector3D,
        loop: int = 0,
    ) -> tuple[int, int, VmdAttributes, np.ndarray]:
        """
        該当キーフレにおけるボーンの移動位置
        """
        # 自身の位置
        mat = np.eye(4)
        mat[:3, 3] = position.vector

        # 付与親を加味して返す
        return (
            fidx,
            bone.index,
            VmdAttributes.POSITION,
            mat @ self.get_effect_position(fidx, fno, model, bone, loop=loop + 1),
        )

    def get_effect_position(
        self,
        fidx: int,
        fno: int,
        model: PmxModel,
        bone: Bone,
        loop: int = 0,
    ) -> np.ndarray:
        """
        付与親を加味した移動を求める
        """
        if not (bone.is_external_translation and bone.effect_index in model.bones):
            return np.eye(4)

        if 0 == bone.effect_factor or 20 < loop:
            # 付与率が0の場合、常に0になる
            return np.eye(4)

        # 付与親の移動量を取得する（それが付与持ちなら更に遡る）
        effect_bone = model.bones[bone.effect_index]
        effect_bf = self[effect_bone.name][fno]
        _, _, _, effect_pos_mat = self.get_position(
            fidx, fno, model, effect_bone, effect_bf.position, loop=loop + 1
        )
        # 付与率を加味する
        effect_pos_mat[:3, 3] *= bone.effect_factor

        return effect_pos_mat

    def get_local_position(
        self,
        fidx: int,
        bone: Bone,
        fno_local_poses: dict[int, MVector3D],
        is_parent_bone_not_local_cancels: Iterable[bool],
        parent_local_poses: Iterable[MVector3D],
        parent_local_axises: Iterable[MVector3D],
    ) -> tuple[int, int, VmdAttributes, np.ndarray]:
        """
        該当キーフレにおけるボーンのローカル位置
        """
        # 自身のローカル移動量
        local_pos = fno_local_poses[bone.index]

        return (
            fidx,
            bone.index,
            VmdAttributes.LOCAL_POSITION,
            calc_local_position(
                local_pos,
                bone.is_not_local_cancel,
                bone.local_axis,
                tuple(is_parent_bone_not_local_cancels),
                tuple(parent_local_poses),
                tuple(parent_local_axises),
            ),
        )

    def get_scale(
        self,
        fidx: int,
        fno: int,
        model: PmxModel,
        bone: Bone,
        scale: MVector3D,
        loop: int = 0,
    ) -> tuple[int, int, VmdAttributes, np.ndarray]:
        """
        該当キーフレにおけるボーンの縮尺
        """

        # 自身のスケール
        scale_mat = np.eye(4)
        scale_mat[:3, :3] += np.diag(np.where(scale.vector < -1, -1, scale.vector))

        # 付与親を加味して返す
        return (
            fidx,
            bone.index,
            VmdAttributes.SCALE,
            self.get_effect_scale(fidx, fno, model, bone, scale_mat, loop=loop + 1),
        )

    def get_effect_scale(
        self,
        fidx: int,
        fno: int,
        model: PmxModel,
        bone: Bone,
        scale_mat: np.ndarray,
        loop: int = 0,
    ) -> np.ndarray:
        """
        付与親を加味した縮尺を求める
        """
        if not (bone.is_external_translation and bone.effect_index in model.bones):
            return scale_mat

        if 0 == bone.effect_factor or 20 < loop:
            # 付与率が0の場合、常に1になる
            return np.eye(4)

        # 付与親の回転量を取得する（それが付与持ちなら更に遡る）
        effect_bone = model.bones[bone.effect_index]
        effect_bf = self[effect_bone.name][fno]
        _, _, _, effect_scale_mat = self.get_scale(
            fidx, fno, model, effect_bone, effect_bf.scale, loop=loop + 1
        )

        return scale_mat @ effect_scale_mat

    def get_local_scale(
        self,
        fidx: int,
        bone: Bone,
        fno_local_scales: dict[int, MVector3D],
        is_parent_bone_not_local_cancels: Iterable[bool],
        parent_local_scales: Iterable[MVector3D],
        parent_local_axises: Iterable[MVector3D],
    ) -> tuple[int, int, VmdAttributes, np.ndarray]:
        """
        該当キーフレにおけるボーンのローカル縮尺
        """
        # 自身のローカルスケール
        local_scale = fno_local_scales[bone.index]

        return (
            fidx,
            bone.index,
            VmdAttributes.LOCAL_SCALE,
            calc_local_scale(
                local_scale,
                bone.is_not_local_cancel,
                bone.local_axis,
                tuple(is_parent_bone_not_local_cancels),
                tuple(parent_local_scales),
                tuple(parent_local_axises),
            ),
        )

    def calc_ik_rotations(
        self,
        fnos: list[int],
        model: PmxModel,
        target_bone_names: Iterable[str],
        out_fno_log: bool = False,
        description: str = "",
        max_worker: int = 1,
    ):
        """IK関連ボーンの事前計算"""
        ik_bone_names = [
            model.bones[bone_index].name
            for bone_index in sorted(
                set(
                    [
                        model.bones[target_bone_name].index
                        for target_bone_name in target_bone_names
                        if model.bones[target_bone_name].is_ik
                        and model.bones[target_bone_name].ik.links
                    ]
                    + [
                        ik_target_bone_index
                        for target_bone_name in target_bone_names
                        for ik_target_bone_index in model.bones[
                            target_bone_name
                        ].ik_target_indexes
                        if model.bones[ik_target_bone_index].is_ik
                        and model.bones[ik_target_bone_index].ik.links
                    ]
                )
            )
        ]
        if not ik_bone_names:
            # IKボーンがない場合はそのまま終了
            return

        ik_link_bone_names = [
            model.bones[link.bone_index].name
            for ik_bone_name in ik_bone_names
            for link in model.bones[ik_bone_name].ik.links
            if link.bone_index in model.bones
        ]
        if not ik_link_bone_names:
            # IKリンクボーンがない場合はそのまま終了
            return

        if 1 == max_worker:
            n = 0
            total_index_count = len(ik_bone_names) * len(fnos)

            for ik_bone_name in ik_bone_names:
                ik_bone = model.bones[ik_bone_name]

                for fidx, fno in enumerate(fnos):
                    if out_fno_log:
                        logger.count(
                            "IK事前計算[{d}]",
                            d=description,
                            index=n,
                            total_index_count=total_index_count,
                            display_block=200,
                        )

                    # IKターゲットのボーンに対してIK計算を行う
                    _, _, ik_link_qqs = self.get_ik_rotation(fidx, fno, model, ik_bone)

                    for link in ik_bone.ik.links:
                        link_bone = model.bones[link.bone_index]

                        link_bf = self[link_bone.name][fno]
                        link_bf.ik_rotation = ik_link_qqs[link_bone.index]

                        # IK用なので最後に追加して補間曲線は分割しない
                        self[link_bone.name].append(link_bf)

                    n += 1
        else:
            # 末端IKボーン名リストを取得する
            tail_ik_bone_names: list[str] = []
            for ik_bone_name in ik_bone_names:
                bone = model.bones[ik_bone_name]
                if (
                    bone.is_ik
                    and bone.ik.bone_index in model.bones
                    and [ik_link.bone_index for ik_link in bone.ik.links]
                    and not [
                        ik_link.bone_index
                        for child_bone_index in bone.child_bone_indexes
                        if model.bones[child_bone_index].is_ik
                        for ik_link in model.bones[child_bone_index].ik.links
                    ]
                ):
                    tail_ik_bone_names.append(ik_bone_name)

            with ThreadPoolExecutor(
                thread_name_prefix="bone_matrixes", max_workers=max_worker
            ) as executor:
                n = 0
                total_index_count = len(tail_ik_bone_names) * len(fnos)
                futures: list[Future] = []

                for ik_bone_name in tail_ik_bone_names:
                    ik_bone = model.bones[ik_bone_name]

                    for fidx, fno in enumerate(fnos):
                        # IKツリーの根元から、IKターゲットのボーンに対してIK計算を行う
                        futures.append(
                            executor.submit(
                                self.get_ik_rotation_tree, fidx, fno, model, ik_bone
                            )
                        )

                for future in as_completed(futures):
                    if out_fno_log:
                        logger.count(
                            "IK事前計算[{d}]",
                            d=description,
                            index=n,
                            total_index_count=total_index_count,
                            display_block=500,
                        )
                    n += 1

                    if future.exception():
                        raise future.exception()

                    fno, ik_link_qqs = future.result()

                    for ik_link_bone_index, ik_link_qq in ik_link_qqs.items():
                        link_bone = model.bones[ik_link_bone_index]

                        link_bf = self[link_bone.name][fno]
                        link_bf.ik_rotation = ik_link_qq

                        # IK用なので最後に追加して補間曲線は分割しない
                        self[link_bone.name].append(link_bf)

    def get_rotation(
        self,
        fidx: int,
        fno: int,
        model: PmxModel,
        bone: Bone,
        loop: int = 0,
    ) -> tuple[int, int, VmdAttributes, tuple[MQuaternion, MQuaternion]]:
        """
        該当キーフレにおけるボーンの相対位置
        is_calc_ik : IKを計算するか(循環してしまう場合があるので、デフォルトFalse)
        """

        # FK(捩り) > IK(捩り) > 付与親(捩り)
        bf = self[bone.name][fno]

        if bf.ik_rotation is not None:
            # IK用回転を持っている場合、置き換え
            ik_qq = bf.ik_rotation.copy()
        else:
            fk_qq = bf.rotation.copy()

            # IKを加味した回転を必要があれば軸に沿わせる
            ik_qq = self.get_axis_rotation(bone, fk_qq)

        # 付与親を加味した回転
        if bone.is_external_rotation and bone.effect_index in model.bones:
            effect_qq = self.get_effect_rotation(fidx, fno, model, bone, loop=loop + 1)

            return (
                fidx,
                bone.index,
                VmdAttributes.ROTATION,
                (self.get_axis_rotation(bone, (ik_qq * effect_qq).normalized()), ik_qq),
            )

        return fidx, bone.index, VmdAttributes.ROTATION, (ik_qq, ik_qq)

    def get_effect_rotation(
        self,
        fidx: int,
        fno: int,
        model: PmxModel,
        bone: Bone,
        loop: int = 0,
    ) -> MQuaternion:
        """
        付与親を加味した回転を求める
        """
        if 0 == bone.effect_factor or loop > 20:
            # 付与率が0の場合、常に0になる
            # MMDエンジン対策で無限ループを避ける
            return MQuaternion()

        # 付与親の回転量を取得する（それが付与持ちなら更に遡る）
        effect_bone = model.bones[bone.effect_index]
        _, _, _, (effect_qq, _) = self.get_rotation(
            fidx,
            fno,
            model,
            effect_bone,
            loop=loop + 1,
        )
        if 0 <= bone.effect_factor:
            # 正の付与親
            return effect_qq.multiply_factor(bone.effect_factor)
        else:
            # 負の付与親の場合、逆回転
            return (effect_qq.multiply_factor(abs(bone.effect_factor))).inverse()

    def get_ik_rotation_tree(
        self,
        fidx: int,
        fno: int,
        model: PmxModel,
        ik_bone: Bone,
    ) -> tuple[int, dict[int, MQuaternion]]:
        """
        複数のIKが連なっている場合に直列で求められるようツリー関係を意識してIK計算を行う
        """
        qqs: Optional[dict[int, MQuaternion]] = None

        for bone_index in model.bone_trees[ik_bone.name].indexes:
            bone = model.bones[bone_index]
            if bone.ik and bone.ik.links:
                _, _, qqs = self.get_ik_rotation(fidx, fno, model, bone, qqs)

        return fno, qqs

    def get_ik_rotation(
        self,
        fidx: int,
        fno: int,
        model: PmxModel,
        ik_bone: Bone,
        qqs: dict[int, MQuaternion] = None,
    ) -> tuple[int, int, dict[int, MQuaternion]]:
        """
        IKを加味した回転を求める
        """

        # ik_fno = 1
        # bake_motion = VmdMotion()

        # IKターゲットボーン
        effector_bone = model.bones[ik_bone.ik.bone_index]

        # IK関連の行列を一括計算
        ik_matrixes = self.animate_bone_matrixes(
            [fno],
            model,
            bone_names=[ik_bone.name],
            is_calc_ik=False,
        )

        # 処理対象ボーン名取得
        target_bone_names = self.get_animate_bone_names(model, [effector_bone.name])

        # 処理対象ボーンの行列取得
        bone_dict, bone_offset_matrixes, bone_pos_matrixes = self.create_bone_matrixes(
            model, target_bone_names
        )

        # モーションボーンの初期値を取得
        (
            is_motion_identity_poses,
            is_motion_identity_qqs,
            is_motion_identity_scales,
            is_motion_identity_local_poses,
            is_motion_identity_local_qqs,
            is_motion_identity_local_scales,
            motion_bone_poses,
            motion_bone_qqs,
            motion_bone_scales,
            motion_bone_local_poses,
            motion_bone_local_qqs,
            motion_bone_local_scales,
            motion_bone_fk_qqs,
        ) = self.get_bone_matrixes(
            [fno],
            model,
            target_bone_names,
            out_fno_log=False,
        )

        if qqs is None:
            qqs: dict[int, MQuaternion] = {}

        for bone_name in target_bone_names:
            bone = model.bones[bone_name]
            if bone.index in qqs:
                motion_bone_qqs[0, bone.index] = qqs[bone.index].to_matrix4x4().vector
            else:
                qqs[bone.index] = MMatrix4x4(
                    motion_bone_qqs[0, bone.index]
                ).to_quaternion()

        prev_qqs: dict[int, MQuaternion] = {}
        now_qqs: dict[int, MQuaternion] = dict(
            [(ik_link.bone_index, MQuaternion()) for ik_link in ik_bone.ik.links]
        )

        is_break = False
        for loop in range(ik_bone.ik.loop_count):
            for lidx, ik_link in enumerate(ik_bone.ik.links):
                # ikLink は末端から並んでる
                if ik_link.bone_index not in model.bones:
                    continue

                # 処理対象IKボーン
                link_bone = model.bones[ik_link.bone_index]

                if (
                    ik_link.angle_limit
                    and not ik_link.min_angle_limit.radians
                    and not ik_link.max_angle_limit.radians
                ) or (
                    ik_link.local_angle_limit
                    and not ik_link.local_min_angle_limit.radians
                    and not ik_link.local_max_angle_limit.radians
                ):
                    # 角度制限があってまったく動かない場合、IK計算しないで次に行く
                    continue

                # 単位角
                unit_rad = ik_bone.ik.unit_rotation.radians.x * (lidx + 1)

                # IK関連の行列を取得
                effector_matrixes = self.calc_bone_matrixes(
                    [fno],
                    model,
                    bone_dict,
                    bone_offset_matrixes,
                    bone_pos_matrixes,
                    is_motion_identity_poses,
                    is_motion_identity_qqs,
                    is_motion_identity_scales,
                    is_motion_identity_local_poses,
                    is_motion_identity_local_qqs,
                    is_motion_identity_local_scales,
                    motion_bone_poses,
                    motion_bone_qqs,
                    motion_bone_scales,
                    motion_bone_local_poses,
                    motion_bone_local_qqs,
                    motion_bone_local_scales,
                    motion_bone_fk_qqs,
                    matrixes=None,
                    out_fno_log=False,
                    description="",
                )

                # IKボーンのグローバル位置
                global_target_pos = ik_matrixes[ik_bone.name, fno].position

                # 現在のIKターゲットボーンのグローバル位置を取得
                global_effector_pos = effector_matrixes[
                    effector_bone.name, fno
                ].position

                # 注目ノード（実際に動かすボーン）
                link_matrix = effector_matrixes[link_bone.name, fno].global_matrix

                # ワールド座標系から注目ノードの局所座標系への変換
                link_inverse_matrix = link_matrix.inverse()

                # 注目ノードを起点とした、エフェクタのローカル位置
                local_effector_pos = (
                    link_inverse_matrix * global_effector_pos
                ).normalized()
                # 注目ノードを起点とした、IK目標のローカル位置
                local_target_pos = (
                    link_inverse_matrix * global_target_pos
                ).normalized()

                # if 1e-6 > (local_effector_pos - local_target_pos).length_squared():
                #     # 位置の差がほとんどない場合、終了
                #     is_break = True
                #     break

                # ベクトル (1) を (2) に一致させるための最短回転量（Axis-Angle）
                # 回転角
                rotation_rad: float = np.arccos(
                    np.clip(local_effector_pos.dot(local_target_pos), -1, 1)
                )

                # 回転軸
                rotation_axis: MVector3D = (
                    local_effector_pos.normalized()
                    .cross(local_target_pos.normalized())
                    .normalized()
                )

                # 角度がほとんどない場合、終了
                if rotation_rad < 1e-7:
                    break

                rotation_rad = np.clip(rotation_rad, -unit_rad, unit_rad)

                # リンクボーンの角度を取得
                link_ik_qq = qqs[link_bone.index]
                total_actual_ik_qq = None

                if ik_link.local_angle_limit:
                    # ローカル軸角度制限が入っている場合、ローカル軸に合わせて理想回転を求める
                    if (
                        ik_link.local_min_angle_limit.radians.x
                        or ik_link.local_max_angle_limit.radians.x
                    ):
                        # 既存のFK回転・IK回転・今回の計算をすべて含めて実際回転を求める
                        total_actual_ik_qq = self.calc_single_axis_rotation(
                            ik_link.local_min_angle_limit.radians.x,
                            ik_link.local_max_angle_limit.radians.x,
                            link_ik_qq,
                            rotation_axis,
                            rotation_rad,
                            0,
                            link_bone.corrected_local_x_vector,
                            ik_bone.ik.unit_rotation.radians.x,
                            is_local=True,
                        )
                    elif (
                        ik_link.local_min_angle_limit.radians.y
                        or ik_link.local_max_angle_limit.radians.y
                    ):
                        # 既存のFK回転・IK回転・今回の計算をすべて含めて実際回転を求める
                        total_actual_ik_qq = self.calc_single_axis_rotation(
                            ik_link.local_min_angle_limit.radians.y,
                            ik_link.local_max_angle_limit.radians.y,
                            link_ik_qq,
                            rotation_axis,
                            rotation_rad,
                            1,
                            link_bone.corrected_local_y_vector,
                            ik_bone.ik.unit_rotation.radians.x,
                            is_local=True,
                        )
                    elif (
                        ik_link.local_min_angle_limit.radians.z
                        or ik_link.local_max_angle_limit.radians.z
                    ):
                        # 既存のFK回転・IK回転・今回の計算をすべて含めて実際回転を求める
                        total_actual_ik_qq = self.calc_single_axis_rotation(
                            ik_link.local_min_angle_limit.radians.z,
                            ik_link.local_max_angle_limit.radians.z,
                            link_ik_qq,
                            rotation_axis,
                            rotation_rad,
                            2,
                            link_bone.corrected_local_z_vector,
                            ik_bone.ik.unit_rotation.radians.x,
                            is_local=True,
                        )
                elif ik_link.angle_limit:
                    # 角度制限が入ってる場合

                    if (
                        ik_link.min_angle_limit.radians.x
                        or ik_link.max_angle_limit.radians.x
                    ):
                        # 既存のFK回転・IK回転・今回の計算をすべて含めて実際回転を求める
                        total_actual_ik_qq = self.calc_single_axis_rotation(
                            ik_link.min_angle_limit.radians.x,
                            ik_link.max_angle_limit.radians.x,
                            link_ik_qq,
                            rotation_axis,
                            rotation_rad,
                            0,
                            MVector3D(1, 0, 0),
                            ik_bone.ik.unit_rotation.radians.x,
                        )
                    elif (
                        ik_link.min_angle_limit.radians.y
                        or ik_link.max_angle_limit.radians.y
                    ):
                        # 既存のFK回転・IK回転・今回の計算をすべて含めて実際回転を求める
                        total_actual_ik_qq = self.calc_single_axis_rotation(
                            ik_link.min_angle_limit.radians.y,
                            ik_link.max_angle_limit.radians.y,
                            link_ik_qq,
                            rotation_axis,
                            rotation_rad,
                            1,
                            MVector3D(0, 1, 0),
                            ik_bone.ik.unit_rotation.radians.x,
                        )
                    elif (
                        ik_link.min_angle_limit.radians.z
                        or ik_link.max_angle_limit.radians.z
                    ):
                        # 既存のFK回転・IK回転・今回の計算をすべて含めて実際回転を求める
                        total_actual_ik_qq = self.calc_single_axis_rotation(
                            ik_link.min_angle_limit.radians.z,
                            ik_link.max_angle_limit.radians.z,
                            link_ik_qq,
                            rotation_axis,
                            rotation_rad,
                            2,
                            MVector3D(0, 0, 1),
                            ik_bone.ik.unit_rotation.radians.x,
                        )

                else:
                    if link_bone.has_fixed_axis:
                        # 軸制限ありの場合、軸にそった理想回転量とする
                        rotation_axis = link_bone.corrected_fixed_axis

                        # # 制限角で最大変位量を制限する
                        # limit_rotation_rad = min(
                        #     ik_bone.ik.unit_rotation.radians.x, rotation_rad
                        # )
                        # correct_ik_qq = MQuaternion.from_axis_angles(
                        #     rotation_axis, limit_rotation_rad
                        # )

                        # actual_ik_qq = link_ik_qq * correct_ik_qq
                        # link_axis = actual_ik_qq.to_axis().normalized()
                        # link_rad = actual_ik_qq.to_radian()
                        # link_sign = np.sign(
                        #     link_bone.corrected_fixed_axis.dot(link_axis)
                        # )

                        # # 既存のFK回転・IK回転・今回の計算をすべて含めて実際回転を求める
                        # total_actual_ik_qq = MQuaternion.from_axis_angles(
                        #     link_bone.corrected_fixed_axis, link_rad * link_sign
                        # )

                    # # 制限角で最大変位量を制限する
                    # limit_rotation_rad = min(
                    #     ik_bone.ik.unit_rotation.radians.x, rotation_rad
                    # )

                    correct_ik_qq = MQuaternion.from_axis_angles(
                        rotation_axis, rotation_rad
                    ).shorten()

                    # 既存のFK回転・IK回転・今回の計算をすべて含めて実際回転を求める
                    total_actual_ik_qq = link_ik_qq * correct_ik_qq

                if link_bone.has_fixed_axis:
                    # 軸制限回転を求める
                    total_actual_ik_qq = total_actual_ik_qq.to_fixed_axis_rotation(
                        link_bone.corrected_fixed_axis
                    )

                prev_qqs[link_bone.index] = now_qqs[link_bone.index]
                now_qqs[link_bone.index] = total_actual_ik_qq

                # # ■ -----------------
                # original_link_bf = VmdBoneFrame(ik_fno, link_bone.name, register=True)
                # original_link_bf.rotation = link_ik_qq.copy()
                # bake_motion.append_bone_frame(original_link_bf)
                # ik_fno += 1

                # ideal_ik_qq = MQuaternion.from_axis_angles(rotation_axis, rotation_rad)

                # total_ideal_ik_qq: MQuaternion = link_ik_qq * ideal_ik_qq

                # total_ideal_bf = VmdBoneFrame(ik_fno, link_bone.name, register=True)
                # total_ideal_bf.rotation = total_ideal_ik_qq.copy()
                # bake_motion.append_bone_frame(total_ideal_bf)
                # ik_fno += 1

                # total_bf = VmdBoneFrame(ik_fno, link_bone.name, register=True)
                # total_bf.rotation = total_actual_ik_qq.copy()
                # bake_motion.append_bone_frame(total_bf)
                # ik_fno += 1
                # # ■ -----------------

                # IKの結果を更新
                qqs[link_bone.index] = self.get_axis_rotation(
                    link_bone, total_actual_ik_qq
                )

                motion_bone_qqs[0, link_bone.index] = (
                    total_actual_ik_qq.to_matrix4x4().vector
                )
                is_motion_identity_qqs = False

            if is_break:
                break

            if False not in [
                ik_link.bone_index in now_qqs
                and ik_link.bone_index in prev_qqs
                and 1e-12
                > abs(1 - now_qqs[ik_link.bone_index].dot(prev_qqs[ik_link.bone_index]))
                for ik_link in ik_bone.ik.links
            ]:
                # すべてのリンクボーンで前回とほぼ変わらない角度であった場合、終了
                break

        # # ■ --------------
        # from datetime import datetime

        # from mlib.vmd.vmd_writer import VmdWriter

        # VmdWriter(
        #     bake_motion,
        #     f"E:/MMD/サイジング/足IK/IK_step/{datetime.now():%Y%m%d_%H%M%S_%f}_{ik_bone.name}_{fno:04d}.vmd",
        #     model_name="Test Model",
        # ).save()
        # # ■ --------------

        # IKの計算結果の回転を加味して返す
        return fno, ik_bone.index, qqs

    def calc_single_axis_rotation(
        self,
        min_angle_limit: float,
        max_angle_limit: float,
        now_ik_qq: MQuaternion,
        rotation_axis: MVector3D,
        rotation_rad: float,
        axis: int,
        axis_vec: MVector3D,
        unit_radian: float,
        is_local: bool = False,
    ) -> MQuaternion:
        """
        全ての角度をラジアン角度に分割して、そのうちのひとつの軸だけを動かす回転を取得する
        """
        # 現在調整予定角度の全ての軸の角度
        quat = MQuaternion.from_axis_angles(rotation_axis, rotation_rad).shorten()
        total_ik_qq = now_ik_qq * quat

        total_ik_rad = total_ik_qq.to_radian()
        if axis_vec.dot(rotation_axis) < 0:
            total_ik_rad = -total_ik_rad

        fSX = math.sin(total_ik_rad)  # sin(θ)
        fX = math.asin(fSX)  # 一軸回り決定

        # ジンバルロック回避
        total_ik_rads = total_ik_qq.to_radians(MQuaternionOrder.YXZ)
        is_gimbal = False
        if (
            (
                axis == 0
                and abs(total_ik_rads.y) > self.GIMBAL2_RAD
                and abs(total_ik_rads.z) > self.GIMBAL2_RAD
            )
            or (
                axis == 1
                and abs(total_ik_rads.x) > self.GIMBAL2_RAD
                and abs(total_ik_rads.z) > self.GIMBAL2_RAD
            )
            or (
                axis == 2
                and abs(total_ik_rads.x) > self.GIMBAL2_RAD
                and abs(total_ik_rads.y) > self.GIMBAL2_RAD
            )
        ):
            is_gimbal = True

        if is_gimbal or abs(total_ik_rad) > math.pi:
            fX = total_ik_rads.vector[axis]
            if fX < 0:
                fX = -(math.pi - fX)
            else:
                fX = math.pi - fX

        # 角度の制限
        if fX < min_angle_limit:
            tf = 2 * min_angle_limit - fX
            fX = np.clip(tf, min_angle_limit, max_angle_limit)
        if fX > max_angle_limit:
            tf = 2 * max_angle_limit - fX
            fX = np.clip(tf, min_angle_limit, max_angle_limit)

        # 指定の軸方向に回す
        return MQuaternion.from_axis_angles(axis_vec, fX).shorten()

    def get_axis_rotation(self, bone: Bone, qq: MQuaternion) -> MQuaternion:
        """
        軸制限回転を求める
        """
        if bone.has_fixed_axis:
            return qq.to_fixed_axis_rotation(bone.corrected_fixed_axis)

        return qq

    def get_local_rotation(
        self,
        fidx: int,
        bone: Bone,
        fno_local_qqs: dict[int, MQuaternion],
        is_parent_bone_not_local_cancels: Iterable[bool],
        parent_local_qqs: Iterable[MQuaternion],
        parent_local_axises: Iterable[MVector3D],
    ) -> tuple[int, int, VmdAttributes, np.ndarray]:
        """
        該当キーフレにおけるボーンのローカル回転
        """
        # 自身のローカル回転量
        local_qq = fno_local_qqs[bone.index]

        return (
            fidx,
            bone.index,
            VmdAttributes.LOCAL_ROTATION,
            calc_local_rotation(
                local_qq,
                bone.is_not_local_cancel,
                bone.local_axis,
                tuple(is_parent_bone_not_local_cancels),
                tuple(parent_local_qqs),
                tuple(parent_local_axises),
            ),
        )


@lru_cache(maxsize=None)
def calc_local_position(
    local_pos: MVector3D,
    is_bone_not_local_cancel: bool,
    local_axis: MVector3D,
    is_parent_bone_not_local_cancels: tuple[bool],
    parent_local_poses: tuple[MVector3D],
    parent_local_axises: tuple[MVector3D],
) -> np.ndarray:
    local_parent_matrix = np.eye(4)

    # 親を辿る
    if not is_bone_not_local_cancel:
        for n in range(1, len(parent_local_axises) + 1):
            local_parent_matrix = local_parent_matrix @ calc_local_position(
                parent_local_poses[-n],
                is_parent_bone_not_local_cancels[-n],
                parent_local_axises[-n],
                tuple(is_parent_bone_not_local_cancels[:-n]),
                tuple(parent_local_poses[:-n]),
                tuple(parent_local_axises[:-n]),
            )

    # ローカル軸に沿った回転行列
    rotation_matrix = local_axis.to_local_matrix4x4().vector

    local_pos_mat = np.eye(4)
    local_pos_mat[:3, 3] = local_pos.vector

    # ローカル軸に合わせた移動行列を作成する(親はキャンセルする)
    return (
        inv(local_parent_matrix)
        @ inv(rotation_matrix)
        @ local_pos_mat
        @ rotation_matrix
    )


@lru_cache(maxsize=None)
def calc_local_rotation(
    local_qq: MQuaternion,
    is_bone_not_local_cancel: bool,
    local_axis: MVector3D,
    is_parent_bone_not_local_cancels: tuple[bool],
    parent_local_qqs: tuple[MQuaternion],
    parent_local_axises: tuple[MVector3D],
) -> np.ndarray:
    local_parent_matrix = np.eye(4)

    # 親を辿る
    if not is_bone_not_local_cancel:
        for n in range(1, len(parent_local_axises) + 1):
            local_parent_matrix = local_parent_matrix @ calc_local_rotation(
                parent_local_qqs[-n],
                is_parent_bone_not_local_cancels[-n],
                parent_local_axises[-n],
                tuple(is_parent_bone_not_local_cancels[:-n]),
                tuple(parent_local_qqs[:-n]),
                tuple(parent_local_axises[:-n]),
            )

    # ローカル軸に沿った回転行列
    rotation_matrix = local_axis.to_local_matrix4x4().vector

    local_rot_mat = local_qq.to_matrix4x4().vector

    # ローカル軸に合わせた移動行列を作成する(親はキャンセルする)
    return (
        inv(local_parent_matrix)
        @ inv(rotation_matrix)
        @ local_rot_mat
        @ rotation_matrix
    )


@lru_cache(maxsize=None)
def calc_local_scale(
    local_scale: MVector3D,
    is_bone_not_local_cancel: bool,
    local_axis: MVector3D,
    is_parent_bone_not_local_cancels: tuple[bool],
    parent_local_scales: tuple[MVector3D],
    parent_local_axises: tuple[MVector3D],
) -> np.ndarray:
    local_parent_matrix = np.eye(4)

    # 親を辿る
    if not is_bone_not_local_cancel:
        for n in range(1, len(parent_local_axises) + 1):
            local_parent_matrix = local_parent_matrix @ calc_local_scale(
                parent_local_scales[-n],
                is_parent_bone_not_local_cancels[-n],
                parent_local_axises[-n],
                tuple(is_parent_bone_not_local_cancels[:-n]),
                tuple(parent_local_scales[:-n]),
                tuple(parent_local_axises[:-n]),
            )

    # ローカル軸に沿った回転行列
    rotation_matrix = local_axis.to_local_matrix4x4().vector

    # マイナス縮尺にはしない
    local_scale_mat = np.eye(4)
    local_scale_mat[:3, :3] += np.diag(
        np.where(local_scale.vector < -1, -1, local_scale.vector)
    )

    # ローカル軸に合わせた移動行列を作成する(親はキャンセルする)
    return (
        inv(local_parent_matrix)
        @ inv(rotation_matrix)
        @ local_scale_mat
        @ rotation_matrix
    )


class VmdMorphNameFrames(BaseIndexNameDictModel[VmdMorphFrame]):
    """
    モーフ名別キーフレ辞書
    """

    def __getitem__(self, key: Union[int, str]) -> VmdMorphFrame:
        if isinstance(key, str):
            return VmdMorphFrame(name=key, index=0)

        if key in self.data:
            return self.get_by_index(key)

        # キーフレがない場合、生成したのを返す（保持はしない）
        prev_index, middle_index, next_index = self.range_indexes(key)

        # prevとnextの範囲内である場合、補間曲線ベースで求め直す
        return self.calc(
            prev_index,
            middle_index,
            next_index,
        )

    def calc(self, prev_index: int, index: int, next_index: int) -> VmdMorphFrame:
        if index in self.data:
            return self.data[index]

        if index in self.cache:
            mf = self.cache[index]
        else:
            mf = VmdMorphFrame(name=self.name, index=index)
            self.cache[index] = mf

        if prev_index == next_index:
            if next_index == index:
                # 全くキーフレがない場合、そのまま返す
                return mf

            # FKのprevと等しい場合、指定INDEX以前がないので、その次のをコピーして返す
            mf.ratio = self.data[next_index].ratio
            return mf

        prev_mf = (
            self.data[prev_index]
            if prev_index in self
            else VmdMorphFrame(name=self.name, index=prev_index)
        )
        next_mf = (
            self.data[next_index]
            if next_index in self
            else VmdMorphFrame(name=self.name, index=next_index)
        )

        # モーフは補間なし
        ry = (index - prev_index) / (next_index - prev_index)
        mf.ratio = prev_mf.ratio + (next_mf.ratio - prev_mf.ratio) * ry

        return mf


class VmdMorphFrames(BaseIndexNameDictWrapperModel[VmdMorphNameFrames]):
    """
    モーフキーフレ辞書
    """

    def __init__(self) -> None:
        super().__init__()

    def create(self, key: str) -> VmdMorphNameFrames:
        return VmdMorphNameFrames(name=key)

    @property
    def max_fno(self) -> int:
        return max([max(self[fname].indexes + [0]) for fname in self.names] + [0])

    def animate_vertex_morphs(
        self, fno: int, model: PmxModel, is_gl: bool = True
    ) -> np.ndarray:
        """頂点モーフ変形量"""
        row = len(model.vertices)
        poses = np.full((row, 3), np.zeros(3))

        for morph in model.morphs.filter_by_type(MorphType.VERTEX):
            if morph.name not in self.data:
                # モーフそのものの定義がなければスルー
                continue
            mf = self[morph.name][fno]
            if not mf.ratio:
                continue

            # モーションによる頂点モーフ変動量
            for offset in morph.offsets:
                if type(offset) is VertexMorphOffset and offset.vertex_index < row:
                    ratio_pos: MVector3D = offset.position * mf.ratio
                    if is_gl:
                        poses[offset.vertex_index] += ratio_pos.gl.vector
                    else:
                        poses[offset.vertex_index] += ratio_pos.vector

        return np.array(poses)

    def animate_after_vertex_morphs(
        self, fno: int, model: PmxModel, is_gl: bool = True
    ) -> np.ndarray:
        """ボーン変形後頂点モーフ変形量"""
        row = len(model.vertices)
        poses = np.full((row, 3), np.zeros(3))

        for morph in model.morphs.filter_by_type(MorphType.AFTER_VERTEX):
            if morph.name not in self.data:
                # モーフそのものの定義がなければスルー
                continue
            mf = self[morph.name][fno]
            if not mf.ratio:
                continue

            # モーションによる頂点モーフ変動量
            for offset in morph.offsets:
                if type(offset) is VertexMorphOffset and offset.vertex_index < row:
                    ratio_pos: MVector3D = offset.position * mf.ratio
                    if is_gl:
                        poses[offset.vertex_index] += ratio_pos.gl.vector
                    else:
                        poses[offset.vertex_index] += ratio_pos.vector

        return np.array(poses)

    def animate_uv_morphs(
        self, fno: int, model: PmxModel, uv_index: int, is_gl: bool = True
    ) -> np.ndarray:
        row = len(model.vertices)
        poses = np.full((row, 4), np.zeros(4))

        target_uv_type = MorphType.UV if 0 == uv_index else MorphType.EXTENDED_UV1
        for morph in model.morphs.filter_by_type(target_uv_type):
            if morph.name not in self.data:
                # モーフそのものの定義がなければスルー
                continue
            mf = self[morph.name][fno]
            if not mf.ratio:
                continue

            # モーションによるUVモーフ変動量
            for offset in morph.offsets:
                if type(offset) is UvMorphOffset and offset.vertex_index < row:
                    ratio_pos: MVector4D = offset.uv * mf.ratio
                    poses[offset.vertex_index] += ratio_pos.vector

        if is_gl:
            # UVのYは 1 - y で求め直しておく
            poses[:, 1] = 1 - poses[:, 1]

        return np.array(poses)

    def animate_bone_morphs(self, fno: int, model: PmxModel) -> VmdBoneFrames:
        bone_frames = VmdBoneFrames()
        for morph in model.morphs.filter_by_type(MorphType.BONE):
            if morph.name not in self.data:
                # モーフそのものの定義がなければスルー
                continue
            mf = self[morph.name][fno]
            if not mf.ratio:
                continue

            # モーションによるボーンモーフ変動量
            for offset in morph.offsets:
                if type(offset) is BoneMorphOffset and offset.bone_index in model.bones:
                    bf = bone_frames[model.bones[offset.bone_index].name][fno]
                    bf = self.animate_bone_morph_frame(fno, model, bf, offset, mf.ratio)
                    bone_frames[bf.name][fno] = bf

        return bone_frames

    def animate_bone_morph_frame(
        self,
        fno: int,
        model: PmxModel,
        bf: VmdBoneFrame,
        offset: BoneMorphOffset,
        ratio: float,
    ) -> VmdBoneFrame:
        bf.position += offset.position * ratio
        bf.local_position += offset.local_position * ratio
        bf.rotation *= MQuaternion.from_euler_degrees(offset.rotation.degrees * ratio)
        bf.local_rotation *= MQuaternion.from_euler_degrees(
            offset.local_rotation.degrees * ratio
        )
        bf.scale += offset.scale * ratio
        bf.local_scale += offset.local_scale * ratio
        return bf

    def animate_group_morphs(
        self,
        fno: int,
        model: PmxModel,
        materials: list[ShaderMaterial],
        is_gl: bool = True,
    ) -> tuple[np.ndarray, VmdBoneFrames, list[ShaderMaterial]]:
        group_vertex_poses = np.full((len(model.vertices), 3), np.zeros(3))
        bone_frames = VmdBoneFrames()

        # デフォルトの材質情報を保持（シェーダーに合わせて一部入れ替え）
        for morph in model.morphs.filter_by_type(MorphType.GROUP):
            if morph.name not in self.data:
                # モーフそのものの定義がなければスルー
                continue
            mf = self[morph.name][fno]
            if not mf.ratio:
                continue

            # モーションによるボーンモーフ変動量
            for group_offset in morph.offsets:
                if (
                    type(group_offset) is GroupMorphOffset
                    and group_offset.morph_index in model.morphs
                ):
                    part_morph = model.morphs[group_offset.morph_index]
                    mf_factor = mf.ratio * group_offset.morph_factor
                    if not mf_factor:
                        continue

                    for offset in part_morph.offsets:
                        if (
                            type(offset) is VertexMorphOffset
                            and offset.vertex_index < group_vertex_poses.shape[0]
                        ):
                            ratio_pos: MVector3D = offset.position * mf_factor
                            if is_gl:
                                group_vertex_poses[
                                    offset.vertex_index
                                ] += ratio_pos.gl.vector
                            else:
                                group_vertex_poses[
                                    offset.vertex_index
                                ] += ratio_pos.vector
                        elif (
                            type(offset) is BoneMorphOffset
                            and offset.bone_index in model.bones
                        ):
                            bf = bone_frames[model.bones[offset.bone_index].name][fno]
                            bf = self.animate_bone_morph_frame(
                                fno, model, bf, offset, mf_factor
                            )
                            bone_frames[bf.name][fno] = bf
                        elif (
                            type(offset) is MaterialMorphOffset
                            and offset.material_index in model.materials
                        ):
                            materials = self.animate_material_morph_frame(
                                model,
                                offset,
                                mf_factor,
                                materials,
                                MShader.LIGHT_AMBIENT4,
                            )

        return group_vertex_poses, bone_frames, materials

    def animate_material_morph_frame(
        self,
        model: PmxModel,
        offset: MaterialMorphOffset,
        ratio: float,
        materials: list[ShaderMaterial],
        light_ambient: MVector4D,
    ) -> list[ShaderMaterial]:
        if 0 > offset.material_index:
            # 0の場合、全材質を対象とする
            material_indexes = model.materials.indexes
        else:
            # 特定材質の場合、材質固定
            material_indexes = [offset.material_index]
        # 指定材質を対象として変動量を割り当てる
        for target_calc_mode in [
            MaterialMorphCalcMode.MULTIPLICATION,
            MaterialMorphCalcMode.ADDITION,
        ]:
            # 先に乗算を計算した後に加算を加味する
            for material_index in material_indexes:
                # 元々の材質情報をコピー
                mat = model.materials[material_index]

                # オフセットに合わせた材質情報
                material = Material(
                    mat.index,
                    mat.name,
                    mat.english_name,
                )
                material.diffuse = offset.diffuse
                material.ambient = offset.ambient
                material.specular = offset.specular
                material.edge_color = offset.edge_color
                material.edge_size = offset.edge_size

                material_offset = ShaderMaterial(
                    material,
                    light_ambient,
                    offset.texture_factor,
                    offset.toon_texture_factor,
                    offset.sphere_texture_factor,
                )

                # オフセットに合わせた材質情報
                material_offset *= ratio
                if offset.calc_mode == target_calc_mode:
                    if offset.calc_mode == MaterialMorphCalcMode.ADDITION:
                        # 加算
                        materials[material_index] += material_offset
                    else:
                        # 乗算
                        materials[material_index] *= material_offset

        return materials

    def animate_material_morphs(
        self, fno: int, model: PmxModel
    ) -> list[ShaderMaterial]:
        # デフォルトの材質情報を保持（シェーダーに合わせて一部入れ替え）
        materials = [ShaderMaterial(m, MShader.LIGHT_AMBIENT4) for m in model.materials]

        for morph in model.morphs.filter_by_type(MorphType.MATERIAL):
            if morph.name not in self.data:
                # モーフそのものの定義がなければスルー
                continue
            mf = self[morph.name][fno]
            if not mf.ratio:
                continue

            # モーションによる材質モーフ変動量
            for offset in morph.offsets:
                if type(offset) is MaterialMorphOffset and (
                    offset.material_index in model.materials
                    or 0 > offset.material_index
                ):
                    materials = self.animate_material_morph_frame(
                        model, offset, mf.ratio, materials, MShader.LIGHT_AMBIENT4
                    )

        return materials


class VmdCameraFrames(BaseIndexNameDictModel[VmdCameraFrame]):
    """
    カメラキーフレリスト
    """

    def __init__(self) -> None:
        super().__init__()


class VmdLightFrames(BaseIndexNameDictModel[VmdLightFrame]):
    """
    照明キーフレリスト
    """

    def __init__(self) -> None:
        super().__init__()


class VmdShadowFrames(BaseIndexNameDictModel[VmdShadowFrame]):
    """
    照明キーフレリスト
    """

    def __init__(self) -> None:
        super().__init__()


class VmdShowIkFrames(BaseIndexNameDictModel[VmdShowIkFrame]):
    """
    IKキーフレリスト
    """

    def __init__(self) -> None:
        super().__init__()


class VmdMotion(BaseHashModel):
    """
    VMDモーション

    Parameters
    ----------
    path : str, optional
        パス, by default None
    signature : str, optional
        パス, by default None
    model_name : str, optional
        パス, by default None
    bones : VmdBoneFrames
        ボーンキーフレリスト, by default []
    morphs : VmdMorphFrames
        モーフキーフレリスト, by default []
    morphs : VmdMorphFrames
        モーフキーフレリスト, by default []
    cameras : VmdCameraFrames
        カメラキーフレリスト, by default []
    lights : VmdLightFrames
        照明キーフレリスト, by default []
    shadows : VmdShadowFrames
        セルフ影キーフレリスト, by default []
    show_iks : VmdShowIkFrames
        IKキーフレリスト, by default []
    """

    __slots__ = (
        "path",
        "digest",
        "signature",
        "model_name",
        "bones",
        "morphs",
        "cameras",
        "lights",
        "shadows",
        "show_iks",
    )

    def __init__(
        self,
        path: Optional[str] = None,
    ):
        super().__init__(path=path or "")
        self.signature: str = ""
        self.model_name: str = ""
        self.bones: VmdBoneFrames = VmdBoneFrames()
        self.morphs: VmdMorphFrames = VmdMorphFrames()
        self.cameras: VmdCameraFrames = VmdCameraFrames()
        self.lights: VmdLightFrames = VmdLightFrames()
        self.shadows: VmdShadowFrames = VmdShadowFrames()
        self.show_iks: VmdShowIkFrames = VmdShowIkFrames()

    @property
    def bone_count(self) -> int:
        return int(np.sum([len(bfs.register_indexes) for bfs in self.bones]))

    @property
    def morph_count(self) -> int:
        return int(np.sum([len(mfs.indexes) for mfs in self.morphs]))

    @property
    def ik_count(self) -> int:
        return int(np.sum([len(ifs.iks) for ifs in self.show_iks]))

    @property
    def max_fno(self) -> int:
        return max(self.bones.max_fno, self.morphs.max_fno)

    @property
    def name(self) -> str:
        return self.model_name

    def cache_clear(self) -> None:
        self.bones.cache_clear()

    def append_bone_frame(self, bf: VmdBoneFrame) -> None:
        """ボーンキーフレ追加"""
        self.bones[bf.name].append(bf)

    def append_morph_frame(self, mf: VmdMorphFrame) -> None:
        """モーフキーフレ追加"""
        self.morphs[mf.name].append(mf)

    def insert_bone_frame(self, bf: VmdBoneFrame) -> None:
        """ボーンキーフレ挿入"""
        self.bones[bf.name].insert(bf)

    def insert_morph_frame(self, mf: VmdMorphFrame) -> None:
        """モーフキーフレ挿入"""
        self.morphs[mf.name].insert(mf)

    def animate(self, fno: int, model: PmxModel, is_gl: bool = True) -> tuple[
        int,
        np.ndarray,
        VmdBoneFrameTrees,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        list[ShaderMaterial],
    ]:
        logger.debug(f"-- スキンメッシュアニメーション[{model.name}][{fno:04d}]: 開始")

        # 頂点モーフ
        vertex_morph_poses = self.morphs.animate_vertex_morphs(fno, model, is_gl)
        # logger.test(f"-- スキンメッシュアニメーション[{model.name}][{fno:04d}]: 頂点モーフ")

        # ボーン変形後頂点モーフ
        after_vertex_morph_poses = self.morphs.animate_after_vertex_morphs(
            fno, model, is_gl
        )
        # logger.test(f"-- スキンメッシュアニメーション[{model.name}][{fno:04d}]: ボーン変形後頂点モーフ")

        # UVモーフ
        uv_morph_poses = self.morphs.animate_uv_morphs(fno, model, 0, is_gl)
        # logger.test(f"-- スキンメッシュアニメーション[{model.name}][{fno:04d}]: UVモーフ")

        # 追加UVモーフ1
        uv1_morph_poses = self.morphs.animate_uv_morphs(fno, model, 1, is_gl)
        # logger.test(f"-- スキンメッシュアニメーション[{model.name}][{fno:04d}]: 追加UVモーフ1")

        # 追加UVモーフ2-4は無視

        # 材質モーフ
        material_morphs = self.morphs.animate_material_morphs(fno, model)
        # logger.test(f"-- スキンメッシュアニメーション[{model.name}][{fno:04d}]: 材質モーフ")

        # グループモーフ
        (
            group_vertex_morph_poses,
            group_morph_bone_frames,
            group_materials,
        ) = self.morphs.animate_group_morphs(fno, model, material_morphs, is_gl)
        # logger.test(f"-- スキンメッシュアニメーション[{model.name}][{fno:04d}]: グループモーフ")

        bone_matrixes = self.animate_bone([fno], model)

        # OpenGL座標系に変換

        gl_matrixes = np.array([bft.local_matrix_ary.T for bft in bone_matrixes])

        gl_matrixes[..., 0, 1:3] *= -1
        gl_matrixes[..., 1:3, 0] *= -1
        gl_matrixes[..., 3, 0] *= -1

        # logger.test(f"-- スキンメッシュアニメーション[{model.name}][{fno:04d}]: OpenGL座標系変換")

        return (
            fno,
            gl_matrixes,
            bone_matrixes,
            vertex_morph_poses + group_vertex_morph_poses,
            after_vertex_morph_poses,
            uv_morph_poses,
            uv1_morph_poses,
            group_materials,
        )

    def animate_bone(
        self,
        fnos: list[int],
        model: PmxModel,
        bone_names: Iterable[str] = [],
        is_calc_ik: bool = True,
        clear_ik: bool = False,
        out_fno_log: bool = False,
        description: str = "",
        max_worker: int = 1,
    ) -> VmdBoneFrameTrees:
        all_morph_bone_frames = VmdBoneFrames()

        if clear_ik:
            self.cache_clear()

        for fidx, fno in enumerate(fnos):
            if out_fno_log:
                logger.count(
                    "キーフレーム確認[{d}]",
                    d=description,
                    index=fidx,
                    total_index_count=len(fnos),
                    display_block=500,
                )

            # logger.test(f"-- ボーンアニメーション[{model.name}][{fno:04d}]: 開始")

            # 材質モーフ
            material_morphs = self.morphs.animate_material_morphs(fno, model)
            # logger.test(f"-- ボーンアニメーション[{model.name}][{fno:04d}]: 材質モーフ")

            # ボーンモーフ
            morph_bone_frames = self.morphs.animate_bone_morphs(fno, model)
            # logger.test(f"-- ボーンアニメーション[{model.name}][{fno:04d}]: ボーンモーフ")

            for bfs in morph_bone_frames:
                bf = bfs[fno]

                if clear_ik:
                    # IK計算しない場合、IK計算結果を渡さない
                    bf.ik_rotation = None

                mbf = all_morph_bone_frames[bf.name][bf.index]
                all_morph_bone_frames[bf.name][bf.index] = mbf + bf

            # グループモーフ
            _, group_morph_bone_frames, _ = self.morphs.animate_group_morphs(
                fno, model, material_morphs
            )
            # logger.test(f"-- ボーンアニメーション[{model.name}][{fno:04d}]: グループモーフ")

            for bfs in group_morph_bone_frames:
                bf = bfs[fno]
                mbf = all_morph_bone_frames[bf.name][bf.index]

                if clear_ik:
                    # IK計算しない場合、IK計算結果を渡さない
                    bf.ik_rotation = None
                    mbf.ik_rotation = None

                all_morph_bone_frames[bf.name][bf.index] = mbf + bf

            # logger.test(f"-- ボーンアニメーション[{model.name}][{fno:04d}]: モーフキーフレ加算")

        # ボーン変形行列操作
        bone_matrixes = self.bones.animate_bone_matrixes(
            fnos,
            model,
            all_morph_bone_frames,
            bone_names,
            is_calc_ik=is_calc_ik,
            out_fno_log=out_fno_log,
            description=description,
            max_worker=max_worker,
        )
        # logger.test(f"-- ボーンアニメーション[{model.name}]: ボーン変形行列操作")

        return bone_matrixes
