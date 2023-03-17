# Pydrilling documentation

## Installation of pydrilling 
To install the python analysis package, go to the root directory of this repository and execute the command.
```
pip install -e .
```

To test if the installation was successful try the following command on your python terminal 

``` python
import pydrilling
```

## Scripts

### Data utils scripts

| **#** | **script**                 | **Description**                                                  |
| ----- | -------------------------- | ---------------------------------------------------------------- |
| 1     | `seg_nrrd_to_pngs.py`      | Convert a segmented nrrd file into png images                    |
| 2     | `modify_pngs_with_hdf5.py` | Modify png images using list of removed voxels from a hdf5 file. |

Scripts can be run at any path using 

```bash
python -m pydrilling.Scripts.seg_nrrd_to_pngs
python -m pydrilling.Scripts.modify_pngs_with_hdf5
```
see [modify pngs with hdf5 tutorial](./Scripts/modify_anatomy_with_hdf5_tutorial.md).