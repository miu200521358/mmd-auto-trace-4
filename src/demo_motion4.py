import argparse
import os
import numpy as np

from mlib.vmd.vmd_collection import VmdMotion
from mlib.vmd.vmd_reader import VmdReader
from mlib.vmd.vmd_writer import VmdWriter
from mlib.core.math import MVector3D, MQuaternion
from mlib.core.interpolation import create_interpolation, get_infections2

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HMR2 demo code")
    parser.add_argument("--target_dir", type=str)

    args = parser.parse_args()

    mp_rot_motion = VmdReader().read_by_filepath(
        os.path.join(args.target_dir, "output_poses_mp_rot.vmd")
    )
    reduce_motion = VmdMotion()

    xs = []
    ys = []
    zs = []

    for fno in range(mp_rot_motion.bones.max_fno):
        xs.append(mp_rot_motion.bones["センター"][fno].position.x * 1.5)
        ys.append(mp_rot_motion.bones["センター"][fno].position.y)
        zs.append(mp_rot_motion.bones["センター"][fno].position.z)

    x_infections = get_infections2(xs, 0.5, 0.05)
    y_infections = get_infections2(ys, 0.5, 0.05)
    z_infections = get_infections2(zs, 0.8, 0.3)

    print("x_infections:")
    print(x_infections)
    print("y_infections:")
    print(y_infections)
    print("z_infections:")
    print(z_infections)

    xz_infections = np.array(list(set(x_infections) | set(z_infections)))
    xz_infections.sort()

    y1bf = reduce_motion.bones["グルーブ"][0]
    y1bf.register = True
    y1bf.position = MVector3D(0, ys[0], 0)
    reduce_motion.append_bone_frame(y1bf)

    xz1bf = reduce_motion.bones["センター"][0]
    xz1bf.register = True
    xz1bf.position = MVector3D(xs[0], 0, zs[0])
    reduce_motion.append_bone_frame(xz1bf)

    # グルーブ
    for y1, y2 in zip(y_infections[:-1], y_infections[1:]):
        ybz = create_interpolation(ys[y1 : (y2 + 1)])

        y2bf = reduce_motion.bones["グルーブ"][y2]
        y2bf.register = True
        y2bf.position = MVector3D(0, ys[y2], 0)
        y2bf.interpolations.translation_y = ybz

        reduce_motion.append_bone_frame(y2bf)

    # センター
    for x1, x2 in zip(xz_infections[:-1], xz_infections[1:]):
        xbz = create_interpolation(xs[x1 : (x2 + 1)])
        zbz = create_interpolation(zs[x1 : (x2 + 1)])

        x2bf = reduce_motion.bones["センター"][x2]
        x2bf.register = True
        x2bf.position = MVector3D(xs[x2], 0, zs[x2])
        x2bf.interpolations.translation_x = xbz
        x2bf.interpolations.translation_z = zbz

        reduce_motion.append_bone_frame(x2bf)

    for bone_name in mp_rot_motion.bones.names:
        if bone_name in ["センター", "グルーブ"]:
            continue

        rs = [mp_rot_motion.bones[bone_name][0].rotation]
        ds = [1.0]
        for fno in range(1, mp_rot_motion.bones.max_fno):
            ds.append(
                MQuaternion.dot(rs[-1], mp_rot_motion.bones[bone_name][fno].rotation)
            )
            rs.append(mp_rot_motion.bones[bone_name][fno].rotation)

        d_infections = get_infections2(ds, 0.02, 0.001)

        print("d_infections:")
        print(d_infections)

        r1bf = reduce_motion.bones[bone_name][0]
        r1bf.register = True
        r1bf.rotation = rs[0]
        reduce_motion.append_bone_frame(r1bf)

        for d1, d2 in zip(d_infections[:-1], d_infections[1:]):
            rbz = create_interpolation(ds[d1 : (d2 + 1)])

            r2bf = reduce_motion.bones[bone_name][d2]
            r2bf.register = True
            r2bf.rotation = rs[d2]
            r2bf.interpolations.rotation = rbz

            reduce_motion.append_bone_frame(r2bf)

    VmdWriter(
        reduce_motion,
        os.path.join(args.target_dir, "output_poses_mp_rot_reduce.vmd"),
        "WHAM_MP",
    ).save()
