import os
import sys
import joblib
import numpy as np
from tqdm import tqdm

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from mlib.vmd.vmd_collection import VmdMotion, VmdBoneFrame
from mlib.vmd.vmd_writer import VmdWriter
from mlib.pmx.pmx_reader import PmxReader
from mlib.pmx.pmx_collection import PmxModel
from mlib.core.math import MVector3D, MQuaternion

SMPL_JOINT_32 = [
    "Nose",  # 0
    "LEye",  # 1
    "REye",  # 2
    "LEar",  # 3
    "REar",  # 4
    "LShoulder",  # 5
    "RShoulder",  # 6
    "LElbow",  # 7
    "RElbow",  # 8
    "LWrist",  # 9
    "RWrist",  # 10
    "LLeg",  # 11
    "RLeg",  # 12
    "LKnee",  # 13
    "RKnee",  # 14
    "LAnkle",  # 15
    "RAnkle",  # 16
    "",  # 17
    "",  # 18
    "RHip",  # 19
    "LHip",  # 20
    "",  # 21
    "",  # 22
    "",  # 23
    "",  # 24
    "",  # 25
    "",  # 26
    "",  # 27
    "",  # 28
    "Neck",  # 29
    "Head2",  # 30
    "",  # 31
    "",  # 32
]


PMX_CONNECTIONS = {
    "下半身": "Pelvis",
    "下半身2": "Pelvis2",
    "左足": "LLeg",
    "右足": "RLeg",
    "上半身": "Spine",
    "首": "Neck",
    "左ひざ": "LKnee",
    "右ひざ": "RKnee",
    "左足首": "LAnkle",
    "右足首": "RAnkle",
    "頭": "Head",
    "頭先": "Head2",
    "鼻": "Nose",
    "左腕": "LShoulder",
    "右腕": "RShoulder",
    "左ひじ": "LElbow",
    "右ひじ": "RElbow",
    "左手首": "LWrist",
    "右手首": "RWrist",
    "左耳": "LEar",
    "右耳": "REar",
    "左目": "LEye",
    "右目": "REye",
    "首根元": "NeckBase",
}

PMX_REVERSE_CONNECTIONS = {v: k for k, v in PMX_CONNECTIONS.items()}

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
        "direction": ("首", "頭"),
        "up": ("左耳", "右耳"),
        "cancel": (
            "上半身",
            "上半身2",
        ),
        "invert": {
            "before": MVector3D(),
            "after": MVector3D(),
        },
    },
    "頭": {
        "direction": ("左目", "右目"),
        "up": ("頭", "頭先"),
        "cancel": (
            "上半身",
            "首",
        ),
        "invert": {
            "before": MVector3D(-40, 0, 0),
            "after": MVector3D(),
        },
    },
    "左肩": {
        "direction": ("首根元", "左腕"),
        "up": ("左腕", "左ひじ"),
        "cancel": ("上半身",),
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
            "上半身2",
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
            "上半身2",
            "左肩",
            "左腕",
        ),
        "invert": {
            "before": MVector3D(),
            "after": MVector3D(),
        },
    },
    "右肩": {
        "direction": ("首根元", "右腕"),
        "up": ("右腕", "右ひじ"),
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
            "上半身2",
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
            "上半身2",
            "右肩",
            "右腕",
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
}

# 身長158cmプラグインより
MIKU_CM = 0.1259496

np.set_printoptions(suppress=True, precision=6, threshold=30, linewidth=200)

if __name__ == "__main__":
    # ------------------------------
    wham_output_path = (
        # "C:/MMD/mmd-auto-trace-4/WHAM/output/demo/IMG_9732/wham_output_vis.pkl"
        "C:/MMD/mmd-auto-trace-4/WHAM/output/demo/snobbism_part1/wham_output_vis.pkl"
    )

    pmx_reader = PmxReader()
    trace_model = pmx_reader.read_by_filepath(
        "C:/MMD/mmd-auto-trace-3/data/pmx/trace_model.pmx"
    )

    # .pthファイルからデータをロード
    wham_output = joblib.load(wham_output_path)

    # numpy配列に変換
    wham_output_numpy = np.array(wham_output)

    print(wham_output_numpy)

    wham_output_dict = dict(wham_output)

    poses_mov_motion = VmdMotion()
    poses_rot_motion = VmdMotion()

    joints = wham_output_dict["joints"]
    print("joints", joints[:2])

    for i in range(joints.shape[0]):
        joint = joints[i]
        # print(f"joint {i}: {joint}")
        for j in range(joints.shape[1]):
            if not SMPL_JOINT_32[j]:
                continue
            jt = joint[j]
            pose_bf = VmdBoneFrame(i, SMPL_JOINT_32[j], register=True)
            pose_bf.position = MVector3D(jt[0], jt[1], -jt[2])
            pose_bf.position *= 10

            poses_mov_motion.append_bone_frame(pose_bf)

        pelvis_bf = VmdBoneFrame(i, "Pelvis", register=True)
        pelvis_bf.position = (
            poses_mov_motion.bones["LHip"][i].position
            + poses_mov_motion.bones["RHip"][i].position
        ) / 2
        poses_mov_motion.append_bone_frame(pelvis_bf)

        pelvis2_bf = VmdBoneFrame(i, "Pelvis2", register=True)
        pelvis2_bf.position = (
            poses_mov_motion.bones["LLeg"][i].position
            + poses_mov_motion.bones["RLeg"][i].position
        ) / 2
        poses_mov_motion.append_bone_frame(pelvis2_bf)

        spine_bf = VmdBoneFrame(i, "Spine", register=True)
        spine_bf.position = (
            poses_mov_motion.bones["LHip"][i].position
            + poses_mov_motion.bones["RHip"][i].position
        ) / 2
        poses_mov_motion.append_bone_frame(spine_bf)

        head_bf = VmdBoneFrame(i, "Head", register=True)
        head_bf.position = (
            poses_mov_motion.bones["LEye"][i].position
            + poses_mov_motion.bones["REye"][i].position
        ) / 2
        poses_mov_motion.append_bone_frame(head_bf)

        neck_base_bf = VmdBoneFrame(i, "NeckBase", register=True)
        neck_base_bf.position = (
            poses_mov_motion.bones["LShoulder"][i].position
            + poses_mov_motion.bones["RShoulder"][i].position
        ) / 2
        poses_mov_motion.append_bone_frame(neck_base_bf)

        center_bf = VmdBoneFrame(i, "センター", register=True)
        center_bf.position = pelvis_bf.position.copy()
        poses_rot_motion.append_bone_frame(center_bf)

        # ------------------------------

    VmdWriter(
        poses_mov_motion,
        "C:/MMD/mmd-auto-trace-4/WHAM/output/demo/snobbism_part1/output_poses_mov.vmd",
        "h36_17",
    ).save()

    for target_bone_name, vmd_params in VMD_CONNECTIONS.items():
        direction_from_name = PMX_CONNECTIONS[vmd_params["direction"][0]]
        direction_to_name = PMX_CONNECTIONS[vmd_params["direction"][1]]
        up_from_name = PMX_CONNECTIONS[vmd_params["up"][0]]
        up_to_name = PMX_CONNECTIONS[vmd_params["up"][1]]
        cross_from_name = (
            PMX_CONNECTIONS[vmd_params["cross"][0]]
            if "cross" in vmd_params
            else PMX_CONNECTIONS[vmd_params["direction"][0]]
        )
        cross_to_name = (
            PMX_CONNECTIONS[vmd_params["cross"][1]]
            if "cross" in vmd_params
            else PMX_CONNECTIONS[vmd_params["direction"][1]]
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
                trace_model.bones[PMX_REVERSE_CONNECTIONS[direction_to_name]].position
                - trace_model.bones[
                    PMX_REVERSE_CONNECTIONS[direction_from_name]
                ].position
            ).normalized()

            bone_up = (
                trace_model.bones[PMX_REVERSE_CONNECTIONS[up_to_name]].position
                - trace_model.bones[PMX_REVERSE_CONNECTIONS[up_from_name]].position
            ).normalized()
            bone_cross = (
                trace_model.bones[PMX_REVERSE_CONNECTIONS[cross_to_name]].position
                - trace_model.bones[PMX_REVERSE_CONNECTIONS[cross_from_name]].position
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
        "C:/MMD/mmd-auto-trace-4/WHAM/output/demo/snobbism_part1/output_poses_rot.vmd",
        "h36_17",
    ).save()
