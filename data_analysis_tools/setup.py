import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="volumetric_sim_tools",
    version="0.0.0",
    author="Juan Antonio Barragan",
    author_email="jbarrag3@jhu.edu",
    description="Python module with helper functions to analyze data from the drilling simulator",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    install_requires=["numpy", "scipy", "rich", "click", "pynrrd", "Pillow", "natsort", "h5py"],
    include_package_data=True,
    python_requires=">=3.7",
    entry_points={
        "console_scripts": [
            "volusim_tools_generate_experiment_video = volumetric_sim_tools.Scripts.generate_experiment_video:main",
            "volusim_tools_seg_nrrd_to_pngs = volumetric_sim_tools.Scripts.seg_nrrd_to_pngs:main",
            "volusim_tools_mark_removed_voxels = volumetric_sim_tools.Scripts.mark_removed_voxels:main",
        ]
    },
)
