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

#include "sim_assisted_nav.h"
#include "camera_interfaces/camera_interface_factory.h"
#include <ambf_server/RosComBase.h>
#include <opencv2/highgui/highgui.hpp>
#include <opencv2/imgproc.hpp>
#include <yaml-cpp/yaml.h>
#include <fstream>

using namespace std;

static string g_current_filepath;

afCameraHMD::afCameraHMD()
{
    // For HTC Vive Pro
    m_width = 2880;
    m_height = 1600;
    m_alias_scaling = 1.0;
}

int afCameraHMD::init(const afBaseObjectPtr a_afObjectPtr, const afBaseObjectAttribsPtr a_objectAttribs)
{
    m_camera = (afCameraPtr)a_afObjectPtr; // Get pointer to camera
    assignGLFWCallbacks();
    create_stereo_cam_info_from_yaml(m_camera->getName(), a_objectAttribs);

    // Build the single stereo camera source selected by the video_source config.
    m_camera_interface = create_stereo_camera_interface(*stereo_cam_info);
    if (!m_camera_interface || !m_camera_interface->init())
    {
        cerr << "ERROR! Failed to create/initialize camera interface for source '"
             << stereo_cam_info->video_source << "'." << endl;
        return -1;
    }

    // Variables related to ROS topics
    ros_interface.init();

    m_camera->setOverrideRendering(true);

    m_camera->getInternalCamera()->m_stereoOffsetW = 0.1;

    m_frameBuffer = cFrameBuffer::create();
    m_frameBuffer->setup(m_camera->getInternalCamera(), m_width * m_alias_scaling, m_height * m_alias_scaling, true, true, GL_RGBA);

    string file_path = __FILE__;
    g_current_filepath = file_path.substr(0, file_path.rfind("/"));

    afShaderAttributes shaderAttribs;
    shaderAttribs.m_shaderDefined = true;
    shaderAttribs.m_vtxFilepath = g_current_filepath + "/shaders/sim_assisted_shader.vs";
    shaderAttribs.m_fragFilepath = g_current_filepath + "/shaders/sim_assisted_shader.fs";

    m_shaderPgm = afShaderUtils::createFromAttribs(&shaderAttribs, m_camera->getName(), "SIM_ASSISTED_CAM");
    if (!m_shaderPgm)
    {
        cerr << "ERROR! FAILED TO LOAD SHADER PGM \n";
        return -1;
    }

    m_quadMesh = new cMesh();
    // clang-format off
    float quad[] = {
        // positions
        -1.0f, 1.0f, 0.0f,
        -1.0f, -1.0f, 0.0f,
        1.0f, -1.0f, 0.0f,
        -1.0f, 1.0f, 0.0f,
        1.0f, -1.0f, 0.0f,
        1.0f, 1.0f, 0.0f,
    };
    // clang-format on

    for (int vI = 0; vI < 2; vI++)
    {
        int off = vI * 9;
        cVector3d v0(quad[off + 0], quad[off + 1], quad[off + 2]);
        cVector3d v1(quad[off + 3], quad[off + 4], quad[off + 5]);
        cVector3d v2(quad[off + 6], quad[off + 7], quad[off + 8]);
        m_quadMesh->newTriangle(v0, v1, v2);
    }
    m_quadMesh->m_vertices->setTexCoord(1, 0.0, 0.0, 1.0);
    m_quadMesh->m_vertices->setTexCoord(2, 1.0, 0.0, 1.0);
    m_quadMesh->m_vertices->setTexCoord(0, 0.0, 1.0, 1.0);
    m_quadMesh->m_vertices->setTexCoord(3, 0.0, 1.0, 1.0);
    m_quadMesh->m_vertices->setTexCoord(4, 1.0, 0.0, 1.0);
    m_quadMesh->m_vertices->setTexCoord(5, 1.0, 1.0, 1.0);

    // Textures
    m_hmdImageTexture = cTexture2d::create();

    m_quadMesh->computeAllNormals();

    // Objects have multiple textures available in AMBF.
    // To pass multiple textures to the shader, we can use these multiple default textures.
    // For this case the rosImageTexture gets assigned to m_texture and
    // the texture from the m_imageBuffer to metallicTexture.

    m_quadMesh->m_texture = m_hmdImageTexture;
    // m_quadMesh->m_metallicTexture = m_frameBuffer->m_imageBuffer;

    if (m_camera->m_frameBuffer->m_imageBuffer == nullptr)
    {
        throw runtime_error("Frame buffer of m_camera should be initilized in the multiview_panels plugin");
    }
    m_quadMesh->m_metallicTexture = m_camera->m_frameBuffer->m_imageBuffer;

    m_quadMesh->setUseTexture(true);

    m_quadMesh->setShaderProgram(m_shaderPgm);
    m_quadMesh->setShowEnabled(true);

    m_vrWorld = new cWorld();
    m_vrWorld->addChild(m_quadMesh);

    cerr << "INFO! LOADING VR PLUGIN \n";
    cout << "JUAN!!!!\n\n\n\n";

    return 1;
}

void afCameraHMD::graphicsUpdate()
{
    static bool first_time = true;
    // if (first_time)
    // {
    //     makeFullScreen();
    //     first_time = false;
    // }

    update_textures_for_headset();

    // updateHMDParams(); // Update HMD parameters before m_frameBuffer render creates problems.
    glfwMakeContextCurrent(m_camera->m_window);
    m_frameBuffer->renderView();
    updateHMDParams();
    afRenderOptions ro;
    ro.m_updateLabels = true;

    cWorld *cachedWorld = m_camera->getInternalCamera()->getParentWorld();
    m_camera->getInternalCamera()->setStereoMode(C_STEREO_DISABLED);
    m_camera->getInternalCamera()->setParentWorld(m_vrWorld);
    static cWorld *ew = new cWorld();
    cWorld *fl = m_camera->getInternalCamera()->m_frontLayer;
    m_camera->getInternalCamera()->m_frontLayer = ew;
    m_camera->render(ro);
    m_camera->getInternalCamera()->m_frontLayer = fl;
    m_camera->getInternalCamera()->setStereoMode(C_STEREO_PASSIVE_LEFT_RIGHT);
    m_camera->getInternalCamera()->setParentWorld(cachedWorld);
}

void afCameraHMD::physicsUpdate(double dt)
{
#if AMBF_ROS1
    ros::spinOnce();
#elif AMBF_ROS2
    rclcpp::spin_some(ros_interface.ros_node_handle);
#endif
}

void afCameraHMD::reset()
{
}

bool afCameraHMD::close()
{
    // Tear down the camera source (ZED close() / Decklink release()) while the
    // GL/ROS context is still valid, rather than at process exit.
    m_camera_interface.reset();
    return true;
}

void afCameraHMD::updateHMDParams()
{
    GLint id = m_shaderPgm->getId();
    //    cerr << "INFO! Shader ID " << id << endl;
    glUseProgram(id);

    // m_quadMesh->m_texture which points m_rosImageTexture gets automatically assigned to texture unit 0.
    glUniform1i(glGetUniformLocation(id, "rosImageTexture"), 0);
    // m_quadMesh->m_metallic which points to a frameBuffer gets assigned to texture unit 2.
    glUniform1i(glGetUniformLocation(id, "frameBufferTexture"), 2);

    // Additional parameters
    glUniform1f(glGetUniformLocation(id, "small_window_disparity"), ros_interface.window_disparity);

    // Toggle the small picture-over-picture windows on/off (bool uniform set via int).
    glUniform1i(glGetUniformLocation(id, "show_small_window"), ros_interface.show_small_window ? 1 : 0);

    glUniform1i(glGetUniformLocation(id, "window_width"), m_width);
    glUniform1i(glGetUniformLocation(id, "window_height"), m_height);
}

void afCameraHMD::makeFullScreen()
{
    const GLFWvidmode *mode = glfwGetVideoMode(m_camera->m_monitor);
    int w = 2880;
    int h = 1600;
    int x = mode->width - w;
    int y = mode->height - h;
    int xpos, ypos;
    glfwGetMonitorPos(m_camera->m_monitor, &xpos, &ypos);
    x += xpos;
    y += ypos;
    glfwSetWindowPos(m_camera->m_window, x, y);
    glfwSetWindowSize(m_camera->m_window, w, h);
    m_camera->m_width = w;
    m_camera->m_height = h;
    glfwSwapInterval(0);
    cerr << "\t Making " << m_camera->getName() << " fullscreen \n";
}

void afCameraHMD::create_stereo_cam_info_from_yaml(string cam_name, const afBaseObjectAttribsPtr a_objectAttribs)
{
    YAML::Node specificationDataNode;

    // cerr << "INFO! SPECIFICATION DATA " << a_objectAttribs->getSpecificationData().m_rawData << endl;
    specificationDataNode = YAML::Load(a_objectAttribs->getSpecificationData().m_rawData);
    YAML::Node plugin_config = specificationDataNode["sim_assisted_nav_plugin_config"];

    if (!plugin_config.IsDefined())
    {
        throw runtime_error("sim_assisted_nav_plugin_config not defined in the yaml file");
    }

    // Example yaml config
    // video_source: ros          # ros, zed or decklink
    // format: RGB                # RGB or RGBA
    // color_conversion: false
    // left_rostopic: /stereo/left/image_raw    # video_source: ros only
    // right_rostopic: /stereo/right/image_raw  # video_source: ros only
    // left_device: 0             # video_source: decklink only
    // right_device: 1            # video_source: decklink only

    try
    {
        auto cfg = std::make_unique<StereoCameraConfig>();
        cfg->camera_name = cam_name;
        cfg->video_source = plugin_config["video_source"].as<string>();
        cfg->pixel_format = plugin_config["format"].as<string>();
        cfg->convert_from_RGB2BGR = plugin_config["color_conversion"].as<bool>();

        // Source-specific keys are read only for the matching video_source.
        if (cfg->video_source == "ros")
        {
            cfg->rostopic_left = plugin_config["left_rostopic"].as<string>();
            cfg->rostopic_right = plugin_config["right_rostopic"].as<string>();
        }
        else if (cfg->video_source == "decklink")
        {
            cfg->left_device = plugin_config["left_device"].as<int>();
            cfg->right_device = plugin_config["right_device"].as<int>();
        }
        // "zed" needs no source-specific keys.

        cfg->validate();
        stereo_cam_info = std::move(cfg);
    }
    catch (YAML::Exception &e)
    {
        cerr << "sim_assisted_nav_plugin_config expects the following config fields " << endl;
        cerr << "video_source (ros, zed or decklink)" << endl;
        cerr << "format" << endl;
        cerr << "color_conversion" << endl;
        cerr << "left_rostopic, right_rostopic (video_source: ros)" << endl;
        cerr << "left_device, right_device (video_source: decklink)" << endl;

        throw runtime_error("Error in sim_assisted_nav_plugin_config");
    }
}

// TODO: callbacks for raw video are not use and are not updated with the latest logic.

// void afCameraHMD::left_img_callback(const sensor_msgs::ImageConstPtr &msg)
// {
//     try
//     {
//         left_img_ptr = cv_bridge::toCvCopy(msg, msg->encoding);
//     }
//     catch (cv_bridge::Exception &e)
//     {
//         ROS_ERROR("Could not convert");
//     }

//     // cv::resize(cv_ptr->image,cv_ptr->image,cv::Size(cv_ptr->image.cols/2,cv_ptr->image.rows/2));

//     cv::Rect sizeRect(0, 0, left_img_ptr->image.cols - left_img_ptr->image.cols * clipsize, left_img_ptr->image.rows);
//     left_img_ptr->image = left_img_ptr->image(sizeRect);

//     // cv::imshow("Left img", left_img_ptr->image);
//     // cv::waitKey(1);
// }

// void afCameraHMD::right_img_callback(const sensor_msgs::ImageConstPtr &msg)
// {
//     try
//     {
//         right_img_ptr = cv_bridge::toCvCopy(msg, msg->encoding);
//         // frame2 = cv::imdecode(cv::Mat(msg->data), CV_LOAD_IMAGE_COLOR);
//     }
//     catch (cv_bridge::Exception &e)
//     {
//         ROS_ERROR("Could not convert");
//     }

//     cv::Rect sizeRect2(clipsize, 0, right_img_ptr->image.cols - right_img_ptr->image.cols * clipsize, right_img_ptr->image.rows);
//     right_img_ptr->image = right_img_ptr->image(sizeRect2);

//     // cv::imshow("Right img", right_img_ptr->image);
//     // cv::waitKey(1);

//     // update_ros_textures_for_headset();
// }

/*
 * Pull the latest stereo pair from the active camera source and convert it to
 * a chai3d texture to display. If a fresh pair is not available, return without
 * doing anything.
 */
void afCameraHMD::update_textures_for_headset()
{
    // grab() pulls a fresh pair for pull-based sources (ZED, Decklink) and is a
    // no-op for push-based ROS topics.
    if (!m_camera_interface->grab() || !m_camera_interface->has_received_stereo_images())
    {
        return;
    }

    // TODO: For the ROS source, left_image()/right_image() are filled by the ROS
    // TODO: callback thread while this graphics thread reads them. The clone()s
    // TODO: below take a private copy, but a mutex in RosStereoCameraInterface
    // TODO: would be the proper fix.
    cv::Mat left_img = m_camera_interface->left_image().clone();
    cv::Mat right_img = m_camera_interface->right_image().clone();

    if (left_img.cols != right_img.cols || left_img.rows != right_img.rows)
    {
        cerr << "Left and right images have different sizes. Left: "
             << left_img.cols << " x " << left_img.rows
             << ", Right: " << right_img.cols << " x " << right_img.rows << endl;
        return;
    }

    // m_concat_img must be a member: chai3d's setData stores the pointer without
    // copying, so the buffer backing it must outlive this function.
    cv::hconcat(left_img, right_img, m_concat_img);
    cv::flip(m_concat_img, m_concat_img, 0);

    if (stereo_cam_info->convert_from_RGB2BGR)
    {
        // This is required for zed mini.
        cv::cvtColor(m_concat_img, m_concat_img, cv::COLOR_RGB2BGR);
    }

    // Initialize chai ROS texture.
    int ros_image_size = m_concat_img.cols * m_concat_img.rows * m_concat_img.elemSize();
    int texture_image_size = m_hmdImageTexture->m_image->getWidth() * m_hmdImageTexture->m_image->getHeight() * m_hmdImageTexture->m_image->getBytesPerPixel();

    if (ros_image_size != texture_image_size)
    {
        cout << "INITILIZE rosImageTexture" << endl;
        m_hmdImageTexture->m_image->erase();
        m_hmdImageTexture->m_image->allocate(m_concat_img.cols, m_concat_img.rows, stereo_cam_info->pixel_format_gl, GL_UNSIGNED_BYTE);
    }

    m_hmdImageTexture->m_image->setData(m_concat_img.data, ros_image_size);
    m_hmdImageTexture->markForUpdate();
}

void afCameraHMD::assignGLFWCallbacks()
{
    glfwSetWindowUserPointer(m_camera->m_window, this);

    // Configure callbacks
    // The lambda function can only get access to the class method by using `glfwGetWindowUserPointer`
    void (*lambda_resize_window)(GLFWwindow *, int, int) = [](GLFWwindow *w, int width, int height)
    {
        static_cast<afCameraHMD *>(glfwGetWindowUserPointer(w))->windowSizeCallback(w, width, height);
    };
    glfwSetFramebufferSizeCallback(m_camera->m_window, lambda_resize_window);
}

void afCameraHMD::windowSizeCallback(GLFWwindow *window_ptr, int width, int height)
{
    m_width = width;
    m_height = height;

    // cout << "Window size callback" << endl;
    // cout << width << " " << height << endl;
}
