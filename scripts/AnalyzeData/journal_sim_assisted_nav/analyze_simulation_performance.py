from pathlib import Path
import rosbag
import argparse

def extract_messages(bag_path: str, topic_name: str, output_file: str = None):
    bag_path = Path(bag_path)
    if not bag_path.exists():
        raise FileNotFoundError(f"Bag file {bag_path} does not exist.")

    messages = []
    with rosbag.Bag(str(bag_path), "r") as bag:
        for topic, msg, t in bag.read_messages(topics=[topic_name]):
            messages.append(msg)
            print(f"Time: {t.to_sec()} | graphics: {msg.graphics_loop_freq} | dynamic: {msg.dynamic_loop_freq}")

    if output_file:
        with open(output_file, "w") as f:
            f.write("time,graphics,dynamic\n")
            for msg in messages:
                f.write(f"{msg.header.stamp.to_sec()},{msg.graphics_loop_freq},{msg.dynamic_loop_freq}\n")
        print(f"Saved {len(messages)} messages to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Extract messages from a ROS1 bag topic.")
    parser.add_argument("--bag_path", required=True, help="Path to the .bag file")
    parser.add_argument("--output_file", help="File to save extracted messages (optional)")
    args = parser.parse_args()

    topic_name = "/ambf/env/World/State" 

    extract_messages(args.bag_path, topic_name, args.output_file)

if __name__ == "__main__":
    main()