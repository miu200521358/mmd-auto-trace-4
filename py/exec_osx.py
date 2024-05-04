from glob import glob
import json
import os
import sys
import argparse
import cv2
import numpy as np
import torchvision.transforms as transforms
import torch.backends.cudnn as cudnn
import torch
from tqdm import tqdm

sys.path.insert(0, os.path.join("..", "OSX", "main"))
sys.path.insert(0, os.path.join("..", "OSX", "data"))

from config import cfg
from common.base import Demoer
from common.utils.preprocessing import load_img, process_bbox, generate_patch_image

OSX_JOINT_NAMES = [
    "pelvis",  # 0
    "left_hip",  # 1
    "right_hip",  # 2
    "spine1",  # 3
    "left_knee",  # 4
    "right_knee",  # 5
    "spine2",  # 6
    "left_ankle",  # 7
    "right_ankle",  # 8
    "spine3",  # 9
    "left_foot",  # 10
    "right_foot",  # 11
    "neck",  # 12
    "left_collar",  # 13
    "right_collar",  # 14
    "head",  # 15
    "left_shoulder",  # 16
    "right_shoulder",  # 17
    "left_elbow",  # 18
    "right_elbow",  # 19
    "left_wrist",  # 20
    "right_wrist",  # 21
]

LEFT_HAND_JOINT_NAMES = [
    "left_index1",  # 0
    "left_index2",  # 1
    "left_index3",  # 2
    "left_middle1",  # 3
    "left_middle2",  # 4
    "left_middle3",  # 5
    "left_pinky1",  # 6
    "left_pinky2",  # 7
    "left_pinky3",  # 8
    "left_ring1",  # 9
    "left_ring2",  # 10
    "left_ring3",  # 11
    "left_thumb1",  # 12
    "left_thumb2",  # 13
    "left_thumb3",  # 14
]

RIGHT_HAND_JOINT_NAMES = [
    "right_index1",  # 0
    "right_index2",  # 1
    "right_index3",  # 2
    "right_middle1",  # 3
    "right_middle2",  # 4
    "right_middle3",  # 5
    "right_pinky1",  # 6
    "right_pinky2",  # 7
    "right_pinky3",  # 8
    "right_ring1",  # 9
    "right_ring2",  # 10
    "right_ring3",  # 11
    "right_thumb1",  # 12
    "right_thumb2",  # 13
    "right_thumb3",  # 14
]


def exec_person_osx(
    video_path: str, original_json_path: str, args: argparse.Namespace, demoer, detector
):
    with open(original_json_path) as f:
        original_data = json.load(f)

    video = cv2.VideoCapture(video_path)

    # 総フレーム数
    count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    # 横
    W = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    # 縦
    H = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    # fps
    fps = video.get(cv2.CAP_PROP_FPS)
    # 元のフレームを30fpsで計算し直した場合の1Fごとの該当フレーム数
    interpolations = np.round(np.arange(0, count, fps / 30)).astype(np.int32).tolist()

    for i, frame_id in enumerate(tqdm(interpolations)):
        if str(i) not in original_data["frames"]:
            continue

        original_data["frames"][str(i)]["osx"] = {}

        # 動画から1枚キャプチャして読み込む
        video.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
        flag, frame = video.read()
        if not flag:
            break

        # フレームの中から人物のtracked_bboxを取得
        tracked_bbox = original_data["frames"][str(i)]["tracked_bbox"]

        # tracked_bboxの領域を取得したフレームから切り出す
        x, y, w, h = tracked_bbox
        clipped_x1 = max(0, int(x) - 20)
        clipped_y1 = max(0, int(y) - 20)
        clipped_x2 = min(int(x + w) + 20, W)
        clipped_y2 = min(int(y + h) + 20, H)
        clipped_frame = frame[clipped_y1:clipped_y2, clipped_x1:clipped_x2].astype(
            np.uint8
        )

        # prepare input image
        transform = transforms.ToTensor()
        clipped_frame_height, clipped_frame_width = clipped_frame.shape[:2]

        with torch.no_grad():
            results = detector(clipped_frame)
        person_results = results.xyxy[0][results.xyxy[0][:, 5] == 0]
        class_ids, confidences, boxes = [], [], []
        for detection in person_results:
            x1, y1, x2, y2, confidence, class_id = detection.tolist()
            class_ids.append(class_id)
            confidences.append(confidence)
            boxes.append([x1, y1, x2 - x1, y2 - y1])
        indices = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)
        if len(indices) == 0:
            continue
        bbox = boxes[indices[0]]  # x,y,h,w
        bbox = process_bbox(bbox, clipped_frame_width, clipped_frame_height)
        img, img2bb_trans, bb2img_trans = generate_patch_image(
            clipped_frame, bbox, 1.0, 0.0, False, cfg.input_img_shape
        )
        img = transform(img.astype(np.float32)) / 255
        img = img.cuda()[None, :, :, :]
        inputs = {"img": img}
        targets = {}
        meta_info = {}

        # mesh recovery
        with torch.no_grad():
            out = demoer.model(inputs, targets, meta_info, "test")

        mesh = out["smplx_mesh_cam"].detach().cpu().numpy()
        mesh = mesh[0]

        root_poses = out["smplx_root_pose"].detach().cpu().numpy().reshape(-1, 3)
        body_poses = out["smplx_body_pose"].detach().cpu().numpy().reshape(-1, 3)
        lhand_pose = out["smplx_lhand_pose"].detach().cpu().numpy().reshape(-1, 3)
        rhand_pose = out["smplx_rhand_pose"].detach().cpu().numpy().reshape(-1, 3)

        joints = {
            OSX_JOINT_NAMES[0]: {
                "x": float(root_poses[0][0]),
                "y": float(root_poses[0][1]),
                "z": float(root_poses[0][2]),
            }
        }
        for jname, joint in zip(OSX_JOINT_NAMES[1:], body_poses):
            joints[jname] = {
                "x": float(joint[0]),
                "y": float(joint[1]),
                "z": float(joint[2]),
            }
        for jname, joint in zip(LEFT_HAND_JOINT_NAMES, lhand_pose):
            joints[jname] = {
                "x": float(joint[0]),
                "y": float(joint[1]),
                "z": float(joint[2]),
            }
        for jname, joint in zip(RIGHT_HAND_JOINT_NAMES, rhand_pose):
            joints[jname] = {
                "x": float(joint[0]),
                "y": float(joint[1]),
                "z": float(joint[2]),
            }

        original_data["frames"][str(i)]["osx"] = joints

    with open(original_json_path.replace("_original", "_osx"), "w") as f:
        json.dump(original_data, f, ensure_ascii=False, indent=4)


def exec_osx(video_path: str, output_dir: str, args: argparse.Namespace):
    cfg.set_args(args.gpu_ids)
    cudnn.benchmark = False

    # load model
    cfg.set_additional_args(
        encoder_setting=args.encoder_setting,
        decoder_setting=args.decoder_setting,
        pretrained_model_path=args.pretrained_model_path,
        testset=args.testset,
    )

    demoer = Demoer()
    demoer._make_model()

    model_path = args.pretrained_model_path
    assert os.path.exists(model_path), "Cannot find model at " + model_path

    demoer.model.eval()

    # detect human bbox with yolov5s
    detector = torch.hub.load("ultralytics/yolov5", "yolov5s", pretrained=True)

    # 該当ディレクトリ内のoriginal.jsonを探す
    for json_fn in glob(os.path.join(output_dir, "*_original.json")):
        exec_person_osx(video_path, json_fn, args, demoer, detector)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", type=str, dest="gpu_ids", default="0")
    parser.add_argument("--video_path", type=str)
    parser.add_argument("--output_dir", type=str, default="output")
    parser.add_argument(
        "--encoder_setting", type=str, default="osx_l", choices=["osx_b", "osx_l"]
    )
    parser.add_argument(
        "--decoder_setting",
        type=str,
        default="normal",
        choices=["normal", "wo_face_decoder", "wo_decoder"],
    )
    parser.add_argument(
        "--pretrained_model_path",
        type=str,
        default="../OSX/pretrained_models/osx_l.pth.tar",
    )
    parser.add_argument("--testset", type=str, default="EHF")
    args = parser.parse_args()

    # test gpus
    if not args.gpu_ids:
        assert 0, print("Please set proper gpu ids")

    if "-" in args.gpu_ids:
        gpus = args.gpu_ids.split("-")
        gpus[0] = int(gpus[0])
        gpus[1] = int(gpus[1]) + 1
        args.gpu_ids = ",".join(map(lambda x: str(x), list(range(*gpus))))

    return args


if __name__ == "__main__":
    args = parse_args()
    exec_osx(args.video_path, args.output_dir, args)
