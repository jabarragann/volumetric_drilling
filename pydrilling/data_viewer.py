from argparse import ArgumentParser
import cv2
import h5py
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation as R
from tqdm import tqdm

from pydrilling.data_validation import pose_to_matrix
from pathlib import Path


def generate_video(hdf5_path: Path, output_path: Path = None):
    # Read HDF5 data
    file = h5py.File(args.file, "r")
    l_img = file["data"]["l_img"]
    r_img = file["data"]["r_img"]
    depth = file["data"]["depth"]
    segm = file["data"]["segm"]
    K = file["metadata"]["camera_intrinsic"]
    extrinsic = file["metadata"]["camera_extrinsic"]

    pose_cam = pose_to_matrix(file["data"]["pose_main_camera"])
    pose_cam = np.matmul(
        pose_cam, np.linalg.inv(extrinsic)[None]
    )  # update pose so world directly maps to CV
    pose_drill = pose_to_matrix(file["data"]["pose_mastoidectomy_drill"])

    # Create video
    cmap = plt.get_cmap()

    if output_path is None:
        output_path = hdf5_path.with_suffix(".avi")

    output_path = str(output_path)  # Opencv does not like Pathlib
    out = cv2.VideoWriter(
        output_path, cv2.VideoWriter_fourcc("M", "J", "P", "G"), 30, (640 * 2, 480 * 2)
    )

    for i in tqdm(range(l_img.shape[0])):
        d = (cmap(depth[i])[..., :3] * 255).astype(np.uint8)
        rgb = np.concatenate([l_img[i], r_img[i]], axis=1)
        depth_segm = np.concatenate([d, segm[i]], axis=1)
        frame = np.concatenate([rgb, depth_segm], axis=0)
        out.write(frame)

    out.release()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        action="store",
        help="Iterate through all data frame by frame",
    )
    parser.add_argument(
        "--idx", nargs="+", default=None, action="store", help="View the data of provided index"
    )
    parser.add_argument(
        "--generate_video", action="store_true", help="create a video of recorded data"
    )
    args = parser.parse_args()

    file = Path(args.file)
    if file.exists():
        generate_video(file)
    else:
        print(f"{file} does not exists")
