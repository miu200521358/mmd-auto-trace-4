from datetime import datetime
from glob import glob
import os
import sys
import time

import py.exec_pkl2json as exec_pkl2json
import exec_mediapipe
import exec_smooth
import exec_track


if __name__ == "__main__":
    video_path = sys.argv[1]
    if len(sys.argv) > 2:
        output_dir_path = sys.argv[2]
    else:
        # 出力ディレクトリ絶対パス未指定の場合、日時込みで作成する
        output_dir_path = os.path.join(
            os.path.dirname(video_path),
            f"{os.path.basename(video_path).split('.')[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        )
        os.makedirs(output_dir_path, exist_ok=True)

    cfg = exec_track.Human4DConfig()
    cfg.video.source = video_path
    cfg.video.output_dir = output_dir_path
    cfg.block_frame_num = 1000

    if not os.path.exists(os.path.join(cfg.video.output_dir, "end_of_frame")):
        # まだフレーム最後まで読み取り出来ていなかった場合、読み取り実行
        exec_track.main(cfg)

    time.sleep(3)

    # 最後までいったら変換処理
    if os.path.exists(os.path.join(cfg.video.output_dir, "end_of_frame")):
        original_json_paths = glob(
            os.path.join(cfg.video.output_dir, "*_original.json")
        )
        if not original_json_paths:
            # まだjson変換出来ていない場合、変換
            exec_pkl2json.main(output_dir_path)
        else:
            mp_json_paths = glob(os.path.join(cfg.video.output_dir, "*_mp.json"))
            if not mp_json_paths:
                # まだmediapipe実行出来ていない場合、実行
                exec_mediapipe.main(video_path, output_dir_path)
            else:
                smooth_json_paths = glob(
                    os.path.join(cfg.video.output_dir, "*_smooth.json")
                )
                if not smooth_json_paths:
                    # まだスムージング実行出来ていない場合、実行
                    exec_smooth.smooth(output_dir_path)

                    with open(os.path.join(output_dir_path, "gpu_complete"), "w") as f:
                        # 最後までいったら終了
                        f.write("gpu complete")

                    print("All prepare done!")
                else:
                    with open(os.path.join(output_dir_path, "gpu_complete"), "w") as f:
                        # 最後までいったら終了
                        f.write("gpu complete")
