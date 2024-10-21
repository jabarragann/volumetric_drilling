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
#include <ambf_server/RosComBase.h>
#include <opencv2/highgui/highgui.hpp>
#include <yaml-cpp/yaml.h>
#include <fstream>

using namespace std;

string g_current_filepath;

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
    ros_node_handle = afROSNode::getNode();

    create_stereo_cam_info_from_yaml(m_camera->getName(), a_objectAttribs);
    // Ros subscribers
    // left_sub = ros_node_handle->subscribe(stereo_cam_info->rostopic_left, 2, &afCameraHMD::left_img_callback, this);
    // right_sub = ros_node_handle->subscribe(stereo_cam_info->rostopic_right, 2, &afCameraHMD::right_img_callback, this);

    left_sub = ros_node_handle->subscribe(stereo_cam_info->rostopic_left, 2, &afCameraHMD::left_compressed_img_callback, this);
    right_sub = ros_node_handle->subscribe(stereo_cam_info->rostopic_right, 2, &afCameraHMD::right_compressed_img_callback, this);

    window_disparity_sub = ros_node_handle->subscribe("/sim_assisted_nav/small_window_disparity", 2, &afCameraHMD::window_disparity_callback, this);

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

    // Variables related to ROS topics
    concat_img_ptr = boost::make_shared<cv_bridge::CvImage>();
    left_img_ptr = boost::make_shared<cv_bridge::CvImage>();
    right_img_ptr = boost::make_shared<cv_bridge::CvImage>();

    // Textures
    m_rosImageTexture = cTexture2d::create();

    m_quadMesh->computeAllNormals();

    // Objects have multiple textures available in AMBF.
    // To pass multiple textures to the shader, we can use these multiple default textures.
    // For this case the rosImageTexture gets assigned to m_texture and
    // the texture from the m_imageBuffer to metallicTexture.

    m_quadMesh->m_texture = m_rosImageTexture;
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
}

void afCameraHMD::reset()
{
}

bool afCameraHMD::close()
{
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
    glUniform1f(glGetUniformLocation(id, "small_window_disparity"), window_disparity);
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
    YAML::Node plugin_config = specificationDataNode["stereo_cam_config"];

    if (plugin_config.IsDefined())
    {
        // Example yaml config
        // left_rostopic: /stereo/left/image_raw
        // right_rostopic: /stereo/right/image_raw
        // format: RGB
        // color_conversion: false

        try
        {
            string left_rostopic = plugin_config["left_rostopic"].as<string>();
            string right_rostopic = plugin_config["right_rostopic"].as<string>();
            string format = plugin_config["format"].as<string>();
            bool color_conversion = plugin_config["color_conversion"].as<bool>();

            stereo_cam_info = new StereoRosCameraWrapper(left_rostopic, right_rostopic, cam_name, format, color_conversion);
        }
        catch (YAML::Exception &e)
        {
            cerr << "stereo_cam_config expects the following config fields " << endl;
            cerr << "left_rostopic" << endl;
            cerr << "right_rostopic" << endl;
            cerr << "format" << endl;
            cerr << "color_conversion" << endl;

            throw runtime_error("Error in stereo_cam_config");
        }
    }
    else
    {
        throw runtime_error("stereo_cam_config not defined in the yaml file");
    }
}

void afCameraHMD::left_compressed_img_callback(const sensor_msgs::CompressedImageConstPtr &msg)
{
    try
    {
        cv::Mat image = cv::imdecode(msg->data, cv::IMREAD_ANYCOLOR | cv::IMREAD_ANYDEPTH);

        if (!image.empty())
        {
            left_img_ptr->image = image;
            left_img_ptr->encoding = sensor_msgs::image_encodings::BGR8;
        }
        else
        {
            ROS_WARN("Converted image is empty.");
            throw runtime_error("Converted image is empty.");
        }
    }
    catch (cv::Exception &e)
    {
        ROS_ERROR("Error decompressing image: %s", e.what());
    }

    // cv::Rect sizeRect(0, 0, left_img_ptr->image.cols - left_img_ptr->image.cols * clipsize, left_img_ptr->image.rows);
    // left_img_ptr->image = left_img_ptr->image(sizeRect);
}
void afCameraHMD::right_compressed_img_callback(const sensor_msgs::CompressedImagePtr &msg)
{
    try
    {
        cv::Mat image = cv::imdecode(msg->data, cv::IMREAD_ANYCOLOR | cv::IMREAD_ANYDEPTH);

        if (!image.empty())
        {
            right_img_ptr->image = image;
            right_img_ptr->encoding = sensor_msgs::image_encodings::BGR8;
        }
        else
        {
            ROS_WARN("Converted image is empty.");
            throw runtime_error("Converted image is empty.");
        }
    }
    catch (cv::Exception &e)
    {
        ROS_ERROR("Error decompressing image: %s", e.what());
    }

    // cv::Rect sizeRect2(clipsize, 0, right_img_ptr->image.cols - right_img_ptr->image.cols * clipsize, right_img_ptr->image.rows);
    // right_img_ptr->image = right_img_ptr->image(sizeRect2);

    // cv::imshow("Right img", right_img_ptr->image);
    // cv::waitKey(1);

    update_ros_textures_for_headset(); // This should go there FIX JUAN.
}
void afCameraHMD::left_img_callback(const sensor_msgs::ImageConstPtr &msg)
{
    try
    {
        left_img_ptr = cv_bridge::toCvCopy(msg, msg->encoding);
    }
    catch (cv_bridge::Exception &e)
    {
        ROS_ERROR("Could not convert");
    }

    // cv::resize(cv_ptr->image,cv_ptr->image,cv::Size(cv_ptr->image.cols/2,cv_ptr->image.rows/2));

    cv::Rect sizeRect(0, 0, left_img_ptr->image.cols - left_img_ptr->image.cols * clipsize, left_img_ptr->image.rows);
    left_img_ptr->image = left_img_ptr->image(sizeRect);

    // cv::imshow("Left img", left_img_ptr->image);
    // cv::waitKey(1);
}

void afCameraHMD::right_img_callback(const sensor_msgs::ImageConstPtr &msg)
{
    try
    {
        right_img_ptr = cv_bridge::toCvCopy(msg, msg->encoding);
        // frame2 = cv::imdecode(cv::Mat(msg->data), CV_LOAD_IMAGE_COLOR);
    }
    catch (cv_bridge::Exception &e)
    {
        ROS_ERROR("Could not convert");
    }

    cv::Rect sizeRect2(clipsize, 0, right_img_ptr->image.cols - right_img_ptr->image.cols * clipsize, right_img_ptr->image.rows);
    right_img_ptr->image = right_img_ptr->image(sizeRect2);

    // cv::imshow("Right img", right_img_ptr->image);
    // cv::waitKey(1);

    update_ros_textures_for_headset();
}

/*
* Process ros images and convert them to chai3d texture to display.
* If left or right images are not received return without doing anything.
*/
void afCameraHMD::update_ros_textures_for_headset()
{
    // Return if ros images are not initialized.
    if (left_img_ptr == nullptr || right_img_ptr == nullptr)
    {
        return;
    }
    if (left_img_ptr->image.cols != right_img_ptr->image.cols || left_img_ptr->image.rows != right_img_ptr->image.rows)
    {
        ROS_WARN("Left and right images have different sizes. Left: %d x %d, Right: %d x %d", left_img_ptr->image.cols, left_img_ptr->image.rows, right_img_ptr->image.cols, right_img_ptr->image.rows);
        return;
    }

    // Process ros images if received left and right.
    cv::hconcat(left_img_ptr->image, right_img_ptr->image, concat_img_ptr->image);
    cv::flip(concat_img_ptr->image, concat_img_ptr->image, 0);

    if (stereo_cam_info->convert_from_RGB2BGR)
    {
        // This is required for zed mini.
        cv::cvtColor(concat_img_ptr->image, concat_img_ptr->image, cv::COLOR_RGB2BGR);
    }

    // Initialize chai ROS texture.
    int ros_image_size = concat_img_ptr->image.cols * concat_img_ptr->image.rows * concat_img_ptr->image.elemSize();
    int texture_image_size = m_rosImageTexture->m_image->getWidth() * m_rosImageTexture->m_image->getHeight() * m_rosImageTexture->m_image->getBytesPerPixel();

    if (ros_image_size != texture_image_size)
    {
        cout << "INITILIZE rosImageTexture" << endl;
        m_rosImageTexture->m_image->erase();

        // Original implementation in Xinhao's plugin
        // m_rosImageTexture->m_image->allocate(cv_ptr->image.cols, cv_ptr->image.rows, getImageFormat(cv_ptr->encoding), getImageType(cv_ptr->encoding));

        m_rosImageTexture->m_image->allocate(concat_img_ptr->image.cols, concat_img_ptr->image.rows, stereo_cam_info->pixel_format_gl, GL_UNSIGNED_BYTE);
        m_rosImageTexture->m_image->setData(concat_img_ptr->image.data, ros_image_size);

        // Only for debuggin purposes
        // m_rosImageTexture->saveToFile("rosImageTexture_juan.png");
    }
    else
    {
        m_rosImageTexture->m_image->setData(concat_img_ptr->image.data, ros_image_size);
    }

    //  cerr << "INFO! Image Sizes" << msg->width << "x" << msg->height << " - " << msg->encoding << endl;
    m_rosImageTexture->markForUpdate();

    // cv::imshow("Concat image", concat_img_ptr->image);
    // cv::waitKey(1);
    // cv::resize(cv_ptr2->image,cv_ptr2->image,cv::Size(cv_ptr2->image.cols/2,cv_ptr2->image.rows/2));
}

void afCameraHMD::window_disparity_callback(const std_msgs::Float32 &msg)
{
    window_disparity = msg.data;
}
