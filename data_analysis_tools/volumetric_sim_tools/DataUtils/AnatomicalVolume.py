from __future__ import annotations
from pathlib import Path
import re
from natsort import natsorted
import numpy as np
from dataclasses import dataclass
from PIL import Image

from volumetric_sim_tools.DataUtils.DataMerger import Voxels


@dataclass
class AnatomicalVolume:
    """Anatomical volume representation

    Parameters
    -------
    anatomy_matrix: np.ndarray
        Matrix representation of anatomical volume. Shape of array is
        (W,H,Nimgs,C) where C is the number of colors (RGBA), W is the width and
        H is the height.

    """

    anatomy_matrix: np.array

    def __post_init__(self):
        assert len(self.anatomy_matrix.shape) == 4, "wrong shape for input matrix"
        self.z_dim = self.anatomy_matrix.shape[2]

    def save_png_images(self, dst_path: Path, im_prefix="plane"):
        print("Saving volume to png images ....")
        for nz in range(self.z_dim):
            im_name = im_prefix + f"{nz:06d}" + ".png"
            im_name = str(dst_path / im_name)
            self.save_image(self.anatomy_matrix[:, :, nz, :], im_name)

    def save_image(self, array, im_name):
        im = Image.fromarray(array.astype(np.uint8))
        im.save(im_name)

    def save_data_matrix(self, path: Path):
        pass

    def remove_voxels(self, voxels_to_remove: Voxels):
        consistent = 0
        total = len(voxels_to_remove)
        for idx, (ts, loc, color) in enumerate(voxels_to_remove):
            consistent += self.__remove_voxel(loc.squeeze(), color.squeeze())

        correctness_score = consistent / total * 100
        print(f"correct %: {correctness_score:0.03f}")
        if correctness_score < 99:
            print(
                f"Warning! If correct % is not a 100%, the hdf5 data and pngs \
                    images are not from the same anatomical structure"
            )

    def __remove_voxel(self, voxel_loc: np.ndarray, voxel_color: np.ndarray):
        """Remove a voxel using voxels in hdf5. To obtain the corresponding
        voxel_loc in the anatomical volume, the following considerations need
        to be taken into account:

        Voxels_loc are reported as x,y,z positions while anatomical structures
        as stored using row,col indexes.

        Images in simulator are fliped along the y-axis (rows are flipped)

        """
        color_in_anatomy = self.anatomy_matrix[255 - voxel_loc[1], voxel_loc[0], voxel_loc[2]]
        is_color_the_same = np.all(color_in_anatomy == voxel_color)
        if not is_color_the_same:
            return 0
        else:
            self.anatomy_matrix[255 - voxel_loc[1], voxel_loc[0], voxel_loc[2]] = np.array(
                [255.0, 0.0, 0.0, 50.0]
            )
            return 1

    def is_remove_voxel_data(self):
        pass

    @classmethod
    def from_png_list(cls, path: Path) -> AnatomicalVolume:
        prev_id = -1

        # Natsorting doesn't like Path objects.
        img_list = [str(img) for img in path.glob("*.png")]
        img_list = natsorted(img_list)

        img_res = np.asarray(Image.open(img_list[0])).shape
        data_matrix = np.zeros((img_res[0], img_res[1], len(img_list), 4))

        for count, img_name in enumerate(img_list):
            png_id = cls.__is_png_id_valid(img_name.split("/")[-1], prev_id)
            img = np.asarray(Image.open(img_name))
            data_matrix[:, :, count, :] = img
            prev_id = png_id

        return AnatomicalVolume(data_matrix)

    @staticmethod
    def __is_png_id_valid(file_name: str, prev_id: int) -> int:
        png_id = re.findall("[0-9]+", file_name)
        if len(png_id) == 0:
            raise RuntimeError("No id in png image")
        png_id = int(png_id[0])
        if png_id <= prev_id:
            print(f"error processing {file_name}")
            raise RuntimeError(
                f"Images not processed in right order (prev {prev_id}- current {png_id}). Error with natsorting?"
            )

        return png_id

    @classmethod
    def from_matrix(cls, path: Path) -> AnatomicalVolume:
        pass


if __name__ == "__main__":

    root_path = Path("/home/juan1995/research_juan/cisII_SDF_project/Data/Anatomies/AnatomyA")
    src_path = Path(root_path) / "Images"
    dst_path = Path(root_path) / "ModifiedImages"

    anatomical_vol = AnatomicalVolume.from_png_list(src_path)

    anatomical_vol.save_png_images(dst_path, im_prefix="modifiedplane_")
