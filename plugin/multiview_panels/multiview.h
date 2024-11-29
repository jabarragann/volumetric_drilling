
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

// To silence warnings on MacOS
#define GL_SILENCE_DEPRECATION
#include <afFramework.h>
#include "memory"
#include "vector"
#include "ros/ros.h"
#include "volume_slicer.h"

using namespace std;
using namespace ambf;

// class SliceAnnotator;
class SideViewWindow;
class CtSliceSideWindow;

class afCameraMultiview : public afObjectPlugin
{
public:
    afCameraMultiview();
    ~afCameraMultiview();
    virtual int init(const afBaseObjectPtr a_afObjectPtr, const afBaseObjectAttribsPtr a_objectAttribs) override;
    virtual void graphicsUpdate() override;
    virtual void physicsUpdate(double dt) override;
    virtual void reset() override;
    virtual bool close() override;

    void updateHMDParams();

    void makeFullScreen();

    void windowSizeCallback(GLFWwindow *w, int width, int height);
    void assignGLFWCallbacks();

    void init_multi_view_panels();
    void init_volume_pointer();
    void init_volume_slicer();

    void parse_plugin_config(const afBaseObjectAttribsPtr a_objectAttribs);

    // Get location of drill tip from volumetric drilling to display it in side windows.
    void drill_location_callback(const geometry_msgs::PointStamped::ConstPtr &msg);

    // Render virtual camera in the multi-window view.
    void render_virtual_camera();

    // Update CT slices based on drill location.
    void update_ct_slices_with_drill_location();

protected:
    bool render_to_frame_buffer = true;
    afCameraPtr m_camera; // AMBF camera pointer
    cFrameBufferPtr m_frameBuffer;

    cCamera *main_cam;  // Parent camera for the world and CT panels cameras
    cCamera *world_cam; // Camera rendering the volume

    // Camera pointing to a empty world to display CT slices
    cCamera *side_cam1; // Camera pointing to a empty world to display CT slices
    cCamera *side_cam2; // Camera pointing to a empty world to display CT slices
    cCamera *side_cam3; // Camera pointing to a empty world to display CT slices

    SideViewWindow *model_3d_window;
    std::unique_ptr<CtSliceSideWindow> ct_axial_window;
    std::unique_ptr<CtSliceSideWindow> ct_coronal_window;
    std::unique_ptr<CtSliceSideWindow> ct_sagittal_window;

    cWorld *side_view_world;
    cMesh *m_quadMesh;
    int m_width;
    int m_height;
    int m_alias_scaling;
    cShaderProgramPtr m_shaderPgm;

    // Images loaded from file
    cImagePtr out_of_volume_img;
    cImagePtr background_img;

    // Timers
    int ct_slice_idx = 0;
    int total_slices = 0;

    // Volume
    cVoxelObject *c_voxel_object;
    bool volume_initialized = false;
    cMultiImagePtr volume_slices_ptr;

    std::unique_ptr<VolumeSlicer> volume_slicer;

    ros::NodeHandle *ros_node_handle;
    ros::Subscriber drill_loc_subscriber;
    cVector3d drill_location;

    // Config strings
    string drill_loc_topic = "/ambf/env/plugin/volumetric_drilling/drill_location_in_volume";
    string out_of_volume_img_path = "plugin/multiview_panels/sample_imgs/out_of_volume.jpg";
    string background_img_path = "plugin/multiview_panels/sample_imgs/black_background.jpg";

protected:
    float m_viewport_scale[2];
    float m_distortion_coeffs[4];
    float m_aberr_scale[3];
    float m_sep;
    float m_left_lens_center[2];
    float m_right_lens_center[2];
    float m_warp_scale;
    float m_warp_adj;
    float m_vpos;
};

class SideViewWindow
{
protected:
    string window_name;
    cFrameBufferPtr buffer;
    cViewPanel *panel;
    cCamera *camera;
    int m_width;
    int m_height;
    int m_alias_scaling;
    int c_viewpanel_dim = 500;

public:
    SideViewWindow(string window_name, cCamera *camera, int m_width, int m_height, int pos_x, int pos_y, int m_alias_scaling);
    ~SideViewWindow();
    cViewPanel *get_panel() { return panel; }
    void render_view() { buffer->renderView(); }
    void update_window_size(int width, int height)
    {
        buffer->setSize(width, height);
        panel->setSize(width, height);
        c_viewpanel_dim = width;
    }
    void update_panel_location(int x, int y) { panel->setLocalPos(x, y); }
    cCamera *get_camera() { return camera; }
};
class CtSliceSideWindow : public SideViewWindow
{
    cBitmap *background_cbitmap;
    cBitmap *ctslice_cbitmap;
    cBackground *background;
    cImagePtr outofvolume_cimage;
    cImagePtr background_cimage;

public:
    float scale_factor = -1.0;

    CtSliceSideWindow(string window_name, cCamera *camera, int m_width, int m_height, int pos_x, int pos_y, int m_alias_scaling,
                      cImagePtr white_brackground_img, cImagePtr out_of_volume_img);
    ~CtSliceSideWindow();
    bool update_ct_slice(cImagePtr ct_slice_img) { return ctslice_cbitmap->loadFromImage(ct_slice_img); };

    void maximize_with_scale_factor();

    // Maximize slice while maitaining aspect ratio
    void maximize_slice(int new_max_dim);

    void update_ct_slice_size(int width, int height)
    {
        ctslice_cbitmap->setSize(width, height);
    }
    void maximize_slice_when_out_of_volume()
    {
        ctslice_cbitmap->setSize(c_viewpanel_dim, c_viewpanel_dim);
        ctslice_cbitmap->setLocalPos(0, 0);
    }
};

AF_REGISTER_OBJECT_PLUGIN(afCameraMultiview)