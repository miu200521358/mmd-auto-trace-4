from datetime import datetime
from glob import glob
import os
import sys
import time

import convert_pkl2json
import exec_mediapipe
import exec_smooth
import exec_track


if __name__ == "__main__":
    video_path = sys.argv[1]

    # 出力ディレクトリを日時込みで作成する
    output_dir_path = os.path.join(
        os.path.dirname(video_path),
        f"{os.path.basename(video_path).split('.')[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    )
    os.makedirs(output_dir_path, exist_ok=True)

    cfg = exec_track.Human4DConfig()
    cfg.video.source = video_path
    cfg.video.output_dir = output_dir_path
    cfg.block_frame_num = 100000

    exec_track.main(cfg)

    time.sleep(3)

    convert_pkl2json.main(output_dir_path)

    time.sleep(3)

    exec_mediapipe.main(video_path, output_dir_path)

    time.sleep(3)

    exec_smooth.smooth(output_dir_path)

    time.sleep(3)

    os.system(
        f"./build/mat42 -modelPath='./data/pmx/v4_trace_model.pmx' -dirPath='{output_dir_path}'"
    )
