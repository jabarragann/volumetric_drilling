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

#include "stereo_camera_config.h"

#include <GL/gl.h>
#include <iostream>
#include <stdexcept>

void StereoCameraConfig::validate()
{
    if (pixel_format == "RGB")
    {
        pixel_format_gl = GL_RGB;
    }
    else if (pixel_format == "RGBA")
    {
        pixel_format_gl = GL_RGBA;
    }
    else
    {
        std::cerr << "ERROR! Pixel format " << pixel_format << " not supported. Check plugin config." << std::endl;
        throw std::runtime_error("Pixel format not supported");
    }

    if (video_source != "ros" && video_source != "zed" && video_source != "decklink")
    {
        std::cerr << "ERROR! Video source " << video_source << " not supported. Check plugin config." << std::endl;
        throw std::runtime_error("Video source not supported");
    }
}
