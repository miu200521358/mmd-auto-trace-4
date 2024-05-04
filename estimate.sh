#!/bin/bash

clear

paths=("/mnt/e/MMD_E/201805_auto/01/cat/cat_30fps.mp4"
        "/mnt/e/MMD_E/201805_auto/02/seven/seven.mp4"
        "/mnt/e/MMD_E/201805_auto/03/wave/wave_full.mp4"
        "/mnt/e/MMD_E/201805_auto/04/yoiyoi/yoiyoi.mp4")

for path in ${paths[@]}; do
    echo "=================================="
    echo $path
    # 姿勢推定+追跡+json出力
    python py/exec_track.py video.source=$path
done

