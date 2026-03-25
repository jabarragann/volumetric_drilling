cmake_minimum_required (VERSION 3.3)
project (volumetric_drilling)

set(CMAKE_CXX_STANDARD 17)

find_package(AMBF)
find_package(Boost COMPONENTS program_options filesystem)

set (AMBF_ROS_VERSION 2)
find_package (ament_cmake QUIET)
message ("Found ROS 2")

set (ROS2_depends rclcpp geometry_msgs std_msgs ambf_server AMBF volumetric_drilling_msgs)

foreach (_dep ${ROS2_depends})
    find_package (${_dep} REQUIRED)
endforeach()

include_directories(${AMBF_INCLUDE_DIRS})
include_directories(${Boost_INCLUDE_DIRS})

link_directories(${AMBF_LIBRARY_DIRS})
add_definitions(${AMBF_DEFINITIONS})

set (vol_plugin_prefix "volumetric_drilling")

add_library(volumetric_drilling SHARED
    ${vol_plugin_prefix}/common.h
    ${vol_plugin_prefix}/volumetric_drilling.cpp
    ${vol_plugin_prefix}/volumetric_drilling.h
    ${vol_plugin_prefix}/ros_interface.cpp
    ${vol_plugin_prefix}/ros_interface.h
    ${vol_plugin_prefix}/joystick.cpp
    ${vol_plugin_prefix}/joystick.h
    ${vol_plugin_prefix}/footpedal.cpp
    ${vol_plugin_prefix}/footpedal.h
    ${vol_plugin_prefix}/wave_generator.cpp
    ${vol_plugin_prefix}/wave_generator.h
    ${vol_plugin_prefix}/drill_manager.cpp
    ${vol_plugin_prefix}/drill_manager.h
    ${vol_plugin_prefix}/camera_panel_manager.h
    ${vol_plugin_prefix}/camera_panel_manager.cpp
    ${vol_plugin_prefix}/gaze_marker_controller.h
    ${vol_plugin_prefix}/gaze_marker_controller.cpp
    )


install (
TARGETS volumetric_drilling
LIBRARY DESTINATION lib
ARCHIVE DESTINATION lib
RUNTIME DESTINATION bin
)
ament_target_dependencies (volumetric_drilling ${ROS2_depends})
ament_package ()

# add_library(camera_hmd camera_hmd/hmd.cpp camera_hmd/hmd.h)
# target_link_libraries(camera_hmd ${AMBF_LIBRARIES})
# set_property(TARGET camera_hmd PROPERTY POSITION_INDEPENDENT_CODE TRUE)