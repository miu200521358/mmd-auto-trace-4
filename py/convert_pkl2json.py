from glob import glob
import json
import os
import sys
import joblib
import numpy as np
from phalp.utils import get_pylogger
from tqdm import tqdm

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

JOINT_INDEXES = dict([(j, i) for i, j in enumerate(JOINT_NAMES)])


def convert_pkl2json(pkl_path):
    with open(pkl_path, "rb") as f:
        lib_data = joblib.load(f)

    for k1 in sorted(lib_data.keys()):
        if lib_data[k1]["camera"]:
            start_z = lib_data[k1]["camera"][0][2]

    all_data = {}
    for k1 in tqdm(sorted(lib_data.keys())):
        v1 = lib_data[k1]
        time = v1["time"]
        # if not (0 < time < 100):
        #     continue

        for t, tracked_id in enumerate(v1["tracked_ids"]):
            if tracked_id not in all_data:
                all_data[tracked_id] = {}
            all_data[tracked_id][time] = {}
            if t < len(v1["tracked_bbox"]):
                all_data[tracked_id][time]["tracked_bbox"] = (
                    v1["tracked_bbox"][t].astype(np.float64).tolist()
                )
            if t < len(v1["conf"]):
                all_data[tracked_id][time]["conf"] = v1["conf"][t].astype(np.float64)

            if t < len(v1["camera"]):
                cam_pos = v1["camera"][t].astype(np.float64).tolist()
                all_data[tracked_id][time]["camera"] = {
                    "x": cam_pos[0],
                    "y": -cam_pos[1],
                    "z": cam_pos[2],
                }

            if t < len(v1["3d_joints"]):
                joints = v1["3d_joints"][t].astype(np.float64).tolist()

                all_data[tracked_id][time]["3d_joints"] = {}
                for i, (joint, jname) in enumerate(zip(joints, JOINT_NAMES)):
                    all_data[tracked_id][time]["3d_joints"][jname] = {
                        "x": joint[0],
                        "y": -joint[1],
                        "z": joint[2],
                    }

                all_data[tracked_id][time]["global_3d_joints"] = {}
                for i, (joint, jname) in enumerate(zip(joints, JOINT_NAMES)):
                    all_data[tracked_id][time]["global_3d_joints"][jname] = {
                        "x": joint[0] + all_data[tracked_id][time]["camera"]["x"],
                        "y": -(joint[1] + all_data[tracked_id][time]["camera"]["y"]),
                        "z": joint[2]
                        + (all_data[tracked_id][time]["camera"]["z"] - start_z) * 0.1,
                    }

            if t < len(v1["2d_joints"]):
                joints = v1["2d_joints"][t].reshape(-1, 2).astype(np.float64).tolist()

                all_data[tracked_id][time]["2d_joints"] = {}
                for i, (joint, jname) in enumerate(zip(joints, JOINT_NAMES)):
                    all_data[tracked_id][time]["2d_joints"][jname] = {
                        "x": joint[0],
                        "y": joint[1],
                    }

    if not all_data:
        log.error("No data to convert!")
        return

    for tracked_id in sorted(all_data.keys()):
        json_path = pkl_path.replace(".pkl", f"_{tracked_id:02d}_original.json")
        with open(json_path, "w") as f:
            json.dump({"frames": all_data[tracked_id]}, f, indent=4)
        log.info(f"Saved: {json_path}")


if __name__ == "__main__":
    for pkl_path in glob(os.path.join(sys.argv[1], "*.pkl")):
        convert_pkl2json(pkl_path)
