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

#include "zed_camera_interface.h"
#include <opencv2/imgproc.hpp>
#include <iostream>

using namespace std;

// Wrap a sl::Mat (CPU memory) in a cv::Mat header without copying data.
static cv::Mat slMat2cvMat(sl::Mat &input)
{
    int cv_type = -1;
    switch (input.getDataType())
    {
    case sl::MAT_TYPE::F32_C1: cv_type = CV_32FC1; break;
    case sl::MAT_TYPE::F32_C2: cv_type = CV_32FC2; break;
    case sl::MAT_TYPE::F32_C3: cv_type = CV_32FC3; break;
    case sl::MAT_TYPE::F32_C4: cv_type = CV_32FC4; break;
    case sl::MAT_TYPE::U8_C1:  cv_type = CV_8UC1;  break;
    case sl::MAT_TYPE::U8_C2:  cv_type = CV_8UC2;  break;
    case sl::MAT_TYPE::U8_C3:  cv_type = CV_8UC3;  break;
    case sl::MAT_TYPE::U8_C4:  cv_type = CV_8UC4;  break;
    default: break;
    }
    return cv::Mat(input.getHeight(), input.getWidth(), cv_type,
                   input.getPtr<sl::uchar1>(sl::MEM::CPU));
}

ZedCameraInterface::ZedCameraInterface()
{
}

ZedCameraInterface::~ZedCameraInterface()
{
    close();
}

bool ZedCameraInterface::init()
{
    if (m_opened)
    {
        return true;
    }

    sl::InitParameters init_parameters;
    init_parameters.camera_resolution = sl::RESOLUTION::HD720;
    init_parameters.camera_fps = 30;

    auto state = m_zed.open(init_parameters);
    if (state != sl::ERROR_CODE::SUCCESS)
    {
        cerr << "ERROR! Failed to open ZED camera: " << state << endl;
        return false;
    }
    m_opened = true;
    return true;
}

void ZedCameraInterface::close()
{
    if (m_opened)
    {
        m_zed.close();
        m_opened = false;
    }
}

bool ZedCameraInterface::grab()
{
    if (!m_opened && !init())
    {
        return false;
    }

    if (m_zed.grab() != sl::ERROR_CODE::SUCCESS)
    {
        return false;
    }

    m_zed.retrieveImage(m_zed_left, sl::VIEW::LEFT);
    m_zed.retrieveImage(m_zed_right, sl::VIEW::RIGHT);

    cv::Mat left_bgra = slMat2cvMat(m_zed_left);
    cv::Mat right_bgra = slMat2cvMat(m_zed_right);

    cv::cvtColor(left_bgra, left_img, cv::COLOR_BGRA2BGR);
    cv::cvtColor(right_bgra, right_img, cv::COLOR_BGRA2BGR);

    m_has_images = !left_img.empty() && !right_img.empty();
    return m_has_images;
}

bool ZedCameraInterface::has_received_stereo_images() const
{
    return m_has_images && !left_img.empty() && !right_img.empty();
}

const cv::Mat &ZedCameraInterface::left_image() const
{
    return left_img;
}

const cv::Mat &ZedCameraInterface::right_image() const
{
    return right_img;
}
