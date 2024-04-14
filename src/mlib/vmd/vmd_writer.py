import os
import struct

from mlib.core.base import BaseModel
from mlib.core.logger import MLogger
from mlib.vmd.vmd_collection import VmdMotion

logger = MLogger(os.path.basename(__file__))


class VmdWriter(BaseModel):
    def __init__(self, motion: VmdMotion, output_path: str, model_name: str) -> None:
        super().__init__()
        self.motion = motion
        self.output_path = output_path
        self.model_name = model_name

    def save(self) -> None:
        with open(self.output_path, "wb") as fout:
            # header
            fout.write(b"Vocaloid Motion Data 0002\x00\x00\x00\x00\x00")

            try:
                # モデル名を20byteで切る
                model_bname = (
                    self.model_name.encode("cp932")
                    .decode("shift_jis")
                    .encode("shift_jis")[:20]
                )
            except Exception:
                logger.warning(
                    "モデル名に日本語・英語で判読できない文字（環境依存文字・他言語文字等）が含まれているため、仮モデル名を設定します。 {m}",
                    m=self.model_name,
                    decoration=MLogger.Decoration.BOX,
                )
                model_bname = "Vmd Sized Model".encode("shift_jis")[:20]

            # 20文字に満たなかった場合、埋める
            model_bname = model_bname.ljust(20, b"\x00")
            fout.write(model_bname)

            # bone frames
            fout.write(struct.pack("<L", self.motion.bone_count))  # ボーンフレーム数
            fidx = 0
            bone_count = self.motion.bone_count
            for bone_name in self.motion.bones.names:
                for fno in reversed(self.motion.bones[bone_name].register_indexes):
                    logger.count(
                        "ボーンモーション出力",
                        index=fidx,
                        total_index_count=bone_count,
                        display_block=10000,
                    )
                    fidx += 1

                    bf = self.motion.bones[bone_name][fno]
                    # INDEXを逆順に出力する
                    bname = (
                        bf.name.encode("cp932")
                        .decode("shift_jis")
                        .encode("shift_jis")[:15]
                        .ljust(15, b"\x00")
                    )  # 15文字制限
                    fout.write(bname)
                    fout.write(struct.pack("<L", int(bf.index)))
                    fout.write(struct.pack("<f", float(bf.position.x)))
                    fout.write(struct.pack("<f", float(bf.position.y)))
                    fout.write(struct.pack("<f", float(bf.position.z)))
                    v = bf.rotation.normalized().to_vector4()
                    fout.write(struct.pack("<f", float(v.x)))
                    fout.write(struct.pack("<f", float(v.y)))
                    fout.write(struct.pack("<f", float(v.z)))
                    fout.write(struct.pack("<f", float(v.w)))
                    fout.write(
                        bytearray(
                            [
                                int(min(255, max(0, x)))
                                for x in bf.interpolations.merge()
                            ]
                        )
                    )

            fout.write(struct.pack("<L", self.motion.morph_count))  # 表情フレーム数
            fidx = 0
            morph_count = self.motion.morph_count
            for morph_name in self.motion.morphs.names:
                for fno in reversed(self.motion.morphs[morph_name].indexes):
                    logger.count(
                        "モーフモーション出力",
                        index=fidx,
                        total_index_count=morph_count,
                        display_block=10000,
                    )
                    fidx += 1

                    mf = self.motion.morphs[morph_name][fno]
                    # INDEXを逆順に出力する
                    bname = (
                        mf.name.encode("cp932")
                        .decode("shift_jis")
                        .encode("shift_jis")[:15]
                        .ljust(15, b"\x00")
                    )  # 15文字制限
                    fout.write(bname)
                    fout.write(struct.pack("<L", int(mf.index)))
                    fout.write(struct.pack("<f", float(mf.ratio)))

            fout.write(struct.pack("<L", len(self.motion.cameras)))  # カメラキーフレーム数
            for fno in reversed(self.motion.cameras.indexes):
                cf = self.motion.cameras[fno]
                fout.write(struct.pack("<L", int(cf.index)))
                fout.write(struct.pack("<f", float(cf.distance)))
                fout.write(struct.pack("<f", float(cf.position.x)))
                fout.write(struct.pack("<f", float(cf.position.y)))
                fout.write(struct.pack("<f", float(cf.position.z)))
                fout.write(struct.pack("<f", float(cf.rotation.degrees.x)))
                fout.write(struct.pack("<f", float(cf.rotation.degrees.y)))
                fout.write(struct.pack("<f", float(cf.rotation.degrees.z)))
                fout.write(
                    bytearray(
                        [int(min(255, max(0, x))) for x in cf.interpolations.merge()]
                    )
                )
                fout.write(struct.pack("<L", int(cf.viewing_angle)))
                fout.write(struct.pack("b", int(cf.perspective)))

            fout.write(struct.pack("<L", len(self.motion.lights)))  # 照明キーフレーム数
            for fno in reversed(self.motion.lights.indexes):
                lf = self.motion.lights[fno]
                fout.write(struct.pack("<L", int(lf.index)))
                fout.write(struct.pack("<f", float(lf.color.x)))
                fout.write(struct.pack("<f", float(lf.color.y)))
                fout.write(struct.pack("<f", float(lf.color.z)))
                fout.write(struct.pack("<f", float(lf.position.x)))
                fout.write(struct.pack("<f", float(lf.position.y)))
                fout.write(struct.pack("<f", float(lf.position.z)))

            fout.write(struct.pack("<L", len(self.motion.shadows)))  # セルフ影キーフレーム数
            for fno in reversed(self.motion.shadows.indexes):
                sf = self.motion.shadows[fno]
                fout.write(struct.pack("<L", int(sf.index)))
                fout.write(struct.pack("<f", float(sf.type)))
                fout.write(struct.pack("<f", float(sf.distance)))

            fout.write(
                struct.pack("<L", self.motion.ik_count)
            )  # モデル表示・IK on/offキーフレーム数
            for sk in self.motion.show_iks:
                fout.write(struct.pack("<L", sk.index))
                fout.write(struct.pack("b", sk.show))
                fout.write(struct.pack("<L", len(sk.iks)))
                for ik in sk.iks:
                    bname = (
                        ik.name.encode("cp932")
                        .decode("shift_jis")
                        .encode("shift_jis")[:20]
                        .ljust(20, b"\x00")
                    )  # 20文字制限
                    fout.write(bname)
                    fout.write(struct.pack("b", ik.onoff))
