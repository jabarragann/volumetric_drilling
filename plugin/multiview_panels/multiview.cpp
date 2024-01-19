
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

#include "multiview.h"

using namespace std;

//------------------------------------------------------------------------------
// DECLARED FUNCTIONS
//------------------------------------------------------------------------------

//------------------------------------------------------------------------------

string g_current_filepath;

afCameraMultiview::afCameraMultiview()
{
    // For HTC Vive Pro
    m_width = 0;
    m_height = 0;
    m_alias_scaling = 1.0;
}

int afCameraMultiview::init(const afBaseObjectPtr a_afObjectPtr, const afBaseObjectAttribsPtr a_objectAttribs)
{
    m_camera = (afCameraPtr)a_afObjectPtr;
    m_camera->setOverrideRendering(true);

    m_width = m_camera->m_width;
    m_height = m_camera->m_height;

    main_cam = new cCamera(NULL);
    world_cam = m_camera->getInternalCamera();
    side_cam = new cCamera(world_cam->getParentWorld());

    world_buff = cFrameBuffer::create();
    world_buff->setup(world_cam, m_width * m_alias_scaling, m_height * m_alias_scaling, true, true, GL_RGBA);
    side_buff = cFrameBuffer::create();
    side_buff->setup(side_cam, m_width * m_alias_scaling, m_height * m_alias_scaling, true, true, GL_RGBA);

    m_frameBuffer = cFrameBuffer::create();
    m_frameBuffer->setup(world_cam, m_width * m_alias_scaling, m_height * m_alias_scaling, true, true, GL_RGBA);

    // create and setup view panel 1
    world_panel = new cViewPanel(world_buff);
    main_cam->m_frontLayer->addChild(world_panel);
    // create and setup view panel 2
    side_panel = new cViewPanel(side_buff);
    main_cam->m_frontLayer->addChild(side_panel);

    // update display panel sizes and positions
    int halfW = m_width / 2;
    int halfH = m_height / 2;
    int offset = 1;
    world_panel->setLocalPos(0.0, 0.0);
    world_panel->setSize(halfW, m_height);
    side_panel->setLocalPos(halfW + offset, 0.0);
    side_panel->setSize(halfW, m_height);
    // update frame buffer sizes
    world_buff->setSize(halfW, m_height);
    side_buff->setSize(halfW, m_height);

    // Set background
    cBackground *background2 = new cBackground();
    side_cam->m_backLayer->addChild(background2);
    background2->setCornerColors(cColorf(1.0f, 0.0f, 1.0f),
                                 cColorf(1.0f, 0.0f, 1.0f),
                                 cColorf(0.0f, 0.8f, 0.8f),
                                 cColorf(0.0f, 0.8f, 0.8f));

    cout << "Load Juan multiview pane plugin V1.1" << endl;
    cout << "\n\n\n\n\n"
         << endl;

    return 1;
}

void afCameraMultiview::graphicsUpdate()
{
    glfwMakeContextCurrent(m_camera->m_window);
    world_buff->renderView();

    // SIMPLE RENDER
    // afRenderOptions ro;
    // ro.m_updateLabels = true;
    // m_camera->render(ro);

    // MANUAL RENDER
    glfwMakeContextCurrent(m_camera->m_window);
    // get width and height of window
    glfwGetFramebufferSize(m_camera->m_window, &m_width, &m_height);
    // render world

    // world_cam->renderView(m_width, m_height);

    side_buff->renderView();
    world_buff->renderView();
    main_cam->renderView(m_width, m_height);

    // swap buffers
    glfwSwapBuffers(m_camera->m_window);
}

void afCameraMultiview::physicsUpdate(double dt)
{
}

void afCameraMultiview::reset()
{
}

bool afCameraMultiview::close()
{
    return true;
}

void afCameraMultiview::updateHMDParams()
{
}

void afCameraMultiview::makeFullScreen()
{
    // const GLFWvidmode *mode = glfwGetVideoMode(m_camera->m_monitor);
    // int w = 2880;
    // int h = 1600;
    // int x = mode->width - w;
    // int y = mode->height - h;
    // int xpos, ypos;
    // glfwGetMonitorPos(m_camera->m_monitor, &xpos, &ypos);
    // x += xpos;
    // y += ypos;
    // glfwSetWindowPos(m_camera->m_window, x, y);
    // glfwSetWindowSize(m_camera->m_window, w, h);
    // m_camera->m_width = w;
    // m_camera->m_height = h;
    // glfwSwapInterval(0);
    // cerr << "\t Making " << m_camera->getName() << " fullscreen \n";
}
