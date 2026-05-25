import time
import csv
import re
import yaml
from pathlib import Path
from ambf_client import Client # type: ignore
from geometry_msgs.msg import Pose
import numpy as np
from scipy.spatial.transform import Rotation as R
from pyprojroot.here import here # type: ignore
from tqdm import tqdm
import argparse
import rclpy


""" 
Run env with saved assets with cmd below.
Note: As this script replaces the functionality of the tf plugin, do not include
 --tf_list argument in the launch command.

```
ambf_simulator --launch_file launch.yaml \
               -l 8,13 --mute true --nt 1
```
"""

DEFAULT_CSV_FILE = (
    here() / "resources/ros2_test_assets/phantom01/motions/atracsys_touching_surface.csv"
)  
DEFAULT_TF_CONFIG = "resources/ros2_test_assets/phantom01/motions/tf_config.yaml"

# CSV_FILE ="/home/juan95/research/discovery_grant/saint_2026/experiments/drilling-pilot-2026-03-13/recordings/drilling_02.csv" 
# DEFAULT_CSV_FILE = "/home/juan95/research/discovery_grant/saint_2026/experiments/drilling-pilot-2026-03-13/recordings/drilling_02.csv"

APPLY_PERIOD = 0.01  # 100 ms

def pose_to_matrix(pose: Pose) -> np.ndarray:
    T = np.eye(4)
    T[:3, :3] = R.from_quat(
        [
            pose.orientation.x,
            pose.orientation.y,
            pose.orientation.z,
            pose.orientation.w,
        ]
    ).as_matrix()
    T[:3, 3] = [pose.position.x, pose.position.y, pose.position.z]
    return T


def matrix_to_pose(T: np.ndarray) -> Pose:
    pose = Pose()
    pose.position.x = float(T[0, 3])
    pose.position.y = float(T[1, 3])
    pose.position.z = float(T[2, 3])

    q = R.from_matrix(T[:3, :3]).as_quat()  # [x, y, z, w]
    pose.orientation.x = float(q[0])
    pose.orientation.y = float(q[1])
    pose.orientation.z = float(q[2])
    pose.orientation.w = float(q[3])
    return pose

def load_tf_config(tf_config_path):
    path = Path(tf_config_path)
    if not path.is_file():
        raise FileNotFoundError(f"tf_config not found: {path}")

    with open(path, "r") as f:
        cfg = yaml.safe_load(f)

    pivot_block = cfg.get("TF marker_body-drill_tip")
    if pivot_block is None:
        raise KeyError("Missing 'TF marker_body-drill_tip' in tf_config")
    pivot_tf = pivot_block["transformation"]
    pos = pivot_tf["position"]
    rpy = pivot_tf["orientation"]

    marker_T_tip = np.eye(4)
    marker_T_tip[:3, :3] = R.from_euler(
        "xyz", [float(rpy["r"]), float(rpy["p"]), float(rpy["y"])]
    ).as_matrix()
    marker_T_tip[:3, 3] = [float(pos["x"]), float(pos["y"]), float(pos["z"])]

    drill_block = cfg.get("TF drill_tip-drill_body")
    if drill_block is None:
        raise KeyError("Missing 'TF drill_tip-drill_body' in tf_config")
    drill_body_name = drill_block["child"]

    match = re.match(r"drill_body_(\d+)mm$", drill_body_name)
    if not match:
        raise ValueError(
            f"Unexpected drill body name '{drill_body_name}'; "
            "expected pattern 'drill_body_<N>mm'"
        )
    drill_size = int(match.group(1))

    return marker_T_tip, drill_body_name, drill_size


def main(args):
    marker_T_tip, drill_body_name, drill_size = load_tf_config(args.tf_config)
    print(f"Loaded tf_config: drill={drill_body_name} (size={drill_size}mm)")

    client = Client("client")
    client.connect()

    print("Connected to AMBF")

    drill_body_handle = client.get_obj_handle(drill_body_name)
    drill_marker_handle = client.get_obj_handle("marker")
    drill_tip_handle = client.get_obj_handle("drill_tip")

    if drill_marker_handle is None or drill_tip_handle is None:
        raise RuntimeError("Could not retrieve drill handles")

    print("Handles acquired")

    print(marker_T_tip)

    ## Body drill - rotate 180 degrees about y (flip X and Z)
    tip_T_body = np.identity(4)
    tip_T_body[0, 0] = -1.0
    tip_T_body[2, 2] = -1.0

    # -------------------------
    # Read CSV and apply poses
    # -------------------------
    with open(args.csv_file, "r") as f:
        rows = [
            row for row in csv.reader(f)
            if row and row[0].strip().lower() != "x"
        ]

    print(f"Loaded {len(rows)} pose entries from {args.csv_file}")

    for row in tqdm(rows, desc="Applying poses", unit="pose"):
        x, y, z, rx, ry, rz, rw = map(float, row)

        body_pose = Pose()

        # Position
        body_pose.position.x = x
        body_pose.position.y = y
        body_pose.position.z = z

        # Orientation (quaternion)
        body_pose.orientation.x = rx
        body_pose.orientation.y = ry
        body_pose.orientation.z = rz
        body_pose.orientation.w = rw

        world_T_marker = pose_to_matrix(body_pose)
        world_T_tip = world_T_marker @ marker_T_tip
        world_T_body = world_T_tip @ tip_T_body

        tip_final_pose = matrix_to_pose(world_T_tip)
        body_final_pose = matrix_to_pose(world_T_body)

        # Apply to both handles
        drill_body_handle.set_pose(body_final_pose)
        drill_tip_handle.set_pose(tip_final_pose)
        drill_marker_handle.set_pose(body_pose)

        time.sleep(APPLY_PERIOD)

    client.clean_up()
    rclpy.shutdown()
    print("Finished applying poses")

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Control the drill in AMBF via Atracsys pose stream.")
    parser.add_argument(
        "--tf-config",
        type=str,
        default=DEFAULT_TF_CONFIG,
        help="Path to tf_config.yaml. Pivot transform and drill body are read from it.",
    )
    parser.add_argument(
        "--csv-file",
        type=str,
        default=DEFAULT_CSV_FILE,
        help="Path to CSV with marker poses (x,y,z,rx,ry,rz,rw per row).",
    )
    args, unknown = parser.parse_known_args()

    main(args)
