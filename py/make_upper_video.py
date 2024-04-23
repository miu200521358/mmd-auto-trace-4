import math
import os
import sys

import cv2
import joblib
import numpy as np
from tqdm import tqdm
from phalp.utils.trace_io import TraceFrameExtractor
from convert_pkl2json import JOINT_INDEXES


def make_upper_video(video_path, pkl_path):
    with open(pkl_path, "rb") as f:
        lib_data = joblib.load(f)

    video_name = video_path.split("/")[-1].split(".")[0]
    frame_extractor = TraceFrameExtractor(video_path)

    all_data = {}
    size_data = {}
    for k1 in tqdm(sorted(lib_data.keys())):
        v1 = lib_data[k1]
        time = v1["time"]
        frame = frame_extractor.read_frame(time)
        for t, tracked_id in enumerate(v1["tracked_ids"]):
            if tracked_id not in all_data:
                all_data[tracked_id] = {}
                all_data[tracked_id]["U"] = {}
                all_data[tracked_id]["R"] = {}
                all_data[tracked_id]["L"] = {}
                size_data[tracked_id] = {}
                size_data[tracked_id]["U"] = {}
                size_data[tracked_id]["R"] = {}
                size_data[tracked_id]["L"] = {}

            if t < len(v1["2d_joints"]):
                joints = v1["2d_joints"][t].reshape(-1, 2).astype(np.float64).tolist()

                h, w, _ = frame.shape

                pelvis_x, pelvis_y = np.round(
                    np.array(joints[JOINT_INDEXES["Pelvis (MPII)"]]) * np.array([w, h])
                ).astype(int)
                head_x, head_y = np.round(
                    np.array(joints[JOINT_INDEXES["Top of Head (LSP)"]])
                    * np.array([w, h])
                ).astype(int)
                left_wrist_x, left_wrist_y = np.round(
                    np.array(joints[JOINT_INDEXES["OP LWrist"]]) * np.array([w, h])
                ).astype(int)
                right_wrist_x, right_wrist_y = np.round(
                    np.array(joints[JOINT_INDEXES["OP RWrist"]]) * np.array([w, h])
                ).astype(int)
                left_shoulder_x, left_shoulder_y = np.round(
                    np.array(joints[JOINT_INDEXES["OP LShoulder"]]) * np.array([w, h])
                ).astype(int)
                right_shoulder_x, right_shoulder_y = np.round(
                    np.array(joints[JOINT_INDEXES["OP RShoulder"]]) * np.array([w, h])
                ).astype(int)

                min_x = np.min(
                    [
                        pelvis_x,
                        head_x,
                        left_wrist_x,
                        right_wrist_x,
                        left_shoulder_x,
                        right_shoulder_x,
                    ]
                )
                max_x = np.max(
                    [
                        pelvis_x,
                        head_x,
                        left_wrist_x,
                        right_wrist_x,
                        left_shoulder_x,
                        right_shoulder_x,
                    ]
                )
                min_y = np.min(
                    [
                        pelvis_y,
                        head_y,
                        left_wrist_y,
                        right_wrist_y,
                        left_shoulder_y,
                        right_shoulder_y,
                    ]
                )
                max_y = np.max(
                    [
                        pelvis_y,
                        head_y,
                        left_wrist_y,
                        right_wrist_y,
                        left_shoulder_y,
                        right_shoulder_y,
                    ]
                )

                neck_frame = frame[min_y - 200 : max_y, min_x - 100 : max_x + 100, :]
                if neck_frame.any():
                    all_data[tracked_id]["U"][time] = cv2.resize(
                        neck_frame,
                        (
                            neck_frame.shape[1] * 5,
                            neck_frame.shape[0] * 5,
                        ),
                        interpolation=cv2.INTER_CUBIC,
                    )
                    size_data[tracked_id]["U"][time] = np.array(
                        all_data[tracked_id]["U"][time].shape
                    )

                    # img_path = os.path.join(
                    #     os.path.dirname(pkl_path),
                    #     f"{video_name}_{tracked_id:02d}_U_{time:04d}.png",
                    # )
                    # cv2.imwrite(img_path, all_data[tracked_id]["U"][time])

                for hand in ["R", "L"]:
                    wrist_x, wrist_y = np.round(
                        np.array(joints[JOINT_INDEXES[f"OP {hand}Wrist"]])
                        * np.array([w, h])
                    ).astype(int)
                    elbow_x, elbow_y = np.round(
                        np.array(joints[JOINT_INDEXES[f"OP {hand}Elbow"]])
                        * np.array([w, h])
                    ).astype(int)

                    min_x = np.min([wrist_x, elbow_x])
                    max_x = np.max([wrist_x, elbow_x])
                    min_y = np.min([wrist_y, elbow_y])
                    max_y = np.max([wrist_y, elbow_y])

                    hand_frame = frame[
                        min_y - 80 : max_y + 80, min_x - 80 : max_x + 80, :
                    ]
                    if hand_frame.any():
                        all_data[tracked_id][hand][time] = cv2.resize(
                            hand_frame,
                            (
                                hand_frame.shape[1] * 5,
                                hand_frame.shape[0] * 5,
                            ),
                            interpolation=cv2.INTER_CUBIC,
                        )
                        size_data[tracked_id][hand][time] = np.array(
                            all_data[tracked_id][hand][time].shape
                        )

                        # img_path = os.path.join(
                        #     os.path.dirname(pkl_path),
                        #     f"{video_name}_{tracked_id:02d}_{hand}_{time:04d}.jpg",
                        # )
                        # cv2.imwrite(img_path, all_data[tracked_id][hand][time])

    for tracked_id in all_data.keys():
        for hand in ["U", "R", "L"]:
            if all_data[tracked_id][hand]:
                sizes = []
                for time in all_data[tracked_id][hand].keys():
                    sizes.append(size_data[tracked_id][hand][time])
                max_size = np.max(sizes, axis=0)

            hand_video = cv2.VideoWriter(
                os.path.join(
                    os.path.dirname(pkl_path),
                    f"{video_name}_{tracked_id:02d}_{hand}.mp4",
                ),
                cv2.VideoWriter_fourcc(*"mp4v"),
                30,
                (max_size[1], max_size[0]),
            )

            for time in tqdm(
                range(max(all_data[tracked_id][hand].keys()) + 1),
                desc=f"{tracked_id:02d}_{hand}",
            ):
                if time in all_data[tracked_id][hand]:
                    frame = np.zeros((max_size[0], max_size[1], 3), dtype=np.uint8)
                    frame[
                        : all_data[tracked_id][hand][time].shape[0],
                        : all_data[tracked_id][hand][time].shape[1],
                    ] = all_data[tracked_id][hand][time]
                    hand_video.write(frame)
                else:
                    t = time
                    while t not in all_data[tracked_id][hand]:
                        t -= 1
                    frame = np.zeros((max_size[0], max_size[1], 3), dtype=np.uint8)
                    frame[
                        : all_data[tracked_id][hand][t].shape[0],
                        : all_data[tracked_id][hand][t].shape[1],
                    ] = all_data[tracked_id][hand][t]
                    hand_video.write(frame)

            hand_video.release()


if __name__ == "__main__":
    make_upper_video(sys.argv[1], sys.argv[2])
