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

#include <gst/gst.h>
#include <opencv2/core.hpp>

#include <string>

namespace stereo_video
{
// Connects to a running StereoVideoSource (found by name) and splits its
// side-by-side frames into left/right BGR images. Any number of clients, in
// any number of processes, can be connected to the same source.
class StereoVideoClient
{
public:
    StereoVideoClient() = default;
    ~StereoVideoClient();

    StereoVideoClient(const StereoVideoClient &) = delete;
    StereoVideoClient &operator=(const StereoVideoClient &) = delete;

    // Connects to the source. Silently returns false if the source is not running.
    bool init(const std::string &name = "camera");

    // Waits up to timeout_ms for the next frame. Returns false on timeout or
    // if the connection to the source was lost (see is_connected()).
    bool grab(int timeout_ms = 100);

    bool is_connected() const { return m_pipeline != nullptr; }
    bool has_received_stereo_images() const { return !m_left_img.empty() && !m_right_img.empty(); }

    // Deep copies owned by the client; overwritten by the next grab().
    const cv::Mat &left_image() const { return m_left_img; }
    const cv::Mat &right_image() const { return m_right_img; }

    void close();

private:
    GstElement *m_pipeline = nullptr;
    GstElement *m_sink = nullptr;

    cv::Mat m_left_img;
    cv::Mat m_right_img;
};
} // namespace stereo_video
