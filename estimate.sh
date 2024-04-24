#!/bin/bash

clear

paths=("/mnt/e/MMD_E/201805_auto/03/bbf/bbf.mp4" "/mnt/e/MMD_E/201805_auto/04/charles/charles.mp4")

for path in ${paths[@]}; do
    echo "=================================="
    echo $path
    # 姿勢推定+追跡+json出力
    python py/exec_track.py video.source=$path video.output_dir=outputs
done

