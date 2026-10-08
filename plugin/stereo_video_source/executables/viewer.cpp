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

// Shows the left/right images of a running stereo video source side by side.
// Several viewers can run at once. Press 'q' or ESC to quit.

#include "stereo_video_client.h"
#include "stereo_video_common.h"

#include <boost/program_options.hpp>
#include <opencv2/highgui.hpp>

#include <chrono>
#include <iostream>

using namespace std;
namespace po = boost::program_options;

int main(int argc, char **argv)
{
    string name;
    bool vertical = false;

    po::options_description desc("Stereo video viewer options");
    desc.add_options()
        ("help,h", "Show this help")
        ("name,n", po::value(&name)->default_value("camera"), "Name of the source to connect to")
        ("vertical,v", po::bool_switch(&vertical), "Stack left/right vertically");

    po::variables_map vm;
    try
    {
        po::store(po::parse_command_line(argc, argv, desc), vm);
        po::notify(vm);
    }
    catch (const po::error &e)
    {
        cerr << e.what() << "\n" << desc << endl;
        return 1;
    }
    if (vm.count("help"))
    {
        cout << desc << endl;
        return 0;
    }

    stereo_video::StereoVideoClient client;
    if (!client.init(name))
    {
        cerr << "Could not connect to stereo video source '" << name << "' at "
             << stereo_video::socket_path_for(name) << ". Is video_source running?" << endl;
        return 1;
    }

    const string window = "stereo video: " + name;
    cv::namedWindow(window, cv::WINDOW_NORMAL);

    cv::Mat display;
    int frames = 0;
    auto fps_start = chrono::steady_clock::now();
    while (true)
    {
        if (client.grab())
        {
            if (vertical)
            {
                cv::vconcat(client.left_image(), client.right_image(), display);
            }
            else
            {
                cv::hconcat(client.left_image(), client.right_image(), display);
            }
            cv::imshow(window, display);
            frames++;
        }
        else if (!client.is_connected())
        {
            cerr << "Lost connection to stereo video source" << endl;
            return 1;
        }

        const chrono::duration<double> elapsed = chrono::steady_clock::now() - fps_start;
        if (elapsed.count() >= 5.0)
        {
            cout << "FPS: " << frames / elapsed.count() << endl;
            frames = 0;
            fps_start = chrono::steady_clock::now();
        }

        const int key = cv::waitKey(1) & 0xFF;
        if (key == 'q' || key == 27)
        {
            break;
        }
    }
    return 0;
}
