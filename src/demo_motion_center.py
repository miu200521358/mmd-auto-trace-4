import argparse
import os
import joblib
import numpy as np
from tqdm import tqdm

from mlib.vmd.vmd_collection import VmdMotion, VmdBoneFrame
from mlib.vmd.vmd_writer import VmdWriter
from mlib.pmx.pmx_reader import PmxReader
from mlib.pmx.pmx_collection import PmxModel
from mlib.core.math import MVector3D, MQuaternion
from loguru import logger

np.set_printoptions(suppress=True, precision=6, threshold=30, linewidth=200)

# 身長158cmプラグインより
MIKU_CM = 0.1259496
X = 0
Y = 1
Z = 2
XS = 1
YS = 1
ZS = 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HMR2 demo code")
    parser.add_argument("--target_dir", type=str)

    args = parser.parse_args()
    logger.info(f"target_dir: {args.target_dir} ---------------------------")

    wham_center_motion = VmdMotion()
    wham_mov1_motion = VmdMotion()
    wham_mov2_motion = VmdMotion()
    wham_mov3_motion = VmdMotion()

    all_vis_results = joblib.load(os.path.join(args.target_dir, "wham_output_vis.pkl"))
    all_wham_results = joblib.load(os.path.join(args.target_dir, "wham_output.pkl"))
    start_pos = MVector3D()

    i = 0
    for (wham_idx, wham_results), (vis_idx, vis_results) in zip(
        all_wham_results.items(), all_vis_results.items()
    ):
        for j, (
            poses_root_world,
            poses_root_cam,
            trans_world,
            pred_root_world,
            pose_world,
            pose,
            joints,
            global_R,
            global_T,
        ) in enumerate(
            tqdm(
                zip(
                    wham_results["poses_root_world"][0],
                    wham_results["poses_root_cam"],
                    wham_results["trans_world"],
                    wham_results["pred_root_world"],
                    wham_results["pose_world"],
                    wham_results["pose"],
                    vis_results["joints"],
                    vis_results["global_R"],
                    vis_results["global_T"],
                ),
                desc=f"WHAM Center {wham_idx} {vis_idx}",
            )
        ):
            bf1 = VmdBoneFrame(name="1", index=i, register=True)
            bf1.position = (
                MVector3D(
                    float(global_R[0][X] * XS), float(global_R[0][Y] * YS), float(global_R[0][Z] * ZS)
                )
                / MIKU_CM
            )
            wham_center_motion.append_bone_frame(bf1)

            bf2 = VmdBoneFrame(name="2", index=i, register=True)
            bf2.position = (
                MVector3D(
                    float(global_R[1][X] * XS), float(global_R[1][Y] * YS), float(global_R[1][Z] * ZS)
                )
                / MIKU_CM
            )
            wham_center_motion.append_bone_frame(bf2)

            bf3 = VmdBoneFrame(name="3", index=i, register=True)
            bf3.position = (
                MVector3D(
                    float(global_R[2][X] * XS), float(global_R[2][Y] * YS), float(global_R[2][Z] * ZS)
                )
                / MIKU_CM
            )
            wham_center_motion.append_bone_frame(bf3)

            bf4 = VmdBoneFrame(name="4", index=i, register=True)
            bf4.position = (
                MVector3D(float(global_T[X] * XS), float(global_T[Y] * YS), float(global_T[Z] * ZS))
                / MIKU_CM
            )
            wham_center_motion.append_bone_frame(bf4)

            bf6 = VmdBoneFrame(name="6", index=i, register=True)
            bf6.position = (
                MVector3D(
                    float(poses_root_cam[0][0][X] * XS),
                    float(poses_root_cam[0][0][Y] * YS),
                    float(poses_root_cam[0][0][Z] * ZS),
                )
                / MIKU_CM
            )
            wham_center_motion.append_bone_frame(bf6)

            bf7 = VmdBoneFrame(name="7", index=i, register=True)
            bf7.position = (
                MVector3D(
                    float(poses_root_cam[0][1][X] * XS),
                    float(poses_root_cam[0][1][Y] * YS),
                    float(poses_root_cam[0][1][Z] * ZS),
                )
                / MIKU_CM
            )
            wham_center_motion.append_bone_frame(bf7)

            bf8 = VmdBoneFrame(name="8", index=i, register=True)
            bf8.position = (
                MVector3D(
                    float(poses_root_cam[0][2][X] * XS),
                    float(poses_root_cam[0][2][Y] * YS),
                    float(poses_root_cam[0][2][Z] * ZS),
                )
                / MIKU_CM
            )
            wham_center_motion.append_bone_frame(bf8)

            bf9 = VmdBoneFrame(name="9", index=i, register=True)
            bf9.position = (
                MVector3D(
                    float(trans_world[0]), float(trans_world[1]), float(trans_world[2])
                )
                / MIKU_CM
            )
            wham_center_motion.append_bone_frame(bf9)

            bf10 = VmdBoneFrame(name="10", index=i, register=True)
            bf10.position = (
                MVector3D(
                    float(pred_root_world[X] * XS),
                    float(pred_root_world[Y] * YS),
                    float(pred_root_world[Z] * ZS),
                )
                / MIKU_CM
            )
            wham_center_motion.append_bone_frame(bf10)

            bf11 = VmdBoneFrame(name="11", index=i, register=True)
            bf11.position = (
                MVector3D(
                    float(poses_root_world[0][X] * XS),
                    float(poses_root_world[0][Y] * YS),
                    float(poses_root_world[0][Z] * ZS),
                )
                / MIKU_CM
            )
            wham_center_motion.append_bone_frame(bf11)

            bf12 = VmdBoneFrame(name="12", index=i, register=True)
            bf12.position = (
                MVector3D(
                    float(poses_root_world[1][X] * XS),
                    float(poses_root_world[1][Y] * YS),
                    float(poses_root_world[1][Z] * ZS),
                )
                / MIKU_CM
            )
            wham_center_motion.append_bone_frame(bf12)

            bf13 = VmdBoneFrame(name="13", index=i, register=True)
            bf13.position = (
                MVector3D(
                    float(poses_root_world[2][X] * XS),
                    float(poses_root_world[2][Y] * YS),
                    float(poses_root_world[2][Z] * ZS),
                )
                / MIKU_CM
            )

            for j, joint in enumerate(joints):
                joint_pos = (
                    MVector3D(float(joint[X] * XS), float(joint[Y] * YS), float(joint[Z] * ZS))
                    / MIKU_CM
                )
                bf = VmdBoneFrame(name=f"{j}", index=i, register=True)
                bf.position = joint_pos + bf9.position
                wham_mov1_motion.append_bone_frame(bf)

            for j, joint in enumerate(pose_world.reshape(-1, 3)):
                joint_pos = (
                    MVector3D(float(joint[X] * XS), float(joint[Y] * YS), float(joint[Z] * ZS))
                    / MIKU_CM
                )
                bf = VmdBoneFrame(name=f"{j}", index=i, register=True)
                bf.position = joint_pos
                wham_mov2_motion.append_bone_frame(bf)

            for j, joint in enumerate(pose.reshape(-1, 3)):
                joint_pos = (
                    MVector3D(float(joint[X] * XS), float(joint[Y] * YS), float(joint[Z] * ZS))
                    / MIKU_CM
                )
                bf = VmdBoneFrame(name=f"{j}", index=i, register=True)
                bf.position = joint_pos
                wham_mov3_motion.append_bone_frame(bf)

            i += 1

    VmdWriter(
        wham_center_motion,
        os.path.join(args.target_dir, f"wham_mov_center_{(X+1)*XS}{(Y+1)*YS}{(Z+1)*ZS}.vmd"),
        "WHAM",
    ).save()

    VmdWriter(
        wham_mov1_motion,
        os.path.join(args.target_dir, f"wham_mov_number_joints_{(X+1)*XS}{(Y+1)*YS}{(Z+1)*ZS}.vmd"),
        "WHAM",
    ).save()

    VmdWriter(
        wham_mov2_motion,
        os.path.join(args.target_dir, f"wham_mov_number_pos_world_{(X+1)*XS}{(Y+1)*YS}{(Z+1)*ZS}.vmd"),
        "WHAM",
    ).save()

    VmdWriter(
        wham_mov3_motion,
        os.path.join(args.target_dir, f"wham_mov_number_pos_{(X+1)*XS}{(Y+1)*YS}{(Z+1)*ZS}.vmd"),
        "WHAM",
    ).save()
