
from __future__ import annotations
from pathlib import Path
import re
from natsort import natsorted
import numpy as np 
from dataclasses import dataclass
from PIL import Image


@dataclass
class AnatomicalVolume:
    """ Anatomical volume representation

    Parameters 
    -------
    anatomy_matrix: np.ndarray
        Matrix representation of anatomical volume. Shape of array is
        (W,H,Nimgs,C) where C is the number of colors (RGBA), W is the width and
        H is the height. 

    """

    anatomy_matrix: np.array

    def __post_init__(self):
        assert len(self.anatomy_matrix.shape)  == 4, "wrong shape for input matrix"
        self.z_dim = self.anatomy_matrix.shape[0]


    def save_png_images(self, dst_path:Path, im_prefix="modifiedplane"):
        print("Saving volume to png images ....")
        for nz in range(self.z_dim):
            im_name = im_prefix + f"{nz:06d}" + ".png"
            im_name = str(dst_path / im_name)
            self.save_image(self.anatomy_matrix[:, :, nz, :], im_name)

    def save_image(self, array, im_name):
        im = Image.fromarray(array.astype(np.uint8))
        im.save(im_name)

    def save_data_matrix(self, path:Path):
        pass

    def remove_all_voxels(self, voxels:np.ndarray, voxels_colors:np.ndarray):
        pass

    def __remove_voxel(self, voxel_loc:np.ndarray, voxel_color:np.ndarray):
        pass

    def is_remove_voxel_data(self):
        pass
    
    @classmethod
    def from_png_list(cls, path:Path)-> AnatomicalVolume:
        prev_id = -1

        img_list = natsorted([img for img in path.glob("*.png")])
        img_res = np.asarray(Image.open(img_list[0])).shape
        data_matrix = np.zeros((img_res[0],img_res[1],len(img_list),4))

        for count, img_name in enumerate(img_list):
            png_id = cls.__is_png_id_valid(img_name.name, prev_id) 
            img = np.asarray(Image.open(img_name))
            data_matrix[:,:,count,:] = img 
            prev_id = png_id
        
        return AnatomicalVolume(data_matrix)

    @staticmethod 
    def __is_png_id_valid(file_name:str, prev_id:int)->int:
        png_id = re.findall("[0-9]+", file_name)
        if len(png_id) == 0:
            raise RuntimeError("No id in png image")
        png_id = int(png_id[0])
        if png_id <= prev_id:
            raise RuntimeError(f"Images not processed in right order (prev {prev_id}- current {png_id})")
        
        return png_id


    @classmethod
    def from_matrix(cls, path:Path)->AnatomicalVolume:
        pass


if __name__ == "__main__":

    root_path = Path("/home/juan1995/research_juan/cisII_SDF_project/Data/Anatomies/AnatomyA")
    src_path = Path(root_path)/"Images"
    dst_path = Path(root_path)/"ModifiedImages"

    anatomical_vol = AnatomicalVolume.from_png_list(src_path)

    anatomical_vol.save_png_images(dst_path)


