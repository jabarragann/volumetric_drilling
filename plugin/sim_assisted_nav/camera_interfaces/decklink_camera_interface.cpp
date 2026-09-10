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

#include "decklink_camera_interface.h"

#include <glob.h>

#include <atomic>
#include <chrono>
#include <iostream>
#include <memory>
#include <sstream>
#include <thread>

using namespace std;

namespace
{
// A healthy Decklink pipeline prerolls in well under this. If opening takes
// longer we assume there is no capture hardware / driver, or no SDI signal.
constexpr int kDecklinkOpenTimeoutSeconds = 8;

// The Blackmagic `desktopvideo` driver creates /dev/blackmagic/* device nodes
// only when at least one card is present. Fast, dependency-free pre-check; the
// watchdog in init() is the real guarantee. If a future driver version puts the
// nodes elsewhere this can be removed without changing the graceful behaviour.
bool blackmagic_nodes_present()
{
    glob_t g{};
    bool found = (glob("/dev/blackmagic/*", 0, nullptr, &g) == 0 && g.gl_pathc > 0);
    globfree(&g);
    return found;
}
} // namespace

DecklinkCameraInterface::DecklinkCameraInterface(int left_device, int right_device)
    : m_left_device(left_device), m_right_device(right_device)
{
}

DecklinkCameraInterface::~DecklinkCameraInterface()
{
    close();
}

std::string DecklinkCameraInterface::build_pipeline(int device_number)
{
    std::stringstream ss;
    ss << "decklinkvideosrc device-number=" << device_number
       << " connection=sdi buffer-size=1"
       << " ! deinterlace fields=top"
       << " ! videoconvert"
       << " ! appsink drop=TRUE max-buffers=1";
    return ss.str();
}

bool DecklinkCameraInterface::init()
{
    if (m_opened || m_unavailable)
    {
        return true;
    }

    if (!blackmagic_nodes_present())
    {
        cerr << "\n===============================================================\n"
             << "WARNING! No Decklink capture card detected (no /dev/blackmagic/*\n"
             << "device nodes). The sim_assisted_nav plugin is configured with\n"
             << "  video_source: decklink   (left device-number " << m_left_device
             << ", right device-number " << m_right_device << ")\n"
             << "The plugin will keep running but the headset view will show no\n"
             << "camera images. Set 'video_source: ros' in the camera ADF, or run\n"
             << "on the capture PC that has the Decklink SDI card, to silence this.\n"
             << "===============================================================\n"
             << endl;
        m_unavailable = true;
        return true;
    }

    // cv::VideoCapture::open() on a decklinkvideosrc pipeline blocks with no
    // timeout when the element cannot preroll (missing hardware/driver, or no
    // SDI signal). Do the open on a detached worker thread writing into
    // heap-owned state, and give up after the watchdog timeout. The state is
    // kept alive by a shared_ptr so abandoning a wedged thread is safe.
    struct OpenState
    {
        std::atomic<bool> done{false};
        std::atomic<bool> ok{false};
        cv::VideoCapture left;
        cv::VideoCapture right;
    };
    auto state = std::make_shared<OpenState>();

    const std::string left_pipe = build_pipeline(m_left_device);
    const std::string right_pipe = build_pipeline(m_right_device);

    std::thread([state, left_pipe, right_pipe]()
                {
                    state->left.open(left_pipe, cv::CAP_GSTREAMER);
                    state->right.open(right_pipe, cv::CAP_GSTREAMER);
                    state->ok.store(state->left.isOpened() && state->right.isOpened());
                    state->done.store(true);
                })
        .detach();

    const auto deadline = std::chrono::steady_clock::now() +
                          std::chrono::seconds(kDecklinkOpenTimeoutSeconds);
    while (!state->done.load() && std::chrono::steady_clock::now() < deadline)
    {
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }

    if (!state->done.load())
    {
        cerr << "\n===============================================================\n"
             << "WARNING! Decklink capture card not responding. Opening the\n"
             << "GStreamer pipeline (left device-number " << m_left_device
             << ", right device-number " << m_right_device << ") did not\n"
             << "complete within " << kDecklinkOpenTimeoutSeconds << " s. This\n"
             << "machine most likely has no Decklink hardware, or there is no SDI\n"
             << "signal. The sim_assisted_nav plugin will keep running but the\n"
             << "headset view will show no camera images. Set 'video_source: ros'\n"
             << "in the camera ADF to silence this.\n"
             << "===============================================================\n"
             << endl;
        // The opener thread is wedged inside GStreamer. It is detached and owns
        // its VideoCapture objects through `state`; abandon both here.
        m_unavailable = true;
        return true;
    }

    if (!state->ok.load())
    {
        cerr << "WARNING! Failed to open Decklink GStreamer pipelines "
                "(left device-number " << m_left_device
             << ", right device-number " << m_right_device << "). "
                "Verify OpenCV was built with GStreamer support "
                "(cv::CAP_GSTREAMER). The headset view will show no camera "
                "images." << endl;
        m_unavailable = true;
        return true;
    }

    m_left_cap = std::move(state->left);
    m_right_cap = std::move(state->right);
    m_opened = true;
    return true;
}

void DecklinkCameraInterface::close()
{
    m_left_cap.release();
    m_right_cap.release();
    m_opened = false;
}

bool DecklinkCameraInterface::grab()
{
    if (m_unavailable)
    {
        return false;
    }

    if (!m_opened && !init())
    {
        return false;
    }

    // init() may return true without opening the devices (source unavailable).
    if (!m_opened)
    {
        return false;
    }

    // `videoconvert` in the pipeline already yields BGR frames.
    m_left_cap.read(m_left_img);
    m_right_cap.read(m_right_img);

    m_has_images = !m_left_img.empty() && !m_right_img.empty();
    return m_has_images;
}

bool DecklinkCameraInterface::has_received_stereo_images() const
{
    return m_has_images && !m_left_img.empty() && !m_right_img.empty();
}

const cv::Mat &DecklinkCameraInterface::left_image() const
{
    return m_left_img;
}

const cv::Mat &DecklinkCameraInterface::right_image() const
{
    return m_right_img;
}
