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

using namespace std;

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

    ambf_ral::create_subscriber<AMBF_RAL_MSG(std_msgs, Bool), HmdRosInterface>(show_small_window_sub, ros_node_handle, "/sim_assisted_nav/show_small_window", 2, &HmdRosInterface::show_small_window_callback, this);

    ambf_ral::create_subscriber<AMBF_RAL_MSG(geometry_msgs, Point), HmdRosInterface>(small_window_offset_sub, ros_node_handle, "/sim_assisted_nav/small_window_offset", 2, &HmdRosInterface::small_window_offset_callback, this);
}

#if AMBF_ROS1
void HmdRosInterface::window_disparity_callback(const std_msgs::Float32 &msg)
{
    window_disparity = msg.data;
}

void HmdRosInterface::show_small_window_callback(const std_msgs::Bool &msg)
{
    show_small_window = msg.data;
}

void HmdRosInterface::small_window_offset_callback(const geometry_msgs::Point &msg)
{
    small_window_horizontal_offset = msg.x;
    small_window_vertical_offset = msg.y;
}
#elif AMBF_ROS2
void HmdRosInterface::window_disparity_callback(const std_msgs::msg::Float32::SharedPtr msg)
{
    window_disparity = msg->data;
}

void HmdRosInterface::show_small_window_callback(const std_msgs::msg::Bool::SharedPtr msg)
{
    show_small_window = msg->data;
}

void HmdRosInterface::small_window_offset_callback(const geometry_msgs::msg::Point::SharedPtr msg)
{
    small_window_horizontal_offset = msg->x;
    small_window_vertical_offset = msg->y;
}
#endif
