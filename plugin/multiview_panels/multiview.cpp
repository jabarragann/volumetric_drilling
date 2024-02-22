
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

void afCameraMultiview::windowSizeCallback(GLFWwindow *, int new_width, int new_height)
{
    // update display panel sizes and positions
    int halfW = new_width / 2;
    int halfH = new_height / 2;
    int offset = 1;
    world_panel->setLocalPos(0.0, 0.0);
    world_panel->setSize(halfW, new_height);
    side_panel->setLocalPos(halfW + offset, 0.0);
    side_panel->setSize(halfW, new_height);
    // update frame buffer sizes
    world_buff->setSize(halfW, new_height);
    side_buff->setSize(halfW, new_height);
}

void afCameraMultiview::assignGLFWCallbacks()
{
    glfwSetWindowUserPointer(m_camera->m_window, this);

    // Configure callbacks
    // The lambda function can only get access to the class method by using `glfwGetWindowUserPointer`
    void (*lambda_resize_window)(GLFWwindow *, int, int) = [](GLFWwindow *w, int width, int height)
    {
        static_cast<afCameraMultiview *>(glfwGetWindowUserPointer(w))->windowSizeCallback(w, width, height);
    };
    glfwSetFramebufferSizeCallback(m_camera->m_window, lambda_resize_window);
}

void afCameraMultiview::init_volume_pointer()
{
    ambf::afWorldPtr m_worldPtr = m_camera->m_afWorld;
    ambf::afVolumePtr volume_ptr = m_worldPtr->getVolume("mastoidectomy_volume");

    if (!volume_ptr)
    {
        std::cerr << "ERROR! FAILED TO FIND VOLUME NAMED "
                  << "mastoidectomy_volume" << endl;

        std::runtime_error("Volume not found");
    }

    volume_voxels = volume_ptr->getInternalVolume();
}

cMultiImage *afCameraMultiview::set_ct_slice(int slice)
{
    cImage *img_ptr = volume_voxels->m_texture->m_image.get();
    cMultiImage *ptr = dynamic_cast<cMultiImage *>(img_ptr);

    if (ptr)
    {
        ptr->selectImage(75);
        cImage *img = ptr->getImage();
        std::shared_ptr<cImage> img_shared(ptr);
        side_cam->m_frontLayer->addChild(ct_slice1);
        bool success = ct_slice1->loadFromImage(img_shared);
        ct_slice1->setSize(500, 500);
    }

    return ptr;
}

int afCameraMultiview::init(const afBaseObjectPtr a_afObjectPtr, const afBaseObjectAttribsPtr a_objectAttribs)
{
    // AMBF OBJECTS CONFIG
    m_camera = (afCameraPtr)a_afObjectPtr;
    m_camera->setOverrideRendering(true);

    m_width = m_camera->m_width;
    m_height = m_camera->m_height;

    // ADDITIONAL CHAI OBJECTS CONFIG
    main_cam = new cCamera(NULL);
    side_view_world = new cWorld();
    world_cam = m_camera->getInternalCamera();
    side_cam = new cCamera(side_view_world);

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
    windowSizeCallback(m_camera->m_window, m_width, m_height);
    assignGLFWCallbacks();

    // Set background
    cBackground *background2 = new cBackground();
    side_cam->m_backLayer->addChild(background2);
    background2->setCornerColors(cColorf(1.0f, 0.0f, 1.0f),
                                 cColorf(1.0f, 0.0f, 1.0f),
                                 cColorf(0.0f, 0.8f, 0.8f),
                                 cColorf(0.0f, 0.8f, 0.8f));

    // load bitmap
    sample_bitmap = new cBitmap();
    ct_slice1 = new cBitmap();

    std::string img_path = "plugin/multiview_panels/sample_imgs/white_background.jpg";
    side_cam->m_frontLayer->addChild(sample_bitmap);
    bool success = sample_bitmap->loadFromFile(img_path);

    cout << "Load Juan multiview pane plugin V1.2" << endl;
    cout << "Bitmap upload status: " << success << endl;
    cout << "\n\n\n\n\n"
         << endl;

    return 1;
}

void afCameraMultiview::graphicsUpdate()
{
    if (!volume_initialized)
    {
        // Volume pointer needs to be initialized in first graphics update.
        // Volume might not be available when calling the init function
        init_volume_pointer();
        volume_initialized = true;

        double start_time = glfwGetTime();
        cMultiImage *ptr = set_ct_slice(75);

        if (ptr) // if not nullptr
        {
            cout << "safe downcast" << endl;
            cout << "image count " << ptr->getImageCount() << endl;
            cout << "get current idx " << ptr->getCurrentIndex() << endl;
            cout << "(width, height) = (" << ptr->getWidth() << ", " << ptr->getHeight() << ")" << endl;
            cout << "get fmt " << ptr->getFormat() << endl;
            cout << "get type " << ptr->getType() << endl;
            cout << "get bits per pixel " << ptr->getBitsPerPixel() << endl;
        }
        cout << "Time to load img: " << glfwGetTime() - start_time << endl;
        cout << "\n\n\n\n"
             << endl;
    }

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
