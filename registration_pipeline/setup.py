import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="sim_assisted",
    version="0.0.0",
    author="Juan Antonio Barragan",
    author_email="jbarrag3@jh.edu",
    description="Registration pipeline for simulation assisted navigation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    install_requires=["rich", "click"],
    include_package_data=True,
    python_requires=">=3.8",
)