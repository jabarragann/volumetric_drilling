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

    \author    <nnaguru1@jh.edu>
    \author    Nimesh Nagururu
    \author    Adnan Munawar
*/
//==============================================================================
#ifndef COLLISION_PUBLISHER_H
#define COLLISION_PUBLISHER_H



#include <string>
#include <afFramework.h>
#include <ambf_server/ambf_ral_config.h>
#include <ambf_server/ambf_ral.h>
#include <ambf_server/RosComBase.h>

#if AMBF_ROS1
#include <ros/ros.h>
#include <geometry_msgs/WrenchStamped.h>
#include <geometry_msgs/PointStamped.h>
#include <geometry_msgs/Point.h>
#include <std_msgs/ColorRGBA.h>
#include <std_msgs/Float32.h>
#include <std_msgs/Bool.h>
#include <volumetric_drilling_msgs/Voxels.h>
#include <volumetric_drilling_msgs/DrillSize.h>
#include <volumetric_drilling_msgs/VolumeInfo.h>
#include <volumetric_drilling_msgs/Index.h>

#elif AMBF_ROS2
#include <rclcpp/rclcpp.hpp>
#include "geometry_msgs/msg/wrench_stamped.hpp"
#include "geometry_msgs/msg/point_stamped.hpp"
#include "geometry_msgs/msg/point.hpp"
#include "std_msgs/msg/color_rgba.hpp"
#include "std_msgs/msg/float32.hpp"
#include "std_msgs/msg/bool.hpp"
#include "volumetric_drilling_msgs/msg/voxels.hpp"
#include "volumetric_drilling_msgs/msg/drill_size.hpp"
#include "volumetric_drilling_msgs/msg/volume_info.hpp"
#include "volumetric_drilling_msgs/msg/index.hpp"
#endif

using namespace chai3d;

class DrillingPublisher
{
public:
    DrillingPublisher(std::string a_namespace, std::string a_plugin);
    ~DrillingPublisher();
    void init(std::string a_namespace, std::string a_plugin);
    ambf_ral::node_ptr_t m_rosNode;
    void publishDrillSize(int burrSize, double time);

    void setVolumeInfo(cTransform &pose, cVector3d &dimensions, cVector3d &voxel_count);

    void publishVolumeInfo(double time);

    void appendToVoxelMsg(cVector3d &index, cColorf &color);

    void clearVoxelMsg();

    void publishVoxelMsg(double time);

    void publishForceFeedback(cVector3d &force, cVector3d &moment, double time);

    void publishDrillLocationInVolume(cVector3d &location, double time);

private:

#if AMBF_ROS1
    std::shared_ptr<ros::Publisher> m_voxelsRemovalPub;
    std::shared_ptr<ros::Publisher> m_drillSizePub;
    std::shared_ptr<ros::Publisher> m_volumeInfoPub;
    std::shared_ptr<ros::Publisher> m_forcefeedbackPub;
    std::shared_ptr<ros::Publisher> m_drillLocationInVolumePub;

    volumetric_drilling_msgs::Voxels m_voxel_msg;
    volumetric_drilling_msgs::DrillSize m_drill_size_msg;
    volumetric_drilling_msgs::VolumeInfo m_volume_info_msg;
    geometry_msgs::WrenchStamped m_force_feedback_msg;

#elif AMBF_ROS2
    rclcpp::Publisher<volumetric_drilling_msgs::msg::Voxels>::SharedPtr m_voxelsRemovalPub;
    rclcpp::Publisher<volumetric_drilling_msgs::msg::DrillSize>::SharedPtr m_drillSizePub;
    rclcpp::Publisher<volumetric_drilling_msgs::msg::VolumeInfo>::SharedPtr m_volumeInfoPub;
    rclcpp::Publisher<geometry_msgs::msg::WrenchStamped>::SharedPtr m_forcefeedbackPub;
    rclcpp::Publisher<geometry_msgs::msg::PointStamped>::SharedPtr m_drillLocationInVolumePub;

    volumetric_drilling_msgs::msg::Voxels m_voxel_msg;
    volumetric_drilling_msgs::msg::DrillSize m_drill_size_msg;
    volumetric_drilling_msgs::msg::VolumeInfo m_volume_info_msg;
    geometry_msgs::msg::WrenchStamped m_force_feedback_msg;
#endif
};

class SimulationAssistedNavRosInterface
{
public:
    SimulationAssistedNavRosInterface(std::string a_namespace = "sim_assisted_nav");
    ambf_ral::node_ptr_t m_rosNode;

    float window_disparity = 0.1;
    float small_window_horizontal_offset = 0.00;
    float small_window_vertical_offset = 0.00;
    // Tracks whether the small picture-over-picture windows are shown. Toggled
    // via keyboard and published to the sim_assisted_nav shader.
    bool show_small_window = true;
#if AMBF_ROS1
    std::shared_ptr<ros::Publisher> small_window_disparity_pub;
    std::shared_ptr<ros::Publisher> show_small_window_pub;
    std::shared_ptr<ros::Publisher> small_window_offset_pub;
#elif AMBF_ROS2
    rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr small_window_disparity_pub;
    rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr show_small_window_pub;
    rclcpp::Publisher<geometry_msgs::msg::Point>::SharedPtr small_window_offset_pub;
#endif

    // rclcpp::Subscription<std_msgs::msg::Float32MultiArray>::SharedPtr manual_slices_sub;
    cVector3d increase_vector = cVector3d(0.00, 0.00, 0.00);

    // void manual_slices_callback(std_msgs::msg::Float32MultiArray msg)
    // {
    //     // if (msg.data.size() == 2)
    //     // {
    //     //     if (msg.data[0] == 0)
    //     //     {
    //     //         increase_vector.x(msg.data[1]);
    //     //     }
    //     //     else if (msg.data[0] == 1)
    //     //     {
    //     //         increase_vector.y(msg.data[1]);
    //     //     }
    //     //     else if (msg.data[0] == 2)
    //     //     {
    //     //         increase_vector.z(msg.data[1]);
    //     //     }
    //     //     // increase_vector += cVector3d(0.005, 0.005, 0.005);
    //     //     // cout << msg.data[0] << " " << msg.data[1] << endl;
    //     // cout << increase_vector.x() << " " << increase_vector.y() << " " << increase_vector.z() << endl;
    //     // }
    // }
};

#endif // VOLUMETRIC_PLUGIN_COLLISION_PUBLISHER_H
