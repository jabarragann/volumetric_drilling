from pathlib import Path
from typing import List, Tuple
from volumetric_sim_tools.DataUtils.DataMerger import DataMerger, Voxels
import click
import numpy as np


def check_path(path: Path):
    if not path.exists():
        print(f"Path {path} does not exist")
        exit(0)


def create_path(path: Path):
    if not path.exists():
        print("creating dst_path")
        path.mkdir()
    return path


def extract_valid_intervals(
    timestamps: np.ndarray, max_gap: float = 0.2
) -> List[Tuple[float, float]]:
    valid_intervals = []
    start_time = timestamps[0]

    for i in range(1, len(timestamps)):
        delta = timestamps[i] - timestamps[i - 1]

        if delta > max_gap:
            end_time = timestamps[i - 1]
            valid_intervals.append((start_time, end_time))
            start_time = timestamps[i]

    # Handle final segment
    if timestamps[-1] - start_time <= max_gap:
        valid_intervals.append((start_time, timestamps[-1]))

    return valid_intervals


def write_intervals_to_ltxt(intervals: List[Tuple[float, float]], output_file: Path):
    with open(output_file, "w") as f:
        for start, end in intervals:
            f.write(f"{start:.6f} {end:.6f}\n")

    print(f"Written {len(intervals)} valid intervals to {output_file}")


def calculate_tracking_percentage(
    valid_intervals_raw: List[Tuple[float, float]],
    exp_start_time: float,
    exp_end_time: float,
) -> Tuple[float, List[Tuple[float, float]]]:
    # Remove intervals outside of experiment times.
    valid_intervals: List[Tuple[float, float]] = []
    for line in valid_intervals_raw:
        start, end = line[:]
        if end > exp_start_time and start < exp_end_time:
            valid_intervals.append((start, end))

    if exp_start_time > valid_intervals[0][0]:
        valid_intervals[0] = (exp_start_time, valid_intervals[0][1])
    if exp_end_time < valid_intervals[-1][1]:
        valid_intervals[-1] = (valid_intervals[-1][0], exp_end_time)

    total_valid_time = sum(end - start for start, end in valid_intervals)
    total_experiment_time = exp_end_time - exp_start_time
    percentage_of_valid_time = (total_valid_time / total_experiment_time) * 100

    print([end - start for start, end in valid_intervals])
    print(percentage_of_valid_time)
    print(percentage_of_valid_time)
    print(total_experiment_time)

    return percentage_of_valid_time, valid_intervals


@click.command()
@click.option("--hdf5_dir", required=True, help="path to hdf5 file")
def generate_experiment_statistics(hdf5_dir: str):
    _hdf5_dir = Path(hdf5_dir)
    check_path(_hdf5_dir)

    print("Loading experiment data ...")
    experiment_data = DataMerger()
    experiment_data.get_merged_data(_hdf5_dir)

    removed_voxels: Voxels = experiment_data.get_removed_voxels()
    ts, loc, color = removed_voxels[:]
    ts = ts.flatten()

    atracsys_ts, atracsys_data = experiment_data.get_atracsys_data()

    tracking_percentage = -1.0
    if atracsys_ts is not None:
        threshold = 0.2
        valid_ts_path = _hdf5_dir / f"valid_ts_{threshold:0.2f}.txt"
        valid_intervals_raw = extract_valid_intervals(atracsys_ts, max_gap=threshold)
        tracking_percentage, valid_intervals = calculate_tracking_percentage(
            valid_intervals_raw, ts[0], ts[-1]
        )
        write_intervals_to_ltxt(valid_intervals, valid_ts_path)

    print(f"{ts.shape}")
    print(f"{loc.shape}")
    print(f"{color.shape}")

    print(ts[0], ts[-1])
    print(ts[0] - ts[0], ts[-1] - ts[0])
    print(f"Total removed voxels:  {len(removed_voxels)}")
    print(
        f"Experiment total time: {removed_voxels.get_total_time():0.4f} - voxels removed: {loc.shape}"
    )
    print(f"Percentage of time that drill was tracked: {tracking_percentage:.2f}%")

    total_removed = len(removed_voxels)
    unique_colors, counts = np.unique(color, axis=0, return_counts=True)

    print("Unique colors and their counts:")
    for color, count in zip(unique_colors, counts):
        print(f"Color {color}: {count} : {count / total_removed * 100:.2f}%")

    ## Colors Nimesh experiment -- exp03
    # Bone --> (241, 214, 145, 255)
    # Anatomy --> ( 221, 130, 101, 255)

    ## Colors Andy experiment -- exp04
    # Box: --> (216,101, 79, 255)
    # Bone: --> (174, 167, 164, 255)
    # Anatomy: --> (111, 184, 210, 255)

    ## Misterious extra color not in images --> (174, 39,35,255)


def main():
    generate_experiment_statistics()


if __name__ == "__main__":
    main()
