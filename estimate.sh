#!/bin/bash

clear

names=("snobbism" "baka" "heart" "buraiB" "buraiL")

for name in ${names[@]}; do
    echo "=================================="
    echo $name
    # 姿勢推定+追跡+json出力
    python src/exec_track.py video.source=inputs/$name.mp4 video.output_dir=outputs
done

