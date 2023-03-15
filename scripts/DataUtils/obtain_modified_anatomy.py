from pathlib import Path
import numpy as np
from pydrilling.DataUtils.AnatomicalVolume import AnatomicalVolume
from pydrilling.DataUtils.DataMerger import DataMerger
import argparse

# TODO: Think about creating a gui for this script.

def main():

    # Load Anatomy
    root_path = Path("/home/juan1995/research_juan/cisII_SDF_project/Data/Anatomies/AnatomyA")
    src_path = Path(root_path)/"Images"
    dst_path = Path(root_path)/"FinalImages2"
    print("Loading anatomy ...")
    anatomical_vol = AnatomicalVolume.from_png_list(src_path)

    # Load experiment files
    exp_path = Path("/home/juan1995/research_juan/cisII_SDF_project/Data/UserStudy2_IROS")
    # exp_path = exp_path / "Participant_08/2023-02-08 10:07:14_AnatomyA_baseline" 
    exp_path = exp_path / "Participant_09/2023-02-10 09:54:45" 

    print("Modifying anatomy with experiment data ...")
    experiment_data = DataMerger()
    experiment_data.get_merged_data(exp_path)

    removed_voxels = experiment_data.get_removed_voxels()
    anatomical_vol.remove_voxels(removed_voxels)    

    anatomical_vol.save_png_images(dst_path, im_prefix="finalplane")


if __name__ == "__main__":
    main() 



