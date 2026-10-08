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

#include "stereo_video_source.h"
#include "stereo_video_common.h"

#include <gio/gio.h>

#include <filesystem>
#include <iostream>
#include <sstream>

using namespace std;

namespace stereo_video
{
StereoVideoSource::StereoVideoSource(const StereoVideoSourceConfig &config)
    : m_config(config), m_socket_path(socket_path_for(config.name))
{
}

StereoVideoSource::~StereoVideoSource()
{
    stop();
}

std::string StereoVideoSource::build_eye_branch(int device, int compositor_pad) const
{
    std::stringstream ss;
    if (m_config.test_pattern)
    {
        ss << "videotestsrc is-live=true pattern=" << (compositor_pad == 0 ? "smpte" : "ball")
           << " ! video/x-raw,framerate=60/1";
    }
    else
    {
        // Same capture settings as DecklinkCameraInterface.
        ss << "decklinkvideosrc device-number=" << device
           << " connection=" << m_config.connection
           << " mode=" << m_config.mode
           << " ! deinterlace fields=top";
    }
    // Normalize each eye so the compositor always sees the same size/format.
    ss << " ! videoconvert ! videoscale"
       << " ! video/x-raw,format=BGRx,width=" << m_config.width << ",height=" << m_config.height
       << " ! queue leaky=downstream max-size-buffers=1"
       << " ! mix.sink_" << compositor_pad << " ";
    return ss.str();
}

std::string StereoVideoSource::pipeline_description() const
{
    std::stringstream ss;
    ss << "compositor name=mix background=black sink_1::xpos=" << m_config.width
       << " ! video/x-raw,format=BGRx,width=" << 2 * m_config.width << ",height=" << m_config.height
       << " ! queue leaky=downstream max-size-buffers=1"
       << " ! unixfdsink socket-path=" << m_socket_path << " sync=false "
       << build_eye_branch(m_config.left_device, 0)
       << build_eye_branch(m_config.right_device, 1);
    return ss.str();
}

bool StereoVideoSource::claim_socket() const
{
    if (!std::filesystem::exists(m_socket_path))
    {
        return true;
    }

    // If something accepts connections on the socket, another source owns it.
    GSocketClient *client = g_socket_client_new();
    GSocketAddress *address = g_unix_socket_address_new(m_socket_path.c_str());
    GSocketConnection *connection =
        g_socket_client_connect(client, G_SOCKET_CONNECTABLE(address), nullptr, nullptr);
    g_object_unref(address);
    g_object_unref(client);
    if (connection)
    {
        g_object_unref(connection);
        cerr << "Another stereo video source is already running on " << m_socket_path << endl;
        return false;
    }

    std::filesystem::remove(m_socket_path);
    return true;
}

bool StereoVideoSource::start()
{
    if (m_pipeline)
    {
        return true;
    }

    if (!ensure_gst_initialized() || !claim_socket())
    {
        return false;
    }

    const std::string description = pipeline_description();
    GError *error = nullptr;
    m_pipeline = gst_parse_launch(description.c_str(), &error);
    if (error)
    {
        cerr << "Failed to build stereo video source pipeline: " << error->message << endl;
        g_clear_error(&error);
        if (m_pipeline)
        {
            gst_object_unref(m_pipeline);
            m_pipeline = nullptr;
        }
        return false;
    }

    if (gst_element_set_state(m_pipeline, GST_STATE_PLAYING) == GST_STATE_CHANGE_FAILURE)
    {
        GstBus *pipeline_bus = bus();
        pop_bus_error(pipeline_bus, "Stereo video source");
        gst_object_unref(pipeline_bus);
        stop();
        return false;
    }
    return true;
}

void StereoVideoSource::stop()
{
    if (!m_pipeline)
    {
        return;
    }
    gst_element_set_state(m_pipeline, GST_STATE_NULL);
    gst_object_unref(m_pipeline);
    m_pipeline = nullptr;
    std::filesystem::remove(m_socket_path);
}

GstBus *StereoVideoSource::bus() const
{
    return m_pipeline ? gst_pipeline_get_bus(GST_PIPELINE(m_pipeline)) : nullptr;
}
} // namespace stereo_video
