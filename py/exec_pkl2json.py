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


def convert(all_lib_data: list[dict], output_dir_path):
    all_data = {}

    start_z = 0
    for lib_data in all_lib_data:
        for k1 in sorted(lib_data.keys()):
            if lib_data[k1]["camera"]:
                start_z = lib_data[k1]["camera"][0][2]
                break
            if start_z:
                break
        if start_z:
            break

    prev_last_key = 0
    track_ids = []

    for lib_data in all_lib_data:
        start_time = -1
        for k1 in tqdm(sorted(lib_data.keys())):
            v1 = lib_data[k1]
            time = v1["time"] + prev_last_key
            if start_time == -1:
                start_time = time

            for t, tid in enumerate(v1["tracked_ids"]):
                tracked_id = int(tid)

                key = (tracked_id, start_time)
                if key not in all_data:
                    all_data[key] = {}

                if tracked_id not in track_ids:
                    track_ids.append(tracked_id)

                all_data[key][time] = {}
                if t < len(v1["tracked_bbox"]):
                    all_data[key][time]["tracked_bbox"] = (
                        v1["tracked_bbox"][t].astype(np.float64).tolist()
                    )
                if t < len(v1["conf"]):
                    all_data[key][time]["conf"] = v1["conf"][t].astype(
                        np.float64
                    )

                if t < len(v1["camera"]):
                    cam_pos = v1["camera"][t].astype(np.float64).tolist()
                    all_data[key][time]["camera"] = {
                        "x": cam_pos[0],
                        "y": -cam_pos[1],
                        "z": cam_pos[2],
                    }

                if t < len(v1["3d_joints"]):
                    joints = v1["3d_joints"][t].astype(np.float64).tolist()

                    all_data[key][time]["3d_joints"] = {}
                    for i, (joint, jname) in enumerate(zip(joints, JOINT_NAMES)):
                        all_data[key][time]["3d_joints"][jname] = {
                            "x": joint[0],
                            "y": -joint[1],
                            "z": joint[2],
                        }

                    all_data[key][time]["global_3d_joints"] = {}
                    for i, (joint, jname) in enumerate(zip(joints, JOINT_NAMES)):
                        all_data[key][time]["global_3d_joints"][jname] = {
                            "x": float(joint[0] + all_data[key][time]["camera"]["x"]),
                            "y": float(-(
                                joint[1] + all_data[key][time]["camera"]["y"]
                            )),
                            "z": float(joint[2]
                            + (all_data[key][time]["camera"]["z"] - start_z)
                            * 0.05),
                        }

                if t < len(v1["2d_joints"]):
                    joints = (
                        v1["2d_joints"][t].reshape(-1, 2).astype(np.float64).tolist()
                    )

                    all_data[key][time]["2d_joints"] = {}
                    for i, (joint, jname) in enumerate(zip(joints, JOINT_NAMES)):
                        all_data[key][time]["2d_joints"][jname] = {
                            "x": joint[0],
                            "y": joint[1],
                        }

        # 終わったら最後のキーを保持
        prev_last_key = int(sorted(lib_data.keys())[-1])

    if not all_data:
        log.error("No data to convert!")
        return

    for tracked_id, start_time in tqdm(sorted(all_data.keys())):
        json_path = os.path.join(output_dir_path, f"{start_time:05d}_{tracked_id:02d}_original.json")
        key = (tracked_id, start_time)

        with open(json_path, "w") as f:
            json.dump({"frames": all_data[key]}, f, indent=4)
        # log.info(f"Saved: {json_path}")


def main(output_dir_path):
    log.info("Start: pkl to json =============================")

    all_lib_data = []
    for pkl_path in sorted(glob(os.path.join(output_dir_path, "*.pkl"))):
        with open(pkl_path, "rb") as f:
            all_lib_data.append(joblib.load(f))

    convert(all_lib_data, output_dir_path)

    log.info("End: pkl to json =============================")


if __name__ == "__main__":
    main(sys.argv[1])
