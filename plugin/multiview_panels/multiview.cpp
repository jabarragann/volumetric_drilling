
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
#include <yaml-cpp/yaml.h>

using namespace std;

//------------------------------------------------------------------------------
// DECLARED FUNCTIONS
//------------------------------------------------------------------------------

//------------------------------------------------------------------------------

string g_current_filepath;

void afCameraMultiview::parse_plugin_config(const afBaseObjectAttribsPtr a_objectAttribs)
{
    YAML::Node specificationDataNode;
    // cerr << "INFO! SPECIFICATION DATA " << a_objectAttribs->getSpecificationData().m_rawData << endl;
    specificationDataNode = YAML::Load(a_objectAttribs->getSpecificationData().m_rawData);
    YAML::Node plugin_config = specificationDataNode["multiview_plugin_config"];

    if (plugin_config.IsDefined())
    {
        try
        {
            render_to_frame_buffer = plugin_config["render_to_frame_buffer"].as<bool>();
        }
        catch (YAML::Exception &e)
        {
            cerr << "multiview_plugin_config has some errors" << endl;
            cerr << "Using default value of render_to_frame_buffer: " << render_to_frame_buffer << endl;
        }
    }
}
int afCameraMultiview::init(const afBaseObjectPtr a_afObjectPtr, const afBaseObjectAttribsPtr a_objectAttribs)
{
    // AMBF OBJECTS CONFIG
    m_camera = (afCameraPtr)a_afObjectPtr;
    m_camera->setOverrideRendering(true);

    cout << "" << endl;
    cout << "/*********************************************" << endl;
    cout << "/* Init AMBF Plugin for multiview of CT slices (Loded in camera = " << m_camera->getName() << " )" << endl;
    cout << "/*********************************************" << endl;

    parse_plugin_config(a_objectAttribs);

    // Assistance window config
    m_width = 1000;
    m_height = 1000;
    m_camera->m_width = m_width;
    m_camera->m_height = m_height;
    glfwMakeContextCurrent(m_camera->m_window);
    glfwSetWindowSize(m_camera->m_window, m_width, m_height);

    // ADDITIONAL CHAI OBJECTS CONFIG
    world_cam = m_camera->getInternalCamera();

    init_multi_view_panels();

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
    ros_interface.init(drill_loc_topic);

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

        // Calculate scale factor for CT slices
        // cVector3d volume_voxel_dims = volume_ptr->getVoxelcount();
        float max_dimension = std::max({volume_slices_ptr->getWidth(), volume_slices_ptr->getHeight(), volume_slices_ptr->getImageCount()});
        float scale_factor = 500.0 / max_dimension;
        ct_axial_window->scale_factor = scale_factor;
        ct_coronal_window->scale_factor = scale_factor;
        ct_sagittal_window->scale_factor = scale_factor;

        // total_slices = volume_slices_ptr->getImageCount();
        // volume_slices_ptr->selectImage(0);

        // bool success = ct_axial_window->update_ct_slice(out_of_volume_img);
        // ct_axial_window->update_ct_slice_size(500, 500);
    }
    else
    {
        update_ct_slices_with_drill_location();
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

    ct_axial_window->render_view();
    ct_coronal_window->render_view();
    ct_sagittal_window->render_view();
    render_virtual_camera();

    // (OPTION 1)
    // RENDER ONLY TO THE FRAME BUFFER AND HAVE THE SIM_ASSISTED_NAV PLUGIN HANDLE THE RENDERING.
    // THIS ENABLE THE IMAGE OVER IMAGE VIEW.

    // (OPTION 2)
    // RENDER MULTIVIEW PLUGIN ON THE CAMERA.
    // THIS REQUIRES RENDERING THE MAIN_CAM AND ADDING THE MULTIVE PLUGIN TO MAIN CAM.

    if (render_to_frame_buffer)
    {
        m_camera->m_frameBuffer->renderView(); // (OPT1)
    }
    else
    {
        main_cam->renderView(m_width, m_height); // (OPT2)
    }

    // swap buffers
    glfwSwapBuffers(m_camera->m_window);
}

void afCameraMultiview::physicsUpdate(double dt)
{
    // Process pending ROS callbacks each AMBF iteration.
    if (ros_interface.ros_node_handle)
    {
#if AMBF_ROS1
        ros::spinOnce();
#elif AMBF_ROS2
        rclcpp::spin_some(ros_interface.ros_node_handle);
#endif
    }
}

void afCameraMultiview::reset()
{
}

bool afCameraMultiview::close()
{
    // cout << "Closing " << m_camera->getName() << endl;
    return true;
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

RosInterface::RosInterface()
{
}

RosInterface::~RosInterface()
{
}

void RosInterface::init(const std::string &drill_loc_topic)
{
    ros_node_handle = afROSNode::getNodeAndRegister("/multiview_panels");

    ambf_ral::create_subscriber<AMBF_RAL_MSG(geometry_msgs, PointStamped), RosInterface>
        (drill_loc_subscriber, ros_node_handle, drill_loc_topic, 4, &RosInterface::drill_location_callback, this);
}

#if AMBF_ROS1
    void RosInterface::drill_location_callback(const geometry_msgs::PointStamped& msg)
{
    // drill_location = cVector3d(msg->point.x, msg->point.y, msg->point.z);
    drill_location = cVector3d(msg.point.x, msg.point.y, msg.point.z);
}
#elif AMBF_ROS2
void RosInterface::drill_location_callback(const geometry_msgs::msg::PointStamped::SharedPtr msg)
{
    drill_location = cVector3d(msg->point.x, msg->point.y, msg->point.z);
}
#endif

void afCameraMultiview::render_virtual_camera()
{
    model_3d_window->get_camera()->setStereoMode(C_STEREO_DISABLED);
    static cWorld *empty_fl = new cWorld();

    cWorld *fl = m_camera->getInternalCamera()->m_frontLayer;
    model_3d_window->get_camera()->m_frontLayer = empty_fl;
    model_3d_window->render_view();
    model_3d_window->get_camera()->m_frontLayer = fl;
    model_3d_window->get_camera()->setStereoMode(C_STEREO_PASSIVE_LEFT_RIGHT);
}

void afCameraMultiview::update_ct_slices_with_drill_location()
{
    if (ros_interface.drill_location.x() > 0 && ros_interface.drill_location.y() > 0 && ros_interface.drill_location.z() > 0)
    {
        bool success;
        // 1) CREATE SLICES
        // 2) ANNOTATED SLICES WITH DRILL LOCATION
        // 3) DISPLAY SLICE
        unique_ptr<Slice2D> axial_slice = volume_slicer->create_2d_slice_reverse_y("xy", ros_interface.drill_location.z());
        int reverse_y_loc = axial_slice->slice_height - 1 - ros_interface.drill_location.y();
        axial_slice->annotate(ros_interface.drill_location.x(), reverse_y_loc);
        success = ct_axial_window->update_ct_slice(axial_slice->volume_slice);
        ct_axial_window->maximize_with_scale_factor();

        unique_ptr<Slice2D> coronal_slice = volume_slicer->create_2d_slice("xz", ros_interface.drill_location.y());
        coronal_slice->annotate(ros_interface.drill_location.x(), ros_interface.drill_location.z());
        success = ct_coronal_window->update_ct_slice(coronal_slice->volume_slice);
        ct_coronal_window->maximize_with_scale_factor();

        unique_ptr<Slice2D> sagittal_slice = volume_slicer->create_2d_slice("yz", ros_interface.drill_location.x());
        sagittal_slice->annotate(ros_interface.drill_location.y(), ros_interface.drill_location.z());
        success = ct_sagittal_window->update_ct_slice(sagittal_slice->volume_slice);
        ct_sagittal_window->maximize_with_scale_factor();
    }
    else
    {
        bool success;
        success = ct_axial_window->update_ct_slice(out_of_volume_img);
        ct_axial_window->maximize_slice_when_out_of_volume();

        success = ct_coronal_window->update_ct_slice(out_of_volume_img);
        ct_coronal_window->maximize_slice_when_out_of_volume();

        success = ct_sagittal_window->update_ct_slice(out_of_volume_img);
        ct_sagittal_window->maximize_slice_when_out_of_volume();
    }
}

void afCameraMultiview::windowSizeCallback(GLFWwindow *, int new_width, int new_height)
{
    // update display panel sizes and positions based on window size

    // int halfW = new_width / 2;
    // int halfH = new_height / 2;
    // int offset = 1;
    // world_window->update_window_size(halfW, halfH);
    // world_window->update_panel_location(0, 0);

    // ct_slice1_window->update_window_size(halfW, halfH);
    // ct_slice1_window->update_panel_location(halfW + offset, 0);

    // ct_slice2_window->update_window_size(halfW, halfH);
    // ct_slice2_window->update_panel_location(0, halfH + offset);

    // ct_slice3_window->update_window_size(halfW, halfH);
    // ct_slice3_window->update_panel_location(halfW + offset, halfH + offset);
    // cout << new_width << " " << new_height << endl;
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
}

cImagePtr create_c_image_from_file(string filename)
{
    string file_path = __FILE__;
    string current_filepath = file_path.substr(0, file_path.rfind("/"));
    string complete_img_path = current_filepath + "/sample_imgs/" + filename;

    cImagePtr image = cImage::create();
    bool success = image->loadFromFile(complete_img_path);

    if (!success)
    {
        std::cerr << "ERROR! FAILED TO LOAD OUT OF VOLUME IMAGE " << complete_img_path << endl;
        exit(1);
    }

    return image;
}

void afCameraMultiview::init_multi_view_panels()
{
    main_cam = new cCamera(NULL);
    side_view_world = new cWorld();
    side_cam1 = new cCamera(side_view_world);
    side_cam2 = new cCamera(side_view_world);
    side_cam3 = new cCamera(side_view_world);

    m_frameBuffer = cFrameBuffer::create();
    m_frameBuffer->setup(world_cam, m_width * m_alias_scaling, m_height * m_alias_scaling, true, true, GL_RGBA);

    out_of_volume_img = create_c_image_from_file(background_img_path);
    background_img = create_c_image_from_file(background_img_path);

    int halfW = m_width / 2;
    int halfH = m_height / 2;
    int offset = 1;

    ct_coronal_window = std::unique_ptr<CtSliceSideWindow>(new CtSliceSideWindow("coronal_view", side_cam2,
                                                                                 m_width / 2, m_height / 2,
                                                                                 0, 0, m_alias_scaling,
                                                                                 background_img, out_of_volume_img));

    ct_sagittal_window = std::unique_ptr<CtSliceSideWindow>(new CtSliceSideWindow("sagittal_view", side_cam3,
                                                                                  m_width / 2, m_height / 2,
                                                                                  halfW + offset, 0, m_alias_scaling,
                                                                                  background_img, out_of_volume_img));

    ct_axial_window = std::unique_ptr<CtSliceSideWindow>(new CtSliceSideWindow("axial_view", side_cam1,
                                                                               m_width / 2, m_height / 2,
                                                                               0, halfH + offset, m_alias_scaling,
                                                                               background_img, out_of_volume_img));

    model_3d_window = new SideViewWindow("3d_view", world_cam, m_width, m_height, halfW + offset, halfH + offset, m_alias_scaling);

    main_cam->m_frontLayer->addChild(model_3d_window->get_panel());
    main_cam->m_frontLayer->addChild(ct_axial_window->get_panel());
    main_cam->m_frontLayer->addChild(ct_coronal_window->get_panel());
    main_cam->m_frontLayer->addChild(ct_sagittal_window->get_panel());
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

SideViewWindow::SideViewWindow(string window_name, cCamera *camera, int m_width, int m_height, int x_pos, int y_pos,
                               int m_alias_scaling) : window_name(window_name), camera(camera), m_width(m_width),
                                                      m_height(m_height), m_alias_scaling(m_alias_scaling)
{
    buffer = cFrameBuffer::create();
    buffer->setup(camera, m_width * m_alias_scaling, m_height * m_alias_scaling, true, true, GL_RGBA);
    panel = new cViewPanel(buffer);
    update_window_size(m_width, m_height);
    update_panel_location(x_pos, y_pos);
}

SideViewWindow::~SideViewWindow()
{

    // cout << "Destroying Side view window " << window_name << endl;
    delete panel;

    // This will trigger a seg fault
    // delete camera;
}

CtSliceSideWindow::CtSliceSideWindow(string window_name, cCamera *camera, int m_width, int m_height, int pos_x, int pos_y,
                                     int m_alias_scaling, cImagePtr white_brackground_img,
                                     cImagePtr out_of_volume_img) : SideViewWindow(window_name, camera, m_width, m_height, pos_x, pos_y, m_alias_scaling),
                                                                    background_cimage(white_brackground_img), outofvolume_cimage(out_of_volume_img)
{
    // Set background
    background = new cBackground();
    camera->m_backLayer->addChild(background);
    background->setCornerColors(cColorf(1.0f, 0.0f, 1.0f),
                                cColorf(1.0f, 0.0f, 1.0f),
                                cColorf(0.0f, 0.8f, 0.8f),
                                cColorf(0.0f, 0.8f, 0.8f));

    // load bitmaps
    background_cbitmap = new cBitmap();
    background_cbitmap->loadFromImage(background_cimage);
    camera->m_frontLayer->addChild(background_cbitmap);

    ctslice_cbitmap = new cBitmap();
    ctslice_cbitmap->loadFromImage(out_of_volume_img);
    camera->m_frontLayer->addChild(ctslice_cbitmap);

    update_ct_slice_size(m_width, m_height);
}

void CtSliceSideWindow::maximize_with_scale_factor()
{
    int new_width = ctslice_cbitmap->getWidth();
    int new_height = ctslice_cbitmap->getHeight();

    if (scale_factor > 0)
    {
        new_width = ctslice_cbitmap->getWidth() * scale_factor;
        new_height = ctslice_cbitmap->getHeight() * scale_factor;
    }

    // Center slice
    float x_offset = (c_viewpanel_dim - new_width) / 2;
    float y_offset = (c_viewpanel_dim - new_height) / 2;

    // Update ctslice bitmap
    ctslice_cbitmap->setLocalPos(x_offset, y_offset);
    update_ct_slice_size(new_width, new_height);

    // TO VISUALIZE BORDERS
    // background_cbitmap->setLocalPos(x_offset, y_offset);
    // background_cbitmap->setSize(new_width, new_height);

    // TO COVER THE WHOLE PANE
    background_cbitmap->setLocalPos(0, 0);
    background_cbitmap->setSize(c_viewpanel_dim, c_viewpanel_dim);
}

void CtSliceSideWindow::maximize_slice(int new_max_dim)
{

    int w = ctslice_cbitmap->getWidth();
    int h = ctslice_cbitmap->getHeight();

    if (w >= h)
    {
        float aspect = (float)h / (float)w;
        ctslice_cbitmap->setSize(new_max_dim, new_max_dim * aspect);
    }
    else
    {
        float aspect = (float)w / (float)h;
        ctslice_cbitmap->setSize(new_max_dim * aspect, new_max_dim);
    }
}

CtSliceSideWindow::~CtSliceSideWindow()
{
    cout << "Destroying CT slice " << window_name << endl;
    delete background_cbitmap;
    delete background;
    delete ctslice_cbitmap;
}
