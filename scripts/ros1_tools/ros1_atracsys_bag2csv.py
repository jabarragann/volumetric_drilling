
#!/usr/bin/env python3

import rosbag
import csv
import sys
from geometry_msgs.msg import PoseStamped

def bag_to_csv(bag_path, output_csv):
    with rosbag.Bag(bag_path, 'r') as bag, open(output_csv, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)

        # Write header
        writer.writerow(['x', 'y', 'z', 'rx', 'ry', 'rz', 'rw'])

        for topic, msg, t in bag.read_messages(topics=['/atracsys/drill_marker/measured_cp']):
            pose = msg.pose

            row = [
                pose.position.x,
                pose.position.y,
                pose.position.z,
                pose.orientation.x,
                pose.orientation.y,
                pose.orientation.z,
                pose.orientation.w
            ]

            writer.writerow(row)

    print(f"Saved poses to {output_csv}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 bag_to_csv.py input.bag output.csv")
        sys.exit(1)

    bag_to_csv(sys.argv[1], sys.argv[2])
