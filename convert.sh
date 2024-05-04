#!/bin/bash

clear

paths=("/mnt/e/MMD_E/201805_auto/02/buster/buster.mp4")

output_dirs=(
    "/mnt/e/MMD_E/201805_auto/02/buster/buster_20240425_015307"
)

model_path="/mnt/c/MMD/mmd-auto-trace-4/configs/pmx/v4_trace_model.pmx"

for i in "${!paths[@]}"; do
    echo "=================================="
    echo "${paths[i]}"
    # mediapipe
    python py/exec_mediapipe.py --video "${paths[i]}" --output_dir "${output_dirs[i]}"
    # 平滑化
    python py/smooth.py "${output_dirs[i]}"
    # vmd変換処理
    ./dist/mat4 -modelPath=$model_path -dirPath="${output_dirs[i]}"
done
