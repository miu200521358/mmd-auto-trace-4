from glob import glob
import json
import os
import sys

import numpy as np
from pykalman import UnscentedKalmanFilter
from tqdm import tqdm
from convert_pkl2json import JOINT_NAMES
from exec_mediapipe import MP_JOINT_NAMES

from phalp.utils import get_pylogger

log = get_pylogger(__name__)

JOINT_NOISE = {
    ("camera", "x"): 6.0,
    ("camera", "y"): 6.0,
    ("camera", "z"): 12.0,
    # 25 OpenPose joints (in the order provided by OpenPose)
    "OP Nose": 3.0,  # 0
    "OP Neck": 3.0,  # 1
    "OP RShoulder": 3.0,  # 2
    "OP RElbow": 3.0,  # 3
    "OP RWrist": 3.0,  # 4
    "OP LShoulder": 3.0,  # 5
    "OP LElbow": 3.0,  # 6
    "OP LWrist": 3.0,  # 7
    "OP MidHip": 3.0,  # 8
    "OP RHip": 3.0,  # 9
    "OP RKnee": 3.0,  # 10
    "OP RAnkle": 3.0,  # 11
    "OP LHip": 3.0,  # 12
    "OP LKnee": 3.0,  # 13
    "OP LAnkle": 3.0,  # 14
    "OP REye": 3.0,  # 15
    "OP LEye": 3.0,  # 16
    "OP REar": 3.0,  # 17
    "OP LEar": 3.0,  # 18
    "OP LBigToe": 3.0,  # 19
    "OP LSmallToe": 3.0,  # 20
    "OP LHeel": 3.0,  # 21
    "OP RBigToe": 3.0,  # 22
    "OP RSmallToe": 3.0,  # 23
    "OP RHeel": 3.0,  # 24
    # 24 Ground Truth joints (superset of joints from different datasets)
    "Right Ankle": 3.0,  # 25
    "Right Knee": 3.0,  # 26
    "Right Hip": 3.0,  # 27
    "Left Hip": 3.0,  # 28
    "Left Knee": 3.0,  # 29
    "Left Ankle": 3.0,  # 30
    "Right Wrist": 3.0,  # 31
    "Right Elbow": 3.0,  # 32
    "Right Shoulder": 3.0,  # 33
    "Left Shoulder": 3.0,  # 34
    "Left Elbow": 3.0,  # 35
    "Left Wrist": 3.0,  # 36
    "Neck (LSP)": 3.0,  # 37
    "Top of Head (LSP)": 3.0,  # 38
    "Pelvis (MPII)": 3.0,  # 39
    "Thorax (MPII)": 3.0,  # 40
    "Spine (H36M)": 3.0,  # 41
    "Jaw (H36M)": 3.0,  # 42
    "Head (H36M)": 3.0,  # 43
    "Nose": 3.0,  # 44
    "Left Eye": 3.0,  # 45
    "Right Eye": 3.0,  # 46
    "Left Ear": 3.0,  # 47
    "Right Ear": 3.0,  # 48
    # mediapipe
    "nose": 0.7,  # 0
    "left eye (inner)": 0.7,  # 1
    "left eye": 0.7,  # 2
    "left eye (outer)": 0.7,  # 3
    "right eye (inner)": 0.7,  # 4
    "right eye": 0.7,  # 5
    "right eye (outer)": 0.7,  # 6
    "left ear": 0.7,  # 7
    "right ear": 0.7,  # 8
    "mouth (left)": 0.7,  # 9
    "mouth (right)": 0.7,  # 10
    "left shoulder": 0.7,  # 11
    "right shoulder": 0.7,  # 12
    "left elbow": 0.7,  # 13
    "right elbow": 0.7,  # 14
    "left wrist": 0.7,  # 15
    "right wrist": 0.7,  # 16
    "left pinky": 0.7,  # 17
    "right pinky": 0.7,  # 18
    "left index": 0.7,  # 19
    "right index": 0.7,  # 20
    "left thumb": 0.7,  # 21
    "right thumb": 0.7,  # 22
    "left hip": 0.7,  # 23
    "right hip": 0.7,  # 24
    "left knee": 0.7,  # 25
    "right knee": 0.7,  # 26
    "left ankle": 0.7,  # 27
    "right ankle": 0.7,  # 28
    "left heel": 0.7,  # 29
    "right heel": 0.7,  # 30
    "left foot index": 0.7,  # 31
    "right foot index": 0.7,  # 32
    # # osx
    # "pelvis": 0.7,  # 0
    # "left_hip": 0.7,  # 1
    # "right_hip": 0.7,  # 2
    # "left wrist": 0.7,  # 3
    # "left_knee": 0.7,  # 4
    # "right_knee": 0.7,  # 5
    # "spine2": 0.7,  # 6
    # "left_ankle": 0.7,  # 7
    # "right_ankle": 0.7,  # 8
    # "spine3": 0.7,  # 9
    # "left_foot": 0.7,  # 10
    # "right_foot": 0.7,  # 11
    # "neck": 0.7,  # 12
    # "left_collar": 0.7,  # 13
    # "right_collar": 0.7,  # 14
    # "head": 0.7,  # 15
    # "left_shoulder": 0.7,  # 16
    # "right_shoulder": 0.7,  # 17
    # "left_elbow": 0.7,  # 18
    # "right_elbow": 0.7,  # 19
    # "left_wrist": 0.7,  # 20
    # "right_wrist": 0.7,  # 21
    # "left_index1": 0.7,  # 22
    # "left_index2": 0.7,  # 23
    # "left_index3": 0.7,  # 24
    # "left_middle1": 0.7,  # 25
    # "left_middle2": 0.7,  # 26
    # "left_middle3": 0.7,  # 27
    # "left_pinky1": 0.7,  # 28
    # "left_pinky2": 0.7,  # 29
    # "left_pinky3": 0.7,  # 30
    # "left_ring1": 0.7,  # 31
    # "left_ring2": 0.7,  # 32
    # "left_ring3": 0.7,  # 33
    # "left_thumb1": 0.7,  # 34
    # "left_thumb2": 0.7,  # 35
    # "left_thumb3": 0.7,  # 36
    # "right_index1": 0.7,  # 37
    # "right_index2": 0.7,  # 38
    # "right_index3": 0.7,  # 39
    # "right_middle1": 0.7,  # 40
    # "right_middle2": 0.7,  # 41
    # "right_middle3": 0.7,  # 42
    # "right_pinky1": 0.7,  # 43
    # "right_pinky2": 0.7,  # 44
    # "right_pinky3": 0.7,  # 45
    # "right_ring1": 0.7,  # 46
    # "right_ring2": 0.7,  # 47
    # "right_ring3": 0.7,  # 48
    # "right_thumb1": 0.7,  # 49
    # "right_thumb2": 0.7,  # 50
    # "right_thumb3": 0.7,  # 51
}


def smooth(target_dir: str):
    for i, json_path in enumerate(glob(os.path.join(target_dir, "*_mp.json"))):
        with open(json_path, "r") as f:
            data = json.load(f)

        smoothed_data = {"frames": {}}

        joint_positions = {
            ("camera", "x"): [],
            ("camera", "y"): [],
            ("camera", "z"): [],
        }

        for jname in JOINT_NAMES[:45]:
            joint_positions[("3d_joints", jname)] = []
            joint_positions[("global_3d_joints", jname)] = []
        for jname in MP_JOINT_NAMES:
            joint_positions[("mediapipe", jname)] = []

        start_camera_z = 0.0
        start_fno = -1
        mp_start_fno = -1
        j = 0
        for time, frame_data in tqdm(
            data["frames"].items(), desc=f"Prepare[{i:02d}] ..."
        ):
            if start_fno == -1:
                start_fno = int(time)
                start_camera_z = frame_data["camera"]["z"]
                j = int(time)

            for k in range(j, int(time)):
                k2 = str(k)
                if 0 < len(joint_positions[("camera", "x")]):
                    j2 = len(joint_positions[("camera", "x")]) - 1
                    joint_positions[("camera", "x")].append(
                        np.array([0, 0, joint_positions[("camera", "x")][j2][0]])
                    )
                    joint_positions[("camera", "y")].append(
                        np.array([0, 0, joint_positions[("camera", "y")][j2][1]])
                    )
                    joint_positions[("camera", "z")].append(
                        np.array([0, 0, joint_positions[("camera", "z")][j2][2]])
                    )

                    prev_data = data["frames"][str(j - 1)]
                    smoothed_data["frames"][k2] = {
                        "tracked_bbox": prev_data["tracked_bbox"],
                        "conf": 0.0,
                        "camera": {"x": 0.0, "y": 0.0, "z": 0.0},
                        "3d_joints": {},
                        "global_3d_joints": {},
                        "2d_joints": prev_data["2d_joints"],
                        "mediapipe": {},
                    }

                    for jname in JOINT_NAMES[:45]:
                        joint_positions[("3d_joints", jname)].append(
                            np.array(
                                [
                                    joint_positions[("3d_joints", jname)][j2][0],
                                    joint_positions[("3d_joints", jname)][j2][1],
                                    joint_positions[("3d_joints", jname)][j2][2],
                                ]
                            )
                        )
                        joint_positions[("global_3d_joints", jname)].append(
                            np.array(
                                [
                                    joint_positions[("global_3d_joints", jname)][j2][0],
                                    joint_positions[("global_3d_joints", jname)][j2][1],
                                    joint_positions[("global_3d_joints", jname)][j2][2],
                                ]
                            )
                        )
                        smoothed_data["frames"][k2]["3d_joints"][jname] = {
                            "x": prev_data["3d_joints"][jname]["x"],
                            "y": prev_data["3d_joints"][jname]["y"],
                            "z": prev_data["3d_joints"][jname]["z"],
                        }
                        smoothed_data["frames"][k2]["global_3d_joints"][jname] = {
                            "x": prev_data["global_3d_joints"][jname]["x"],
                            "y": prev_data["global_3d_joints"][jname]["y"],
                            "z": prev_data["global_3d_joints"][jname]["z"],
                        }

                    if 0 < len(joint_positions[("mediapipe", "left wrist")]):
                        j2 = len(joint_positions[("mediapipe", "left wrist")]) - 1

                        for jname in MP_JOINT_NAMES:
                            joint_positions[("mediapipe", jname)].append(
                                np.array(
                                    [
                                        joint_positions[("mediapipe", jname)][j2][0],
                                        joint_positions[("mediapipe", jname)][j2][1],
                                        joint_positions[("mediapipe", jname)][j2][2],
                                    ]
                                )
                            )
                            if "mediapipe" in prev_data and prev_data["mediapipe"]:
                                smoothed_data["frames"][k2]["mediapipe"][jname] = {
                                    "x": prev_data["mediapipe"][jname]["x"],
                                    "y": prev_data["mediapipe"][jname]["y"],
                                    "z": prev_data["mediapipe"][jname]["z"],
                                    "visibility": prev_data["mediapipe"][jname][
                                        "visibility"
                                    ],
                                    "presence": prev_data["mediapipe"][jname][
                                        "presence"
                                    ],
                                }

                    continue

            smoothed_data["frames"][time] = {
                "tracked_bbox": data["frames"][time]["tracked_bbox"],
                "conf": data["frames"][time]["conf"],
                "camera": {"x": 0.0, "y": 0.0, "z": 0.0},
                "3d_joints": {},
                "global_3d_joints": {},
                "2d_joints": data["frames"][time]["2d_joints"],
                "mediapipe": {},
            }

            if "camera" in frame_data:
                joint_positions[("camera", "x")].append(
                    np.array([frame_data["camera"]["x"], 0, 0])
                )
                if (
                    time > 0
                    and abs(
                        joint_positions[("camera", "y")][-1] - frame_data["camera"]["y"]
                    )
                    > 0.04
                ):
                    # 跳ねる場合があるのでスルー
                    joint_positions[("camera", "y")].append(
                        np.array([0, joint_positions[("camera", "y")][-1], 0])
                    )
                else:
                    joint_positions[("camera", "y")].append(
                        np.array([0, frame_data["camera"]["y"], 0])
                    )
                joint_positions[("camera", "z")].append(
                    np.array([0, 0, frame_data["camera"]["z"] - start_camera_z])
                )
            if "3d_joints" in frame_data:
                for jname, joint in frame_data["3d_joints"].items():
                    joint_positions[("3d_joints", jname)].append(
                        np.array([joint["x"], joint["y"], joint["z"]])
                    )
                    smoothed_data["frames"][time]["3d_joints"][jname] = {
                        "x": frame_data["3d_joints"][jname]["x"],
                        "y": frame_data["3d_joints"][jname]["y"],
                        "z": frame_data["3d_joints"][jname]["z"],
                    }

            if "global_3d_joints" in frame_data:
                for jname, joint in frame_data["global_3d_joints"].items():
                    joint_positions[("global_3d_joints", jname)].append(
                        np.array([joint["x"], joint["y"], joint["z"]])
                    )
                    smoothed_data["frames"][time]["global_3d_joints"][jname] = {
                        "x": frame_data["global_3d_joints"][jname]["x"],
                        "y": frame_data["global_3d_joints"][jname]["y"],
                        "z": frame_data["global_3d_joints"][jname]["z"],
                    }

            if "mediapipe" in frame_data:
                if mp_start_fno == -1:
                    mp_start_fno = int(time)

                if frame_data["mediapipe"]:
                    for jname, joint in frame_data["mediapipe"].items():
                        joint_positions[("mediapipe", jname)].append(
                            np.array([joint["x"], joint["y"], joint["z"]])
                        )
                        smoothed_data["frames"][time]["mediapipe"][jname] = {
                            "x": frame_data["mediapipe"][jname]["x"],
                            "y": frame_data["mediapipe"][jname]["y"],
                            "z": frame_data["mediapipe"][jname]["z"],
                            "visibility": frame_data["mediapipe"][jname]["visibility"],
                            "presence": frame_data["mediapipe"][jname]["presence"],
                        }
                else:
                    if 0 < len(joint_positions[("mediapipe", "left wrist")]):
                        j2 = len(joint_positions[("mediapipe", "left wrist")]) - 1
                        prev_data = data["frames"][str(j - 1)]
                        for jname in MP_JOINT_NAMES:
                            joint_positions[("mediapipe", jname)].append(
                                np.array(
                                    [
                                        joint_positions[("mediapipe", jname)][j2][0],
                                        joint_positions[("mediapipe", jname)][j2][1],
                                        joint_positions[("mediapipe", jname)][j2][2],
                                    ]
                                )
                            )
                            if prev_data["mediapipe"]:
                                smoothed_data["frames"][time]["mediapipe"][jname] = {
                                    "x": prev_data["mediapipe"][jname]["x"],
                                    "y": prev_data["mediapipe"][jname]["y"],
                                    "z": prev_data["mediapipe"][jname]["z"],
                                    "visibility": prev_data["mediapipe"][jname][
                                        "visibility"
                                    ],
                                    "presence": prev_data["mediapipe"][jname][
                                        "presence"
                                    ],
                                }

            j = int(time) + 1

        def tf(state, noise):
            # 加速度を考慮した動的モデル
            pos = state[:3] + state[3:6] + 0.5 * state[6:9]
            vel = state[3:6] + state[6:9]
            acc = state[6:9] + noise[6:9]
            return np.concatenate([pos, vel, acc])

        def of(state, noise):
            return state[:3] + noise

        for (type_name, joint_name), joint_poses in tqdm(
            joint_positions.items(), desc=f"Smoothing [{i:02d}] ..."
        ):
            if np.sum(joint_poses) == 0:
                continue

            # プロセスノイズの標準偏差
            if (type_name, joint_name) in JOINT_NOISE:
                process_noise_sd = JOINT_NOISE[(type_name, joint_name)]
            else:
                process_noise_sd = JOINT_NOISE[joint_name]

            # 観測ノイズの標準偏差を計算
            observation_noise_sd = np.std(np.array(joint_poses))

            initial_state = np.concatenate(
                [joint_poses[0], [0, 0, 0], [0, 0, 0]]
            )  # 初期状態に速度0、加速度0を追加

            ukf = UnscentedKalmanFilter(
                transition_functions=tf,
                observation_functions=of,
                transition_covariance=process_noise_sd**2
                * np.eye(9),  # 状態は位置、速度、加速度を含む
                observation_covariance=observation_noise_sd**2 * np.eye(3),
                initial_state_mean=initial_state,
                initial_state_covariance=process_noise_sd * np.eye(9),
                random_state=0,
            )

            # 平滑化
            smoothed_state_means, _ = ukf.smooth(np.array(joint_poses))

            for j, joint_pose in enumerate(smoothed_state_means[:, :3]):
                j2 = str(j + start_fno)
                mj = str(j + mp_start_fno)
                if "camera" == type_name:
                    if joint_name == "x":
                        smoothed_data["frames"][j2]["camera"]["x"] = joint_pose[0]
                    elif joint_name == "y":
                        smoothed_data["frames"][j2]["camera"]["y"] = joint_pose[1]
                    elif joint_name == "z":
                        smoothed_data["frames"][j2]["camera"]["z"] = (
                            joint_pose[2] + start_camera_z
                        )
                elif "mediapipe" == type_name:
                    if joint_name not in smoothed_data["frames"][j2][type_name]:
                        smoothed_data["frames"][mj][type_name][joint_name] = {
                            "x": 0.0,
                            "y": 0.0,
                            "z": 0.0,
                        }
                    smoothed_data["frames"][mj][type_name][joint_name]["x"] = (
                        joint_pose[0]
                    )
                    smoothed_data["frames"][mj][type_name][joint_name]["y"] = (
                        joint_pose[1]
                    )
                    smoothed_data["frames"][mj][type_name][joint_name]["z"] = (
                        joint_pose[2]
                    )
                else:
                    smoothed_data["frames"][j2][type_name][joint_name] = {
                        "x": joint_pose[0],
                        "y": joint_pose[1],
                        "z": joint_pose[2],
                    }

        smooth_json_path = json_path.replace("_mp.json", "_smooth.json")
        with open(smooth_json_path, "w") as f:
            json.dump(smoothed_data, f, indent=4)


if __name__ == "__main__":
    log.info("Start: smooth =============================")

    smooth(sys.argv[1])

    log.info("End: smooth =============================")
