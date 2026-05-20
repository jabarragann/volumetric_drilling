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

#include "stereo_camera_interface.h"

#include <sl/Camera.hpp>

// Stereo video source backed by the ZED SDK. Pull-based: grab() captures a
// fresh pair from the camera.
class ZedCameraInterface : public StereoCameraInterface
{
public:
    ZedCameraInterface();
    ~ZedCameraInterface() override;

    bool init() override;
    bool grab() override;
    bool has_received_stereo_images() const override;
    const cv::Mat &left_image() const override;
    const cv::Mat &right_image() const override;

    void close();

private:
    sl::Camera m_zed;
    sl::Mat m_zed_left;
    sl::Mat m_zed_right;

    // BGR images written by grab().
    cv::Mat left_img;
    cv::Mat right_img;

    bool m_opened = false;
    bool m_has_images = false;
};
