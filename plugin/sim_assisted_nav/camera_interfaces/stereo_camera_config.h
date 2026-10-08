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

#pragma once

#include <string>

// Configuration for the stereo camera source, parsed from the
// `sim_assisted_nav_plugin_config` block of the camera ADF. A single struct
// holds the fields for every source; the parser fills only the ones relevant
// to the chosen video_source.
struct StereoCameraConfig
{
    // Selects which StereoCameraInterface implementation to build.
    std::string video_source; // "ros" | "zed" | "decklink" | "unixfd"
    std::string camera_name;

    // ROS source only.
    std::string rostopic_left;
    std::string rostopic_right;

    // Decklink source only.
    int left_device = -1;
    int right_device = -1;

    // Unixfd source only: name of the running video_source to connect to.
    std::string source_name;

    // Output texture format.
    std::string pixel_format;    // "RGB" | "RGBA"
    int pixel_format_gl = 0;     // derived by validate()
    bool convert_from_RGB2BGR = false;

    // Validate the enum-like fields and derive pixel_format_gl. Throws
    // std::runtime_error on an unsupported value.
    void validate();
};
