
from __future__ import annotations
from pathlib import Path
import numpy as np 
from dataclasses import dataclass


@dataclass
class AnatomicalVolume:

    anatomy_matrix: np.array


    def save_png_images(path:Path):
        pass

    def save_data_matrix(path:Path):
        pass

    def remove_all_voxels(voxels:np.ndarray, voxels_colors:np.ndarray):
        pass

    def __remove_voxel(voxel_loc:np.ndarray, voxel_color:np.ndarray):
        pass
    
    @dataclass
    def from_png_list(cls, path:Path)-> AnatomicalVolume:
        pass

    @dataclass
    def from_matrix(cls, path:Path)->AnatomicalVolume:
        pass


if __name__ == "__main__":

    test_path = "/home/juan1995/research_juan/cisII_SDF_project/Data/Anatomies/AnatomyA/Images"
    test_path = Path(test_path)

    anatomical_vol = AnatomicalVolume.from_png_list(test_path)

    
