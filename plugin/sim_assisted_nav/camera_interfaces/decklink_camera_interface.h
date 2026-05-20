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

#include <opencv2/videoio.hpp>

#include <string>

// Stereo video source backed by two Decklink SDI capture devices, read through
// GStreamer via OpenCV's VideoCapture. Pull-based: grab() reads one frame from
// each device.
class DecklinkCameraInterface : public StereoCameraInterface
{
public:
    DecklinkCameraInterface(int left_device, int right_device);
    ~DecklinkCameraInterface() override;

    bool init() override;
    bool grab() override;
    bool has_received_stereo_images() const override;
    const cv::Mat &left_image() const override;
    const cv::Mat &right_image() const override;

    void close();

private:
    // GStreamer pipeline string for a single Decklink device.
    static std::string build_pipeline(int device_number);

    int m_left_device;
    int m_right_device;

    cv::VideoCapture m_left_cap;
    cv::VideoCapture m_right_cap;

    cv::Mat m_left_img;
    cv::Mat m_right_img;

    bool m_opened = false;
    bool m_has_images = false;
};
