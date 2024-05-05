#!/bin/bash

clear

paths=(
    "/mnt/e/MMD_E/201805_auto/02/buster/buster.mp4"
    "/mnt/e/MMD_E/201805_auto/01/snobbism/snobbism.mp4"
    "/mnt/e/MMD_E/201805_auto/01/heart/heart_full5.mp4"
    "/mnt/e/MMD_E/201805_auto/02/sugar/sugar.mp4"
    "/mnt/e/MMD_E/201805_auto/03/bbf/bbf.mp4"
    "/mnt/e/MMD_E/201805_auto/03/night/night.mp4"
    "/mnt/e/MMD_E/201805_auto/04/charles/charles.mp4"
)

output_dirs=(
    "/mnt/e/MMD_E/201805_auto/02/buster/buster_20240425_015307"
    "/mnt/e/MMD_E/201805_auto/01/snobbism/snobbism_20240425_015712"
    "/mnt/e/MMD_E/201805_auto/01/heart/heart_full5_20240425_015022"
    "/mnt/e/MMD_E/201805_auto/02/sugar/sugar_20240501_054628/results"
    "/mnt/e/MMD_E/201805_auto/03/bbf/bbf_20240503_200532/results"
    "/mnt/e/MMD_E/201805_auto/03/night/night_20240425_015629"
    "/mnt/e/MMD_E/201805_auto/04/charles/charles_20240425_020048/results"
)

model_path="/mnt/c/MMD/mmd-auto-trace-4/configs/pmx/v4_trace_model.pmx"

for i in "${!paths[@]}"; do
    echo "=================================="
    echo "${paths[i]}"
    # # pkl2json
    # echo "pkl2json -----------------"
    # python py/convert_pkl2json.py "${output_dirs[i]}"
    # # mediapipe
    # echo "mediapipe -----------------"
    # python py/exec_mediapipe.py --video "${paths[i]}" --output_dir "${output_dirs[i]}"
    # # osx
    # python py/exec_osx.py --video "${paths[i]}" --output_dir "${output_dirs[i]}"
    # 平滑化
    echo "smooth -----------------"
    python py/smooth.py "${output_dirs[i]}"
    # vmd変換処理
    echo "vmd convert -----------------"
    ./dist/mat4 -modelPath=$model_path -dirPath="${output_dirs[i]}"
done