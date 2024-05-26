from glob import glob
import os
import sys
import time

import exec_smooth
import exec_pkl2json


if __name__ == "__main__":
    output_dir_path = sys.argv[1]
    limit_minutes = 24 * 60 * 60

    exec_pkl2json.main(output_dir_path)
    exec_smooth.smooth(output_dir_path, limit_minutes)

    os.system(
        f"./build/mat4 -modelPath='./data/pmx/v4_trace_model.pmx' -dirPath='{output_dir_path}' -limitMinutes={limit_minutes}"
    )

    time.sleep(3)

    print("All CPU done!")
