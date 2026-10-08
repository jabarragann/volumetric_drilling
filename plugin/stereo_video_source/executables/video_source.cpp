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

// Runs the stereo video source: captures left/right Decklink inputs and serves
// them to any number of clients (viewer, AMBF plugin, ...). Stop with Ctrl+C.

#include "stereo_video_common.h"
#include "stereo_video_source.h"

#include <boost/program_options.hpp>
#include <glib-unix.h>

#include <csignal>
#include <iostream>

using namespace std;
namespace po = boost::program_options;

static gboolean on_sigint(gpointer user_data)
{
    cout << "\nCaught SIGINT, stopping..." << endl;
    g_main_loop_quit(static_cast<GMainLoop *>(user_data));
    return G_SOURCE_REMOVE;
}

static gboolean on_bus_message(GstBus *, GstMessage *msg, gpointer user_data)
{
    if (GST_MESSAGE_TYPE(msg) == GST_MESSAGE_ERROR)
    {
        GError *error = nullptr;
        gchar *debug = nullptr;
        gst_message_parse_error(msg, &error, &debug);
        cerr << "Stereo video source error: " << error->message << "\n  debug: " << (debug ? debug : "") << endl;
        g_clear_error(&error);
        g_free(debug);
        g_main_loop_quit(static_cast<GMainLoop *>(user_data));
    }
    else if (GST_MESSAGE_TYPE(msg) == GST_MESSAGE_EOS)
    {
        cerr << "Stereo video source: end of stream" << endl;
        g_main_loop_quit(static_cast<GMainLoop *>(user_data));
    }
    return TRUE;
}

int main(int argc, char **argv)
{
    stereo_video::StereoVideoSourceConfig config;

    po::options_description desc("Stereo video source options");
    desc.add_options()
        ("help,h", "Show this help")
        ("name,n", po::value(&config.name)->default_value(config.name), "Source name clients connect to")
        ("left,l", po::value(&config.left_device)->default_value(config.left_device), "Left Decklink device number")
        ("right,r", po::value(&config.right_device)->default_value(config.right_device), "Right Decklink device number")
        ("connection", po::value(&config.connection)->default_value(config.connection), "Decklink connection (sdi, hdmi, ...)")
        ("mode", po::value(&config.mode)->default_value(config.mode), "Decklink mode (auto, 1080i5994, 1080p60, ...)")
        ("width", po::value(&config.width)->default_value(config.width), "Per-eye output width")
        ("height", po::value(&config.height)->default_value(config.height), "Per-eye output height")
        ("test", po::bool_switch(&config.test_pattern), "Use test patterns instead of the Decklink card");

    po::variables_map vm;
    try
    {
        po::store(po::parse_command_line(argc, argv, desc), vm);
        po::notify(vm);
    }
    catch (const po::error &e)
    {
        cerr << e.what() << "\n" << desc << endl;
        return 1;
    }
    if (vm.count("help"))
    {
        cout << desc << endl;
        return 0;
    }

    if (!stereo_video::ensure_gst_initialized())
    {
        return 1;
    }

    stereo_video::StereoVideoSource source(config);
    cout << "Pipeline: " << source.pipeline_description() << endl;
    if (!source.start())
    {
        cerr << "Failed to start stereo video source" << endl;
        return 1;
    }

    GMainLoop *loop = g_main_loop_new(nullptr, FALSE);
    g_unix_signal_add(SIGINT, on_sigint, loop);
    GstBus *bus = source.bus();
    const guint bus_watch_id = gst_bus_add_watch(bus, on_bus_message, loop);
    gst_object_unref(bus);

    cout << "Serving stereo video '" << config.name << "' on " << source.socket_path() << endl;
    g_main_loop_run(loop);

    g_source_remove(bus_watch_id);
    source.stop();
    g_main_loop_unref(loop);
    return 0;
}
