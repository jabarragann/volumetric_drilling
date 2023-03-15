
from __future__ import annotations
from pathlib import Path
import re
from natsort import natsorted
import numpy as np 
from dataclasses import dataclass
from PIL import Image

from pydrilling.DataUtils.DataMerger import Voxels


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
        self.z_dim = self.anatomy_matrix.shape[2]


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

    def remove_voxels(self, voxels_to_remove:Voxels):
        consistent   = 0
        total = len(voxels_to_remove)
        for idx, (ts,loc,color) in enumerate(voxels_to_remove): 
            # print(idx)
            consistent += self.__remove_voxel(loc.squeeze(), color.squeeze())
        print(f"consistent: {consistent}") 
        print(f"error: {total-consistent}") 
        print(f"correct %: {consistent/total*100:0.03f}") 
            # if idx >10:
            #     break

    def __remove_voxel(self, voxel_loc:np.ndarray, voxel_color:np.ndarray):
        color_in_anatomy = self.anatomy_matrix[voxel_loc[2],voxel_loc[1], voxel_loc[0]]  
        # color_in_anatomy = self.anatomy_matrix[voxel_loc[0],voxel_loc[1], voxel_loc[2]]  
        # color_in_anatomy = self.anatomy_matrix[voxel_loc[2],voxel_loc[0], voxel_loc[1]]  
        is_color_the_same = np.all(color_in_anatomy==voxel_color)
        if not is_color_the_same:
            # print(f"loc {voxel_loc}")
            # print(f"volume color(xyz): { self.anatomy_matrix[voxel_loc[0],voxel_loc[1], voxel_loc[2]]  }")
            # print(f"volume color(zxy): { self.anatomy_matrix[voxel_loc[2],voxel_loc[0], voxel_loc[1]]  }")
            # print(f"volume color(zyx): { self.anatomy_matrix[voxel_loc[2],voxel_loc[1], voxel_loc[0]]  }")
            # print(f"hdf5 color:   {voxel_color}")
            # print(np.all(color_in_anatomy==voxel_color))
            return 0
        else:
            return 1

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


