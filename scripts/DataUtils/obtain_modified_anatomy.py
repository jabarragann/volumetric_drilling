from pathlib import Path
import numpy as np
from pydrilling.DataUtils.AnatomicalVolume import AnatomicalVolume
from pydrilling.DataUtils.DataMerger import DataMerger
import click

# TODO: Think about creating a gui for this script.
def check_path(path: Path):
    if not path.exists():
        print(f"Path {path} does not exist")
        exit(0)

    return path


@click.command()
@click.option("--png_dir", required=True, help="path to png images")
@click.option("--hdf5_dir", required=True, help="path to hdf5 file")
@click.option("--output_dir", required=True, help="path to save modified pngs")
def modify_anatomy_with_hdf5(png_dir: str, hdf5_dif: str, output_dir: str):
    png_dir = check_path(Path(png_dir))
    hdf5_dir = check_path(Path(hdf5_dir))
    output_dir = check_path(Path(output_dir))

    print(f"Loading png images ....")
    anatomical_vol = AnatomicalVolume.from_png_list(png_dir)
    print("Loading experiment data ...")
    experiment_data = DataMerger()
    experiment_data.get_merged_data(hdf5_dir)
    print(f"Modify volume ...")
    removed_voxels = experiment_data.get_removed_voxels()
    anatomical_vol.remove_voxels(removed_voxels)

    anatomical_vol.save_png_images(output_dir, im_prefix="finalplane")


# # Sample paths
# # Volume paths
# root_path = Path("/home/juan1995/research_juan/cisII_SDF_project/Data/Anatomies/AnatomyA")
# src_path = Path(root_path) / "Images"
# dst_path = Path(root_path) / "FinalImages2"
# print("Loading anatomy ...")
# # Load experiment files
# exp_path = Path("/home/juan1995/research_juan/cisII_SDF_project/Data/UserStudy2_IROS")
# # exp_path = exp_path / "Participant_08/2023-02-08 10:07:14_AnatomyA_baseline"
# exp_path = exp_path / "Participant_09/2023-02-10 09:54:45"

if __name__ == "__main__":
    modify_anatomy_with_hdf5()
