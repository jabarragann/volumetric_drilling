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

#include "decklink_unixfd_interface.h"

#include <iostream>

using namespace std;

namespace
{
// How often grab() retries connecting while the source is not running.
constexpr std::chrono::seconds kReconnectPeriod(1);
} // namespace

DecklinkUnixfdInterface::DecklinkUnixfdInterface(const std::string &source_name)
    : m_source_name(source_name)
{
}

bool DecklinkUnixfdInterface::try_connect()
{
    m_last_connect_attempt = std::chrono::steady_clock::now();
    if (m_client.init(m_source_name))
    {
        cout << "INFO! Connected to stereo video source '" << m_source_name << "'" << endl;
        m_warned_disconnected = false;
        return true;
    }

    if (!m_warned_disconnected)
    {
        cerr << "WARNING! Stereo video source '" << m_source_name << "' is not running. "
             << "Start it with `ros2 run simulation_assisted_navigation_framework video_source`. "
             << "Retrying every " << kReconnectPeriod.count() << " s." << endl;
        m_warned_disconnected = true;
    }
    return false;
}

bool DecklinkUnixfdInterface::init()
{
    try_connect();
    return true;
}

bool DecklinkUnixfdInterface::grab()
{
    if (!m_client.is_connected())
    {
        if (std::chrono::steady_clock::now() - m_last_connect_attempt < kReconnectPeriod || !try_connect())
        {
            return false;
        }
    }

    // Called from the render loop: never wait for a frame.
    return m_client.grab(0);
}

bool DecklinkUnixfdInterface::has_received_stereo_images() const
{
    return m_client.has_received_stereo_images();
}

const cv::Mat &DecklinkUnixfdInterface::left_image() const
{
    return m_client.left_image();
}

const cv::Mat &DecklinkUnixfdInterface::right_image() const
{
    return m_client.right_image();
}
