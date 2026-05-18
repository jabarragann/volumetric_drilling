//==============================================================================
/*
    Software License Agreement (BSD License)
    Copyright (c) 2019-2022, AMBF
    (https://github.com/WPI-AIM/ambf)

    All rights reserved.

    Redistribution and use in source and binary forms, with or without
    modification, are permitted provided that the following conditions
    are met:

    * Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.

    * Redistributions in binary form must reproduce the above
    copyright notice, this list of conditions and the following
    disclaimer in the documentation and/or other materials provided
    with the distribution.

    * Neither the name of authors nor the names of its contributors may
    be used to endorse or promote products derived from this software
    without specific prior written permission.

    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
    "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
    LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
    FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
    COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
    INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
    BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
    LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
    CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
    LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
    ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
    POSSIBILITY OF SUCH DAMAGE.

    \author    <jbarrag3@jh.edu>
    \author    Juan Antonio Barragan
*/
//==============================================================================

#include "ros_interface.h"
#include <ambf_server/RosComBase.h>
#include <opencv2/highgui/highgui.hpp>

using namespace std;

RosInterface::RosInterface()
{
}

RosInterface::~RosInterface()
{
}

#if AMBF_ROS1
void RosInterface::init_img_pointers()
{
    // ROS 1 way
    left_img_ptr = boost::make_shared<cv_bridge::CvImage>();
    right_img_ptr = boost::make_shared<cv_bridge::CvImage>();
    concat_img_ptr = boost::make_shared<cv_bridge::CvImage>();
    left_for_process = boost::make_shared<cv_bridge::CvImage>();
    right_for_process = boost::make_shared<cv_bridge::CvImage>();
}
#elif AMBF_ROS2
void RosInterface::init_img_pointers()
{
    // ROS 2 way
    left_img_ptr = std::make_shared<cv_bridge::CvImage>();
    right_img_ptr = std::make_shared<cv_bridge::CvImage>();
    concat_img_ptr = std::make_shared<cv_bridge::CvImage>();
    left_for_process = std::make_shared<cv_bridge::CvImage>();
    right_for_process = std::make_shared<cv_bridge::CvImage>();
}
#endif

void RosInterface::init(const std::string &left_topic, const std::string &right_topic)
{
    ros_node_handle = afROSNode::getNodeAndRegister("sim_assisted_nav");

    init_img_pointers();

    ambf_ral::create_subscriber<AMBF_RAL_MSG(sensor_msgs, CompressedImage), RosInterface>(left_sub, ros_node_handle, left_topic, 2, &RosInterface::left_compressed_img_callback, this);
    ambf_ral::create_subscriber<AMBF_RAL_MSG(sensor_msgs, CompressedImage), RosInterface>(right_sub, ros_node_handle, right_topic, 2, &RosInterface::right_compressed_img_callback, this);
    ambf_ral::create_subscriber<AMBF_RAL_MSG(std_msgs, Float32), RosInterface>(window_disparity_sub, ros_node_handle, "/sim_assisted_nav/small_window_disparity", 2, &RosInterface::window_disparity_callback, this);
}

#if AMBF_ROS1
#define SAN_LOG_WARN(fmt, ...) ROS_WARN(fmt, ##__VA_ARGS__)
#define SAN_LOG_ERROR(fmt, ...) ROS_ERROR(fmt, ##__VA_ARGS__)
#elif AMBF_ROS2
#define SAN_LOG_WARN(fmt, ...) RCLCPP_WARN(rclcpp::get_logger("sim_assisted_nav"), fmt, ##__VA_ARGS__)
#define SAN_LOG_ERROR(fmt, ...) RCLCPP_ERROR(rclcpp::get_logger("sim_assisted_nav"), fmt, ##__VA_ARGS__)
#endif

#if AMBF_ROS1
void RosInterface::left_compressed_img_callback(const sensor_msgs::CompressedImage &msg)
#elif AMBF_ROS2
void RosInterface::left_compressed_img_callback(const sensor_msgs::msg::CompressedImage::SharedPtr msg)
#endif
{
    try
    {

#if AMBF_ROS1
        cv::Mat image = cv::imdecode(msg.data, cv::IMREAD_ANYCOLOR | cv::IMREAD_ANYDEPTH);
#elif AMBF_ROS2
        cv::Mat image = cv::imdecode(msg->data, cv::IMREAD_ANYCOLOR | cv::IMREAD_ANYDEPTH);
#endif

        if (!image.empty())
        {
            left_img_ptr->image = image;
            left_img_ptr->encoding = sensor_msgs::image_encodings::BGR8;
        }
        else
        {
            SAN_LOG_WARN("Converted image is empty.");
            throw runtime_error("Converted image is empty.");
        }
    }
    catch (cv::Exception &e)
    {
        SAN_LOG_ERROR("Error decompressing image: %s", e.what());
    }
}


#if AMBF_ROS1
void RosInterface::right_compressed_img_callback(const sensor_msgs::CompressedImage &msg)
#elif AMBF_ROS2
void RosInterface::right_compressed_img_callback(const sensor_msgs::msg::CompressedImage::SharedPtr msg)
#endif
{
    try
    {

#if AMBF_ROS1
        cv::Mat image = cv::imdecode(msg.data, cv::IMREAD_ANYCOLOR | cv::IMREAD_ANYDEPTH);
#elif AMBF_ROS2
        cv::Mat image = cv::imdecode(msg->data, cv::IMREAD_ANYCOLOR | cv::IMREAD_ANYDEPTH);
#endif

        if (!image.empty())
        {
            right_img_ptr->image = image;
            right_img_ptr->encoding = sensor_msgs::image_encodings::BGR8;
        }
        else
        {
            SAN_LOG_WARN("Converted image is empty.");
            throw runtime_error("Converted image is empty.");
        }
    }
    catch (cv::Exception &e)
    {
        SAN_LOG_ERROR("Error decompressing image: %s", e.what());
    }
}

#if AMBF_ROS1
void RosInterface::window_disparity_callback(const std_msgs::Float32 &msg)
{
    window_disparity = msg.data;
}
#elif AMBF_ROS2
void RosInterface::window_disparity_callback(const std_msgs::msg::Float32::SharedPtr msg)
{
    window_disparity = msg->data;
}
#endif
