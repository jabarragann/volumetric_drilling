from setuptools import setup

package_name = "python_test_package"

setup(
    name=package_name,
    version="0.0.1",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="juan95",
    maintainer_email="juan95@todo.todo",
    description="Simple ROS 2 subscriber for drill location topic.",
    license="BSD-3-Clause",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "drill_location_listener = python_test_package.drill_location_listener:main",
        ],
    },
)
