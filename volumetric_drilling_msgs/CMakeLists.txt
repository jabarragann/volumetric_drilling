cmake_minimum_required(VERSION 3.5)
if (POLICY CMP0048)
    cmake_policy(SET CMP0048 NEW)
endif (POLICY CMP0048)
project(volumetric_drilling_msgs)

add_compile_options(-std=c++17)

find_package (ament_cmake QUIET)
set (ROS2_depends ament_cmake rclcpp std_msgs geometry_msgs builtin_interfaces rosidl_default_generators)
foreach (_dep ${ROS2_depends})
  find_package (${_dep} REQUIRED)
endforeach ()

rosidl_generate_interfaces(volumetric_drilling_msgs
  msg/Index.msg
  msg/Voxels.msg
  msg/DrillSize.msg
  msg/VolumeInfo.msg
  DEPENDENCIES builtin_interfaces std_msgs geometry_msgs
  )

ament_package ()
