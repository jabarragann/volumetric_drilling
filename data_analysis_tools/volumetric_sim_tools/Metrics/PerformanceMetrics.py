import argparse
import matplotlib.pyplot as plt
from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import Dict, List
import numpy as np
import h5py
import pandas as pd
from natsort import natsorted

from volumetric_sim_tools.DataUtils.VideoUtils import generate_video
from volumetric_sim_tools.DataUtils.Recording import Recording

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
        recording: Recording,
        generate_first_vid: bool = False,
    ):
        """Calculate metrics from experiment.

        Parameters
        ----------
        data_dir : Path
            directory storing HDF5 files.

        generate_first_vid : bool
            generated the video of the first valid hdf5 file. Valid files contain at least one collision.
        """

        self.recording = recording
        self.file_list: List[Path] = self.recording.file_list
        self.data_dict: Dict[int, h5py.File] = self.recording.data_dict

        self.participant_id = self.recording.participant_id
        self.anatomy = self.recording.anatomy
        self.guidance_modality = self.recording.guidance_modality
        self.trial_idx = self.recording.trial_idx

        if generate_first_vid:
            self.generate_video()
        self.generate_ts_plot()

        self.calculate_metrics()
        # self.metrics_report()

    def generate_ts_plot(self):
        root = self.file_list[0].parent
        plt_name = root / "ts_plot.png"

        burr_change_ts = self.recording.concatenate_data("burr_change/time_stamp")
        data_ts = self.recording.concatenate_data("data/time")
        voxels_removed_ts = self.recording.concatenate_data("voxels_removed/voxel_time_stamp")
        fig, ax = plt.subplots(1)
        # ax.plot(burr_change_ts)
        # Normalize times
        init_time = data_ts[0]
        data_ts -= init_time
        voxels_removed_ts -= init_time
        burr_change_ts -= init_time

        ax.plot(data_ts, np.ones_like(data_ts) * 3, "*", label="data_ts")
        ax.plot(
            voxels_removed_ts, np.ones_like(voxels_removed_ts) * 2, "*", label="voxels_removed_ts"
        )
        # ax.plot(burr_change_ts, np.ones_like(burr_change_ts) * 1, "*", label="burr_change_ts")
        for b_c in burr_change_ts:
            ax.axvline(b_c, label="burr_change_ts", color="black")

        ax.set_xlabel("Time (S)")
        ax.grid()
        ax.set_ylim((0, 4))

        # Create legend without repeated values
        handles, labels = ax.get_legend_handles_labels()
        by_label = OrderedDict(zip(labels, handles))
        ax.legend(by_label.values(), by_label.keys())
        # ax.legend()

        fig.savefig(plt_name)
        plt.close(fig)

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
        print(f"experiment path: {self.recording.data_dir} ")
        print(f"Completion time: {self.completion_time:0.2f}")
        print(f"Collisions dict: \n{self.collision_dict}")

    def generate_summary_dataframe(self):
        df = dict(
            participant_id=[self.participant_id],
            anatomy=[self.anatomy],
            trial_idx=[self.trial_idx],
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

    trial_meta_data = {
        "participant_id": "pilot participant",
        "guidance_modality": "Baseline",
        "anatomy": "A",
    }

    def get_all(name):
        print(name)

    with Recording(data_dir, **trial_meta_data) as recording:
        print(f"Read {len(recording)} h5 files for {recording.participant_id}")
        metrics = PerformanceMetrics(recording, generate_first_vid=False)
        metrics.metrics_report()
        print()

        # Print all available groups
        print("Available datasets in file 0")
        metrics.data_dict[0].visit(get_all)


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
