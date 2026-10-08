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
#include "stereo_video_client.h"

#include <chrono>
#include <string>

// Stereo video read from a running `video_source` process (stereo_video_source)
// over unixfd shared memory. Unlike DecklinkCameraInterface, the capture cards
// are owned by the source, so any number of clients can read the video at once.
class DecklinkUnixfdInterface : public StereoCameraInterface
{
public:
    explicit DecklinkUnixfdInterface(const std::string &source_name);

    // Connects to the source. If it is not running yet, logs a warning and
    // returns true anyway; grab() keeps retrying the connection.
    bool init() override;

    // Non-blocking: returns true only when a new stereo pair arrived.
    bool grab() override;
    bool has_received_stereo_images() const override;
    const cv::Mat &left_image() const override;
    const cv::Mat &right_image() const override;

private:
    bool try_connect();

    std::string m_source_name;
    stereo_video::StereoVideoClient m_client;
    std::chrono::steady_clock::time_point m_last_connect_attempt;
    bool m_warned_disconnected = false;
};
