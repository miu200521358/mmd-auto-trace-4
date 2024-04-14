import argparse
import json
import os

import joblib

from mlib.vmd.vmd_collection import VmdMotion, VmdBoneFrame
from mlib.vmd.vmd_writer import VmdWriter
from mlib.pmx.pmx_reader import PmxReader
from mlib.core.math import MVector3D, MQuaternion

# 身長158cmプラグインより
MIKU_CM = 0.1259496


JOINT_NAMES = [
    "nose",
    "left eye",
    "right eye",
    "left ear",
    "right ear",
    "left shoulder",
    "right shoulder",
    "left elbow",
    "right elbow",
    "left wrist",
    "right wrist",
    "left hip",
    "right hip",
    "left knee",
    "right knee",
    "left ankle",
    "right ankle",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "neck",
    "head tail",
    "",
    "",
]

PMX_CONNECTIONS = {
    "nose": "鼻",
    "left eye": "左目",
    "right eye": "右目",
    "left ear": "左耳",
    "right ear": "右耳",
    "left shoulder": "左腕",
    "right shoulder": "右腕",
    "left elbow": "左ひじ",
    "right elbow": "右ひじ",
    "left wrist": "左手首",
    "right wrist": "右手首",
    "left hip": "左足",
    "right hip": "右足",
    "left knee": "左ひざ",
    "right knee": "右ひざ",
    "left ankle": "左足首",
    "right ankle": "右足首",
    "neck": "首",
    "head tail": "頭先",
}

VMD_CONNECTIONS = {
    "下半身": {
        "direction": ("下半身", "下半身2"),
        "up": ("左足", "右足"),
        "cancel": (),
        "invert": {
            "before": MVector3D(),
            "after": MVector3D(),
        },
    },
    "上半身": {
        "direction": ("上半身", "首"),
        "up": ("左腕", "右腕"),
        "cancel": (),
        "invert": {
            "before": MVector3D(),
            "after": MVector3D(),
        },
    },
    "首": {
        "direction": ("首", "鼻"),
        "up": ("左目", "右目"),
        "cancel": ("上半身",),
        "invert": {
            "before": MVector3D(),
            "after": MVector3D(),
        },
    },
    "頭": {
        "direction": ("頭", "頭先"),
        "up": ("左目", "右目"),
        "cancel": (
            "上半身",
            "首",
        ),
        "invert": {
            "before": MVector3D(),
            "after": MVector3D(),
        },
    },
    "左肩": {
        "direction": ("左肩", "左腕"),
        "up": ("上半身", "首"),
        "cancel": ("上半身", "上半身"),
        "invert": {
            "before": MVector3D(),
            "after": MVector3D(),
        },
    },
    "左腕": {
        "direction": ("左腕", "左ひじ"),
        "up": ("上半身", "首"),
        "cancel": (
            "上半身",
            "左肩",
        ),
        "invert": {
            "before": MVector3D(),
            "after": MVector3D(),
        },
    },
    "左ひじ": {
        "direction": ("左ひじ", "左手首"),
        "up": ("上半身", "首"),
        "cancel": (
            "上半身",
            "左肩",
            "左腕",
        ),
        "invert": {
            "before": MVector3D(),
            "after": MVector3D(),
        },
    },
    "左手首": {
        "direction": ("左手首", "左中指１"),
        "up": ("左親指１", "左中指１"),
        "cancel": (
            "上半身",
            "左肩",
            "左腕",
            "左ひじ",
        ),
        "invert": {
            "before": MVector3D(),
            "after": MVector3D(),
        },
    },
    "右肩": {
        "direction": ("右肩", "右腕"),
        "up": ("上半身", "首"),
        "cancel": ("上半身",),
        "invert": {
            "before": MVector3D(),
            "after": MVector3D(),
        },
    },
    "右腕": {
        "direction": ("右腕", "右ひじ"),
        "up": ("上半身", "首"),
        "cancel": (
            "上半身",
            "右肩",
        ),
        "invert": {
            "before": MVector3D(),
            "after": MVector3D(),
        },
    },
    "右ひじ": {
        "direction": ("右ひじ", "右手首"),
        "up": ("上半身", "首"),
        "cancel": (
            "上半身",
            "右肩",
            "右腕",
        ),
        "invert": {
            "before": MVector3D(),
            "after": MVector3D(),
        },
    },
    "右手首": {
        "direction": ("右手首", "右中指１"),
        "up": ("右親指１", "右中指１"),
        "cancel": (
            "上半身",
            "右肩",
            "右腕",
            "右ひじ",
        ),
        "invert": {
            "before": MVector3D(),
            "after": MVector3D(),
        },
    },
    "左足": {
        "direction": ("左足", "左ひざ"),
        "up": ("左足", "右足"),
        "cancel": ("下半身",),
        "invert": {
            "before": MVector3D(),
            "after": MVector3D(),
        },
    },
    "左ひざ": {
        "direction": ("左ひざ", "左足首"),
        "up": ("左足", "右足"),
        "cancel": (
            "下半身",
            "左足",
        ),
        "invert": {
            "before": MVector3D(),
            "after": MVector3D(),
        },
    },
    "左足首": {
        "direction": ("左足首", "左かかと"),
        "up": ("左かかと", "左つま先"),
        "cancel": (
            "下半身",
            "左足",
            "左ひざ",
        ),
        "invert": {
            "before": MVector3D(-20, 0, 0),
            "after": MVector3D(),
        },
    },
    "右足": {
        "direction": ("右足", "右ひざ"),
        "up": ("左足", "右足"),
        "cancel": ("下半身",),
        "invert": {
            "before": MVector3D(),
            "after": MVector3D(),
        },
    },
    "右ひざ": {
        "direction": ("右ひざ", "右足首"),
        "up": ("左足", "右足"),
        "cancel": (
            "下半身",
            "右足",
        ),
        "invert": {
            "before": MVector3D(),
            "after": MVector3D(),
        },
    },
    "右足首": {
        "direction": ("右足首", "右かかと"),
        "up": ("右かかと", "右つま先"),
        "cancel": (
            "下半身",
            "右足",
            "右ひざ",
        ),
        "invert": {
            "before": MVector3D(-20, 0, 0),
            "after": MVector3D(),
        },
    },
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HMR2 demo code")
    parser.add_argument("--target_dir", type=str)

    args = parser.parse_args()

    poses_mov_motion = VmdMotion()
    poses_rot_motion = VmdMotion()

    pmx_reader = PmxReader()
    trace_model = pmx_reader.read_by_filepath(
        "/mnt/c/MMD/mmd-auto-trace-4/configs/pmx/trace_model.pmx"
    )

    all_wham_results = joblib.load(os.path.join(args.target_dir, "wham_output.pkl"))
    all_viz_results = joblib.load(os.path.join(args.target_dir, "wham_output_vis.pkl"))
    start_joint_root = (
        (all_viz_results[0]["joints"][0][19] + all_viz_results[0]["joints"][0][20]) / 2
    ) * 2

    i = 0
    for n, vis_joints in all_viz_results.items():
        for m, joints in enumerate(vis_joints["joints"]):
            for o, joint in enumerate(joints):
                if not JOINT_NAMES[o]:
                    continue

                joint_pos = (
                    MVector3D(float(joint[0]), float(joint[1]), float(-joint[2]))
                    / MIKU_CM
                )
                bf = VmdBoneFrame(name=PMX_CONNECTIONS[JOINT_NAMES[o]], index=i, register=True)
                bf.position = joint_pos
                poses_mov_motion.append_bone_frame(bf)

            spine_bf = VmdBoneFrame(i, "上半身", register=True)
            spine_bf.position = (
                poses_mov_motion.bones["左足"][i].position
                + poses_mov_motion.bones["右足"][i].position
            ) / 2
            poses_mov_motion.append_bone_frame(spine_bf)

            neck_bf = VmdBoneFrame(i, "首", register=True)
            neck_bf.position = (
                poses_mov_motion.bones["左腕"][i].position
                + poses_mov_motion.bones["右腕"][i].position
            ) / 2
            poses_mov_motion.append_bone_frame(neck_bf)

            left_shoulder_bf = VmdBoneFrame(i, "左肩", register=True)
            left_shoulder_bf.position = (
                poses_mov_motion.bones["左腕"][i].position
                + poses_mov_motion.bones["首"][i].position
            ) / 2
            poses_mov_motion.append_bone_frame(left_shoulder_bf)

            right_shoulder_bf = VmdBoneFrame(i, "右肩", register=True)
            right_shoulder_bf.position = (
                poses_mov_motion.bones["右腕"][i].position
                + poses_mov_motion.bones["首"][i].position
            ) / 2
            poses_mov_motion.append_bone_frame(right_shoulder_bf)

            pelvis_bf = VmdBoneFrame(i, "下半身", register=True)
            pelvis_bf.position = (
                poses_mov_motion.bones["左足"][i].position
                + poses_mov_motion.bones["右足"][i].position
            ) / 2
            poses_mov_motion.append_bone_frame(pelvis_bf)

            pelvis2_bf = VmdBoneFrame(i, "下半身2", register=True)
            pelvis2_bf.position = (
                poses_mov_motion.bones["左ひざ"][i].position
                + poses_mov_motion.bones["右ひざ"][i].position
            ) / 2
            poses_mov_motion.append_bone_frame(pelvis2_bf)

            center_bf = VmdBoneFrame(i, "センター", register=True)
            center_bf.position = pelvis_bf.position.copy()
            poses_rot_motion.append_bone_frame(center_bf)

            i += 1

    os.makedirs(args.target_dir, exist_ok=True)

    VmdWriter(
        poses_mov_motion,
        os.path.join(args.target_dir, "output_poses_mov.vmd"),
        "WHAM",
    ).save()

    for target_bone_name, vmd_params in VMD_CONNECTIONS.items():
        direction_from_name = vmd_params["direction"][0]
        direction_to_name = vmd_params["direction"][1]
        up_from_name = vmd_params["up"][0]
        up_to_name = vmd_params["up"][1]
        cross_from_name = (
            vmd_params["cross"][0]
            if "cross" in vmd_params
            else vmd_params["direction"][0]
        )
        cross_to_name = (
            vmd_params["cross"][1]
            if "cross" in vmd_params
            else vmd_params["direction"][1]
        )
        cancel_names = vmd_params["cancel"]
        invert_qq = MQuaternion.from_euler_degrees(vmd_params["invert"]["before"])

        for mov_bf in poses_mov_motion.bones[direction_from_name]:
            if (
                mov_bf.index not in poses_mov_motion.bones[direction_from_name]
                or mov_bf.index not in poses_mov_motion.bones[direction_to_name]
            ):
                # キーがない場合、スルーする
                continue

            bone_direction = (
                trace_model.bones[direction_to_name].position
                - trace_model.bones[direction_from_name].position
            ).normalized()

            bone_up = (
                trace_model.bones[up_to_name].position
                - trace_model.bones[up_from_name].position
            ).normalized()
            bone_cross = (
                trace_model.bones[cross_to_name].position
                - trace_model.bones[cross_from_name].position
            ).normalized()
            bone_cross_vec: MVector3D = bone_up.cross(bone_cross).normalized()

            initial_qq = MQuaternion.from_direction(bone_direction, bone_cross_vec)

            direction_from_abs_pos = poses_mov_motion.bones[direction_from_name][
                mov_bf.index
            ].position
            direction_to_abs_pos = poses_mov_motion.bones[direction_to_name][
                mov_bf.index
            ].position
            direction: MVector3D = (
                direction_to_abs_pos - direction_from_abs_pos
            ).normalized()

            up_from_abs_pos = poses_mov_motion.bones[up_from_name][
                mov_bf.index
            ].position
            up_to_abs_pos = poses_mov_motion.bones[up_to_name][mov_bf.index].position
            up: MVector3D = (up_to_abs_pos - up_from_abs_pos).normalized()

            cross_from_abs_pos = poses_mov_motion.bones[cross_from_name][
                mov_bf.index
            ].position
            cross_to_abs_pos = poses_mov_motion.bones[cross_to_name][
                mov_bf.index
            ].position
            cross: MVector3D = (cross_to_abs_pos - cross_from_abs_pos).normalized()

            motion_cross_vec: MVector3D = up.cross(cross).normalized()
            motion_qq = MQuaternion.from_direction(direction, motion_cross_vec)

            cancel_qq = MQuaternion()
            for cancel_name in cancel_names:
                cancel_qq *= poses_rot_motion.bones[cancel_name][mov_bf.index].rotation

            bf = VmdBoneFrame(name=target_bone_name, index=mov_bf.index, register=True)
            bf.rotation = (
                cancel_qq.inverse() * motion_qq * initial_qq.inverse() * invert_qq
            )

            poses_rot_motion.append_bone_frame(bf)

    VmdWriter(
        poses_rot_motion,
        os.path.join(args.target_dir, "output_poses_rot.vmd"),
        "WHAM",
    ).save()
