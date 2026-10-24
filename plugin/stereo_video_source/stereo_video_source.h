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

#include <string>

namespace stereo_video
{
struct StereoVideoSourceConfig
{
    // Clients find the source by this name; must be unique per running source.
    std::string name = "camera";

    int left_device = 0;
    int right_device = 1;
    std::string connection = "sdi"; // decklinkvideosrc connection (sdi, hdmi, ...)
    std::string mode = "1080i5994"; // decklinkvideosrc mode (auto, 1080i5994, 1080p60, ...)

    // Each eye is scaled to this size; the published frame is (2 * width) x height.
    int width = 1920;
    int height = 1080;

    // Use videotestsrc patterns instead of the Decklink card.
    bool test_pattern = false;
};

// Captures left/right video, composes them side by side (left | right) and
// publishes the result to any number of clients through `unixfdsink`.
class StereoVideoSource
{
public:
    explicit StereoVideoSource(const StereoVideoSourceConfig &config);
    ~StereoVideoSource();

    StereoVideoSource(const StereoVideoSource &) = delete;
    StereoVideoSource &operator=(const StereoVideoSource &) = delete;

    // Builds the pipeline and sets it to PLAYING. Returns false on failure.
    bool start();
    void stop();

    // Pipeline bus; caller must gst_object_unref() it. Null before start().
    GstBus *bus() const;

    const std::string &socket_path() const { return m_socket_path; }

    // The gst-launch style pipeline description, exposed for logging.
    std::string pipeline_description() const;

private:
    std::string build_eye_branch(int device, int compositor_pad) const;

    StereoVideoSourceConfig m_config;
    std::string m_socket_path;
    GstElement *m_pipeline = nullptr;
};
} // namespace stereo_video
