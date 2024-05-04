#!/bin/bash

clear

paths=("/mnt/e/MMD_E/201805_auto/02/buster/buster_0-100.mp4")

output_dirs=(
    "/mnt/e/MMD_E/201805_auto/02/buster/buster_20240425_015307_冒頭2"
)

model_path="/mnt/c/MMD/mmd-auto-trace-4/configs/pmx/v4_trace_model.pmx"

for i in "${!paths[@]}"; do
    echo "=================================="
    echo "${paths[i]}"
    # # pkl2json
    # python py/convert_pkl2json.py "${output_dirs[i]}"
    # mediapipe
    python py/exec_mediapipe.py --video "${paths[i]}" --output_dir "${output_dirs[i]}"
    # # osx
    # python py/exec_osx.py --video "${paths[i]}" --output_dir "${output_dirs[i]}"
    # 平滑化
    python py/smooth.py "${output_dirs[i]}"
    # vmd変換処理
    # ./dist/mat4 -modelPath=$model_path -dirPath="${output_dirs[i]}"
done
