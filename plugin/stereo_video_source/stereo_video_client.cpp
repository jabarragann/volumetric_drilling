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

#include "stereo_video_client.h"
#include "stereo_video_common.h"

#include <gst/app/gstappsink.h>
#include <opencv2/imgproc.hpp>

#include <iostream>

using namespace std;

namespace stereo_video
{
StereoVideoClient::~StereoVideoClient()
{
    close();
}

bool StereoVideoClient::init(const std::string &name)
{
    if (m_pipeline)
    {
        return true;
    }
    if (!ensure_gst_initialized())
    {
        return false;
    }

    // appsink receives the source's shared-memory buffers directly; grab()
    // converts BGRx -> BGR, which is also the single copy out of shared memory.
    const std::string description =
        "unixfdsrc socket-path=" + socket_path_for(name) +
        " ! appsink name=sink caps=video/x-raw,format=BGRx sync=false max-buffers=1 drop=true";

    GError *error = nullptr;
    m_pipeline = gst_parse_launch(description.c_str(), &error);
    if (error)
    {
        cerr << "Failed to build stereo video client pipeline: " << error->message << endl;
        g_clear_error(&error);
        close();
        return false;
    }
    m_sink = gst_bin_get_by_name(GST_BIN(m_pipeline), "sink");

    // Fails when no source is serving on the socket; callers report it.
    if (gst_element_set_state(m_pipeline, GST_STATE_PLAYING) == GST_STATE_CHANGE_FAILURE)
    {
        close();
        return false;
    }
    return true;
}

bool StereoVideoClient::grab(int timeout_ms)
{
    if (!m_pipeline)
    {
        return false;
    }

    GstBus *bus = gst_pipeline_get_bus(GST_PIPELINE(m_pipeline));
    const bool failed = pop_bus_error(bus, "Stereo video client");
    gst_object_unref(bus);
    if (failed)
    {
        close();
        return false;
    }

    GstSample *sample = gst_app_sink_try_pull_sample(GST_APP_SINK(m_sink), timeout_ms * GST_MSECOND);
    if (!sample)
    {
        return false;
    }

    int width = 0;
    int height = 0;
    GstStructure *structure = gst_caps_get_structure(gst_sample_get_caps(sample), 0);
    gst_structure_get_int(structure, "width", &width);
    gst_structure_get_int(structure, "height", &height);

    GstBuffer *buffer = gst_sample_get_buffer(sample);
    GstMapInfo map;
    if (!buffer || height == 0 || !gst_buffer_map(buffer, &map, GST_MAP_READ))
    {
        gst_sample_unref(sample);
        return false;
    }

    const size_t stride = map.size / height;
    const cv::Mat frame(height, width, CV_8UC4, map.data, stride);
    const int half = width / 2;
    cv::cvtColor(frame(cv::Rect(0, 0, half, height)), m_left_img, cv::COLOR_BGRA2BGR);
    cv::cvtColor(frame(cv::Rect(half, 0, half, height)), m_right_img, cv::COLOR_BGRA2BGR);

    gst_buffer_unmap(buffer, &map);
    gst_sample_unref(sample);
    return true;
}

void StereoVideoClient::close()
{
    if (m_sink)
    {
        gst_object_unref(m_sink);
        m_sink = nullptr;
    }
    if (m_pipeline)
    {
        gst_element_set_state(m_pipeline, GST_STATE_NULL);
        gst_object_unref(m_pipeline);
        m_pipeline = nullptr;
    }
}
} // namespace stereo_video
