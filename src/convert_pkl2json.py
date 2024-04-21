import json
import sys
import joblib
import numpy as np
from phalp.utils import get_pylogger

log = get_pylogger(__name__)

def convert_pkl2json(pkl_path):
    with open(pkl_path, "rb") as f:
        lib_data = joblib.load(f)

    all_data = {}
    for k1 in sorted(lib_data.keys()):
        v1 = lib_data[k1]
        time = v1["time"]
        for tracked_id in v1["tracked_ids"]:
            if tracked_id not in all_data:
                all_data[tracked_id] = {}
            all_data[tracked_id][time] = {}
            all_data[tracked_id][time]["tracked_bbox"] = v1["tracked_bbox"][tracked_id - 1].astype(np.float64).tolist()
            all_data[tracked_id][time]["conf"] = v1["conf"][tracked_id - 1].astype(np.float64)
            all_data[tracked_id][time]["camera"] = v1["camera"][tracked_id - 1].astype(np.float64).tolist()
            all_data[tracked_id][time]["3d_joints"] = v1["3d_joints"][tracked_id - 1].astype(np.float64).tolist()
            all_data[tracked_id][time]["2d_joints"] = v1["2d_joints"][tracked_id - 1].astype(np.float64).tolist()

    for tracked_id in sorted(all_data.keys()):
        json_path = pkl_path.replace(".pkl", f"_{tracked_id:02d}.json")
        with open(json_path, "w") as f:
            json.dump(all_data[tracked_id], f, indent=4)
        log.info(f"Saved: {json_path}")

    return json_path

if __name__ == "__main__":
    convert_pkl2json(sys.argv[1])
