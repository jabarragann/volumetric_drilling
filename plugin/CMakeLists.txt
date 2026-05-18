cmake_minimum_required (VERSION 3.3)
project (simulation_assisted_navigation_framework)

set(CMAKE_CXX_STANDARD 17)

find_package(AMBF)
find_package(Boost COMPONENTS program_options filesystem)
find_package(OpenCV REQUIRED)

# Look for the catkin dependencies (ROS 1)
set (ROS1_depends roscpp ambf_server volumetric_drilling_msgs geometry_msgs std_msgs sensor_msgs cv_bridge)
find_package (catkin QUIET
  COMPONENTS ${ROS1_depends})

if (catkin_FOUND)
    message ("Found ROS 1")
    set (AMBF_ROS_VERSION 1)
    include_directories(include ${catkin_INCLUDE_DIRS})

    catkin_package(
      INCLUDE_DIRS .
      LIBRARIES ${PROJECT_NAME}
      CATKIN_DEPENDS ${ROS1_depends}
    )
else (catkin_FOUND)
    # look for ROS2
    set (AMBF_ROS_VERSION 2)
    find_package (ament_cmake QUIET)
    if (ament_cmake_FOUND)
        message ("Found ROS 2")
        set (ROS2_depends rclcpp geometry_msgs std_msgs sensor_msgs cv_bridge ambf_server AMBF volumetric_drilling_msgs)
        foreach (_dep ${ROS2_depends})
            find_package (${_dep} REQUIRED)
        endforeach()
    endif (ament_cmake_FOUND)
endif (catkin_FOUND)

include_directories(${AMBF_INCLUDE_DIRS})
include_directories(${Boost_INCLUDE_DIRS})
include_directories(${OpenCV_INCLUDE_DIRS})

link_directories(${AMBF_LIBRARY_DIRS})
add_definitions(${AMBF_DEFINITIONS})

## Ambf application plugin - volumetric drilling
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

## Ambf camera plugin - camera hmd
add_library(camera_hmd camera_hmd/hmd.cpp camera_hmd/hmd.h)
target_link_libraries(camera_hmd ${AMBF_LIBRARIES})
set_property(TARGET camera_hmd PROPERTY POSITION_INDEPENDENT_CODE TRUE)

## Ambf camera plugin - sim assisted nav
add_library(sim_assisted_nav SHARED
    sim_assisted_nav/sim_assisted_nav.cpp
    sim_assisted_nav/sim_assisted_nav.h
    sim_assisted_nav/ros_interface.cpp
    sim_assisted_nav/ros_interface.h)
target_link_libraries(sim_assisted_nav ${AMBF_LIBRARIES} ${OpenCV_LIBRARIES})
set_property(TARGET sim_assisted_nav PROPERTY POSITION_INDEPENDENT_CODE TRUE)

# Ambf camera plugin - Multiview plugin
include_directories(multiview_panels)
set(multiview_dir "multiview_panels")

## Slicer lib
add_library(slicer_lib ${multiview_dir}/volume_slicer.cpp ${multiview_dir}/volume_slicer.h)
target_link_libraries(slicer_lib ${AMBF_LIBRARIES})
set_property(TARGET slicer_lib PROPERTY POSITION_INDEPENDENT_CODE TRUE)

## Slicer lib test executables
set(multiview_scripts_dir ${multiview_dir}/test_executables/)
add_executable(create_orthogonal_slices_test ${multiview_scripts_dir}/create_orthogonal_slices_test_deprecated.cpp)
target_link_libraries(create_orthogonal_slices_test ${AMBF_LIBRARIES})
add_executable(test_volume_slicer_01 ${multiview_scripts_dir}/test_volume_slicer_01.cpp)
target_link_libraries(test_volume_slicer_01 slicer_lib ${AMBF_LIBRARIES})

add_library(multiview SHARED ${multiview_dir}/multiview.cpp ${multiview_dir}/multiview.h)
target_link_libraries(multiview ${AMBF_LIBRARIES} slicer_lib)
set_property(TARGET multiview PROPERTY POSITION_INDEPENDENT_CODE TRUE)

# Conditional linkage based on ROS version
if (AMBF_ROS_VERSION EQUAL 1)
    add_dependencies (volumetric_drilling ${catkin_EXPORTED_TARGETS})
    target_link_libraries (volumetric_drilling ${Boost_LIBRARIES} ${AMBF_LIBRARIES} ${catkin_LIBRARIES})

    add_dependencies (camera_hmd ${catkin_EXPORTED_TARGETS})
    target_link_libraries (camera_hmd ${catkin_LIBRARIES})

    add_dependencies (sim_assisted_nav ${catkin_EXPORTED_TARGETS})
    target_link_libraries (sim_assisted_nav ${catkin_LIBRARIES})

    add_dependencies (multiview ${catkin_EXPORTED_TARGETS})
    target_link_libraries (multiview ${catkin_LIBRARIES})
else ()
    install (
        TARGETS
            volumetric_drilling
            camera_hmd
            sim_assisted_nav
            slicer_lib
            multiview
        LIBRARY DESTINATION lib
        ARCHIVE DESTINATION lib
        RUNTIME DESTINATION bin
    )

    ament_target_dependencies (volumetric_drilling ${ROS2_depends})
    ament_target_dependencies (camera_hmd rclcpp)
    ament_target_dependencies (sim_assisted_nav rclcpp sensor_msgs std_msgs cv_bridge ambf_server)
    ament_target_dependencies (multiview rclcpp geometry_msgs ambf_server)

    ament_package ()
endif()
