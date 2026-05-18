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

#include <sl/Camera.hpp>
#include <opencv2/core.hpp>

class ZedCameraInterface
{
public:
    ZedCameraInterface();
    ~ZedCameraInterface();

    bool init();
    void close();

    // Grab a new pair of frames from the camera. Returns true on success.
    bool grab();

    bool has_received_stereo_images() const;

    // BGR images written by grab().
    cv::Mat left_img;
    cv::Mat right_img;

private:
    sl::Camera m_zed;
    sl::Mat m_zed_left;
    sl::Mat m_zed_right;
    bool m_opened = false;
    bool m_has_images = false;
};
