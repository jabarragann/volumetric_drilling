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

#include "ros_interface.h"
#include <ambf_server/RosComBase.h>
#include <opencv2/highgui/highgui.hpp>

using namespace std;

#if AMBF_ROS1
#define SAN_LOG_WARN(fmt, ...) ROS_WARN(fmt, ##__VA_ARGS__)
#define SAN_LOG_ERROR(fmt, ...) ROS_ERROR(fmt, ##__VA_ARGS__)
#elif AMBF_ROS2
#define SAN_LOG_WARN(fmt, ...) RCLCPP_WARN(rclcpp::get_logger("sim_assisted_nav"), fmt, ##__VA_ARGS__)
#define SAN_LOG_ERROR(fmt, ...) RCLCPP_ERROR(rclcpp::get_logger("sim_assisted_nav"), fmt, ##__VA_ARGS__)
#endif

// ---------------------------------------------------------------------------
// RosStereoCamInterface
// ---------------------------------------------------------------------------

RosStereoCamInterface::RosStereoCamInterface()
{
}

RosStereoCamInterface::~RosStereoCamInterface()
{
}

#if AMBF_ROS1
void RosStereoCamInterface::init_img_pointers()
{
    left_img_ptr = boost::make_shared<cv_bridge::CvImage>();
    right_img_ptr = boost::make_shared<cv_bridge::CvImage>();
}
#elif AMBF_ROS2
void RosStereoCamInterface::init_img_pointers()
{
    left_img_ptr = std::make_shared<cv_bridge::CvImage>();
    right_img_ptr = std::make_shared<cv_bridge::CvImage>();
}
#endif

bool RosStereoCamInterface::has_received_stereo_images() const
{
    if (left_img_ptr == nullptr || right_img_ptr == nullptr)
    {
        return false;
    }
    return !left_img_ptr->image.empty() && !right_img_ptr->image.empty();
}

void RosStereoCamInterface::init(const std::string &left_topic, const std::string &right_topic)
{
    ros_node_handle = afROSNode::getNodeAndRegister("sim_assisted_nav");

    init_img_pointers();

    ambf_ral::create_subscriber<AMBF_RAL_MSG(sensor_msgs, CompressedImage), RosStereoCamInterface>(left_sub, ros_node_handle, left_topic, 2, &RosStereoCamInterface::left_compressed_img_callback, this);
    ambf_ral::create_subscriber<AMBF_RAL_MSG(sensor_msgs, CompressedImage), RosStereoCamInterface>(right_sub, ros_node_handle, right_topic, 2, &RosStereoCamInterface::right_compressed_img_callback, this);
}

#if AMBF_ROS1
void RosStereoCamInterface::left_compressed_img_callback(const sensor_msgs::CompressedImage &msg)
#elif AMBF_ROS2
void RosStereoCamInterface::left_compressed_img_callback(const sensor_msgs::msg::CompressedImage::SharedPtr msg)
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
void RosStereoCamInterface::right_compressed_img_callback(const sensor_msgs::CompressedImage &msg)
#elif AMBF_ROS2
void RosStereoCamInterface::right_compressed_img_callback(const sensor_msgs::msg::CompressedImage::SharedPtr msg)
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

// ---------------------------------------------------------------------------
// HmdRosInterface
// ---------------------------------------------------------------------------

HmdRosInterface::HmdRosInterface()
{
}

HmdRosInterface::~HmdRosInterface()
{
}

void HmdRosInterface::init()
{
    ros_node_handle = afROSNode::getNodeAndRegister("sim_assisted_nav");

    ambf_ral::create_subscriber<AMBF_RAL_MSG(std_msgs, Float32), HmdRosInterface>(window_disparity_sub, ros_node_handle, "/sim_assisted_nav/small_window_disparity", 2, &HmdRosInterface::window_disparity_callback, this);
}

#if AMBF_ROS1
void HmdRosInterface::window_disparity_callback(const std_msgs::Float32 &msg)
{
    window_disparity = msg.data;
}
#elif AMBF_ROS2
void HmdRosInterface::window_disparity_callback(const std_msgs::msg::Float32::SharedPtr msg)
{
    window_disparity = msg->data;
}
#endif
