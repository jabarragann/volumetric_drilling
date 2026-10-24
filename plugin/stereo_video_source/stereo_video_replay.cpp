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

#include "stereo_video_replay.h"
#include "stereo_video_common.h"

#include <gst/allocators/allocators.h>
#include <gst/app/gstappsink.h>
#include <gst/app/gstappsrc.h>
#include <nlohmann/json.hpp>

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>

using namespace std;
namespace fs = std::filesystem;
using json = nlohmann::json;

namespace stereo_video
{
namespace
{
// Larger forward jumps seek instead of decoding every frame in between.
// dvrk_data records with a keyframe at least every 30 frames, so seeking is cheap.
constexpr long kMaxDecodeAhead = 30;

// While the replay time does not move (bag paused), the current frame is
// re-sent this often so that clients connecting late still get an image.
constexpr chrono::milliseconds kRepublishPeriod(500);

// unixfdsink only accepts fd-backed memory. Proposing the shm allocator to the
// decoder makes videoconvert write frames straight into memfd memory, so they
// are published without a copy.
GstPadProbeReturn propose_shm_allocator(GstPad *, GstPadProbeInfo *info, gpointer)
{
    GstQuery *query = GST_PAD_PROBE_INFO_QUERY(info);
    if (GST_QUERY_TYPE(query) == GST_QUERY_ALLOCATION)
    {
        GstAllocator *shm = gst_shm_allocator_get();
        gst_query_add_allocation_param(query, shm, nullptr);
        gst_object_unref(shm);
    }
    return GST_PAD_PROBE_OK;
}

bool is_fd_backed(GstBuffer *buffer)
{
    for (guint i = 0; i < gst_buffer_n_memory(buffer); ++i)
    {
        if (!gst_is_fd_memory(gst_buffer_peek_memory(buffer, i)))
        {
            return false;
        }
    }
    return true;
}

bool read_json(const fs::path &path, json &out)
{
    ifstream file(path);
    if (!file)
    {
        cerr << "Cannot open " << path << endl;
        return false;
    }
    try
    {
        file >> out;
    }
    catch (const json::exception &e)
    {
        cerr << "Cannot parse " << path << ": " << e.what() << endl;
        return false;
    }
    return true;
}
} // namespace

StereoVideoReplay::StereoVideoReplay(const StereoVideoReplayConfig &config)
    : m_config(config), m_socket_path(socket_path_for(config.name))
{
}

StereoVideoReplay::~StereoVideoReplay()
{
    stop();
}

bool StereoVideoReplay::load_session()
{
    const fs::path session(m_config.session_dir);
    json index;
    if (!read_json(session / "index.json", index))
    {
        return false;
    }

    const json *stream = nullptr;
    const json &streams = index["streams"];
    for (size_t i = 0; streams.is_array() && i < streams.size(); ++i)
    {
        if (m_config.stream.empty() || streams[i].value("name", "") == m_config.stream)
        {
            stream = &streams[i];
            break;
        }
    }
    if (!stream || !stream->contains("videos") || !(*stream)["videos"].is_array() || (*stream)["videos"].empty())
    {
        cerr << "No video stream '" << m_config.stream << "' in " << session / "index.json" << endl;
        return false;
    }
    const json &videos = (*stream)["videos"];
    if (videos.size() > 1)
    {
        cerr << "WARNING! Stream '" << stream->value("name", "") << "' has " << videos.size()
             << " segments; only the first one is replayed." << endl;
    }

    // The recorder writes <stem>.mp4 next to its frame-timestamp file <stem>.json.
    const fs::path video = session / videos[0].value("file", "");
    json sidecar;
    if (!read_json(fs::path(video).replace_extension(".json"), sidecar))
    {
        return false;
    }
    m_video_path = video.string();

    const json &frames = sidecar["frames"];
    if (!frames.is_array() || frames.empty())
    {
        cerr << "No frames in the timestamp file of " << video << endl;
        return false;
    }

    m_frame_time_ns.clear();
    m_frame_pts_ns.clear();
    const json &first_pts = frames[0]["gst"]["pts_ns"];
    for (const json &frame : frames)
    {
        const json &reception = frame["cpu"]["realtime"]["recorder_reception_ns"];
        if (!reception.is_number_integer())
        {
            cerr << "Frame " << frame.value("frame_index", -1) << " has no recorder_reception_ns" << endl;
            return false;
        }
        // Keep the times sorted so frame_for_time() can binary search them.
        int64_t time_ns = reception.get<int64_t>() + m_config.offset_ns;
        if (!m_frame_time_ns.empty())
        {
            time_ns = max(time_ns, m_frame_time_ns.back());
        }
        m_frame_time_ns.push_back(time_ns);

        // MP4 media time = recording pipeline PTS relative to the first frame.
        const json &pts = frame["gst"]["pts_ns"];
        const json &duration = frame["gst"]["duration_ns"];
        if (pts.is_number_integer() && first_pts.is_number_integer())
        {
            m_frame_pts_ns.push_back(pts.get<int64_t>() - first_pts.get<int64_t>());
        }
        else
        {
            const int64_t step = duration.is_number_integer() ? duration.get<int64_t>() : 33366667;
            m_frame_pts_ns.push_back(m_frame_pts_ns.empty() ? 0 : m_frame_pts_ns.back() + step);
        }
    }
    return true;
}

bool StereoVideoReplay::start()
{
    if (m_decoder)
    {
        return true;
    }
    if (!ensure_gst_initialized() || !load_session() || !claim_socket(m_socket_path))
    {
        return false;
    }
    m_owns_socket = true;

    GError *error = nullptr;
    m_decoder = gst_parse_launch(
        "filesrc name=file ! decodebin ! videoconvert n-threads=4 ! video/x-raw,format=BGRx"
        " ! appsink name=sink sync=false max-buffers=4",
        &error);
    if (!error)
    {
        const string output = "appsrc name=src is-live=true format=time do-timestamp=true"
                              " ! unixfdsink socket-path=" + m_socket_path + " sync=false";
        m_output = gst_parse_launch(output.c_str(), &error);
    }
    if (error)
    {
        cerr << "Failed to build stereo video replay pipeline: " << error->message << endl;
        g_clear_error(&error);
        stop();
        return false;
    }

    GstElement *file = gst_bin_get_by_name(GST_BIN(m_decoder), "file");
    g_object_set(file, "location", m_video_path.c_str(), nullptr);
    gst_object_unref(file);
    m_decoder_sink = gst_bin_get_by_name(GST_BIN(m_decoder), "sink");
    gst_shm_allocator_init_once();
    GstPad *sink_pad = gst_element_get_static_pad(m_decoder_sink, "sink");
    gst_pad_add_probe(sink_pad, GstPadProbeType(GST_PAD_PROBE_TYPE_QUERY_DOWNSTREAM | GST_PAD_PROBE_TYPE_PUSH),
                      propose_shm_allocator, nullptr, nullptr);
    gst_object_unref(sink_pad);
    m_output_src = gst_bin_get_by_name(GST_BIN(m_output), "src");

    if (gst_element_set_state(m_decoder, GST_STATE_PLAYING) == GST_STATE_CHANGE_FAILURE ||
        gst_element_set_state(m_output, GST_STATE_PLAYING) == GST_STATE_CHANGE_FAILURE)
    {
        check_bus(m_decoder, "Stereo video replay decoder");
        check_bus(m_output, "Stereo video replay output");
        stop();
        return false;
    }

    m_stop = false;
    m_failed = false;
    m_thread = thread(&StereoVideoReplay::run, this);
    return true;
}

void StereoVideoReplay::stop()
{
    {
        lock_guard<mutex> lock(m_mutex);
        m_stop = true;
    }
    m_cv.notify_all();
    if (m_thread.joinable())
    {
        m_thread.join();
    }

    for (GstElement **element : {&m_decoder_sink, &m_output_src})
    {
        if (*element)
        {
            gst_object_unref(*element);
            *element = nullptr;
        }
    }
    for (GstElement **pipeline : {&m_decoder, &m_output})
    {
        if (*pipeline)
        {
            gst_element_set_state(*pipeline, GST_STATE_NULL);
            gst_object_unref(*pipeline);
            *pipeline = nullptr;
        }
    }
    // Never remove the socket of another source that refused our claim.
    if (m_owns_socket)
    {
        error_code ec;
        fs::remove(m_socket_path, ec);
        m_owns_socket = false;
    }
}

void StereoVideoReplay::set_time(int64_t time_ns)
{
    {
        lock_guard<mutex> lock(m_mutex);
        m_time_ns = time_ns;
        m_has_time = true;
    }
    m_cv.notify_one();
}

long StereoVideoReplay::frame_for_time(int64_t time_ns) const
{
    return long(upper_bound(m_frame_time_ns.begin(), m_frame_time_ns.end(), time_ns) - m_frame_time_ns.begin()) - 1;
}

long StereoVideoReplay::frame_for_pts(GstClockTime pts_ns) const
{
    const auto it = lower_bound(m_frame_pts_ns.begin(), m_frame_pts_ns.end(), int64_t(pts_ns));
    long index = long(it - m_frame_pts_ns.begin());
    if (index == long(m_frame_pts_ns.size()) ||
        (index > 0 && int64_t(pts_ns) - m_frame_pts_ns[index - 1] < m_frame_pts_ns[index] - int64_t(pts_ns)))
    {
        --index;
    }
    return index;
}

bool StereoVideoReplay::check_bus(GstElement *pipeline, const char *context)
{
    GstBus *bus = gst_element_get_bus(pipeline);
    bool failed = false;
    while (GstMessage *msg = gst_bus_pop_filtered(bus, GST_MESSAGE_ERROR))
    {
        GError *error = nullptr;
        gchar *debug = nullptr;
        gst_message_parse_error(msg, &error, &debug);
        cerr << context << " error: " << error->message << "\n  debug: " << (debug ? debug : "") << endl;
        g_clear_error(&error);
        g_free(debug);
        gst_message_unref(msg);
        failed = true;
    }
    gst_object_unref(bus);
    return !failed;
}

void StereoVideoReplay::seek_to(long frame)
{
    const auto flags = GstSeekFlags(GST_SEEK_FLAG_FLUSH | GST_SEEK_FLAG_ACCURATE);
    if (!gst_element_seek_simple(m_decoder, GST_FORMAT_TIME, flags, m_frame_pts_ns[frame]))
    {
        cerr << "WARNING! Seek to frame " << frame << " failed" << endl;
    }
}

GstSample *StereoVideoReplay::decode_until(long target, long &decoded)
{
    while (!m_stop)
    {
        GstSample *sample = gst_app_sink_try_pull_sample(GST_APP_SINK(m_decoder_sink), 100 * GST_MSECOND);
        if (!sample)
        {
            if (gst_app_sink_is_eos(GST_APP_SINK(m_decoder_sink)) ||
                !check_bus(m_decoder, "Stereo video replay decoder"))
            {
                return nullptr;
            }
            continue;
        }

        decoded = frame_for_pts(GST_BUFFER_PTS(gst_sample_get_buffer(sample)));
        if (decoded >= target)
        {
            return sample;
        }
        gst_sample_unref(sample);
    }
    return nullptr;
}

void StereoVideoReplay::publish(GstSample *sample)
{
    GstCaps *caps = gst_app_src_get_caps(GST_APP_SRC(m_output_src));
    if (!caps || !gst_caps_is_equal(caps, gst_sample_get_caps(sample)))
    {
        gst_app_src_set_caps(GST_APP_SRC(m_output_src), gst_sample_get_caps(sample));
    }
    if (caps)
    {
        gst_caps_unref(caps);
    }

    // Shallow copy (shares the frame memory) when the frame is already in fd
    // memory; otherwise copy it into shm memory, which unixfdsink can send.
    GstBuffer *source = gst_sample_get_buffer(sample);
    GstBuffer *buffer = nullptr;
    if (is_fd_backed(source))
    {
        buffer = gst_buffer_copy(source);
    }
    else
    {
        if (!m_warned_copy)
        {
            cerr << "WARNING! Decoder did not use shm memory; copying every frame." << endl;
            m_warned_copy = true;
        }
        GstAllocator *shm = gst_shm_allocator_get();
        buffer = gst_buffer_new_allocate(shm, gst_buffer_get_size(source), nullptr);
        gst_object_unref(shm);
        gst_buffer_copy_into(buffer, source, GST_BUFFER_COPY_METADATA, 0, -1);
        GstMapInfo map;
        if (gst_buffer_map(source, &map, GST_MAP_READ))
        {
            gst_buffer_fill(buffer, 0, map.data, map.size);
            gst_buffer_unmap(source, &map);
        }
    }
    // appsrc stamps it with the output pipeline's running time instead of the
    // file's media time.
    GST_BUFFER_PTS(buffer) = GST_CLOCK_TIME_NONE;
    GST_BUFFER_DTS(buffer) = GST_CLOCK_TIME_NONE;
    GST_BUFFER_DURATION(buffer) = GST_CLOCK_TIME_NONE;
    gst_app_src_push_buffer(GST_APP_SRC(m_output_src), buffer);
}

void StereoVideoReplay::run()
{
    long current = -1; // frame clients are seeing
    long decoded = -1; // last frame pulled from the decoder
    GstSample *last = nullptr;

    while (!m_stop)
    {
        long target = -1;
        bool changed = false;
        {
            unique_lock<mutex> lock(m_mutex);
            changed = m_cv.wait_for(lock, kRepublishPeriod, [&] {
                return m_stop || (m_has_time && frame_for_time(m_time_ns) != current);
            });
            if (m_has_time)
            {
                target = frame_for_time(m_time_ns);
            }
        }
        if (m_stop)
        {
            break;
        }
        if (!check_bus(m_decoder, "Stereo video replay decoder") || !check_bus(m_output, "Stereo video replay output"))
        {
            m_failed = true;
            break;
        }

        if (!changed)
        {
            if (last)
            {
                publish(last);
            }
            continue;
        }
        if (target < 0)
        {
            // Replay time is before the first frame (e.g. bag looped back).
            current = target;
            continue;
        }

        if (target <= decoded || target > decoded + kMaxDecodeAhead)
        {
            seek_to(target);
            decoded = target - 1;
        }
        GstSample *sample = decode_until(target, decoded);
        if (!sample)
        {
            // End of the file: keep showing the last frame.
            current = target;
            continue;
        }

        current = decoded;
        publish(sample);
        if (last)
        {
            gst_sample_unref(last);
        }
        last = sample;
    }

    if (last)
    {
        gst_sample_unref(last);
    }
}
} // namespace stereo_video
