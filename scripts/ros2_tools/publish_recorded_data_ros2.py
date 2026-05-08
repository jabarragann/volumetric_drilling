import argparse
import csv
import sys
from pathlib import Path

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from pyprojroot.here import here  # type: ignore

TOPIC = "/atracsys/drill_marker/measured_cp"
DEFAULT_CSV_FILE = here() / "resources/ros2_test_assets/phantom01/atracsys_touching_surface.csv"
APPLY_PERIOD = 0.01  # 100 ms


class RecordedPosePublisher(Node):
    def __init__(self, csv_file: Path):
        super().__init__("recorded_pose_publisher")
        self.publisher = self.create_publisher(PoseStamped, TOPIC, 10)
        self.rows = self._load_rows(csv_file)
        self.index = 0
        self.timer = self.create_timer(APPLY_PERIOD, self._on_timer)
        self.get_logger().info(
            f"Loaded {len(self.rows)} poses from {csv_file}, publishing on {TOPIC}"
        )

    @staticmethod
    def _load_rows(path):
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

    def _on_timer(self):
        if self.index >= len(self.rows):
            self.get_logger().info("Finished publishing recorded poses")
            self.timer.cancel()
            rclpy.shutdown()
            return

        x, y, z, rx, ry, rz, rw = self.rows[self.index]
        self.index += 1

        msg = PoseStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "atracsys"
        msg.pose.position.x = x
        msg.pose.position.y = y
        msg.pose.position.z = z
        msg.pose.orientation.x = rx
        msg.pose.orientation.y = ry
        msg.pose.orientation.z = rz
        msg.pose.orientation.w = rw

        self.publisher.publish(msg)


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

    rclpy.init()
    node = RecordedPosePublisher(csv_file)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == "__main__":
    main()
