import os
from pathlib import Path
from typing import List
import h5py
import numpy as np
from natsort import natsorted
from collections import OrderedDict
from dataclasses import InitVar, dataclass

# {0:{ts:float, voxels:ndarray, color:}}
# https://github.com/uvemas/ViTables


@dataclass
class Voxels:
    voxels_loc: np.ndarray
    voxels_color: np.ndarray
    voxels_ts: np.ndarray

    voxel_ts_mapper: InitVar[np.ndarray]

    def __post_init__(self, voxel_ts_mapper):
        self.__current_index = -1

        # Duplicate element in voxels_ts to have the same size as voxels_color and voxel_loc
        ts_idx = voxel_ts_mapper[:]
        self.voxels_ts: np.ndarray = self.voxels_ts[ts_idx]

        self.__start_time = self.voxels_ts[0]
        self.__end_time = self.voxels_ts[-1]

        assert self.voxels_ts.shape[0] == self.voxels_color.shape[0], "inconsistent data"
        assert self.voxels_ts.shape[0] == self.voxels_color.shape[0], "inconsistent data"

    def __len__(self):
        return self.voxels_loc.shape[0]

    def __iter__(self):
        self.__current_index = -1
        return self

    def __next__(self):
        self.__current_index += 1
        if self.__current_index < len(self):
            return self[self.__current_index]
        raise StopIteration

    def __getitem__(self, idx):

        ts = self.voxels_ts[idx]
        loc = self.voxels_loc[idx]
        color = self.voxels_color[idx]

        if isinstance(idx, slice):
            ts = ts.reshape((-1, 1))
        else:
            ts = np.array([ts]).reshape((-1, 1))
            loc = loc.reshape((-1, 3))
            color = color.reshape((-1, 4))

        return ts, loc, color

    def get_total_time(self) -> float:
        return self.__end_time - self.__start_time

    def get_voxels_at_time(self, t: float) -> List[np.ndarray]:
        t = t + self.__start_time
        selected_idx = self.voxels_ts < t

        ts = self.voxels_ts[selected_idx]
        loc = self.voxels_loc[selected_idx]
        color = self.voxels_color[selected_idx]

        return ts, loc, color


class DataMerger:
    def __init__(self):
        self._data = OrderedDict()
        self.file_names = []

    def _clear_data(self):
        for g in self._data.keys():
            self._data[g].clear()

        self.file_names = []

    def get_merged_data(self, dir, verbose=False):
        self._clear_data()

        # os.chdir(dir)
        # names = os.listdir(dir)

        # for n in names:
        #     if n.endswith(".hdf5"):
        #         self.file_names.append(n)
        self.file_names = list(dir.glob("*.hdf5"))
        self.file_names = natsorted(self.file_names)
        print("Number of Files ", len(self.file_names))

        for idx, file_name in enumerate(self.file_names):
            file = h5py.File(file_name, "r")
            if verbose:
                print(idx, "Opening", file_name)
            for grp in file.keys():
                if grp == "metadata":
                    continue

                if grp not in self._data:
                    self._data[grp] = OrderedDict()
                if verbose:
                    print("\t Processing Group ", grp)
                for dset in file[grp].keys():
                    if grp == "data" and dset != "time" and "pose_" not in dset:
                        continue

                    if len(file[grp][dset]) == 0:
                        continue

                    if verbose:
                        print("\t\t Processing Dataset ", dset)
                    if dset not in self._data[grp]:
                        self._data[grp][dset] = file[grp][dset][()]
                    else:
                        self._data[grp][dset] = np.append(
                            self._data[grp][dset], file[grp][dset][()], axis=0
                        )
            file.close()
        return self._data

    def get_removed_voxels(self) -> Voxels:
        """Get array of removed voxels

        Returns
        -------
        np.ndarray
            Array of removed voxels information of shape (N,7). First three
            columes provide the indexes and remaning 4 columns the RGBA color.
        """
        voxel_ts_mapper = self._data["voxels_removed"]["voxel_removed"][:, 0].astype(np.int32)
        voxel_color = self._data["voxels_removed"]["voxel_color"][:, 1:].astype(np.uint8)
        voxel_loc = self._data["voxels_removed"]["voxel_removed"][:, 1:].astype(np.int32)
        voxel_ts = self._data["voxels_removed"]["voxel_time_stamp"]

        voxels = Voxels(voxel_loc, voxel_color, voxel_ts, voxel_ts_mapper)
        # result_arr = np.zeros((voxel_color.shape[0],7)).astype(np.int32)
        # result_arr[:,0:3]= voxel_removed[:,1:].astype(np.int32)
        # result_arr[:,3:7] = voxel_color[:,1:].astype(np.int32)

        return voxels

    @classmethod
    def save_data_to_hdf5(self, data, dst_path, outfile="output.hdf5"):
        output_file = h5py.File(dst_path / outfile, "w")
        for grp in data.keys():
            output_grp = output_file.create_group(grp)
            for dset in data[grp].keys():
                print("Writing Dataset", dset)
                output_grp.create_dataset(dset, data=data[grp][dset], compression="gzip")

        output_file.close()


def main():
    data_merge = DataMerger()
    # data_path = Path("/home/juan1995/research_juan/cisII_SDF_project/Data/RedCap/Baseline")
    # data_path = data_path / "Participant_3/2022-11-04 14.32.45"

    data_path = Path("/home/juan1995/research_juan/cisII_SDF_project/Data/UserStudy2_IROS")
    data_path = data_path / "Participant_08/2023-02-08 10:07:14_AnatomyA_baseline"

    # data_path = data_path / "Participant_08/test_dir"

    # data_path = data_path / "Participant_09/2023-02-10 09:54:45"

    data = data_merge.get_merged_data(data_path)
    removed_voxels: Voxels = data_merge.get_removed_voxels()

    ts, loc, color = removed_voxels[:]
    print(f"{ts.shape}")
    print(f"{loc.shape}")
    print(f"{color.shape}")

    print(f"Total removed voxels:  {len(removed_voxels)}")
    print(
        f"Experiment total time: {removed_voxels.get_total_time():0.4f} - voxels removed: {loc.shape}"
    )

    half_time = removed_voxels.get_total_time() / 2
    ts, loc, color = removed_voxels.get_voxels_at_time(half_time)
    print(f"Voxels removed at time {half_time:0.4f} - voxels removed: {loc.shape}")

    x = 0
    # DataMerger.save_data_to_hdf5(data, data_path)


if __name__ == "__main__":
    main()
