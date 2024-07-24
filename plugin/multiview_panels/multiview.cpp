
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
#include <ambf_server/RosComBase.h>

using namespace std;

//------------------------------------------------------------------------------
// DECLARED FUNCTIONS
//------------------------------------------------------------------------------

//------------------------------------------------------------------------------

string g_current_filepath;

SliceAnnotator::SliceAnnotator(cMultiImagePtr volume_slices_ptr)
{
    this->volume_slices_ptr = volume_slices_ptr;

    this->slice_width = volume_slices_ptr->getWidth();
    this->slice_height = volume_slices_ptr->getHeight();
    this->number_of_slices = volume_slices_ptr->getImageCount();

    this->marker_color = cColorb(254, 0, 0);

    init_pixels_backup();
}

void SliceAnnotator::init_pixels_backup()
{
    for (int i = 0; i < marker_size; i++)
    {
        vector<cColorb> row;
        for (int j = 0; j < marker_size; j++)
        {
            row.push_back(cColorb(0, 0, 0));
        }
        pixels_backup.push_back(row);
    }
}

void SliceAnnotator::select_and_annotate(int slice_idx, int x, int y)
{
    volume_slices_ptr->selectImage(slice_idx);
    for (int i = 0; i < marker_size; i++)
    {
        for (int j = 0; j < marker_size; j++)
        {
            volume_slices_ptr->getPixelColor((i + x) % slice_width, (j + y) % slice_height, pixels_backup[i][j]);
            volume_slices_ptr->setPixelColor((i + x) % slice_width, (j + y) % slice_height, marker_color);
        }
    }

    location_of_last_annotation = AnnotationLocation();
    location_of_last_annotation.set(slice_idx, x, y);
}

void SliceAnnotator::restore_slice()
{
    if (location_of_last_annotation.initialized)
    {
        int slice_idx = location_of_last_annotation.slice_idx;
        int x = location_of_last_annotation.x;
        int y = location_of_last_annotation.y;

        volume_slices_ptr->selectImage(slice_idx);
        for (int i = 0; i < marker_size; i++)
        {
            for (int j = 0; j < marker_size; j++)
            {
                volume_slices_ptr->setPixelColor((i + x) % slice_width, (j + y) % slice_height, pixels_backup[i][j]);
            }
        }
    }
}

void SliceAnnotator::print_volume_information()
{
    cout << "image count " << volume_slices_ptr->getImageCount() << endl;
    cout << "get current idx " << volume_slices_ptr->getCurrentIndex() << endl;
    cout << "(width, height) = (" << volume_slices_ptr->getWidth() << ", " << volume_slices_ptr->getHeight() << ")" << endl;
    cout << "get fmt " << volume_slices_ptr->getFormat() << endl;
    cout << "get type " << volume_slices_ptr->getType() << endl;
    cout << "get bits per pixel " << volume_slices_ptr->getBitsPerPixel() << endl;
    cout << "\n\n\n\n"
         << endl;
}

afCameraMultiview::afCameraMultiview()
{
    // For HTC Vive Pro
    m_width = 0;
    m_height = 0;
    m_alias_scaling = 1.0;
}

afCameraMultiview::~afCameraMultiview()
{
    cout << "Destroying afCameraMultivew plugin object" << endl;
}

void afCameraMultiview::drill_location_callback(const geometry_msgs::PointStamped::ConstPtr &msg)
{
    // std::cout << "Received drill location: " << msg->point.x << " " << msg->point.y << " " << msg->point.z << endl;
    drill_location = cVector3d(msg->point.x, msg->point.y, msg->point.z);
}

void afCameraMultiview::windowSizeCallback(GLFWwindow *, int new_width, int new_height)
{
    // update display panel sizes and positions
    int halfW = new_width / 2;
    int halfH = new_height / 2;
    int offset = 1;
    world_window->update_window_size(halfW, halfH);
    world_window->update_panel_location(0, 0);

    ct_slice1_window->update_window_size(halfW, halfH);
    ct_slice1_window->update_panel_location(halfW + offset, 0);

    ct_slice2_window->update_window_size(halfW, halfH);
    ct_slice2_window->update_panel_location(0, halfH + offset);

    ct_slice3_window->update_window_size(halfW, halfH);
    ct_slice3_window->update_panel_location(halfW + offset, halfH + offset);
    cout << new_width << " " << new_height << endl;
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

        throw(std::runtime_error("Volume not found"));
    }

    c_voxel_object = volume_ptr->getInternalVolume();
    cImagePtr img_ptr = c_voxel_object->m_texture->m_image;

    // Shared pointers can also be downcasted!
    // Using dynamic_pointer_cast instead of dynamic_cast
    volume_slices_ptr = dynamic_pointer_cast<cMultiImage>(img_ptr);

    if (!volume_slices_ptr)
    {
        std::cerr << "ERROR! FAILED TO LOAD IMAGES FROM VOLUME " << endl;
        throw(std::runtime_error("Volume not found"));
    }

    slice_annotator = unique_ptr<SliceAnnotator>(new SliceAnnotator(volume_slices_ptr));
}

void afCameraMultiview::init_volume_slicer()
{
    array<int, 4> volume_shape;
    array<string, 4> dim_names = {"B", "W", "H", "D"};
    volume_shape[0] = volume_slices_ptr->getBitsPerPixel() / 8;
    volume_shape[1] = volume_slices_ptr->getWidth();
    volume_shape[2] = volume_slices_ptr->getHeight();
    volume_shape[3] = volume_slices_ptr->getImageCount();
    unsigned char const *const raw_data = volume_slices_ptr->getData();

    volume_slicer = unique_ptr<VolumeSlicer>(new VolumeSlicer(raw_data, dim_names, volume_shape));
}

void afCameraMultiview::set_slice_in_side_view(int slice_idx)
{
    // bool success = ct_slice1->loadFromImage(volume_slices_ptr);
    // ct_slice1->setSize(500, 500);

    // bool success = ct_slice1_window->update_ct_slice(out_of_volume_img);
    // ct_slice1_window->update_ct_slice_size(500, 500);
}

cImagePtr create_c_image_from_file(string path)
{

    cImagePtr image = cImage::create();
    bool success = image->loadFromFile(path);

    if (!success)
    {
        std::cerr << "ERROR! FAILED TO LOAD OUT OF VOLUME IMAGE " << path << endl;
        exit(1);
    }

    return image;
}

int afCameraMultiview::init(const afBaseObjectPtr a_afObjectPtr, const afBaseObjectAttribsPtr a_objectAttribs)
{
    // AMBF OBJECTS CONFIG
    m_camera = (afCameraPtr)a_afObjectPtr;
    m_camera->setOverrideRendering(true);

    m_width = 1000;
    m_height = 1000;
    m_camera->m_width = m_width;
    m_camera->m_height = m_height;
    glfwMakeContextCurrent(m_camera->m_window);
    glfwSetWindowSize(m_camera->m_window, m_width, m_height);

    // ADDITIONAL CHAI OBJECTS CONFIG
    main_cam = new cCamera(NULL);
    side_view_world = new cWorld();
    world_cam = m_camera->getInternalCamera();
    side_cam1 = new cCamera(side_view_world);
    side_cam2 = new cCamera(side_view_world);
    side_cam3 = new cCamera(side_view_world);

    m_frameBuffer = cFrameBuffer::create();
    m_frameBuffer->setup(world_cam, m_width * m_alias_scaling, m_height * m_alias_scaling, true, true, GL_RGBA);

    out_of_volume_img = create_c_image_from_file(out_of_volume_img_path);
    white_background_img = create_c_image_from_file(white_background_img_path);

    world_window = new SideViewWindow("world_window", world_cam, m_width, m_height, m_alias_scaling);

    ct_slice1_window = std::unique_ptr<CtSliceSideWindow>(new CtSliceSideWindow("ct_slice1_window", side_cam1, m_width / 2,
                                                                                m_height / 2, m_alias_scaling,
                                                                                white_background_img, out_of_volume_img));

    ct_slice2_window = std::unique_ptr<CtSliceSideWindow>(new CtSliceSideWindow("ct_slice2_window", side_cam2, m_width / 2,
                                                                                m_height / 2, m_alias_scaling,
                                                                                white_background_img, out_of_volume_img));

    ct_slice3_window = std::unique_ptr<CtSliceSideWindow>(new CtSliceSideWindow("ct_slice3_window", side_cam3, m_width / 2,
                                                                                m_height / 2, m_alias_scaling,
                                                                                white_background_img, out_of_volume_img));

    main_cam->m_frontLayer->addChild(world_window->get_panel());
    main_cam->m_frontLayer->addChild(ct_slice1_window->get_panel());
    main_cam->m_frontLayer->addChild(ct_slice2_window->get_panel());
    main_cam->m_frontLayer->addChild(ct_slice3_window->get_panel());

    // Use publishing frame buffer of current camera to pass rendered image to sim_assisted_nav plugin
    m_camera->m_frameBuffer = new cFrameBuffer();
    m_camera->m_frameBuffer->setup(main_cam, m_width * m_alias_scaling, m_height * m_alias_scaling, true, true, GL_RGBA);

    // update display panel sizes and positions
    windowSizeCallback(m_camera->m_window, m_width, m_height);
    assignGLFWCallbacks();

    std::cout << "End of init" << "\n\n\n\n\n"
              << m_alias_scaling
              << endl;

    // ROS subscriber config
    ros_node_handle = afROSNode::getNode();
    drill_loc_subscriber = ros_node_handle->subscribe(drill_loc_topic, 300, &afCameraMultiview::drill_location_callback, this);

    return 1;
}

void afCameraMultiview::graphicsUpdate()
{
    if (!volume_initialized)
    {
        // Volume pointer needs to be initialized in first graphics update.
        // Volume might not be available when calling the init function
        init_volume_pointer();
        init_volume_slicer();
        volume_initialized = true;

        set_slice_in_side_view(ct_slice_idx);
        total_slices = volume_slices_ptr->getImageCount();
        slice_annotator->print_volume_information();

        ct_slice_update_time = glfwGetTime();

        volume_slices_ptr->selectImage(0);
        set_slice_in_side_view(ct_slice_idx);

        // bool success = ct_slice1->loadFromImage(out_of_volume_img);
        // ct_slice1->setSize(500, 500);
        bool success = ct_slice1_window->update_ct_slice(out_of_volume_img);
        ct_slice1_window->update_ct_slice_size(500, 500);
    }

    if ((glfwGetTime() - ct_slice_update_time > 0.1) && volume_initialized)
    {
        // ct_slice_idx = (ct_slice_idx + 1) % total_slices;
        if (drill_location.x() > 0 && drill_location.y() > 0 && drill_location.z() > 0)
        {
            bool success;
            // 1) CREATE SLICES
            // 2) ANNOTATED SLICES WITH DRILL LOCATION
            // 3) DISPLAY SLICE
            unique_ptr<Slice2D> xy_slice = volume_slicer->create_2d_slice("xy", drill_location.z());
            xy_slice->annotate(drill_location.x(), drill_location.y());
            success = ct_slice1_window->update_ct_slice(xy_slice->volume_slice);
            ct_slice1_window->update_ct_slice_size(500, 500);

            unique_ptr<Slice2D> xz_slice = volume_slicer->create_2d_slice("xz", drill_location.y());
            xz_slice->annotate(drill_location.x(), drill_location.z());
            success = ct_slice2_window->update_ct_slice(xz_slice->volume_slice);
            ct_slice2_window->update_ct_slice_size(500, 500);

            unique_ptr<Slice2D> yz_slice = volume_slicer->create_2d_slice("yz", drill_location.x());
            yz_slice->annotate(drill_location.y(), drill_location.z());
            success = ct_slice3_window->update_ct_slice(yz_slice->volume_slice);
            ct_slice3_window->update_ct_slice_size(500, 500);

            // slice_annotator->restore_slice(); // Removed red marker from previous location
            // slice_annotator->select_and_annotate(drill_location.z(), drill_location.x(), drill_location.y());
            // // slice_annotator->select_and_annotate(ct_slice_idx, drill_location.x(), drill_location.z());
            // set_slice_in_side_view(ct_slice_idx);
        }
        else
        {
            bool success;
            success = ct_slice1_window->update_ct_slice(out_of_volume_img);
            ct_slice1_window->update_ct_slice_size(500, 500);

            success = ct_slice2_window->update_ct_slice(out_of_volume_img);
            ct_slice2_window->update_ct_slice_size(500, 500);

            success = ct_slice3_window->update_ct_slice(out_of_volume_img);
            ct_slice3_window->update_ct_slice_size(500, 500);
        }
        ct_slice_update_time = glfwGetTime();
    }

    glfwMakeContextCurrent(m_camera->m_window);

    // SIMPLE RENDER
    // afRenderOptions ro;
    // ro.m_updateLabels = true;
    // m_camera->render(ro);

    // MANUAL RENDER
    glfwMakeContextCurrent(m_camera->m_window);
    // get width and height of window
    glfwGetFramebufferSize(m_camera->m_window, &m_width, &m_height);
    // render world

    ct_slice1_window->render_view();
    ct_slice2_window->render_view();
    ct_slice3_window->render_view();
    world_window->get_camera()->setStereoMode(C_STEREO_DISABLED);
    world_window->render_view();
    world_window->get_camera()->setStereoMode(C_STEREO_PASSIVE_LEFT_RIGHT);

    main_cam->renderView(m_width, m_height);
    // m_camera->m_frameBuffer->renderView();

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
    // cout << "Closing " << m_camera->getName() << endl;
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

SideViewWindow::SideViewWindow(string window_name, cCamera *camera, int m_width, int m_height,
                               int m_alias_scaling) : window_name(window_name), camera(camera), m_width(m_width),
                                                      m_height(m_height), m_alias_scaling(m_alias_scaling)
{
    buffer = cFrameBuffer::create();
    buffer->setup(camera, m_width * m_alias_scaling, m_height * m_alias_scaling, true, true, GL_RGBA);
    panel = new cViewPanel(buffer);
    update_window_size(m_width, m_height);
}

SideViewWindow::~SideViewWindow()
{

    // cout << "Destroying Side view window " << window_name << endl;
    delete panel;

    // This will trigger a seg fault
    // delete camera;
}

CtSliceSideWindow::CtSliceSideWindow(string window_name, cCamera *camera, int m_width, int m_height,
                                     int m_alias_scaling, cImagePtr white_brackground_img,
                                     cImagePtr out_of_volume_img) : SideViewWindow(window_name, camera, m_width, m_height, m_alias_scaling),
                                                                    white_background_img(white_brackground_img), out_of_volume_img(out_of_volume_img)
{
    // Set background
    background = new cBackground();
    camera->m_backLayer->addChild(background);
    background->setCornerColors(cColorf(1.0f, 0.0f, 1.0f),
                                cColorf(1.0f, 0.0f, 1.0f),
                                cColorf(0.0f, 0.8f, 0.8f),
                                cColorf(0.0f, 0.8f, 0.8f));

    // load bitmaps
    white_background = new cBitmap();
    white_background->loadFromImage(white_background_img);
    camera->m_frontLayer->addChild(white_background);

    ct_slice = new cBitmap();
    ct_slice->loadFromImage(out_of_volume_img);
    camera->m_frontLayer->addChild(ct_slice);

    update_ct_slice_size(m_width, m_height);
}

CtSliceSideWindow::~CtSliceSideWindow()
{
    cout << "Destroying CT slice " << window_name << endl;
    delete white_background;
    delete background;
    delete ct_slice;
}
