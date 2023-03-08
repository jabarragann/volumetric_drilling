# CIS II project 16: SDF Based Guidance and Safety SDF calculation in skull-based surgery simulation.

The following repository contains a guidance system based on **signed distance functions (SDF)** for a skull-based surgery simulation. This work was done as part of the Computer Integrated Surgery II course at Johns Hopkins University in spring 2022. More information about the installation process of the simulation environment can be found in the [original repository](https://github.com/LCSR-SICKKIDS/volumetric_drilling). 

## Overview

The virtual reality drilling simulator is able to actively modify anatomy with a virtual drill. The simulator has both VR and haptics integration as well as the ability to generate data for use in downstream algorithm development. Volumetric_drilling is a plugin built on top of Asynchronous Multibody Framework ([AMBF](https://github.com/WPI-AIM/ambf)) developed by Munawar et al. We show the use of the plugin in lateral skull base surgery. The following fork includes visual and haptic feedback modalities based on SDF files running in the AMBF simulator..

![image](https://user-images.githubusercontent.com/61888209/136677737-af8e1a6c-1f76-44d7-bb3c-6a9d99ec08fd.png)

## SDF guidance overview

* Developed c++ library to load EDT files into the simulation environment can be found in [link](./EdtReader/). 
* C++ library to calculate EDT voluments can be found in the following [repository](https://github.com/jabarragann/EDT?organization=jabarragann&organization=jabarragann).
* For the python preprocessing scripts to generate SDF files please refer to this [link](./scripts/EdtGeneration/README.MD)

## Installation of python analysis scripts
To install the python analysis package use the command.
```
pip install -e .
```

To test if the installation was successful try the following command on your python terminal 

``` python
import pydrilling
```




# References
Consider citing our article if this project is useful to you!

```
@article{https://doi.org/10.48550/arxiv.2303.01733,
  doi = {10.48550/ARXIV.2303.01733},
  url = {https://arxiv.org/abs/2303.01733},
  author = {Ishida, Hisashi and Barragan, Juan Antonio and Munawar, Adnan and Li, Zhaoshuo and Kazanzides, Peter and Kazhdan, Michael and Trakimas, Danielle and Creighton, Francis X. and Taylor, Russell H.},
  keywords = {Human-Computer Interaction (cs.HC), Robotics (cs.RO), FOS: Computer and information sciences, FOS: Computer and information sciences},
  title = {Improving Surgical Situational Awareness with Signed Distance Field: A Pilot Study in Virtual Reality},
  publisher = {arXiv},
  year = {2023},
  copyright = {arXiv.org perpetual, non-exclusive license}
}
```

<!-- ```
@article{munawar2021virtual,
  title={Virtual reality for synergistic surgical training and data generation},
  author={Munawar, Adnan and Li, Zhaoshuo and Kunjam, Punit and Nagururu, Nimesh and Ding, Andy S and Kazanzides, Peter and Looi, Thomas and Creighton, Francis X and Taylor, Russell H and Unberath, Mathias},
  journal={Computer Methods in Biomechanics and Biomedical Engineering: Imaging \& Visualization},
  pages={1--9},
  year={2021},
  publisher={Taylor \& Francis}
}
``` -->