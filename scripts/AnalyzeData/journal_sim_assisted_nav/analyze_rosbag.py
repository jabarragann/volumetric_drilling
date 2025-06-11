from pathlib import Path
from typing import List, Tuple
import rosbag
import matplotlib.pyplot as plt
import argparse
import rospy
from datetime import datetime


def extract_valid_intervals(
    timestamps: List[float], max_gap: float = 0.2
) -> List[Tuple[float, float]]:
    valid_intervals = []
    start_time = timestamps[0]

    for i in range(1, len(timestamps)):
        delta = timestamps[i] - timestamps[i - 1]

        if delta > max_gap:
            end_time = timestamps[i - 1]
            valid_intervals.append((start_time, end_time))
            start_time = timestamps[i]

    # Handle final segment
    if timestamps[-1] - start_time <= max_gap:
        valid_intervals.append((start_time, timestamps[-1]))

    return valid_intervals


def write_intervals_to_ltxt(intervals: List[Tuple[float, float]], output_file: Path):
    with open(output_file, "w") as f:
        for start, end in intervals:
            f.write(f"{start:.6f} {end:.6f}\n")

    print(f"Written {len(intervals)} valid intervals to {output_file}")


def read_topic_timestamps(bag_path, topic_name):
    timestamps = []

    print(f"Opening bag file: {bag_path}")
    with rosbag.Bag(bag_path, "r") as bag:
        for topic, msg, t in bag.read_messages(topics=[topic_name]):
            timestamps.append(t.to_sec())  # Convert to float seconds

    return timestamps


def timestamps_analysis(timestamps, topic_name, max_delta: float, valid_intervals_path: Path):
    if not timestamps:
        print("No messages found for the given topic.")

        return

    # Calculate time deltas
    times = [t - timestamps[0] for t in timestamps]
    deltas = [j - i for i, j in zip(times[:-1], times[1:])]

    print(timestamps[0], timestamps[-1])
    print(times[0], times[-1])
    print(f"Total time span: {times[-1] - times[0]} seconds")

    # Calculate valid intervals
    valid_intervals = extract_valid_intervals(timestamps, max_gap=max_delta)
    write_intervals_to_ltxt(valid_intervals, valid_intervals_path)

    # Plotting
    plt.figure(figsize=(12, 6))

    plt.subplot(2, 1, 1)
    plt.plot(times, marker="o", linestyle="-", markersize=2)
    plt.title(f"Message Timestamps for Topic: {topic_name}")
    plt.ylabel("Time [s] since first msg")

    plt.subplot(2, 1, 2)
    plt.plot(deltas, marker="x", linestyle="-", color="red")
    plt.title("Time Differences Between Messages")
    plt.xlabel("Message Index")
    plt.ylabel("Time delta [s]")

    plt.tight_layout()
    plt.show()


def main():
    parser = argparse.ArgumentParser(
        description="Plot timestamps from a ROS1 bag topic."
    )
    parser.add_argument("--bag_path", help="Path to the .bag file")
    parser.add_argument("--topic_name", help="Topic to analyze")
    parser.add_argument(
        "--valid_delta",
        type=float,
        default=0.2,
        help="Max gap between atracsys messages to consider valid intervals",
    )
    args = parser.parse_args()

    bag_path = Path(args.bag_path)
    if not bag_path.exists():
        raise FileNotFoundError(f"Bag file {bag_path} does not exist.")

    valid_intervals_path = bag_path.parent / f"valid_intervals_{args.valid_delta}.txt"

    timestamps = read_topic_timestamps(args.bag_path, args.topic_name)
    timestamps_analysis(timestamps, args.topic_name, args.valid_delta, valid_intervals_path)


if __name__ == "__main__":
    main()
