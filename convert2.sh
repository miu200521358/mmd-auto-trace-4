#!/bin/bash

clear

model_path="/mnt/c/MMD/mmd-auto-trace-4/data/pmx/v4_trace_model.pmx"

paths=(
    # "/mnt/e/MMD_E/201805_auto/01/snobbism/snobbism_23.97_1500-1550.mp4"
    # "/mnt/e/MMD_E/201805_auto/02/buster/buster_0-100.mp4"
    # "/mnt/e/MMD_E/201805_auto/01/snobbism/snobbism.mp4"
    # "/mnt/e/MMD_E/201805_auto/03/night/night.mp4"
    # "/mnt/e/MMD_E/201805_auto/02/buster/buster.mp4"
    # "/mnt/e/MMD_E/201805_auto/01/heart/heart_full5.mp4"
    # "/mnt/e/MMD_E/201805_auto/02/sugar/sugar.mp4"
    # "/mnt/e/MMD_E/201805_auto/03/ivory/ivory.mp4"
    "/mnt/e/MMD_E/201805_auto/01/sakura/sakura.mp4"
    # "/mnt/e/MMD_E/201805_auto/02/baka/baka.mp4"
    # "/mnt/e/MMD_E/201805_auto/03/bbf/bbf.mp4"
    # "/mnt/e/MMD_E/201805_auto/04/charles/charles.mp4"
)

output_dirs=(
    # "/mnt/e/MMD_E/201805_auto/01/snobbism/snobbism_23_1500-1550_20240425_015744"
    # "/mnt/e/MMD_E/201805_auto/02/buster/buster_20240425_015307_冒頭2"
    # "/mnt/e/MMD_E/201805_auto/01/snobbism/snobbism_20240425_015712"
    # "/mnt/e/MMD_E/201805_auto/02/buster/buster_20240425_015307"
    # "/mnt/e/MMD_E/201805_auto/03/night/night_20240425_015629"
    # "/mnt/e/MMD_E/201805_auto/01/heart/heart_full5_20240425_015022"
    # "/mnt/e/MMD_E/201805_auto/02/sugar/sugar_20240501_054628"
    # "/mnt/e/MMD_E/201805_auto/03/ivory/ivory_20240503_105004"
    "/mnt/e/MMD_E/201805_auto/01/sakura/sakura_20240425_170447"
    # "/mnt/e/MMD_E/201805_auto/02/baka/baka_20240425_015515"
    # "/mnt/e/MMD_E/201805_auto/03/bbf/bbf_20240503_200532"
    # "/mnt/e/MMD_E/201805_auto/04/charles/charles_20240425_020048/results"
)

for i in "${!paths[@]}"; do
    echo "=================================="
    echo "${paths[i]}"
    # 日時別のディレクトリを作成
    echo "mkdir -----------------"
    time_dir=$(date "+%Y%m%d_%H%M%S")
    path="${output_dirs[i]}/${time_dir}"
    echo "${path}"
    mkdir -p "${path}"

    # # pklをコピー
    # echo "copy pkl -----------------"
    # cp ${output_dirs[i]}/*.pkl "${path}"
    # # pkl2json
    # echo "pkl2json -----------------"
    # python py/convert_pkl2json.py "${path}"
    # # mediapipe
    # echo "mediapipe -----------------"
    # python py/exec_mediapipe.py --video "${paths[i]}" --output_dir "${path}"

    # jsonをコピー
    echo "copy json -----------------"
    cp ${output_dirs[i]}/*_mp.json "${path}"

    # 平滑化
    echo "smooth -----------------"
    python py/smooth.py "${path}"

    # # jsonをコピー
    # echo "copy json -----------------"
    # cp ${output_dirs[i]}/*_smooth.json "${path}"

    # # vmdをコピー
    # echo "copy json -----------------"
    # cp ${output_dirs[i]}/*_result.vmd "${path}"

    # vmd変換処理
    echo "vmd convert -----------------"
    ./build/mat4 -modelPath=$model_path -dirPath="${path}"
done
