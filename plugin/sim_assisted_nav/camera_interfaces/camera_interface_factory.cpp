//==============================================================================
/*
    Software License Agreement (BSD License)
    Copyright (c) 2019-2022, AMBF
    (https://github.com/WPI-AIM/ambf)

    All rights reserved.

    \author    <jbarrag3@jh.edu>
    \author    Juan Antonio Barragan
*/
//==============================================================================

#include "camera_interface_factory.h"

#include "ros_stereo_camera_interface.h"
#include "decklink_camera_interface.h"
#ifdef WITH_ZED
#include "zed_camera_interface.h"
#endif

#include <iostream>

std::unique_ptr<StereoCameraInterface> create_stereo_camera_interface(const StereoCameraConfig &config)
{
    if (config.video_source == "ros")
    {
        return std::make_unique<RosStereoCameraInterface>(config.rostopic_left, config.rostopic_right);
    }
    if (config.video_source == "zed")
    {
#ifdef WITH_ZED
        return std::make_unique<ZedCameraInterface>();
#else
        std::cerr << "ERROR! video_source 'zed' requires the sim_assisted_nav plugin "
                     "to be built with -DWITH_ZED=ON (ZED SDK + CUDA)." << std::endl;
        return nullptr;
#endif
    }
    if (config.video_source == "decklink")
    {
        return std::make_unique<DecklinkCameraInterface>(config.left_device, config.right_device);
    }
    return nullptr;
}
