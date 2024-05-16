#!/bin/bash

clear

model_path="/mnt/c/MMD/mmd-auto-trace-4/data/pmx/v4_trace_model.pmx"

output_dirs=(
    # "/mnt/e/MMD_E/201805_auto/misozi/ashi/input_24fps_20240511_161108/20240511_184004"
    # "/mnt/e/MMD_E/201805_auto/01/snobbism/snobbism_23_1500-1550_20240425_015744"
    "/mnt/e/MMD_E/201805_auto/02/buster/buster_20240511_210727"
    # "/mnt/e/MMD_E/201805_auto/01/snobbism/snobbism_20240425_015712"
    # "/mnt/e/MMD_E/201805_auto/02/buster/buster_20240425_015307"
    # "/mnt/e/MMD_E/201805_auto/03/night/night_20240425_015629"
    # "/mnt/e/MMD_E/201805_auto/01/heart/heart_full5_20240425_015022"
    # "/mnt/e/MMD_E/201805_auto/02/sugar/sugar_20240501_054628"
    # "/mnt/e/MMD_E/201805_auto/03/ivory/ivory_20240503_105004"
    # "/mnt/e/MMD_E/201805_auto/01/sakura/sakura_20240512_015543"
    # "/mnt/e/MMD_E/201805_auto/02/baka/baka_20240425_015515"
    # "/mnt/e/MMD_E/201805_auto/03/bbf/bbf_20240503_200532"
    # "/mnt/e/MMD_E/201805_auto/04/charles/charles_20240425_020048/results"
)

for i in "${!output_dirs[@]}"; do
    echo "=================================="

    # 日時別のディレクトリを作成
    echo "mkdir -----------------"
    time_dir=$(date "+%Y%m%d_%H%M%S")
    dir_path="${output_dirs[i]}/${time_dir}"
    echo "${dir_path}"
    mkdir -p "${dir_path}"

    # pklをコピー
    echo "copy pkl -----------------"
    cp ${output_dirs[i]}/*.pkl "${dir_path}"
    cp ${output_dirs[i]}/end_of_frame "${dir_path}"

    echo "convert -----------------"
    python py/exec_cpu.py "${dir_path}"

done
