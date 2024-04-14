import argparse
from glob import glob
import json
import os
import cv2
import mediapipe as mp
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=str)
    parser.add_argument("--output_dir", type=str)

    args = parser.parse_args()

    BaseOptions = mp.tasks.BaseOptions
    PoseLandmarker = mp.tasks.vision.PoseLandmarker
    PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
    VisionRunningMode = mp.tasks.vision.RunningMode

    options = PoseLandmarkerOptions(
        base_options=BaseOptions(
            model_asset_path="checkpoints/mediapipe/pose_landmarker_full.task"
        ),
        running_mode=VisionRunningMode.VIDEO,
    )

    os.makedirs(os.path.join(args.output_dir, os.path.basename(args.video).split(".")[0]), exist_ok=True)

    with PoseLandmarker.create_from_options(options) as landmarker:
        # json file
        joint_fn = os.path.join(args.output_dir, os.path.basename(args.video).split(".")[0], "mediapipe.json")
        joints_dict = {}

        video = cv2.VideoCapture(args.video)

        # 幅
        W = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
        # 高さ
        H = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
        # 総フレーム数
        count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        # fps
        fps = video.get(cv2.CAP_PROP_FPS)
        # frame_timestamp_ms
        ts = 0

        for i in tqdm(range(count)):
            # 動画から1枚キャプチャして読み込む
            flag, org_img = video.read()
            
            if not flag:
                break

            # STEP 3: Load the input image.
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=org_img)

            ts += 1 / fps * 1000

            # STEP 4: Detect pose landmarks from the input image.
            detection_result = landmarker.detect_for_video(image, int(ts))

            if not detection_result.pose_world_landmarks:
                continue

            joints_dict[i] = {}
            for jname, joint in zip(
                JOINT_NAMES, detection_result.pose_world_landmarks[0]
            ):
                joints_dict[i][jname] = {
                    "x": float(joint.x),
                    "y": float(joint.y),
                    "z": float(joint.z),
                    "visibility": float(joint.visibility),
                    "presence": float(joint.presence),
                }

        with open(joint_fn, "w") as f:
            json.dump(joints_dict, f, ensure_ascii=False, indent=4)
