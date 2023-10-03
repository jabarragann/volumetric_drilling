# Volumetric Sim Analysis Tools 

## Installation of volumetric_sim_tools 
To install the python analysis package, go to the root directory of this repository and execute the command.
```
pip install -e .
```

To test if the installation was successful try the following command on your python terminal 

``` python
import volumetric_sim_tools
```

## Scripts

### Data utils scripts

| **#** | **script**                       | **Description**                                                  |
| ----- | -------------------------------- | ---------------------------------------------------------------- |
| 1     | `generate_experiment_video.py`   | Generate video from HDF5 files.
| 2     | `seg_nrrd_to_pngs.py`            | Convert a segmented nrrd file into png images                    |
| 3     | `mark_removed_voxels.py`         | Modify png images using list of removed voxels from a hdf5 file. |

Scripts are added to your path using console entry points. The access the script use the prefix `volusim_tools_` and the name of the script. For example:

```bash
volusim_tools_mark_removed_voxels --help
```

Alternatively, scripts can be called using the -m as follows
```bash
python -m volumetric_sim_tools.Scripts.mark_removed_voxels
```

## Tutorials
see [mark removed voxels](./docs/mark_removed_voxels.md).
