import h5py
import numpy as np

np.set_printoptions(precision=3)


def get_all(name):
    if "voxels" in name:
        print(name)


def main(f):
    f.visit(get_all)

    ts_dataset = f["voxels_removed/time_stamp"]
    voxel_color_dataset = f["voxels_removed/voxel_color"]

    print(ts_dataset.shape)
    print(voxel_color_dataset.shape)

    for idx in range(5):
        print(f"{idx}-{ts_dataset[idx]}\n{voxel_color_dataset[idx,:,:]}")


if __name__ == "__main__":

    with h5py.File("volumetric_drilling/scripts/data-sample/20221024_130138.hdf5", "r") as f:
        main(f)
