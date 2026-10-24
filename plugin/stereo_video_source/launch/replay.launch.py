"""Replay a dvrk_data recording session: ROS topics (rosbag) and stereo video in sync.

    ros2 launch simulation_assisted_navigation_framework replay.launch.py session:=<session_dir>

`ros2 bag play` publishes the topics and /clock; `video_replay` serves the video
on the same unixfd socket as `video_source`, following that /clock. Control
playback with the bag player's services, e.g.
`ros2 service call /rosbag2_player/toggle_paused rosbag2_interfaces/srv/TogglePaused`.
Run the two commands in separate terminals instead to use the bag player's
keyboard controls (space: pause, arrows: rate).
"""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction
from launch_ros.actions import Node


def launch_setup(context):
    session = os.path.expanduser(context.launch_configurations["session"])
    get = lambda name: context.launch_configurations[name]

    bag_cmd = ["ros2", "bag", "play", os.path.join(session, "rosbag"),
               "--clock", get("clock_hz"), "--rate", get("rate"), "--start-offset", get("start_offset")]
    if get("loop").lower() in ("true", "1"):
        bag_cmd.append("--loop")

    video_args = ["--session", session, "--name", get("name"), "--offset-ms", get("offset_ms")]
    if get("stream"):
        video_args += ["--stream", get("stream")]

    return [
        Node(package="simulation_assisted_navigation_framework", executable="video_replay",
             arguments=video_args, output="screen"),
        ExecuteProcess(cmd=bag_cmd, output="screen"),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("session", description="dvrk_data session directory (contains index.json and rosbag/)"),
        DeclareLaunchArgument("stream", default_value="", description="Video stream (default: first in index.json)"),
        DeclareLaunchArgument("name", default_value="camera", description="Stereo video source name"),
        DeclareLaunchArgument("offset_ms", default_value="0", description="Video shift against the bag (positive: later)"),
        DeclareLaunchArgument("rate", default_value="1.0", description="Playback rate"),
        DeclareLaunchArgument("start_offset", default_value="0.0", description="Start this many seconds into the bag"),
        DeclareLaunchArgument("loop", default_value="false", description="Loop playback"),
        DeclareLaunchArgument("clock_hz", default_value="100", description="/clock rate; bounds video sync error to 1/clock_hz"),
        OpaqueFunction(function=launch_setup),
    ])
