import argparse
from collections import OrderedDict, defaultdict
from pathlib import Path
import numpy as np
import h5py
import pandas as pd
from natsort import natsorted

anatomy_dict = {
    "Bone": "255 249 219",
    "Malleus": "233 0 255",
    "Incus": "0 255 149",
    "Stapes": "63 0 255",
    "Bony_Labyrinth": "91 123 91",
    "IAC": "244 142 52",  # orange structure
    "Superior_Vestibular_Nerve": "255 191 135",
    "Inferior_Vestibular_Nerve": "121 70 24",
    "Cochlear_Nerve": "219 244 52",
    "Facial_Nerve": "244 214 49",
    "Chorda_Tympani": "151 131 29",
    "ICA": "216 100 79",
    "Sinus_+_Dura": "110 184 209",  # blue structure
    "Vestibular_Aqueduct": "91 98 123",
    "TMJ": "100 0 0",  # dark red structure
    "EAC": "255 225 214",  # Other big structure in the front
}


class PerformanceMetrics:
    def __init__(self, data_dir: Path):
        """Calculate metrics from experiment.

        Parameters
        ----------
        data_dir : Path
            directory storing HDF5 files.
        """
        self.data_dir = data_dir
        self.data_dict = None

        if not data_dir.exists():
            print("provided path does not exists")
            exit(0)

        self.file_list, self.data_dict = self.load_hdf5()
        self.calculate_metrics()
        self.metrics_report()
        self.close_files()

    def load_hdf5(self) -> OrderedDict:
        """Create a dictionary with all the hdf5 files sorted by name. Load only files that contain at least one voxel removed.

        Returns
        -------
        OrderedDict

        """
        files_list = []
        data_dict = OrderedDict()
        for file in self.data_dir.glob("*.hdf5"):
            files_list.append(file)

        files_list = natsorted(files_list)  # sort files by name
        final_file_list = []
        idx = 0
        for file in files_list:
            try:
                h5py_file = h5py.File(file, "r")
                # Only add files that have at least one voxel removed
                if "voxels_removed/voxel_time_stamp" in h5py_file:
                    final_file_list.append(file)
                    data_dict[idx] = h5py_file
                    idx += 1
            except:
                pass

        print(f"Parsed {len(data_dict)} hdf5 files")

        return final_file_list, data_dict

    def close_files(self):
        v: h5py.File
        for k, v in self.data_dict.items():
            v.close()

    def calculate_metrics(self):
        self.calculate_completion_time()
        self.calculate_removed_voxel_summary()

    def metrics_report(self):
        print(f"experiment path: {self.data_dir} ")
        print(f"Completion time: {self.completion_time:0.2f}")
        print(f"Collisions dict: \n{self.collision_dict}")

    def calculate_completion_time(self):
        s = len(self.data_dict)
        # # look for hdf5 file that contains the first pixel removed
        # for i in range(len(self.file_list)):
        #     if "voxels_removed/voxel_time_stamp" in self.data_dict[i]:
        #         first_idx = i
        #         break
        # # Look for hdf5 file that contains the last pixel removed
        # for i in range(len(self.file_list)):
        #     if "voxels_removed/voxel_time_stamp" in self.data_dict[i]:
        #         last_idx = s - 1 - i
        #         break

        first_ts = self.data_dict[0]["voxels_removed/voxel_time_stamp"][0]
        last_ts = self.data_dict[s - 1]["voxels_removed/voxel_time_stamp"][-1]

        self.completion_time = last_ts - first_ts

    def calculate_removed_voxel_summary(self):

        result_dict = defaultdict(int)
        for k, v in self.data_dict.items():
            voxel_colors: np.ndarray = v["voxels_removed/voxel_color"][()]
            voxel_colors = voxel_colors.astype(np.int32)

            voxel_colors_df = pd.DataFrame(voxel_colors, columns=["ts_idx", "r", "g", "b", "a"])
            voxel_colors_df["anatomy_name"] = ""

            # add a column with the anatomy names
            for name, color in anatomy_dict.items():
                color = list(map(int, color.split(" ")))
                voxel_colors_df.loc[
                    (voxel_colors_df["r"] == color[0])
                    & (voxel_colors_df["g"] == color[1])
                    & (voxel_colors_df["b"] == color[2]),
                    "anatomy_name",
                ] = name

            # Count number of removed voxels of each anatomy
            voxel_summary = voxel_colors_df.groupby(["anatomy_name"]).count()
            # print(voxel_summary)

            for anatomy in voxel_summary.index:
                result_dict[anatomy] += voxel_summary.loc[anatomy, "ts_idx"]

        self.collision_dict = dict(result_dict)


def main(data_dir: Path):
    PerformanceMetrics(data_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input_dir",
        type=str,
        help="Directory containing all the HDF5 files from a specific experiment.",
    )
    args = parser.parse_args()

    path = Path(args.input_dir)

    main(path)
