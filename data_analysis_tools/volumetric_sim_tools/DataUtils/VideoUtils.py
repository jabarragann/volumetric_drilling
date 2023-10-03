import cv2
import h5py
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation as R
from tqdm import tqdm
from volumetric_sim_tools.DataUtils.Recording import Recording
from pathlib import Path

def pose_to_matrix(pose):
    quat_norm = np.linalg.norm(pose[:, 3:], axis=-1)
    assert np.all(np.isclose(quat_norm, 1.0))
    r = R.from_quat(pose[:, 3:]).as_matrix()
    t = pose[:, :3]
    tau = np.identity(4)[None].repeat(pose.shape[0], axis=0)
    tau[:, :3, :3] = r
    tau[:, :3, -1] = t

    return tau

def generate_video_from_recording(recording: Recording, output_path: Path = None):
    """Generate rgb video from a Recording object"""

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