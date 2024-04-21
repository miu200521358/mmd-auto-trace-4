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

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=str)
    parser.add_argument("--output_dir", type=str)

    args = parser.parse_args()

    BaseOptions = mp.tasks.BaseOptions
    PoseLandmarker = mp.tasks.vision.PoseLandmarker
    PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
    VisionRunningMode = mp.tasks.vision.RunningMode

    HandLandmarker = mp.tasks.vision.HandLandmarker
    HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions

    pose_options = PoseLandmarkerOptions(
        base_options=BaseOptions(
            model_asset_path="checkpoints/mediapipe/pose_landmarker_full.task"
        ),
        running_mode=VisionRunningMode.VIDEO,
    )

    # Create a hand landmarker instance with the video mode:
    hand_options = HandLandmarkerOptions(
        base_options=BaseOptions(
            model_asset_path="checkpoints/mediapipe/hand_landmarker.task"
        ),
        running_mode=VisionRunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.4,
    )

    os.makedirs(
        os.path.join(args.output_dir, os.path.basename(args.video).split(".")[0]),
        exist_ok=True,
    )

    with HandLandmarker.create_from_options(
        hand_options
    ) as hand_landmarker, PoseLandmarker.create_from_options(
        pose_options
    ) as pose_landmarker:
        # json file
        joint_fn = os.path.join(
            args.output_dir,
            os.path.basename(args.video).split(".")[0],
            "mediapipe.json",
        )
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
            pose_detection = pose_landmarker.detect_for_video(image, int(ts))

            if not pose_detection.pose_world_landmarks:
                continue

            joints_dict[i] = {}
            for jname, joint in zip(
                JOINT_NAMES, pose_detection.pose_world_landmarks[0]
            ):
                joints_dict[i][jname] = {
                    "x": float(joint.x),
                    "y": float(joint.y),
                    "z": float(joint.z),
                    "visibility": float(joint.visibility),
                    "presence": float(joint.presence),
                }

            # STEP 4: Detect hand landmarks from the input image.
            hand_detection = hand_landmarker.detect_for_video(image, int(ts))

            if not hand_detection.hand_world_landmarks:
                continue

            for handedness, hand_world_landmarks in zip(
                hand_detection.handedness[0], hand_detection.hand_world_landmarks
            ):
                display_name = handedness.display_name.lower()

                for jname, joint in zip(JOINT_NAMES, hand_world_landmarks):
                    joints_dict[i][f"{display_name} {jname}"] = {
                        "x": float(joint.x),
                        "y": float(joint.y),
                        "z": float(joint.z),
                    }

        with open(joint_fn, "w") as f:
            json.dump(joints_dict, f, ensure_ascii=False, indent=4)
