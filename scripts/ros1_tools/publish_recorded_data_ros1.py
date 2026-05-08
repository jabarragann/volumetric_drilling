import argparse
import csv
import sys
from pathlib import Path

import rospy
from geometry_msgs.msg import PoseStamped
from pyprojroot.here import here  # type: ignore

TOPIC = "/atracsys/drill_marker/measured_cp"
DEFAULT_CSV_FILE = here() / "resources/ros2_test_assets/phantom01/atracsys_touching_surface.csv"
APPLY_PERIOD = 0.01  # 100 ms


def load_rows(path):
    rows = []
    with open(path, "r") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            if row[0].strip().lower() == "x":
                continue
            rows.append(tuple(map(float, row)))
    return rows


def parse_args():
    parser = argparse.ArgumentParser(
        description="Publish recorded atracsys poses as PoseStamped messages."
    )
    parser.add_argument(
        "--csv-file",
        type=Path,
        default=DEFAULT_CSV_FILE,
        help=f"Path to recorded CSV file. Default: {DEFAULT_CSV_FILE}",
    )
    args, _ = parser.parse_known_args()
    return args


def main():
    args = parse_args()
    csv_file: Path = args.csv_file

    if not csv_file.is_file():
        print(f"WARNING: CSV file not found: {csv_file}", file=sys.stderr)
        sys.exit(1)

    rospy.init_node("recorded_pose_publisher")
    publisher = rospy.Publisher(TOPIC, PoseStamped, queue_size=10)

    rows = load_rows(csv_file)
    rospy.loginfo(
        "Loaded %d poses from %s, publishing on %s", len(rows), csv_file, TOPIC
    )

    rate = rospy.Rate(1.0 / APPLY_PERIOD)

    for x, y, z, rx, ry, rz, rw in rows:
        if rospy.is_shutdown():
            break

        msg = PoseStamped()
        msg.header.stamp = rospy.Time.now()
        msg.header.frame_id = "atracsys"
        msg.pose.position.x = x
        msg.pose.position.y = y
        msg.pose.position.z = z
        msg.pose.orientation.x = rx
        msg.pose.orientation.y = ry
        msg.pose.orientation.z = rz
        msg.pose.orientation.w = rw

        publisher.publish(msg)
        rate.sleep()

    rospy.loginfo("Finished publishing recorded poses")


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
