import argparse
from collections import OrderedDict, defaultdict
from pathlib import Path
import numpy as np
import h5py
import pandas as pd
from natsort import natsorted

from pydrilling.data_viewer import generate_video

# {short_name: [color, "long_name"]}
anatomy_dict = {
    "Bone": ["255 249 219", "Bone"],
    "Malleus": ["233 0 255", "Malleus"],
    "Incus": ["0 255 149", "Incus"],
    "Stapes": ["63 0 255", "Stapes"],
    "Bony": ["91 123 91", "Bony_Labyrinth"],
    "IAC": ["244 142 52", "IAC"],
    "SuperiorNerve": ["255 191 135", "Superior_Vestibular_Nerve"],
    "InferiorNerve": ["121 70 24", "Inferior_Vestibular_Nerve"],
    "CochlearNerve": ["219 244 52", "Cochlear_Nerve"],
    "FacialNerve": ["244 214 49", "Facial_Nerve"],
    "Chorda": ["151 131 29", "Chorda_Tympani"],
    "ICA": ["216 100 79", "ICA"],
    "Sinus": ["110 184 209", "Sinus_+_Dura"],
    "Vestibular": ["91 98 123", "Vestibular_Aqueduct"],
    "TMJ": ["100 0 0", "TMJ"],
    "EAC": ["255 225 214", "EAC"],
}


class PerformanceMetrics:
    def __init__(
        self,
        data_dir: Path,
        generate_first_vid: bool = False,
        participant_id: str = None,
        anatomy: str = None,
        guidance_modality: str = None,
    ):
        """Calculate metrics from experiment.

        Parameters
        ----------
        data_dir : Path
            directory storing HDF5 files.

        generate_first_vid : bool
            generated the video of the first valid hdf5 file. Valid files contain at least one collision.
        """

        if participant_id is None or anatomy is None or guidance_modality is None:
            raise Exception("Incomplete meta data")
        else:
            self.participant_id = participant_id
            self.anatomy = anatomy
            self.guidance_modality = guidance_modality

        self.data_dir = data_dir
        self.data_dict = None

        if not data_dir.exists():
            print("provided path does not exists")
            exit(0)

        self.file_list, self.data_dict = self.load_hdf5()

        if generate_first_vid:
            self.generate_video()

        self.calculate_metrics()
        # self.metrics_report()
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

    def generate_video(self):
        # Check if the video is already generated
        path_first_file: Path = self.file_list[0]
        video_path = path_first_file.with_suffix(".avi")
        if not video_path.exists():
            generate_video(path_first_file, output_path=video_path)

    def calculate_metrics(self):
        self.calculate_completion_time()
        self.calculate_removed_voxel_summary()

    def metrics_report(self):
        print(
            f"participant_id: {self.participant_id}, anatomy: {self.anatomy}, guidance: {self.guidance_modality}"
        )
        print(f"experiment path: {self.data_dir} ")
        print(f"Completion time: {self.completion_time:0.2f}")
        print(f"Collisions dict: \n{self.collision_dict}")

    def generate_summary_dataframe(self):
        df = dict(
            participant_id=[self.participant_id],
            anatomy=[self.anatomy],
            guidance=[self.guidance_modality],
            completion_time=self.completion_time,
        )

        for name, anatomy_info_list in anatomy_dict.items():
            voxels_removed = 0
            if name in self.collision_dict:
                voxels_removed = self.collision_dict[name]
            df[name + "_voxels"] = voxels_removed

        return pd.DataFrame(df)

    def calculate_completion_time(self):
        s = len(self.data_dict)

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
            for name, anatomy_info_list in anatomy_dict.items():
                color, full_name = anatomy_info_list
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
