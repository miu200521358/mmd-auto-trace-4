import os
import argparse
import os.path as osp
from glob import glob
from collections import defaultdict
import sys

import cv2
import joblib
import torch
import numpy as np
from progress.bar import Bar
from loguru import logger

sys.path.append(os.path.join(os.path.dirname(__file__), "WHAM"))

from WHAM.configs.config import get_cfg_defaults
from WHAM.lib.data._custom import CustomDataset
from WHAM.lib.utils.imutils import avg_preds
from WHAM.lib.utils.transforms import matrix_to_axis_angle
from WHAM.lib.models import build_network, build_body_model
from WHAM.lib.models.preproc.detector import DetectionModel
from WHAM.lib.models.preproc.extractor import FeatureExtractor
from WHAM.lib.models.smplify import TemporalSMPLify
from WHAM.lib.vis.renderer import Renderer, get_global_cameras

try:
    from WHAM.lib.models.preproc.slam import SLAMModel

    _run_global = True
except:
    logger.info("DPVO is not properly installed. Only estimate in local coordinates !")
    _run_global = False


def run(
    cfg,
    video,
    output_pth,
    network,
    calib=None,
    run_global=True,
):

    cap = cv2.VideoCapture(video)
    assert cap.isOpened(), f"Faild to load video file {video}"
    fps = cap.get(cv2.CAP_PROP_FPS)
    length = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width, height = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(
        cv2.CAP_PROP_FRAME_HEIGHT
    )

    # Whether or not estimating motion in global coordinates
    run_global = run_global and _run_global

    # Preprocess
    with torch.no_grad():
        detector = DetectionModel(cfg.DEVICE.lower())
        extractor = FeatureExtractor(cfg.DEVICE.lower(), cfg.FLIP_EVAL)

        if run_global:
            slam = SLAMModel(video, output_pth, width, height, calib)
        else:
            slam = None

        bar = Bar("Preprocess: 2D detection and SLAM", fill="#", max=length)
        while cap.isOpened():
            flag, img = cap.read()
            if not flag:
                break

            # 2D detection and tracking
            detector.track(img, fps, length)

            # SLAM
            if slam is not None:
                slam.track()

            bar.next()

        tracking_results = detector.process(fps)

        if slam is not None:
            slam_results = slam.process()
        else:
            slam_results = np.zeros((length, 7))
            slam_results[:, 3] = 1.0  # Unit quaternion

        # Extract image features
        # TODO: Merge this into the previous while loop with an online bbox smoothing.
        tracking_results = extractor.run(video, tracking_results)
        logger.info("Complete Data preprocessing!")

        # Save the processed data
        joblib.dump(tracking_results, osp.join(output_pth, "tracking_results.pth"))
        joblib.dump(slam_results, osp.join(output_pth, "slam_results.pth"))
        logger.info(f"Save processed data at {output_pth}")

    # Build dataset
    dataset = CustomDataset(cfg, tracking_results, slam_results, width, height, fps)

    # run WHAM
    results = defaultdict(dict)

    n_subjs = len(dataset)
    for subj in range(n_subjs):

        with torch.no_grad():
            if cfg.FLIP_EVAL:
                # Forward pass with flipped input
                flipped_batch = dataset.load_data(subj, True)
                (
                    _id,
                    x,
                    inits,
                    features,
                    mask,
                    init_root,
                    cam_angvel,
                    frame_id,
                    kwargs,
                ) = flipped_batch
                flipped_pred = network(
                    x,
                    inits,
                    features,
                    mask=mask,
                    init_root=init_root,
                    cam_angvel=cam_angvel,
                    return_y_up=True,
                    **kwargs,
                )

                # Forward pass with normal input
                batch = dataset.load_data(subj)
                (
                    _id,
                    x,
                    inits,
                    features,
                    mask,
                    init_root,
                    cam_angvel,
                    frame_id,
                    kwargs,
                ) = batch
                pred = network(
                    x,
                    inits,
                    features,
                    mask=mask,
                    init_root=init_root,
                    cam_angvel=cam_angvel,
                    return_y_up=True,
                    **kwargs,
                )

                # Merge two predictions
                flipped_pose, flipped_shape = flipped_pred["pose"].squeeze(
                    0
                ), flipped_pred["betas"].squeeze(0)
                pose, shape = pred["pose"].squeeze(0), pred["betas"].squeeze(0)
                flipped_pose, pose = flipped_pose.reshape(-1, 24, 6), pose.reshape(
                    -1, 24, 6
                )
                avg_pose, avg_shape = avg_preds(
                    pose, shape, flipped_pose, flipped_shape
                )
                avg_pose = avg_pose.reshape(-1, 144)
                avg_contact = (
                    flipped_pred["contact"][..., [2, 3, 0, 1]] + pred["contact"]
                ) / 2

                # Refine trajectory with merged prediction
                network.pred_pose = avg_pose.view_as(network.pred_pose)
                network.pred_shape = avg_shape.view_as(network.pred_shape)
                network.pred_contact = avg_contact.view_as(network.pred_contact)
                output = network.forward_smpl(**kwargs)
                pred = network.refine_trajectory(output, cam_angvel, return_y_up=True)

            else:
                # data
                batch = dataset.load_data(subj)
                (
                    _id,
                    x,
                    inits,
                    features,
                    mask,
                    init_root,
                    cam_angvel,
                    frame_id,
                    kwargs,
                ) = batch

                # inference
                pred = network(
                    x,
                    inits,
                    features,
                    mask=mask,
                    init_root=init_root,
                    cam_angvel=cam_angvel,
                    return_y_up=True,
                    **kwargs,
                )

        # if False:
        if args.run_smplify:
            smplify = TemporalSMPLify(
                smpl, img_w=width, img_h=height, device=cfg.DEVICE
            )
            input_keypoints = dataset.tracking_results[_id]["keypoints"]
            pred = smplify.fit(pred, input_keypoints, **kwargs)

            with torch.no_grad():
                network.pred_pose = pred["pose"]
                network.pred_shape = pred["betas"]
                network.pred_cam = pred["cam"]
                output = network.forward_smpl(**kwargs)
                pred = network.refine_trajectory(output, cam_angvel, return_y_up=True)

        # ========= Store results ========= #
        pred_body_pose = (
            matrix_to_axis_angle(pred["poses_body"]).cpu().numpy().reshape(-1, 69)
        )
        pred_root = (
            matrix_to_axis_angle(pred["poses_root_cam"]).cpu().numpy().reshape(-1, 3)
        )
        pred_root_world = (
            matrix_to_axis_angle(pred["poses_root_world"]).cpu().numpy().reshape(-1, 3)
        )
        pred_pose = np.concatenate((pred_root, pred_body_pose), axis=-1)
        pred_pose_world = np.concatenate((pred_root_world, pred_body_pose), axis=-1)
        pred_trans = (pred["trans_cam"] - network.output.offset).cpu().numpy()

        results[_id]["pose"] = pred_pose
        results[_id]["trans"] = pred_trans
        results[_id]["pose_world"] = pred_pose_world
        results[_id]["trans_world"] = pred["trans_world"].cpu().squeeze(0).numpy()
        results[_id]["betas"] = pred["betas"].cpu().squeeze(0).numpy()
        results[_id]["verts"] = (
            (pred["verts_cam"] + pred["trans_cam"].unsqueeze(1)).cpu().numpy()
        )
        results[_id]["frame_ids"] = frame_id

        results[_id]["pred_body_pose"] = pred_body_pose
        results[_id]["pred_root"] = pred_root
        results[_id]["pred_root_world"] = pred_root_world
        results[_id]["poses_body"] = pred["poses_body"].cpu().numpy()
        results[_id]["poses_root_cam"] = pred["poses_root_cam"].cpu().numpy()
        results[_id]["poses_root_world"] = pred["poses_root_world"].cpu().numpy()

    joblib.dump(results, osp.join(output_pth, "wham_output.pkl"))

    # Visualize
    with torch.no_grad():
        run_vis_on_demo(
            cfg, video, results, output_pth, network.smpl, vis_global=run_global
        )

def run_vis_on_demo(cfg, video, results, output_pth, smpl, vis_global=True):
    outputs = defaultdict(dict)

    # to torch tensor
    tt = lambda x: torch.from_numpy(x).float().to(cfg.DEVICE)

    cap = cv2.VideoCapture(video)
    width, height = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(
        cv2.CAP_PROP_FRAME_HEIGHT
    )

    # create renderer with cliff focal length estimation
    focal_length = (width**2 + height**2) ** 0.5
    renderer = Renderer(width, height, focal_length, cfg.DEVICE, smpl.faces)

    # setup global coordinate subject
    # current implementation only visualize the subject appeared longest
    n_frames = {k: len(results[k]["frame_ids"]) for k in results.keys()}
    sid = max(n_frames, key=n_frames.get)
    global_output = smpl.get_output(
        body_pose=tt(results[sid]["pose_world"][:, 3:]),
        global_orient=tt(results[sid]["pose_world"][:, :3]),
        betas=tt(results[sid]["betas"]),
        transl=tt(results[sid]["trans_world"]),
    )
    verts_glob = global_output.vertices.cpu()
    verts_glob[..., 1] = verts_glob[..., 1] - verts_glob[..., 1].min()
    cx, cz = (verts_glob.mean(1).max(0)[0] + verts_glob.mean(1).min(0)[0])[
        [0, 2]
    ] / 2.0
    sx, sz = (verts_glob.mean(1).max(0)[0] - verts_glob.mean(1).min(0)[0])[[0, 2]]
    scale = max(sx.item(), sz.item()) * 1.5

    # set default ground
    renderer.set_ground(scale, cx.item(), cz.item())

    # build global camera
    global_R, global_T, global_lights = get_global_cameras(verts_glob, cfg.DEVICE)

    outputs["frames"] = n_frames
    outputs["joints"] = global_output.joints.cpu().numpy()
    outputs["betas"] = global_output.betas.cpu().numpy()
    outputs["global_R"] = global_R.cpu().numpy()
    outputs["global_T"] = global_T.cpu().numpy()

    joblib.dump(outputs, osp.join(output_pth, "wham_output_vis.pkl"))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--video",
        type=str,
        default="examples/demo_video.mp4",
        help="input video path or youtube link",
    )

    parser.add_argument(
        "--output_pth",
        type=str,
        default="output/demo",
        help="output folder to write results",
    )

    parser.add_argument(
        "--calib", type=str, default=None, help="Camera calibration file path"
    )

    parser.add_argument(
        "--estimate_local_only",
        action="store_true",
        help="Only estimate motion in camera coordinate if True",
    )

    parser.add_argument(
        "--visualize", action="store_true", help="Visualize the output mesh if True"
    )

    parser.add_argument(
        "--save_pkl", action="store_true", help="Save output as pkl file"
    )

    parser.add_argument(
        "--run_smplify",
        action="store_true",
        help="Run Temporal SMPLify for post processing",
    )

    args = parser.parse_args()

    cfg = get_cfg_defaults()
    cfg.merge_from_file("configs/WHAM/yamls/mat4.yaml")

    logger.info(f"GPU name -> {torch.cuda.get_device_name()}")
    logger.info(f'GPU feat -> {torch.cuda.get_device_properties("cuda")}')

    # ========= Load WHAM ========= #
    smpl_batch_size = cfg.TRAIN.BATCH_SIZE * cfg.DATASET.SEQLEN
    smpl = build_body_model(cfg.DEVICE, smpl_batch_size)
    network = build_network(cfg, smpl)
    network.eval()

    # Output folder
    sequence = ".".join(args.video.split("/")[-1].split(".")[:-1])
    output_pth = osp.join(args.output_pth, sequence)
    os.makedirs(output_pth, exist_ok=True)

    run(
        cfg,
        args.video,
        output_pth,
        network,
        args.calib,
        run_global=not args.estimate_local_only,
    )

    print()
    logger.info("Done !")
