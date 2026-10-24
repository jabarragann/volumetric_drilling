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

// Replays the video of a dvrk_data recording session in sync with
// `ros2 bag play --clock` of the same session. Clients (sim_assisted_nav with
// `video_source: unixfd`, stereo_viewer) cannot tell it apart from video_source.

#include "stereo_video_common.h"
#include "stereo_video_replay.h"

#include <boost/program_options.hpp>
#include <rclcpp/rclcpp.hpp>
#include <rosgraph_msgs/msg/clock.hpp>

#include <iomanip>
#include <iostream>

using namespace std;
namespace po = boost::program_options;

int main(int argc, char **argv)
{
    rclcpp::init(argc, argv);
    const vector<string> args = rclcpp::remove_ros_arguments(argc, argv);

    stereo_video::StereoVideoReplayConfig config;
    double offset_ms = 0.0;

    po::options_description desc("Stereo video replay options");
    desc.add_options()
        ("help,h", "Show this help")
        ("session,s", po::value(&config.session_dir)->required(), "dvrk_data session directory (contains index.json)")
        ("stream", po::value(&config.stream), "Video stream to replay (default: first stream in index.json)")
        ("name,n", po::value(&config.name)->default_value(config.name), "Source name clients connect to")
        ("offset-ms", po::value(&offset_ms)->default_value(offset_ms), "Shift the video against the bag (positive: video later)");

    po::variables_map vm;
    try
    {
        po::store(po::command_line_parser(vector<string>(args.begin() + 1, args.end())).options(desc).run(), vm);
        if (vm.count("help"))
        {
            cout << desc << endl;
            rclcpp::shutdown();
            return 0;
        }
        po::notify(vm);
    }
    catch (const po::error &e)
    {
        cerr << e.what() << "\n" << desc << endl;
        rclcpp::shutdown();
        return 1;
    }
    config.offset_ns = int64_t(offset_ms * 1e6);

    stereo_video::StereoVideoReplay replay(config);
    if (!replay.start())
    {
        cerr << "Failed to start stereo video replay" << endl;
        rclcpp::shutdown();
        return 1;
    }

    auto node = rclcpp::Node::make_shared("video_replay");
    auto clock_sub = node->create_subscription<rosgraph_msgs::msg::Clock>(
        "/clock", rclcpp::ClockQoS(), [&replay](const rosgraph_msgs::msg::Clock &msg) {
            replay.set_time(rclcpp::Time(msg.clock).nanoseconds());
        });
    auto watchdog = node->create_wall_timer(chrono::milliseconds(200), [&replay] {
        if (!replay.ok())
        {
            rclcpp::shutdown();
        }
    });

    cout << "Replaying " << replay.video_path() << " (" << replay.frame_count() << " frames, "
         << fixed << setprecision(1) << (replay.last_frame_time_ns() - replay.first_frame_time_ns()) / 1e9 << " s)\n"
         << "Serving stereo video '" << config.name << "' on " << replay.socket_path() << "\n"
         << "Waiting for /clock, e.g. `ros2 bag play " << config.session_dir << "/rosbag --clock 100`" << endl;

    rclcpp::spin(node);

    replay.stop();
    rclcpp::shutdown();
    return replay.ok() ? 0 : 1;
}
