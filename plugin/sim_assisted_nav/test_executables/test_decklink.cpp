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

// Standalone check for DecklinkCameraInterface: grabs left/right frames and
// shows them side by side. Usage: test_decklink [left_device] [right_device]
// Press 'q' or ESC to quit.

#include "decklink_camera_interface.h"

#include <opencv2/highgui.hpp>
#include <opencv2/imgproc.hpp>

#include <cstdlib>
#include <iostream>

using namespace std;

int main(int argc, char **argv)
{
    int left_device = argc > 1 ? atoi(argv[1]) : 0;
    int right_device = argc > 2 ? atoi(argv[2]) : 1;

    cout << "Opening Decklink devices left=" << left_device << " right=" << right_device << endl;
    DecklinkCameraInterface cam(left_device, right_device);
    cam.init();
    if (cam.is_unavailable())
    {
        cerr << "Decklink source unavailable, exiting." << endl;
        return 1;
    }

    const string window = "decklink left | right";
    cv::namedWindow(window, cv::WINDOW_NORMAL);

    cv::Mat stereo;
    while (true)
    {
        if (cam.grab())
        {
            cv::Mat left = cam.left_image();
            cv::Mat right = cam.right_image();
            if (left.rows != right.rows)
            {
                cv::resize(right, right, cv::Size(right.cols * left.rows / right.rows, left.rows));
            }
            cv::hconcat(left, right, stereo);
            cv::imshow(window, stereo);
        }
        else
        {
            cerr << "No frames received" << endl;
        }

        int key = cv::waitKey(1);
        if (key == 'q' || key == 27)
        {
            break;
        }
    }

    cam.close();
    return 0;
}
