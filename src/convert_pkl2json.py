import json
import sys
import joblib
import numpy as np
from phalp.utils import get_pylogger

log = get_pylogger(__name__)

JOINT_NAMES = [
    # 25 OpenPose joints (in the order provided by OpenPose)
    "OP Nose",  # 0
    "OP Neck",  # 1
    "OP RShoulder",  # 2
    "OP RElbow",  # 3
    "OP RWrist",  # 4
    "OP LShoulder",  # 5
    "OP LElbow",  # 6
    "OP LWrist",  # 7
    "OP MidHip",  # 8
    "OP RHip",  # 9
    "OP RKnee",  # 10
    "OP RAnkle",  # 11
    "OP LHip",  # 12
    "OP LKnee",  # 13
    "OP LAnkle",  # 14
    "OP REye",  # 15
    "OP LEye",  # 16
    "OP REar",  # 17
    "OP LEar",  # 18
    "OP LBigToe",  # 19
    "OP LSmallToe",  # 20
    "OP LHeel",  # 21
    "OP RBigToe",  # 22
    "OP RSmallToe",  # 23
    "OP RHeel",  # 24
    # 24 Ground Truth joints (superset of joints from different datasets)
    "Right Ankle",  # 25
    "Right Knee",  # 26
    "Right Hip",  # 27
    "Left Hip",  # 28
    "Left Knee",  # 29
    "Left Ankle",  # 30
    "Right Wrist",  # 31
    "Right Elbow",  # 32
    "Right Shoulder",  # 33
    "Left Shoulder",  # 34
    "Left Elbow",  # 35
    "Left Wrist",  # 36
    "Neck (LSP)",  # 37
    "Top of Head (LSP)",  # 38
    "Pelvis (MPII)",  # 39
    "Thorax (MPII)",  # 40
    "Spine (H36M)",  # 41
    "Jaw (H36M)",  # 42
    "Head (H36M)",  # 43
    "Nose",  # 44
    "Left Eye",  # 45
    "Right Eye",  # 46
    "Left Ear",  # 47
    "Right Ear",  # 48
]


def convert_pkl2json(pkl_path):
    with open(pkl_path, "rb") as f:
        lib_data = joblib.load(f)

    all_data = {}
    for k1 in sorted(lib_data.keys()):
        v1 = lib_data[k1]
        time = v1["time"]
        for tracked_id in v1["tracked_ids"]:
            if tracked_id not in all_data:
                all_data[tracked_id] = {}
            all_data[tracked_id][time] = {}
            all_data[tracked_id][time]["tracked_bbox"] = (
                v1["tracked_bbox"][tracked_id - 1].astype(np.float64).tolist()
            )
            all_data[tracked_id][time]["conf"] = v1["conf"][tracked_id - 1].astype(
                np.float64
            )
            all_data[tracked_id][time]["camera"] = (
                v1["camera"][tracked_id - 1].astype(np.float64).tolist()
            )

            joints = v1["3d_joints"][tracked_id - 1].astype(np.float64).tolist()
            all_data[tracked_id][time]["3d_joints"] = {}
            for i, (joint, jname) in enumerate(zip(joints, JOINT_NAMES)):
                all_data[tracked_id][time]["3d_joints"][jname] = {
                    "x": joint[0],
                    "y": joint[1],
                    "z": joint[2],
                }

            joints = v1["2d_joints"][tracked_id - 1].reshape(-1, 2).astype(np.float64).tolist()
            all_data[tracked_id][time]["2d_joints"] = {}
            for i, (joint, jname) in enumerate(zip(joints, JOINT_NAMES)):
                all_data[tracked_id][time]["2d_joints"][jname] = {
                    "x": joint[0],
                    "y": joint[1],
                }

    for tracked_id in sorted(all_data.keys()):
        json_path = pkl_path.replace(".pkl", f"_{tracked_id:02d}.json")
        with open(json_path, "w") as f:
            json.dump(all_data[tracked_id], f, indent=4)
        log.info(f"Saved: {json_path}")

    return json_path


if __name__ == "__main__":
    convert_pkl2json(sys.argv[1])
