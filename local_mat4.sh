#!/bin/bash

clear

paths=(
    /mnt/e/MMD_E/201805_auto/misozi/ashi/input_resize_24fps.mp4
    # "/mnt/e/MMD_E/201805_auto/01/snobbism/snobbism_23.97_1500-1550.mp4"
    # "/mnt/e/MMD_E/201805_auto/02/buster/buster_0-100.mp4"
    # "/mnt/e/MMD_E/201805_auto/01/sakura/sakura_7000-.mp4"
    # "/mnt/e/MMD_E/201805_auto/01/sakura/sakura.mp4"
    # "/mnt/e/MMD_E/201805_auto/01/snobbism/snobbism.mp4"
    # "/mnt/e/MMD_E/201805_auto/03/night/night.mp4"
    # "/mnt/e/MMD_E/201805_auto/02/buster/buster.mp4"
    # "/mnt/e/MMD_E/201805_auto/01/heart/heart_full5.mp4"
    # "/mnt/e/MMD_E/201805_auto/03/ivory/ivory.mp4"
    # "/mnt/e/MMD_E/201805_auto/02/sugar/sugar.mp4"
    # "/mnt/e/MMD_E/201805_auto/02/baka/baka.mp4"
    # "/mnt/e/MMD_E/201805_auto/03/bbf/bbf.mp4"
    # "/mnt/e/MMD_E/201805_auto/04/charles/charles.mp4"
)

for path in ${paths[@]}; do
    echo "=================================="
    echo $path
    # 姿勢推定+追跡
    python py/main_local.py $path
done

