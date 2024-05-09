echo "4D-Humans -----------------------------"
python py/exec_track.py video.source "$input_video_path" video.output_dir "$process_dir_path"

echo "pkl to json -----------------------------"
python py/convert_pkl2json.py "$result_dir_name"

echo "mediapipe -----------------------------"
python py/exec_mediapipe.py --video "$input_video_path" --output_dir "$result_dir_name"

echo "smooth -----------------------------"
python py/smooth.py "$result_dir_name"

echo "convert motion -----------------------------"
./build/mat4 -modelPath="$model_path" -dirPath="$result_dir_name"
