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

#include <gio/gio.h>
#include <gst/gst.h>

#include <filesystem>
#include <iostream>
#include <string>

// Shared helpers for the stereo video source (1 producer) and its clients (N
// consumers). The source publishes side-by-side BGRx frames (left | right) on a
// unix socket through `unixfdsink`; every client connects with `unixfdsrc` and
// receives the frames as shared-memory file descriptors (no per-client copy in
// the source).
namespace stereo_video
{
// Socket the source and clients rendezvous on. Unix socket paths are limited to
// 107 characters, so keep this short.
inline std::string socket_path_for(const std::string &name)
{
    return "/tmp/stereo_video_" + name + ".socket";
}

// Removes a stale socket left by a crashed source. Returns false if another
// source is still serving on it.
inline bool claim_socket(const std::string &socket_path)
{
    if (!std::filesystem::exists(socket_path))
    {
        return true;
    }

    // If something accepts connections on the socket, another source owns it.
    GSocketClient *client = g_socket_client_new();
    GSocketAddress *address = g_unix_socket_address_new(socket_path.c_str());
    GSocketConnection *connection =
        g_socket_client_connect(client, G_SOCKET_CONNECTABLE(address), nullptr, nullptr);
    g_object_unref(address);
    g_object_unref(client);
    if (connection)
    {
        g_object_unref(connection);
        std::cerr << "Another stereo video source is already running on " << socket_path << std::endl;
        return false;
    }

    std::filesystem::remove(socket_path);
    return true;
}

inline bool ensure_gst_initialized()
{
    if (gst_is_initialized())
    {
        return true;
    }

    GError *error = nullptr;
    if (!gst_init_check(nullptr, nullptr, &error))
    {
        std::cerr << "Failed to initialize GStreamer: " << error->message << std::endl;
        g_clear_error(&error);
        return false;
    }
    return true;
}

// Prints and consumes an error message from `bus`, if there is one. Returns
// true when an error (or end of stream) was found.
inline bool pop_bus_error(GstBus *bus, const std::string &context)
{
    bool failed = false;
    while (GstMessage *msg = gst_bus_pop_filtered(bus, GstMessageType(GST_MESSAGE_ERROR | GST_MESSAGE_EOS)))
    {
        if (GST_MESSAGE_TYPE(msg) == GST_MESSAGE_ERROR)
        {
            GError *error = nullptr;
            gchar *debug = nullptr;
            gst_message_parse_error(msg, &error, &debug);
            std::cerr << context << " error: " << error->message << std::endl;
            if (debug)
            {
                std::cerr << "  debug: " << debug << std::endl;
            }
            g_clear_error(&error);
            g_free(debug);
        }
        else
        {
            std::cerr << context << ": end of stream" << std::endl;
        }
        gst_message_unref(msg);
        failed = true;
    }
    return failed;
}
} // namespace stereo_video
