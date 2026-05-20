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

#include <iostream>
#include <sstream>

using namespace std;

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
    if (m_opened)
    {
        return true;
    }

    m_left_cap.open(build_pipeline(m_left_device), cv::CAP_GSTREAMER);
    m_right_cap.open(build_pipeline(m_right_device), cv::CAP_GSTREAMER);

    if (!m_left_cap.isOpened() || !m_right_cap.isOpened())
    {
        cerr << "ERROR! Failed to open Decklink GStreamer pipelines "
                "(left device-number " << m_left_device
             << ", right device-number " << m_right_device << "). "
                "Verify both devices are connected and that OpenCV was built "
                "with GStreamer support (cv::CAP_GSTREAMER)." << endl;
        close();
        return false;
    }

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
    if (!m_opened && !init())
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
