#!/bin/bash

clear

names=("buster" "night" "snobbism")

for name in ${names[@]}; do
    echo "=================================="
    echo $name
    # 姿勢推定+追跡+json出力
    python src/exec_track.py video.source=inputs/$name.mp4 video.output_dir=outputs video.end_frame=99999
done

