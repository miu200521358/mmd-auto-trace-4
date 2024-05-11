#!/bin/bash

clear

model_path="/mnt/c/MMD/mmd-auto-trace-4/data/pmx/v4_trace_model.pmx"

paths=(
    /mnt/e/MMD_E/201805_auto/misozi/ashi/input_24fps.mp4
    # "/mnt/e/MMD_E/201805_auto/01/snobbism/snobbism_23.97_1500-1550.mp4"
    # "/mnt/e/MMD_E/201805_auto/02/buster/buster_0-100.mp4"
    # "/mnt/e/MMD_E/201805_auto/01/snobbism/snobbism.mp4"
    # "/mnt/e/MMD_E/201805_auto/03/night/night.mp4"
    # "/mnt/e/MMD_E/201805_auto/02/buster/buster.mp4"
    # "/mnt/e/MMD_E/201805_auto/01/heart/heart_full5.mp4"
    # "/mnt/e/MMD_E/201805_auto/02/sugar/sugar.mp4"
    # "/mnt/e/MMD_E/201805_auto/03/ivory/ivory.mp4"
    # "/mnt/e/MMD_E/201805_auto/01/sakura/sakura.mp4"
    # "/mnt/e/MMD_E/201805_auto/02/baka/baka.mp4"
    # "/mnt/e/MMD_E/201805_auto/03/bbf/bbf.mp4"
    # "/mnt/e/MMD_E/201805_auto/04/charles/charles.mp4"
)

output_dirs=(
    "/mnt/e/MMD_E/201805_auto/misozi/ashi/input_24fps_20240511_161108/20240511_184004"
    # "/mnt/e/MMD_E/201805_auto/01/snobbism/snobbism_23_1500-1550_20240425_015744"
    # "/mnt/e/MMD_E/201805_auto/02/buster/buster_20240425_015307_冒頭2"
    # "/mnt/e/MMD_E/201805_auto/01/snobbism/snobbism_20240425_015712"
    # "/mnt/e/MMD_E/201805_auto/02/buster/buster_20240425_015307"
    # "/mnt/e/MMD_E/201805_auto/03/night/night_20240425_015629"
    # "/mnt/e/MMD_E/201805_auto/01/heart/heart_full5_20240425_015022"
    # "/mnt/e/MMD_E/201805_auto/02/sugar/sugar_20240501_054628"
    # "/mnt/e/MMD_E/201805_auto/03/ivory/ivory_20240503_105004"
    # "/mnt/e/MMD_E/201805_auto/01/sakura/sakura_20240425_170447"
    # "/mnt/e/MMD_E/201805_auto/02/baka/baka_20240425_015515"
    # "/mnt/e/MMD_E/201805_auto/03/bbf/bbf_20240503_200532"
    # "/mnt/e/MMD_E/201805_auto/04/charles/charles_20240425_020048/results"
)

for i in "${!paths[@]}"; do
    echo "=================================="
    echo "${paths[i]}"
    echo "${output_dirs[i]}"

    # # pklをコピー
    # echo "copy pkl -----------------"
    # cp ${output_dirs[i]}/*.pkl "${dir_path}"
    # # pkl2json
    # echo "pkl2json -----------------"
    # python py/convert_pkl2json.py "${dir_path}"
    # # mediapipe
    # echo "mediapipe -----------------"
    # python py/exec_mediapipe.py --video "${paths[i]}" --output_dir "${dir_path}"

    # # jsonをコピー
    # echo "copy json -----------------"
    # cp ${output_dirs[i]}/*.json "${dir_path}"

    # # 平滑化
    # echo "smooth -----------------"
    # python py/smooth.py "${dir_path}"

    # jsonをコピー
    echo "copy json -----------------"
    cp ${output_dirs[i]}/*.json "${dir_path}"

    # vmdをコピー
    echo "copy json -----------------"
    cp ${output_dirs[i]}/*.vmd "${dir_path}"

    # vmd変換処理
    echo "vmd convert -----------------"
    ./build/mat4 -modelPath=$model_path -dirPath="${output_dirs[i]}"
done
