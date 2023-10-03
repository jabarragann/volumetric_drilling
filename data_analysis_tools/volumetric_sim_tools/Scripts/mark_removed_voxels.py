from pathlib import Path
import numpy as np
from volumetric_sim_tools.DataUtils.AnatomicalVolume import AnatomicalVolume
from volumetric_sim_tools.DataUtils.DataMerger import DataMerger
import click


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
@click.option("--png_dir", required=True, help="path to png images")
@click.option("--hdf5_dir", required=True, help="path to hdf5 file")
@click.option("--output_dir", required=True, help="path to save modified pngs")
def modify_anatomy_with_hdf5(png_dir: str, hdf5_dir: str, output_dir: str):
    png_dir = check_path(Path(png_dir))
    hdf5_dir = check_path(Path(hdf5_dir))
    output_dir = create_path(Path(output_dir))

    print(f"Loading png images ....")
    anatomical_vol = AnatomicalVolume.from_png_list(png_dir)
    print("Loading experiment data ...")
    experiment_data = DataMerger()
    experiment_data.get_merged_data(hdf5_dir)
    print(f"Modify volume ...")
    removed_voxels = experiment_data.get_removed_voxels()
    anatomical_vol.remove_voxels(removed_voxels)

    anatomical_vol.save_png_images(output_dir, im_prefix="finalplane")

def main():
    modify_anatomy_with_hdf5()

if __name__ == "__main__":
    main()