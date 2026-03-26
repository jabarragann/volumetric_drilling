from __future__ import annotations
from typing import Any
import h5py
from tap import Tap
import rclpy
from rclpy.node import Node
import numpy as np
import os
import time
from pathlib import Path
from rclpy.time import Time

try:
    from volumetric_drilling_msgs.msg import Voxels
except ImportError:
    print(
        "\nvolumetric_drilling_msgs.msg: cannot open shared message file. "
        + "Please source <volumetric_plugin_path>/build/devel/setup.bash \n"
    )

collisions: dict[str, list[Any]] = {}
collisions["voxel_time_stamp"] = []
collisions["voxel_removed"] = []
collisions["voxel_color"] = []


def init_hdf5(args: CliArgs) -> Any:

    # Create hdf5 file with date
    if not Path(args.output_dir).exists():
        os.makedirs(args.output_dir)
    time_str = time.strftime("%Y%m%d_%H%M%S")

    file = h5py.File(args.output_dir + "/" + time_str + ".hdf5", "w") # type: ignore

    metadata = file.create_group("metadata")
    metadata.create_dataset(
        "README",
        data="All position information is in meters unless specified otherwise. \n"
        "Quaternion is a list in the order of [qx, qy, qz, qw]. \n"
        "Poses are defined to be T_world_obj. \n"
        "Depth in CV convention (corrected by extrinsic, T_cv_ambf). \n",
    )

    file.create_group("voxels_removed")

    return file


def write_to_hdf5(f: Any) -> None:

    ########################
    #### Save voxels removed
    voxel_idx = []
    voxel_color = []

    try:
        assert len(collisions["voxel_color"]) == len(collisions["voxel_removed"]), (
            "dimension errors"
        )
        assert len(collisions["voxel_color"]) == len(collisions["voxel_time_stamp"]), (
            "dimension errors"
        )
    except:
        print(f"voxel_color len: {len(collisions['voxel_color'])}")
        print(f"voxel_removed len: {len(collisions['voxel_removed'])}")
        print(f"voxel_time_stamp len: {len(collisions['voxel_time_stamp'])}")
        raise Exception()

    # Add ts index column to voxels_idx and voxels color
    for idx in range(len(collisions["voxel_time_stamp"])):
        num_of_removed = collisions["voxel_removed"][idx].shape[0]

        if num_of_removed > 0:
            idx_column = np.ones((num_of_removed, 1)) * idx
            voxel_idx.append(np.hstack((idx_column, collisions["voxel_removed"][idx])))
            voxel_color.append(np.hstack((idx_column, collisions["voxel_color"][idx])))

    # Write data to hdf5
    try:
        voxel_idx = np.vstack(voxel_idx)
        voxel_color = np.vstack(voxel_color)
        voxel_data = dict(
            voxel_time_stamp=collisions["voxel_time_stamp"],
            voxel_removed=voxel_idx,
            voxel_color=voxel_color,
        )
        for key, value in voxel_data.items():
            print(f"key {key}")
            f["voxels_removed"].create_dataset(
                key, data=value, compression="gzip"
            )  # write to disk
            print(f"key {key} shape {f['voxels_removed'][key].shape}")
            # Reset collisions list -  empty memory
            collisions[key] = []
    except Exception as e:
        print("INFO! No voxels removed in this batch since EXCEPTION:", str(e))

    f.close()


def rm_vox_callback(rm_vox_msg: Voxels):

    # Convert voxel removed and voxel color to numpy
    voxels_colors: list[list[float]] = []
    voxels_indices: list[list[int]] = []
    for idx in range(len(rm_vox_msg.indices)): # type: ignore
        vcolor = rm_vox_msg.colors[idx] # type: ignore
        vidx = rm_vox_msg.indices[idx] #type: ignore

        voxel_color: list[float] = [vcolor.r, vcolor.g, vcolor.b, vcolor.a] # type: ignore
        voxel_idx: list[int] = [vidx.x, vidx.y, vidx.z] # type: ignore

        voxels_colors.append(voxel_color)
        voxels_indices.append(voxel_idx)

    voxels_colors_np = np.array(voxels_colors) * 255
    voxels_indices_np = np.array(voxels_indices)

    time_stamp = Time.from_msg(rm_vox_msg.header.stamp).seconds_nanoseconds()[0] + \
                 Time.from_msg(rm_vox_msg.header.stamp).seconds_nanoseconds()[1] * 1e-9 # type: ignore

    collisions["voxel_time_stamp"].append(time_stamp)
    collisions["voxel_removed"].append(voxels_indices_np)
    collisions["voxel_color"].append(voxels_colors_np)

    print(len(collisions["voxel_time_stamp"]))


def setup_subscriber(args: CliArgs, node: Node):
    print(node.get_topic_names_and_types())
    active_topics = [topic[0] for topic in node.get_topic_names_and_types()]
    subscribers: list[Any] = []
    topics: list[str] = []

    if active_topics == ["/parameter_events", "/rosout"]:
        print("CRITICAL! Launch simulation before recording!")
        exit()

    if args.remove_voxels_topic in active_topics:
        remove_voxels_sub = node.create_subscription(  # type: ignore
            Voxels, # type: ignore
            args.remove_voxels_topic,
            rm_vox_callback, # type: ignore
            10,
        ) 
        subscribers.append(remove_voxels_sub)
        topics.append(args.remove_voxels_topic)

    else:
        print("CRITICAL! Failed to subscribe to " + args.remove_voxels_topic)
        exit()

    print("\n".join(["Subscribed to the following topics:"] + topics))

    return subscribers


class CliArgs(Tap):
    output_dir: str = "temp/ros2/"
    remove_voxels_topic: str = "/ambf/env/plugin/volumetric_drilling/voxels_removed"



def main(args: CliArgs):

    rclpy.init()
    node = Node("data_recorder")
    rclpy.spin_once(node, timeout_sec=0.5)

    _ = setup_subscriber(args, node)  # type: ignore
    file = init_hdf5(args) # type: ignore

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("Terminating due to keyboard interrupt.")
       
        write_to_hdf5(file) # type: ignore
        print("Written to hdf5 file")
    finally:
        if rclpy.ok():
            rclpy.shutdown()

        node.destroy_node()

if __name__ == "__main__":
    args = CliArgs().parse_args()
    main(args)
