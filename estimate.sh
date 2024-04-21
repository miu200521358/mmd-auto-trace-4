clear

names=("buster_1167-1267" "snobbism_1080-1380" "snobbism" "buster" "night")

for name in ${names[@]}; do
    echo "=================================="
    echo $name
    # 姿勢推定+追跡
    python src/demo_track.py video.source=inputs/$name.mp4 video.output_dir=outputs
done

