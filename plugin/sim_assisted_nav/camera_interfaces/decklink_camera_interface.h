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

    // Opens the Decklink pipelines behind a watchdog. If no capture hardware
    // responds (no card / driver, or no SDI signal) it logs a warning, marks
    // the source unavailable, and still returns true so the plugin keeps
    // running; grab() then permanently reports "no frames".
    bool init() override;
    bool grab() override;
    bool has_received_stereo_images() const override;
    const cv::Mat &left_image() const override;
    const cv::Mat &right_image() const override;

    // True once init() has concluded there is no usable Decklink source.
    bool is_unavailable() const { return m_unavailable; }

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

    // Set when the pipelines could not be opened within the watchdog timeout
    // (or a fast pre-check found no Decklink device). Once set, init() and
    // grab() short-circuit so the missing hardware never stalls the sim again.
    bool m_unavailable = false;
};
