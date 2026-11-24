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
#include "footpedal.h"
#include "camera_panel_manager.h"
#include "wave_generator.h"
#include "gaze_marker_controller.h"
#include "drill_manager.h"
#include "memory"
#include "ros_interface.h"
#include <iosfwd>
#include <string>
#include <atomic>
#include <thread>
#include <mutex>
#include <fstream>
#include <rclcpp/rclcpp.hpp>
#include <volumetric_drilling_msgs/srv/save_volume.hpp>

using namespace std;
using namespace ambf;

class Transform2VolumeCoordinates;

class afVolmetricDrillingPlugin : public afSimulatorPlugin
{
public:
    afVolmetricDrillingPlugin();
    virtual int init(int argc, char **argv, const afWorldPtr a_afWorld) override;
    virtual void keyboardUpdate(GLFWwindow *a_window, int a_key, int a_scancode, int a_action, int a_mods) override;
    virtual void mouseBtnsUpdate(GLFWwindow *a_window, int a_button, int a_action, int a_modes) override;
    virtual void mousePosUpdate(GLFWwindow *a_window, double x_pos, double y_pos) override {}
    virtual void mouseScrollUpdate(GLFWwindow *a_window, double x_pos, double y_pos) override;
    virtual void graphicsUpdate() override;
    virtual void physicsUpdate(double dt) override;
    virtual void reset() override;
    virtual bool close() override;

protected:
    void sliceVolume(int axisIdx, double delta);

    // Rotate the main camera's up vector about its look axis by a_angleRad,
    // keeping the camera position and look-at target fixed.
    void rotateCameraUpVector(double a_angleRad);

    // Print the main camera's current pose (location, look at, up) in the
    // world.yaml format so it can be copied directly into the ADF file, and
    // also write it to ./main_camera_info.yaml (reusable as a --cpf input).
    void printCameraPose();

    // Stream the main camera's current pose as a `main_camera:` YAML block
    // (location / look at / up) to os, matching the world.yaml key style.
    void writeMainCameraPoseYaml(std::ostream &os);

    // Override the main camera pose (and its Ctrl+V reset pose) with the
    // location / look at / up read from file_path. If the file is missing or
    // malformed, the pose from world.yaml is kept.
    void overrideMainCameraPoseFromFile(const std::string &file_path);

    // Print a summary of the SAINT / sim-assisted-nav keyboard shortcuts to
    // the terminal. Bound to '?'.
    void printSaintKeyboardShortcuts();

    void makeVRWindowFullscreen(afCameraPtr vrCam, int monitor_number = -1);

    void updateButtons();

    void initializeLabels();

    afCameraPtr findAndAppendCamera(string cam_name);

    void publishDrillTipLocationInsideVolume();

    // Save every Z slice of the current volume as <dir>/plane00<z>.png, with z
    // zero-padded to the digits of the last slice index (e.g. plane00009.png).
    // Empty a_outputDir uses resources/intermediate_volumes/<volume>/<timestamp>.
    // Returns the number of slices written (-1 on error); a_savedDir receives the folder.
    int saveIntermediateVolumes(const std::string &a_outputDir = "", std::string *a_savedDir = nullptr);

    // ROS 2 service <ns>/volumetric_drilling/save_volume (SaveVolume.srv), served
    // from its own node + executor thread so it works without the keyboard.
    void initSaveVolumeService(const std::string &a_namespace);
    void shutdownSaveVolumeService();
    void onSaveVolume(const std::shared_ptr<volumetric_drilling_msgs::srv::SaveVolume::Request> a_req,
                      std::shared_ptr<volumetric_drilling_msgs::srv::SaveVolume::Response> a_res);

    // Summary of voxel-removal contacts so far (used to check whether the
    // voxel removal threshold actually limits removal).
    std::string contactStatsString();

    // Optional per-physics-step diagnostic log (--physics_log <file>, off by default).
    void writePhysicsLogLine(double dt);
    void flushPhysicsLog();

private:
    cVoxelObject *m_voxelObj;

    int m_renderingMode = 0;

    double m_opticalDensity;

    cMutex m_mutexVoxel;

    // Save-volume service (ROS 2 only).
    rclcpp::Node::SharedPtr m_serviceNode;
    rclcpp::executors::SingleThreadedExecutor::SharedPtr m_serviceExecutor;
    rclcpp::Service<volumetric_drilling_msgs::srv::SaveVolume>::SharedPtr m_saveVolumeService;
    std::thread m_serviceThread;

    // Voxel-removal contact statistics, written by the physics thread.
    std::atomic<uint64_t> m_removalTicks{0};   // physics steps that removed voxels
    std::atomic<uint64_t> m_cappedTicks{0};    // ... where contacts > removal threshold
    std::atomic<uint64_t> m_contactEvents{0};  // total contact events in those steps
    std::atomic<uint64_t> m_voxelsRemoved{0};  // total voxels removed

    // Per-physics-step diagnostic log (enabled only with --physics_log).
    bool m_physicsLogOn = false;
    std::ofstream m_physicsLog;
    std::mutex m_physicsLogMutex;
    int m_logColorOk = -1;   // -1 tip not in contact / not target, 0 non-drillable voxel, 1 drillable
    int m_logEvents = 0;
    int m_logRemoved = 0;

    cCollisionAABBBox m_volumeUpdate;

    cColorb m_zeroColor;

    bool m_flagStart = true;

    int m_counter = 0;

    cGenericObject *m_selectedObject = NULL;

    bool m_flagMarkVolumeForUpdate = false;

    afVolumePtr m_volumeObject;

    // camera to render the world
    afCameraPtr m_mainCamera, m_cameraL, m_cameraR, m_stereoCamera;

    map<string, afCameraPtr> m_cameras;

    // warning pop-up label
    cLabel *m_warningLabel;

    // color property of bone
    cColorb m_boneColor;

    // color property for non drill object
    cColorb m_nonDrillColor;

    // get color of voxels at (x,y,z)
    cColorb m_storedColor;

    bool m_enableVolumeSmoothing = false;

    int m_volumeSmoothingLevel = 2;

    cLabel *m_volumeSmoothingLabel;

    cVector3d m_maxVolCorner, m_minVolCorner;

    cVector3d m_maxTexCoord, m_minTexCoord;

    cVector3d m_textureCoordScale; // Scale between volume corners extent and texture coordinates extent

    DrillManager m_drillManager;

    FootPedal m_footpedal;

    WaveGenerator m_waveGenerator;

    GazeMarkerController m_gazeMarkerController;

    CameraPanelManager m_panelManager;

    std::unique_ptr<Transform2VolumeCoordinates> m_volume_coord_utils;

    SimulationAssistedNavRosInterface m_simAssistedNavRosInterface;

    bool m_isUsingDrillForCursor = true;
    afRigidBodyPtr m_drillTipPtr, m_drillReferencePtr;
    cVector3d manual_indexes_for_slices = cVector3d(0, 0, 0);
};

class Transform2VolumeCoordinates
{
    /*
    Transformations in this class should be read from right to left.
    For instance T_world_volume is the transform from volume coordinates to world coordinates.
    */
    afVolumePtr m_volume_object;
    cTransform T_world_volume;
    cTransform T_volume_world;
    bool initialized = false;

public:
    void init(afVolumePtr m_volume_object);
    bool get_index_location_of_drill_tip(cVector3d &drill_tip_in_worldcoord, cVector3d &result_vec);
};

AF_REGISTER_SIMULATOR_PLUGIN(afVolmetricDrillingPlugin)
