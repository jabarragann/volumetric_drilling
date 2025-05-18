from pathlib import Path
from volumetric_sim_tools.DataUtils.DataMerger import DataMerger, Voxels
import click
import numpy as np


def check_path(path: Path):
    if not path.exists():
        print(f"Path {path} does not exist")
        exit(0)

    return path


def create_path(path: Path):
    if not path.exists():
        print("creating dst_path")
        path.mkdir()
    return path


@click.command()
@click.option("--hdf5_dir", required=True, help="path to hdf5 file")
def generate_experiment_statistics(hdf5_dir: str):
    hdf5_dir = check_path(Path(hdf5_dir))

    print("Loading experiment data ...")
    experiment_data = DataMerger()
    experiment_data.get_merged_data(hdf5_dir)

    removed_voxels: Voxels = experiment_data.get_removed_voxels()

    ts, loc, color = removed_voxels[:]
    print(f"{ts.shape}")
    print(f"{loc.shape}")
    print(f"{color.shape}")

    print(f"Total removed voxels:  {len(removed_voxels)}")
    print(
        f"Experiment total time: {removed_voxels.get_total_time():0.4f} - voxels removed: {loc.shape}"
    )

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
