from glob import glob
import os
import sys
import time

import exec_smooth
import convert_pkl2json


if __name__ == "__main__":
    output_dir_path = sys.argv[1]

    # 最後までいったら変換処理
    if not os.path.exists(os.path.join(output_dir_path, "end_of_frame")):
        print("Not end of frame yet!")
        sys.exit(1)

    time.sleep(3)

    original_json_paths = glob(os.path.join(output_dir_path, "*_original.json"))
    if not original_json_paths:
        # まだjson変換出来ていない場合、変換
        convert_pkl2json.main(output_dir_path)

    time.sleep(3)

    smooth_json_paths = glob(os.path.join(output_dir_path, "*_smooth.json"))
    if not smooth_json_paths:
        # まだスムージング実行出来ていない場合、実行
        exec_smooth.smooth(output_dir_path)

        time.sleep(3)

        with open(os.path.join(output_dir_path, "gpu_complete"), "w") as f:
            # 最後までいったら終了
            f.write("gpu complete")

    if os.path.exists(os.path.join(output_dir_path, "gpu_complete")):
        os.system(
            f"./build/mat4 -modelPath='./data/pmx/v4_trace_model.pmx' -dirPath='{output_dir_path}'"
        )

    time.sleep(3)

    if os.path.exists(os.path.join(output_dir_path, "complete")):
        print("All CPU done!")
