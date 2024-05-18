from datetime import datetime
# from glob import glob
import os
import sys
# import time

# import convert_pkl2json
# import exec_mediapipe
# import exec_smooth
import exec_track


if __name__ == "__main__":
    video_path = sys.argv[1]

    cfg = exec_track.Human4DConfig()
    cfg.video.source = video_path

    if len(sys.argv) > 2:
        output_dir_path = sys.argv[2]
        cfg.block_frame_num = sys.argv[3]
    else:
        # 出力ディレクトリ絶対パス未指定の場合、日時込みで作成する
        output_dir_path = os.path.join(
            os.path.dirname(video_path),
            f"{os.path.basename(video_path).split('.')[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        )
        os.makedirs(output_dir_path, exist_ok=True)
        cfg.block_frame_num = 100000

    cfg.video.output_dir = output_dir_path

    if not os.path.exists(os.path.join(cfg.video.output_dir, "end_of_frame")):
        # まだフレーム最後まで読み取り出来ていなかった場合、読み取り実行
        exec_track.main(cfg)

    if os.path.exists(os.path.join(cfg.video.output_dir, "end_of_frame")):
        print("All GPU prepare done!")
    else:
        print("Not end of frame yet!")
        sys.exit(1)
