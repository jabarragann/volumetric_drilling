
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

using namespace std;
using namespace ambf;

class SliceAnnotator;
class afCameraMultiview : public afObjectPlugin
{
public:
    afCameraMultiview();
    virtual int init(const afBaseObjectPtr a_afObjectPtr, const afBaseObjectAttribsPtr a_objectAttribs) override;
    virtual void graphicsUpdate() override;
    virtual void physicsUpdate(double dt) override;
    virtual void reset() override;
    virtual bool close() override;

    void updateHMDParams();

    void makeFullScreen();

    void windowSizeCallback(GLFWwindow *w, int width, int height);
    void assignGLFWCallbacks();

    void init_volume_pointer();
    void set_slice_in_side_view(int slice);

protected:
    afCameraPtr m_camera; // AMBF camera pointer
    cFrameBufferPtr m_frameBuffer;

    cCamera *main_cam; // Parent camera for the word and side cameras

    cCamera *world_cam; // Camera rendering the volumen
    cCamera *side_cam;  // Camera pointing to a empty world to display CT slices
    cFrameBufferPtr world_buff;
    cFrameBufferPtr side_buff;
    cViewPanel *world_panel;
    cViewPanel *side_panel;

    cWorld *side_view_world;
    cMesh *m_quadMesh;
    int m_width;
    int m_height;
    int m_alias_scaling;
    cShaderProgramPtr m_shaderPgm;

    // Bitmaps
    cBitmap *sample_bitmap;
    cBitmap *ct_slice1;

    // Timers
    int ct_slice_idx = 0;
    int total_slices = 0;
    float ct_slice_update_time = 0.0;

    // Volume
    cVoxelObject *volume_voxels;
    bool volume_initialized = false;
    cMultiImagePtr volume_slices_ptr;

    std::unique_ptr<SliceAnnotator> slice_annotator;

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

// TODO: Move the function implementations in this class to `multiview.cpp`
class SliceAnnotator
{
public:
    int slice_width;
    int slice_height;
    int number_of_slices;
    cMultiImagePtr volume_slices_ptr;
    cColorb marker_color;
    int marker_size = 6;

    SliceAnnotator(cMultiImagePtr volume_slices_ptr)
    {
        this->volume_slices_ptr = volume_slices_ptr;

        this->slice_width = volume_slices_ptr->getWidth();
        this->slice_height = volume_slices_ptr->getHeight();
        this->number_of_slices = volume_slices_ptr->getImageCount();

        this->marker_color = cColorb(254, 0, 0);
    }

    void select_and_annotate(int slice_idx, int x, int y)
    {
        volume_slices_ptr->selectImage(slice_idx);
        for (int i = 0; i < marker_size; i++)
        {
            for (int j = 0; j < marker_size; j++)
            {
                volume_slices_ptr->setPixelColor((i + x + slice_idx) % slice_width, (j + y + slice_idx) % slice_height, marker_color);
            }
        }
    }

    void print_volume_information()
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
};

AF_REGISTER_OBJECT_PLUGIN(afCameraMultiview)