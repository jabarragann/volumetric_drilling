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

#include <opencv2/core.hpp>

// Abstract interface shared by every stereo video source feeding the HMD view.
// Concrete sources (ROS topics, ZED SDK, Decklink capture cards) receive their
// source-specific parameters through their constructor, so init() is uniform.
class StereoCameraInterface
{
public:
    virtual ~StereoCameraInterface() = default;

    // Open / connect to the source. Returns true on success.
    virtual bool init() = 0;

    // Pull a fresh stereo pair. Pull-based sources (ZED, Decklink) capture
    // here; push-based sources (ROS) return true as a no-op.
    virtual bool grab() = 0;

    // True once a usable, non-empty stereo pair is available.
    virtual bool has_received_stereo_images() const = 0;

    // Most-recent frames as BGR cv::Mat. Valid only after a successful
    // grab() + has_received_stereo_images() check.
    virtual const cv::Mat &left_image() const = 0;
    virtual const cv::Mat &right_image() const = 0;
};
