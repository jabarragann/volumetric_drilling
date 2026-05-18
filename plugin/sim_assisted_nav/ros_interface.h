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

#pragma once

#include <ambf_server/ambf_ral_config.h>
#include <ambf_server/ambf_ral.h>

#if AMBF_ROS1
#include <ros/ros.h>
#include <sensor_msgs/Image.h>
#include <sensor_msgs/CompressedImage.h>
#include <sensor_msgs/image_encodings.h>
#include <std_msgs/Float32.h>
#include <cv_bridge/cv_bridge.h>
#elif AMBF_ROS2
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <sensor_msgs/msg/compressed_image.hpp>
#include <sensor_msgs/image_encodings.hpp>
#include <std_msgs/msg/float32.hpp>
#include <cv_bridge/cv_bridge.hpp>
#endif

class RosInterface
{
public:
    RosInterface();
    ~RosInterface();
    void init(const std::string &left_topic, const std::string &right_topic);
    void init_img_pointers();

    ambf_ral::node_ptr_t ros_node_handle;
#if AMBF_ROS1
    std::shared_ptr<ros::Subscriber> left_sub, right_sub;
    std::shared_ptr<ros::Subscriber> window_disparity_sub;
#elif AMBF_ROS2
    rclcpp::Subscription<sensor_msgs::msg::CompressedImage>::SharedPtr left_sub, right_sub;
    rclcpp::Subscription<std_msgs::msg::Float32>::SharedPtr window_disparity_sub;
#endif

    cv_bridge::CvImagePtr left_img_ptr = nullptr;
    cv_bridge::CvImagePtr right_img_ptr = nullptr;
    cv_bridge::CvImagePtr concat_img_ptr = nullptr;

    cv_bridge::CvImagePtr left_for_process = nullptr;
    cv_bridge::CvImagePtr right_for_process = nullptr;

    // Shader uniform variable updated via ROS subscription
    float window_disparity = 0.1;

#if AMBF_ROS1
    void left_compressed_img_callback(const sensor_msgs::CompressedImage &msg);
    void right_compressed_img_callback(const sensor_msgs::CompressedImage &msg);
    void window_disparity_callback(const std_msgs::Float32 &msg);
#elif AMBF_ROS2
    void left_compressed_img_callback(const sensor_msgs::msg::CompressedImage::SharedPtr msg);
    void right_compressed_img_callback(const sensor_msgs::msg::CompressedImage::SharedPtr msg);
    void window_disparity_callback(const std_msgs::msg::Float32::SharedPtr msg);
#endif
};
