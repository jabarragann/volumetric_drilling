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

#include "stereo_camera_interface.h"

#include <ambf_server/ambf_ral_config.h>
#include <ambf_server/ambf_ral.h>

#if AMBF_ROS1
#include <ros/ros.h>
#include <sensor_msgs/Image.h>
#include <sensor_msgs/CompressedImage.h>
#include <sensor_msgs/image_encodings.h>
#include <cv_bridge/cv_bridge.h>
#elif AMBF_ROS2
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <sensor_msgs/msg/compressed_image.hpp>
#include <sensor_msgs/image_encodings.hpp>
#include <cv_bridge/cv_bridge.h>
#endif

#include <string>

// Stereo video source backed by two ROS compressed-image topics. Push-based:
// frames arrive asynchronously through subscriber callbacks, so grab() is a
// no-op.
class RosStereoCameraInterface : public StereoCameraInterface
{
public:
    RosStereoCameraInterface(std::string left_topic, std::string right_topic);
    ~RosStereoCameraInterface() override;

    bool init() override;
    bool grab() override;
    bool has_received_stereo_images() const override;
    const cv::Mat &left_image() const override;
    const cv::Mat &right_image() const override;

    void init_img_pointers();

    ambf_ral::node_ptr_t ros_node_handle;
#if AMBF_ROS1
    std::shared_ptr<ros::Subscriber> left_sub, right_sub;
#elif AMBF_ROS2
    rclcpp::Subscription<sensor_msgs::msg::CompressedImage>::SharedPtr left_sub, right_sub;
#endif

    cv_bridge::CvImagePtr left_img_ptr = nullptr;
    cv_bridge::CvImagePtr right_img_ptr = nullptr;

#if AMBF_ROS1
    void left_compressed_img_callback(const sensor_msgs::CompressedImage &msg);
    void right_compressed_img_callback(const sensor_msgs::CompressedImage &msg);
#elif AMBF_ROS2
    void left_compressed_img_callback(const sensor_msgs::msg::CompressedImage::SharedPtr msg);
    void right_compressed_img_callback(const sensor_msgs::msg::CompressedImage::SharedPtr msg);
#endif

private:
    std::string m_left_topic;
    std::string m_right_topic;
};
