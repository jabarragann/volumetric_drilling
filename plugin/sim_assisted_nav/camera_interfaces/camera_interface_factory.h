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

#include <memory>

#include "stereo_camera_interface.h"
#include "stereo_camera_config.h"

// Build the StereoCameraInterface implementation selected by
// config.video_source. Returns nullptr for an unrecognised source (the source
// string is already checked by StereoCameraConfig::validate(), so this is
// defensive only).
std::unique_ptr<StereoCameraInterface> create_stereo_camera_interface(const StereoCameraConfig &config);
