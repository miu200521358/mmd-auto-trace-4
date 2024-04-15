import argparse
import os
import numpy as np
from tqdm import tqdm

from mlib.vmd.vmd_collection import VmdMotion, VmdBoneFrame
from mlib.vmd.vmd_reader import VmdReader
from mlib.vmd.vmd_writer import VmdWriter
from mlib.core.math import MVector3D, MQuaternion
from mlib.pmx.pmx_reader import PmxReader

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HMR2 demo code")
    parser.add_argument("--target_dir", type=str)

    args = parser.parse_args()

    mp_rot_motion = VmdReader().read_by_filepath(
        os.path.join(args.target_dir, "output_poses_mp_rot.vmd")
    )
    ik_bake_motion = mp_rot_motion.copy()
    ik_motion = mp_rot_motion.copy()

    pmx_reader = PmxReader()
    trace_model = pmx_reader.read_by_filepath(
        "/mnt/c/MMD/mmd-auto-trace-4/configs/pmx/trace_model.pmx"
    )

    trace_ik_model = pmx_reader.read_by_filepath(
        "/mnt/c/MMD/mmd-auto-trace-4/configs/pmx/trace_ik_model.pmx"
    )

    # ローカル軸制限設定
    trace_ik_model.bones["左ひじIK"].ik.links[1].local_angle_limit = True
    trace_ik_model.bones["左ひじIK"].ik.links[1].local_min_angle_limit = MVector3D(
        0, -5, 0
    )
    trace_ik_model.bones["左ひじIK"].ik.links[1].local_max_angle_limit = MVector3D(
        0, 180, 0
    )

    trace_ik_model.bones["右ひじIK"].ik.links[1].local_angle_limit = True
    trace_ik_model.bones["右ひじIK"].ik.links[1].local_min_angle_limit = MVector3D(
        0, -5, 0
    )
    trace_ik_model.bones["右ひじIK"].ik.links[1].local_max_angle_limit = MVector3D(
        0, 180, 0
    )

    matrixes = mp_rot_motion.animate_bone(
        list(range(mp_rot_motion.bones.max_fno)),
        trace_model,
        is_calc_ik=False,
        out_fno_log=True,
        description="事前計算",
    )

    # 上半身
    for fno in tqdm(range(mp_rot_motion.bones.max_fno), desc="上半身準備"):
        upper_ik_bf = VmdBoneFrame(name="上半身IK", index=fno, register=True)
        upper_ik_bf.position = matrixes["首", fno].position
        ik_bake_motion.append_bone_frame(upper_ik_bf)

        upper_bf = VmdBoneFrame(name="上半身", index=fno, register=True)
        x_qq, y_qq, z_qq, xz_qq = matrixes[
            "上半身", fno
        ].frame_fk_rotation.separate_by_axis(
            trace_ik_model.bones["上半身"].corrected_local_y_vector
        )
        upper_bf.rotation = x_qq
        ik_bake_motion.append_bone_frame(upper_bf)

    upper_matrixes = ik_bake_motion.animate_bone(
        list(range(mp_rot_motion.bones.max_fno)),
        trace_ik_model,
        bone_names=["首先"],
        is_calc_ik=True,
        out_fno_log=True,
        description="上半身計算",
    )

    for fno in tqdm(range(mp_rot_motion.bones.max_fno), desc="上半身結果"):
        upper_bf = VmdBoneFrame(name="上半身", index=fno, register=True)
        upper_bf.rotation = upper_matrixes["上半身捩", fno].frame_fk_rotation * upper_matrixes["上半身", fno].frame_fk_rotation
        ik_motion.append_bone_frame(upper_bf)

        upper2_bf = VmdBoneFrame(name="上半身2", index=fno, register=True)
        upper2_bf.rotation = upper_matrixes["上半身2捩", fno].frame_fk_rotation * upper_matrixes["上半身2", fno].frame_fk_rotation
        ik_motion.append_bone_frame(upper2_bf)

    # 足IKの設定
    for direction in ["左", "右"]:
        leg_name = f"{direction}足"
        knee_name = f"{direction}ひざ"
        ankle_name = f"{direction}足首"
        toe_name = f"{direction}つま先"
        leg_ik_name = f"{direction}足ＩＫ"

        arm_name = f"{direction}腕"
        elbow_name = f"{direction}ひじ"
        wrist_name = f"{direction}手首"

        for fno in tqdm(range(mp_rot_motion.bones.max_fno), desc=f"{direction}足"):
            leg_ik_bf = VmdBoneFrame(name=leg_ik_name, index=fno, register=True)
            leg_ik_bf.position = matrixes[ankle_name, fno].position
            leg_ik_bf.rotation = matrixes[ankle_name, fno].local_matrix.to_quaternion()
            ik_motion.append_bone_frame(leg_ik_bf)

            leg_bf = VmdBoneFrame(name=leg_name, index=fno, register=True)
            leg_bf.rotation = matrixes[leg_name, fno].frame_fk_rotation
            ik_motion.append_bone_frame(leg_bf)

            knee_bf = VmdBoneFrame(name=knee_name, index=fno, register=True)
            knee_bf.rotation = matrixes[knee_name, fno].frame_fk_rotation
            ik_motion.append_bone_frame(knee_bf)

            ankle_bf = VmdBoneFrame(name=ankle_name, index=fno, register=True)
            ankle_bf.rotation = matrixes[ankle_name, fno].frame_fk_rotation
            ik_motion.append_bone_frame(ankle_bf)

    VmdWriter(
        ik_motion,
        os.path.join(args.target_dir, "output_poses_mp_rot_ik.vmd"),
        "WHAM_MP",
    ).save()
