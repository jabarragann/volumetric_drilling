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

#include "ros_stereo_camera_interface.h"

#include <ambf_server/RosComBase.h>
#include <opencv2/highgui/highgui.hpp>

#include <utility>

using namespace std;

#if AMBF_ROS1
#define SAN_LOG_WARN(fmt, ...) ROS_WARN(fmt, ##__VA_ARGS__)
#define SAN_LOG_ERROR(fmt, ...) ROS_ERROR(fmt, ##__VA_ARGS__)
#elif AMBF_ROS2
#define SAN_LOG_WARN(fmt, ...) RCLCPP_WARN(rclcpp::get_logger("sim_assisted_nav"), fmt, ##__VA_ARGS__)
#define SAN_LOG_ERROR(fmt, ...) RCLCPP_ERROR(rclcpp::get_logger("sim_assisted_nav"), fmt, ##__VA_ARGS__)
#endif

RosStereoCameraInterface::RosStereoCameraInterface(std::string left_topic, std::string right_topic)
    : m_left_topic(std::move(left_topic)), m_right_topic(std::move(right_topic))
{
}

RosStereoCameraInterface::~RosStereoCameraInterface()
{
}

#if AMBF_ROS1
void RosStereoCameraInterface::init_img_pointers()
{
    left_img_ptr = boost::make_shared<cv_bridge::CvImage>();
    right_img_ptr = boost::make_shared<cv_bridge::CvImage>();
}
#elif AMBF_ROS2
void RosStereoCameraInterface::init_img_pointers()
{
    left_img_ptr = std::make_shared<cv_bridge::CvImage>();
    right_img_ptr = std::make_shared<cv_bridge::CvImage>();
}
#endif

bool RosStereoCameraInterface::init()
{
    ros_node_handle = afROSNode::getNodeAndRegister("sim_assisted_nav");

    init_img_pointers();

    ambf_ral::create_subscriber<AMBF_RAL_MSG(sensor_msgs, CompressedImage), RosStereoCameraInterface>(left_sub, ros_node_handle, m_left_topic, 2, &RosStereoCameraInterface::left_compressed_img_callback, this);
    ambf_ral::create_subscriber<AMBF_RAL_MSG(sensor_msgs, CompressedImage), RosStereoCameraInterface>(right_sub, ros_node_handle, m_right_topic, 2, &RosStereoCameraInterface::right_compressed_img_callback, this);

    return true;
}

bool RosStereoCameraInterface::grab()
{
    // Push-based source: frames arrive via ROS callbacks. Nothing to pull.
    return true;
}

bool RosStereoCameraInterface::has_received_stereo_images() const
{
    if (left_img_ptr == nullptr || right_img_ptr == nullptr)
    {
        return false;
    }
    return !left_img_ptr->image.empty() && !right_img_ptr->image.empty();
}

const cv::Mat &RosStereoCameraInterface::left_image() const
{
    return left_img_ptr->image;
}

const cv::Mat &RosStereoCameraInterface::right_image() const
{
    return right_img_ptr->image;
}

#if AMBF_ROS1
void RosStereoCameraInterface::left_compressed_img_callback(const sensor_msgs::CompressedImage &msg)
#elif AMBF_ROS2
void RosStereoCameraInterface::left_compressed_img_callback(const sensor_msgs::msg::CompressedImage::SharedPtr msg)
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
void RosStereoCameraInterface::right_compressed_img_callback(const sensor_msgs::CompressedImage &msg)
#elif AMBF_ROS2
void RosStereoCameraInterface::right_compressed_img_callback(const sensor_msgs::msg::CompressedImage::SharedPtr msg)
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
