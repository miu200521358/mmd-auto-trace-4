#!/bin/bash

clear

paths=("/mnt/e/MMD_E/201805_auto/02/buster/buster_0-100.mp4")

for path in ${paths[@]}; do
    echo "=================================="
    echo $path
    # 姿勢推定+追跡
    python py/exec_track.py video.source=$path
done

