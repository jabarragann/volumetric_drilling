#!/usr/bin/env python3

import sys
import argparse
import json
import threading

import numpy as np
import scipy.spatial
import scipy.optimize

import rclpy
from rclpy.node import Node
from rclpy.utilities import remove_ros_args

from geometry_msgs.msg import PoseArray


# ----------------------------
# Data Collection Node
# ----------------------------
INF = float("inf")

class PoseCollector(Node):
    def __init__(self, ros_topic, expected_marker_count, filter_distance):
        super().__init__("tool_maker")

        self.rostopic = ros_topic
        self.expected_marker_count = expected_marker_count
        self.filter_distance = filter_distance
        self.records = []
        self.collecting = False
        self.reference = []

        print(f"Filter values with z component over {filter_distance: .2f}")
        self.subscription = self.create_subscription(
            PoseArray, ros_topic, self.pose_array_callback, 10
        )

    def display_sample_count(self):
        sys.stdout.write(f"\rNumber of samples collected: {len(self.records)}")
        sys.stdout.flush()

    def pose_array_callback(self, msg):
        if not self.collecting:
            return

        new_pose_array = []
        ## Filter out markers that are far away.
        for m in msg.poses:
            if m.position.z < self.filter_distance:
                new_pose_array.append(m)

        if len(new_pose_array) != self.expected_marker_count:
            print(f"error detected {len(new_pose_array)}")
            return

        record = np.array(
            [
                (pose.position.x, pose.position.y, pose.position.z)
                for pose in new_pose_array
            ]
        )

        if not self.reference:
            self.reference.extend(record)

        correspondence = scipy.spatial.distance.cdist(record, self.reference).argmin(
            axis=0
        )

        if len(np.unique(correspondence)) != len(self.reference):
            return

        ordered_record = record[correspondence]
        self.records.append(ordered_record)
        self.display_sample_count()

    def collect(self):

        input(f"Press Enter to start collection using topic {self.rostopic}")
        print("Collection started\nPress Enter to stop")

        self.display_sample_count()
        self.collecting = True

        # Spin in background thread so input() can block
        executor_thread = threading.Thread(target=rclpy.spin, args=(self,))
        executor_thread.start()

        input("")
        self.collecting = False

        self.destroy_node()

        return self.records


# ----------------------------
# Processing Functions
# ----------------------------


def principal_component_analysis(points, is_planar, planar_threshold=1e-2):

    _, sigma, Vt = np.linalg.svd(points, full_matrices=False)

    if np.linalg.det(Vt) < 0.0:
        Vt[2, :] = -Vt[2, :]

    marker_count = len(points)
    is_planar = is_planar or marker_count == 3

    if is_planar:
        print("Planar flag enabled, projecting markers onto plane...")
        Vt[2, :] = 0

    planarity = sigma[2] / sigma[1]

    if is_planar and planarity > planar_threshold:
        print("WARNING: planar flag enabled but markers do not appear planar.")
    elif not is_planar and planarity < planar_threshold:
        print("Markers appear planar. Consider using --planar flag.")

    return np.matmul(points, Vt.T)


def process_marker_records(records, is_planar):

    averaged_marker_poses = np.mean(records, axis=0)
    isocenter = np.mean(averaged_marker_poses, axis=0)

    points = averaged_marker_poses - isocenter
    points = principal_component_analysis(points, is_planar)

    return points


supported_units = {
    "mm": 0.001,
    "cm": 0.01,
    "m": 1.0,
}


def convert_units(marker_points, output_units):

    input_units = "m"

    print(f"Converting units from {input_units} to {output_units}")

    return marker_points * supported_units[input_units] / supported_units[output_units]


def write_data(points, tool_id, output_file_name):

    fiducials = [{"x": x, "y": y, "z": z} for [x, y, z] in points]
    origin = {"x": 0.0, "y": 0.0, "z": 0.0}

    data = {
        "count": len(fiducials),
        "fiducials": fiducials,
        "pivot": origin,
    }

    if tool_id is not None:
        data["id"] = tool_id

    with open(output_file_name, "w") as f:
        json.dump(data, f, indent=4, sort_keys=True)
        f.write("\n")

    print(f"Generated tool geometry file {output_file_name}")


# ----------------------------
# Main
# ----------------------------


def main():

    rclpy.init()

    argv = remove_ros_args(sys.argv)

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-t", "--topic", type=str, required=True, help="PoseArray topic"
    )

    parser.add_argument(
        "-n", "--number-of-markers", type=int, choices=range(3, 10), required=True
    )

    parser.add_argument("-o", "--output", type=str, required=True)

    parser.add_argument("-p", "--planar", action="store_true")

    parser.add_argument("-i", "--id", type=int)

    parser.add_argument(
        "-u", "--units", type=str, choices=supported_units.keys(), default="mm"
    )

    parser.add_argument(
        "-f",
        "--filter",
        type=float,
        default=INF,
        help="Filter out markers whose z value is farther than this distance (in meters)."
        + "Atracsys GUI shows values in mm.",
    )

    args = parser.parse_args(argv[1:])

    minimum_records_required = 10

    collector = PoseCollector(args.topic, args.number_of_markers, args.filter)

    records = collector.collect()

    if len(records) < minimum_records_required:
        rclpy.shutdown()
        sys.exit(f"Not enough records ({minimum_records_required} minimum)")

    points = process_marker_records(records, args.planar)
    points = convert_units(points, args.units)

    write_data(points, args.id, args.output)

    rclpy.shutdown()


if __name__ == "__main__":
    main()