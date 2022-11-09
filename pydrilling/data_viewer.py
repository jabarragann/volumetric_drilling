from argparse import ArgumentParser
import cv2
import h5py
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation as R
from tqdm import tqdm
from pydrilling.Recording import Recording

from pydrilling.data_validation import pose_to_matrix
from pathlib import Path


def generate_video_from_recording(recording: Recording, output_path: Path = None):

    # Create video
    cmap = plt.get_cmap()

    if output_path is None:
        output_path = recording.data_dir / "full_video.avi"
    output_path = str(output_path)  # Opencv does not like Pathlib paths

    # Write video
    out = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc("M", "J", "P", "G"), 30, (640, 480))
    for l_img, r_img, depth, segm in tqdm(
        recording.img_data_iterator(), total=recording.count_frames()
    ):
        out.write(l_img)

    out.release()

# TODO: Change generate_video function to work with the recording class
# Add an argument that allows you to select the hdf5 that you want a use. Add an option to process all the files
# Do the same for the function above
def generate_video(hdf5_path: Path, output_path: Path = None):
    # Read HDF5 data
    file = h5py.File(hdf5_path, "r")
    l_img = file["data"]["l_img"]
    r_img = file["data"]["r_img"]
    depth = file["data"]["depth"]
    segm = file["data"]["segm"]

    # K = file["metadata"]["camera_intrinsic"]
    # extrinsic = file["metadata"]["camera_extrinsic"]

    # pose_cam = pose_to_matrix(file["data"]["pose_main_camera"])
    # pose_cam = np.matmul(
    #     pose_cam, np.linalg.inv(extrinsic)[None]
    # )  # update pose so world directly maps to CV
    # pose_drill = pose_to_matrix(file["data"]["pose_mastoidectomy_drill"])

    # Create video
    cmap = plt.get_cmap()

    if output_path is None:
        output_path = hdf5_path.with_suffix(".avi")

    output_path = str(output_path)  # Opencv does not like Pathlib paths
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
        "--path_list",
        type=str,
        default=[],
        nargs="+",
        help="List of directories to process. Each directory contains the h5 files a single experiment.",
    )
    args = parser.parse_args()

    for path in args.path_list:
        try:
            print(f"processing {path}")
            root = Path(path)
            recording = Recording(
                root, participant_id="None", anatomy="None", guidance_modality="None"
            )
            generate_video_from_recording(recording)
        except Exception as e:
            print(f"error with {path}")
            print(e)

    # parser = ArgumentParser()
    # parser.add_argument(
    #     "--file",
    #     type=str,
    #     default=None,
    #     action="store",
    #     help="Iterate through all data frame by frame",
    # )
    # parser.add_argument(
    #     "--idx", nargs="+", default=None, action="store", help="View the data of provided index"
    # )
    # parser.add_argument(
    #     "--generate_video", action="store_true", help="create a video of recorded data"
    # )
    # args = parser.parse_args()

    # file = Path(args.file)
    # if file.exists():
    #     generate_video(file)
    # else:
    #     print(f"{file} does not exists")
