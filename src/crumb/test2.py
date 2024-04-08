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

SMPL_JOINT_32 = [
    "Nose",  # 0
    "LEye",  # 1
    "REye",  # 2
    "LEar",  # 3
    "REar",  # 4
    "LShoulder",  # 5
    "RShoulder",  # 6
    "LElbow",  # 7
    "RElbow",  # 8
    "LWrist",  # 9
    "RWrist",  # 10
    "LLeg",  # 11
    "RLeg",  # 12
    "LKnee",  # 13
    "RKnee",  # 14
    "LAnkle",  # 15
    "RAnkle",  # 16
    "",  # 17
    "",  # 18
    "RHip",  # 19
    "LHip",  # 20
    "",  # 21
    "",  # 22
    "",  # 23
    "",  # 24
    "",  # 25
    "",  # 26
    "",  # 27
    "",  # 28
    "Neck",  # 29
    "Head",  # 30
    "",  # 31
    "",  # 32
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
    # ------------------------------
    wham_output_path = (
        "C:/MMD/mmd-auto-trace-4/WHAM/output/demo/IMG_9732/wham_output_vis.pkl"
    )

    # .pthファイルからデータをロード
    wham_output = joblib.load(wham_output_path)

    # numpy配列に変換
    wham_output_numpy = np.array(wham_output)

    print(wham_output_numpy)

    wham_output_dict = dict(wham_output)

    poses_motion = VmdMotion()

    joints = wham_output_dict["joints"]
    print("joints", joints[:2])

    for i in range(joints.shape[0]):
        joint = joints[i]
        # print(f"joint {i}: {joint}")
        for j in range(joints.shape[1]):
            if not SMPL_JOINT_32[j]:
                continue
            jt = joint[j]
            pose_bf = VmdBoneFrame(i, SMPL_JOINT_32[j], register=True)
            pose_bf.position = MVector3D(jt[0], jt[1], -jt[2])
            pose_bf.position *= 10

            poses_motion.append_bone_frame(pose_bf)

        pelvis_bf = VmdBoneFrame(i, "Pelvis", register=True)
        pelvis_bf.position = (
            poses_motion.bones["LHip"][i].position
            + poses_motion.bones["RHip"][i].position
        ) / 2
        poses_motion.append_bone_frame(pelvis_bf)

    VmdWriter(
        poses_motion,
        "C:/MMD/mmd-auto-trace-4/WHAM/output/demo/IMG_9732/output_poses.vmd",
        "h36_17",
    ).save()
