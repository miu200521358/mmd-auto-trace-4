import argparse
from glob import glob
import json
import os
import cv2
import mediapipe as mp
import numpy as np
from tqdm import tqdm

JOINT_NAMES = [
    "nose",
    "left eye (inner)",
    "left eye",
    "left eye (outer)",
    "right eye (inner)",
    "right eye",
    "right eye (outer)",
    "left ear",
    "right ear",
    "mouth (left)",
    "mouth (right)",
    "left shoulder",
    "right shoulder",
    "left elbow",
    "right elbow",
    "left wrist",
    "right wrist",
    "left pinky",
    "right pinky",
    "left index",
    "right index",
    "left thumb",
    "right thumb",
    "left hip",
    "right hip",
    "left knee",
    "right knee",
    "left ankle",
    "right ankle",
    "left heel",
    "right heel",
    "left foot index",
    "right foot index",
]

HAND_JOINT_NAMES = [
    "wrist",
    "thumb_cmc",
    "thumb_mcp",
    "thumb_ip",
    "thumb_tip",
    "index_finger_mcp",
    "index_finger_pip",
    "index_finger_dip",
    "index_finger_tip",
    "middle_finger_mcp",
    "middle_finger_pip",
    "middle_finger_dip",
    "middle_finger_tip",
    "ring_finger_mcp",
    "ring_finger_pip",
    "ring_finger_dip",
    "ring_finger_tip",
    "pinky_finger_mcp",
    "pinky_finger_pip",
    "pinky_finger_dip",
    "pinky_finger_tip",
]


def exec_person_mediapipe(video_path: str, original_json_path: str):
    with open(original_json_path) as f:
        original_data = json.load(f)

    BaseOptions = mp.tasks.BaseOptions
    PoseLandmarker = mp.tasks.vision.PoseLandmarker
    PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
    VisionRunningMode = mp.tasks.vision.RunningMode

    pose_options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path="data/pose_landmarker_full.task"),
        running_mode=VisionRunningMode.VIDEO,
    )

    with PoseLandmarker.create_from_options(pose_options) as pose_landmarker:
        video = cv2.VideoCapture(video_path)

        # 総フレーム数
        count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        # 横
        W = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
        # 縦
        H = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
        # fps
        fps = 30
        # frame_timestamp_ms
        ts = 0
        # 元のフレームを30fpsで計算し直した場合の1Fごとの該当フレーム数
        interpolations = (
            np.round(np.arange(0, count, fps / 30)).astype(np.int32).tolist()
        )

        for i, frame_id in enumerate(tqdm(interpolations)):
            if str(i) not in original_data["frames"]:
                continue

            original_data["frames"][str(i)]["mediapipe"] = {}

            # 動画から1枚キャプチャして読み込む
            video.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
            flag, frame = video.read()
            if not flag:
                break

            # フレームの中から人物のtracked_bboxを取得
            tracked_bbox = original_data["frames"][str(i)]["tracked_bbox"]

            # tracked_bboxの領域を取得したフレームから切り出す
            x, y, w, h = tracked_bbox
            clipped_frame = frame[
                max(0, int(y) - 20) : min(H, int(y + h) + 20),
                max(0, int(x) - 20) : min(int(x + w) + 20, W),
            ].astype(np.uint8)

            # STEP 3: Load the input image.
            image = mp.Image(mp.ImageFormat.SRGB, clipped_frame)

            ts += 1 / fps * 1000

            # STEP 4: Detect pose landmarks from the input image.
            pose_detection = pose_landmarker.detect_for_video(image, int(ts))

            if not pose_detection.pose_world_landmarks:
                continue

            joints = {}
            for jname, joint in zip(
                JOINT_NAMES, pose_detection.pose_world_landmarks[0]
            ):
                joints[jname] = {
                    "x": float(joint.x),
                    "y": float(joint.y),
                    "z": float(joint.z),
                    "visibility": float(joint.visibility),
                    "presence": float(joint.presence),
                }
            original_data["frames"][str(i)]["mediapipe"] = joints

        with open(original_json_path, "w") as f:
            json.dump(original_data, f, ensure_ascii=False, indent=4)


def exec_mediapipe(video_path: str, output_dir: str):
    # 該当ディレクトリ内のoriginal.jsonを探す
    for json_fn in glob(os.path.join(args.output_dir, "*_original.json")):
        exec_person_mediapipe(args.video, json_fn)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=str)
    parser.add_argument("--output_dir", type=str)

    args = parser.parse_args()

    exec_mediapipe(args.video, args.output_dir)
