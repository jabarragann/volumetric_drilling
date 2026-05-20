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
#include "ros_interface.h"
#include "camera_interfaces/stereo_camera_interface.h"
#include "camera_interfaces/stereo_camera_config.h"

#include <memory>

using namespace std;
using namespace ambf;

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

    std::unique_ptr<StereoCameraConfig> stereo_cam_info;
    HmdRosInterface ros_interface;
    std::unique_ptr<StereoCameraInterface> m_camera_interface;

    void update_textures_for_headset();
    int clipsize = 0.3;

    cTexture2dPtr m_hmdImageTexture;
    cv::Mat m_concat_img;

    void assignGLFWCallbacks();
    void windowSizeCallback(GLFWwindow *window_ptr, int width, int height);

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

AF_REGISTER_OBJECT_PLUGIN(afCameraHMD)
