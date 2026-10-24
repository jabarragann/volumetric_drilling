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

#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace stereo_video
{
struct StereoVideoReplayConfig
{
    // dvrk_data session directory (the one holding index.json).
    std::string session_dir;

    // Video stream to replay; empty picks the first stream in index.json.
    std::string stream;

    // Clients find the source by this name, as with StereoVideoSource.
    std::string name = "camera";

    // Added to every frame timestamp: positive values show the video later.
    int64_t offset_ns = 0;
};

// Replays a video recorded by dvrk_data's `record` as if it were a live
// StereoVideoSource. Frames are only published when the replay time (set with
// set_time(), e.g. from the ROS /clock of `ros2 bag play --clock`) reaches the
// frame's recorder reception timestamp, so the video follows the bag's
// pause/rate/seek/loop.
class StereoVideoReplay
{
public:
    explicit StereoVideoReplay(const StereoVideoReplayConfig &config);
    ~StereoVideoReplay();

    StereoVideoReplay(const StereoVideoReplay &) = delete;
    StereoVideoReplay &operator=(const StereoVideoReplay &) = delete;

    // Loads the session, builds the pipelines and starts the publishing
    // thread. Returns false on failure.
    bool start();
    void stop();

    // Replay time, in the recording's CLOCK_REALTIME nanoseconds. Thread safe.
    void set_time(int64_t time_ns);

    // False once a pipeline failed (error already printed).
    bool ok() const { return !m_failed; }

    const std::string &socket_path() const { return m_socket_path; }
    const std::string &video_path() const { return m_video_path; }
    size_t frame_count() const { return m_frame_time_ns.size(); }
    int64_t first_frame_time_ns() const { return m_frame_time_ns.front(); }
    int64_t last_frame_time_ns() const { return m_frame_time_ns.back(); }

private:
    bool load_session();
    void run();

    // Index of the frame to display at `time_ns`, or -1 before the first frame.
    long frame_for_time(int64_t time_ns) const;
    // Index of the decoded frame with media timestamp `pts_ns`.
    long frame_for_pts(GstClockTime pts_ns) const;

    // Pulls decoded frames until frame `target` (or a later one) is reached,
    // updating `decoded` to the last pulled frame. Returns the sample, or
    // nullptr on end of stream / stop.
    GstSample *decode_until(long target, long &decoded);
    void seek_to(long frame);
    void publish(GstSample *sample);
    bool check_bus(GstElement *pipeline, const char *context);

    StereoVideoReplayConfig m_config;
    std::string m_socket_path;
    std::string m_video_path;

    // Per frame: recorder reception time (+ offset) and media time in the MP4.
    std::vector<int64_t> m_frame_time_ns;
    std::vector<int64_t> m_frame_pts_ns;

    GstElement *m_decoder = nullptr;
    GstElement *m_decoder_sink = nullptr;
    GstElement *m_output = nullptr;
    GstElement *m_output_src = nullptr;

    std::thread m_thread;
    std::mutex m_mutex;
    std::condition_variable m_cv;
    int64_t m_time_ns = 0;
    bool m_has_time = false;
    std::atomic<bool> m_stop{false};
    std::atomic<bool> m_failed{false};
    bool m_owns_socket = false;
    bool m_warned_copy = false;
};
} // namespace stereo_video
