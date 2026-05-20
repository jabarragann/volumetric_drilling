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
