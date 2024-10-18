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

    \author    <amunawar@jhu.edu>
    \author    Adnan Munawar
*/
//==============================================================================

// To silence warnings on MacOS
#define GL_SILENCE_DEPRECATION
#include <afFramework.h>
#include <sensor_msgs/Image.h>
#include <cv_bridge/cv_bridge.h>

using namespace std;
using namespace ambf;

class StereoRosCameraWrapper; // Forward declaration

class afCameraHMD : public afObjectPlugin
{
public:
    afCameraHMD();
    virtual int init(const afBaseObjectPtr a_afObjectPtr, const afBaseObjectAttribsPtr a_objectAttribs) override;
    virtual void graphicsUpdate() override;
    virtual void physicsUpdate(double dt) override;
    virtual void reset() override;
    virtual bool close() override;

    void updateHMDParams();

    void makeFullScreen();

    void create_stereo_cam_info_from_yaml(string cam_name, const afBaseObjectAttribsPtr a_objectAttribs);

    // ROS attributes and callbacks
    StereoRosCameraWrapper *stereo_cam_info;
    ros::NodeHandle *ros_node_handle;
    ros::Subscriber left_sub, right_sub;
    ros::Subscriber window_disparity_sub;

    void left_img_callback(const sensor_msgs::ImageConstPtr &msg);
    void right_img_callback(const sensor_msgs::ImageConstPtr &msg);

    void left_compressed_img_callback(const sensor_msgs::CompressedImageConstPtr& msg);
    void right_compressed_img_callback(const sensor_msgs::CompressedImagePtr& msg);

    void window_disparity_callback(const std_msgs::Float32 &msg);
    void update_ros_textures_for_headset();
    cv_bridge::CvImagePtr left_img_ptr = nullptr;
    cv_bridge::CvImagePtr right_img_ptr = nullptr;
    cv_bridge::CvImagePtr concat_img_ptr = nullptr;
    int clipsize = 0.3;

    cTexture2dPtr m_rosImageTexture;

    // Shader uniform variables
    float window_disparity = 0.1;

protected:
    afCameraPtr m_camera;
    cFrameBufferPtr m_frameBuffer;
    cWorld *m_vrWorld;
    cMesh *m_quadMesh;
    int m_width;
    int m_height;
    int m_alias_scaling;
    cShaderProgramPtr m_shaderPgm;
};

struct StereoRosCameraWrapper
{
    string rostopic_left;
    string rostopic_right;
    string camera_name;

    // Either RGB or RGBA
    string pixel_format;
    int pixel_format_gl;
    bool convert_from_RGB2BGR;

    StereoRosCameraWrapper(string rostopic_left, string rostopic_right, string a_camera_name, string a_pixel_format,
                           bool a_convert_from_RGB2BGR) : rostopic_left(rostopic_left), rostopic_right(rostopic_right),
                                                          camera_name(a_camera_name), pixel_format(a_pixel_format),
                                                          convert_from_RGB2BGR(a_convert_from_RGB2BGR)
    {
        if (pixel_format == "RGB")
        {
            pixel_format_gl = GL_RGB;
        }
        else if (pixel_format == "RGBA")
        {
            pixel_format_gl = GL_RGBA;
        }
        else
        {
            cerr << "ERROR! Pixel format " << pixel_format <<  " not supported. Check plugin config." << endl;
            throw runtime_error("Pixel format not supported");
        }
    }
};

AF_REGISTER_OBJECT_PLUGIN(afCameraHMD)
