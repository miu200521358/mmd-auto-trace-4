import os
import sys
import joblib
import numpy as np
import torch


sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from mlib.vmd.vmd_collection import VmdMotion, VmdBoneFrame
from mlib.vmd.vmd_writer import VmdWriter
from mlib.core.math import MVector3D, MQuaternion

H36M_JOINT_NAMES = [
    "Pelvis",
    "RHip",
    "RKnee",
    "RFoot",
    "RFootTip",
    "LHip",
    "LKnee",
    "LFoot",
    "Spine1",
    "Spine2",
    "Neck",
    "Head",
    "LShoulder",
    "LElbow",
    "LWrist",
    "RShoulder",
    "RElbow",
    "RWrist",
]

COCO_JOINT_NAMES = [
    "nose",  # 0
    "leye",  # 1
    "reye",  # 2
    "lear",  # 3
    "rear",  # 4
    "lshoulder",  # 5
    "rshoulder",  # 6
    "lelbow",  # 7
    "relbow",  # 8
    "lwrist",  # 9
    "rwrist",  # 10
    "lhip",  # 11
    "rhip",  # 12
    "lknee",  # 13
    "rknee",  # 14
    "lankle",  # 15
    "rankle",  # 16
]

MPI_JOINT_NAMES = [
    "HeadTop",
    "Neck",
    "RShoulder",
    "RElbow",
    "RWrist",
    "LShoulder",
    "LElbow",
    "LWrist",
    "RHip",
    "RKnee",
    "RAnkle",
    "LHip",
    "LKnee",
    "LAnkle",
    "Root",
    "Spine",
    "Head",
]

SMPL_JOINT_24 = [
    "Pelvis",  # 0
    "LHip",  # 1
    "RHip",  # 2
    "Spine1",  # 3
    "LKnee",  # 4
    "RKnee",  # 5
    "Spine2",  # 6
    "LAnkle",  # 7
    "RAnkle",  # 8
    "Spine3",  # 9
    "LFoot",  # 10
    "RFoot",  # 11
    "Head",  # 12
    "LCollar",  # 13
    "RCollar",  # 14
    "Nose",  # 15
    "LShoulder",  # 16
    "RShoulder",  # 17
    "LElbow",  # 18
    "RElbow",  # 19
    "LWrist",  # 20
    "RWrist",  # 21
    "LMiddle",  # 22
    "RMiddle",  # 23
]

MAIN_JOINTS = [
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
    21,
]

# 身長158cmプラグインより
MIKU_CM = 0.1259496

np.set_printoptions(suppress=True, precision=6, threshold=30, linewidth=200)

if __name__ == "__main__":
    tracking_results_path = (
        "C:/MMD/mmd-auto-trace-4/WHAM/output/demo/IMG_9732/tracking_results.pth"
    )

    tracking_results = dict(joblib.load(tracking_results_path))

    print(tracking_results)

    for k, v in tracking_results.items():
        vd = dict(v)
        frame_ids = vd["frame_id"]
        bboxs = vd["bbox"]
        keypoints = vd["keypoints"]
        features = vd["features"].cpu().numpy()
        init_global_orients = vd["init_global_orient"].cpu().numpy()
        init_body_poses = vd["init_body_pose"].cpu().numpy()
        init_betas = vd["init_betas"].cpu().numpy()
        flipped_bboxs = vd["flipped_bbox"]
        flipped_keypoints = vd["flipped_keypoints"]
        flipped_features = vd["flipped_features"].cpu().numpy()
        flipped_init_global_orients = vd["flipped_init_global_orient"].cpu().numpy()
        flipped_init_body_poses = vd["flipped_init_body_pose"].cpu().numpy()
        flipped_init_betas = vd["flipped_init_betas"].cpu().numpy()

    # ------------------------------
    wham_output_path = (
        "C:/MMD/mmd-auto-trace-4/WHAM/output/demo/IMG_9732/wham_output.pkl"
    )

    # .pthファイルからデータをロード
    wham_output = joblib.load(wham_output_path)

    # numpy配列に変換
    wham_output_numpy = np.array(wham_output)

    print(wham_output_numpy)

    wham_output_dict = dict(wham_output)

    poses_motion = VmdMotion()
    poses_world_motion = VmdMotion()
    poses_rot_motion = VmdMotion()
    poses_world_rot_motion = VmdMotion()

    for tracking_key, tracking_value in wham_output_dict.items():
        print(tracking_key, tracking_value)
        poses = tracking_value["pose"]
        print("poses", poses[:2])
        trans = tracking_value["trans"]
        print("trans", trans[:2])
        poses_world = tracking_value["pose_world"]
        print("poses_world", poses_world[:2])
        trans_world = tracking_value["trans_world"]
        print("trans_world", trans_world[:2])
        betas = tracking_value["betas"]
        print("betas", betas[:2])
        verts = tracking_value["verts"]
        print("verts", verts[:2])
        frame_ids = tracking_value["frame_ids"]
        print("frame_ids", frame_ids[:2])
        poses_body = tracking_value["poses_body"]
        print("poses_body", poses_body[:2])
        print("--------------------")

        for i, fno in enumerate(frame_ids):
            t = MVector3D(trans[i, 0], trans[i, 1], trans[i, 2])
            tw = MVector3D(trans_world[i, 0], trans_world[i, 1], trans_world[i, 2])
            pose = poses[i].reshape(-1, 4)
            pose_world = poses_world[i].reshape(-1, 4)
            pose_body = poses_body[i]
            for j in range(pose.shape[0]):
                pose_bf = VmdBoneFrame(fno, SMPL_JOINT_24[j], register=True)
                pose_bf.position = MVector3D(pose[j, 0], pose[j, 1], pose[j, 2])
                pose_bf.position *= 50 * MIKU_CM

                poses_motion.append_bone_frame(pose_bf)

            for j in range(pose.shape[0]):
                if j == 0:
                    pose_bf = VmdBoneFrame(fno, SMPL_JOINT_24[j], register=True)
                    pose_bf.position = MVector3D(pose[j, 0], pose[j, 1], pose[j, 2])
                    pose_bf.position *= 50 * MIKU_CM
                    poses_rot_motion.append_bone_frame(pose_bf)

                jj = j - 1
                pose_bf = VmdBoneFrame(fno, SMPL_JOINT_24[jj], register=True)
                pose_bf.rotation = MQuaternion.from_axes(
                    MVector3D(
                        pose_body[jj, 0, 0],
                        pose_body[jj, 1, 0],
                        pose_body[jj, 2, 0],
                    ),
                    MVector3D(
                        pose_body[jj, 0, 1],
                        pose_body[jj, 1, 1],
                        pose_body[jj, 2, 1],
                    ),
                    MVector3D(
                        pose_body[jj, 0, 2],
                        pose_body[jj, 1, 2],
                        pose_body[jj, 2, 2],
                    ),
                )

                poses_rot_motion.append_bone_frame(pose_bf)

            for j in range(pose_world.shape[0]):
                pose_world_bf = VmdBoneFrame(fno, SMPL_JOINT_24[j], register=True)
                pose_world_bf.position = MVector3D(
                    pose_world[j, 0], pose_world[j, 2], pose_world[j, 1]
                )
                pose_world_bf.position *= 50 * MIKU_CM

                poses_world_motion.append_bone_frame(pose_world_bf)

            for j in range(pose_world.shape[0]):
                if j == 0:
                    pose_world_bf = VmdBoneFrame(fno, "Pelvis", register=True)
                    pose_world_bf.position = MVector3D(
                        pose_world[j, 2], pose_world[j, 0], pose_world[j, 1]
                    )
                    pose_world_bf.position *= 50 * MIKU_CM
                    poses_world_rot_motion.append_bone_frame(pose_world_bf)

                jj = j - 1
                pose_world_bf = VmdBoneFrame(fno, SMPL_JOINT_24[jj], register=True)
                pose_world_bf.rotation = MQuaternion.from_axes(
                    MVector3D(
                        pose_body[jj, 0, 0],
                        pose_body[jj, 1, 0],
                        pose_body[jj, 2, 0],
                    ),
                    MVector3D(
                        pose_body[jj, 0, 1],
                        pose_body[jj, 1, 1],
                        pose_body[jj, 2, 1],
                    ),
                    MVector3D(
                        pose_body[jj, 0, 2],
                        pose_body[jj, 1, 2],
                        pose_body[jj, 2, 2],
                    ),
                )

                poses_world_rot_motion.append_bone_frame(pose_world_bf)

    VmdWriter(
        poses_motion,
        "C:/MMD/mmd-auto-trace-4/WHAM/output/demo/IMG_9732/output_poses.vmd",
        "h36_17",
    ).save()

    VmdWriter(
        poses_world_motion,
        "C:/MMD/mmd-auto-trace-4/WHAM/output/demo/IMG_9732/output_poses_world.vmd",
        "h36_17",
    ).save()

    VmdWriter(
        poses_motion,
        "C:/MMD/mmd-auto-trace-4/WHAM/output/demo/IMG_9732/output_poses_rot.vmd",
        "h36_17",
    ).save()

    VmdWriter(
        poses_world_motion,
        "C:/MMD/mmd-auto-trace-4/WHAM/output/demo/IMG_9732/output_poses_world_rot.vmd",
        "h36_17",
    ).save()
