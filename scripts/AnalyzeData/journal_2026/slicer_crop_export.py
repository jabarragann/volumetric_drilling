"""
Crop segmentations to an ROI box and export each to a binary STL.

Targets (8 total):
  P01_D09_real_seg .. P01_D12_real_seg   -> use segment named "bone"
  P01_D09_sim_v2   .. P01_D12_sim_v2     -> use the single segment

Method: build the 6 oriented planes of the ROI box, clip the segment's
closed-surface mesh with them (vtkClipClosedSurface caps the cuts so the
result stays watertight), then write the polydata to STL.

Run interactively (scene already loaded):
    exec(open('/home/juan95/research/discovery_grant/volumetric_drilling/'
              'scripts/AnalyzeData/journal_2026/slicer_crop_export.py').read())

Run headless:
    Slicer --no-main-window --no-splash \
        --python-script scripts/AnalyzeData/journal_2026/slicer_crop_export.py \
        --scene /path/to/P01.mrb
"""

import os
import sys
import numpy as np
import vtk
import slicer

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OUTPUT_DIR = os.path.expanduser("/home/juan95/research/discovery_grant/saint_2026/experiments/experiment_2026-06-03/experiment_2026-06-03_accuracy/meshes")
ROI_NAME = "R"
DRILLS = ["09", "10", "11", "12"]

# Remove disconnected "flying voxel" islands smaller than this many voxels
# before generating the surface. Set to 0 to disable. Tune in the GUI first
# (Segment Editor -> Islands -> Remove small islands) to find a safe value.
ISLAND_MIN_SIZE = 200

# (segmentation node name, segment selector, clean_islands) for each export.
# segment selector: a string -> pick segment by that name;
#                   None      -> pick the first segment in the node.
# clean_islands:    True      -> run remove-small-islands before surfacing.
TARGETS = []
for xx in DRILLS:
    TARGETS.append((f"P01_D{xx}_real_seg", "bone", False))
for xx in DRILLS:
    TARGETS.append((f"P01_D{xx}_sim_v2", None, True))

ADD_MODELS_TO_SCENE = True   # also add the clipped result as a model node (handy in the GUI)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_node(name):
    nodes = slicer.util.getNodes(name, useLists=True).get(name, [])
    if not nodes:
        raise RuntimeError(f"Node '{name}' not found in scene")
    return nodes[0]


def resolve_segment_id(seg_node, selector):
    segmentation = seg_node.GetSegmentation()
    if selector is None:
        if segmentation.GetNumberOfSegments() == 0:
            raise RuntimeError(f"'{seg_node.GetName()}' has no segments")
        return segmentation.GetNthSegmentID(0)
    sid = segmentation.GetSegmentIdBySegmentName(selector)
    if not sid:
        raise RuntimeError(f"Segment named '{selector}' not found in '{seg_node.GetName()}'")
    return sid


def remove_small_islands(seg_node, segment_id, min_size_voxels):
    """Delete disconnected components smaller than min_size_voxels from one segment.
    Same as Segment Editor -> Islands -> Remove small islands, run on the labelmap."""
    editor_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
    editor = slicer.qMRMLSegmentEditorWidget()
    try:
        editor.setMRMLScene(slicer.mrmlScene)
        editor.setMRMLSegmentEditorNode(editor_node)
        editor.setSegmentationNode(seg_node)
        editor.setCurrentSegmentID(segment_id)
        editor.setActiveEffectByName("Islands")
        effect = editor.activeEffect()
        effect.setParameter("Operation", "REMOVE_SMALL_ISLANDS")
        effect.setParameter("MinimumSize", int(min_size_voxels))
        effect.self().onApply()
        editor.setActiveEffectByName("")
    finally:
        editor.setMRMLSegmentEditorNode(None)
        slicer.mrmlScene.RemoveNode(editor_node)
        editor.deleteLater()

    # Drop any cached surface so it is rebuilt from the cleaned labelmap.
    if hasattr(seg_node, "RemoveClosedSurfaceRepresentation"):
        seg_node.RemoveClosedSurfaceRepresentation()


def segment_world_polydata(seg_node, segment_id):
    """Closed-surface mesh of one segment, in world (RAS) coordinates."""
    seg_node.CreateClosedSurfaceRepresentation()
    poly = vtk.vtkPolyData()
    seg_node.GetClosedSurfaceRepresentation(segment_id, poly)
    if poly.GetNumberOfPoints() == 0:
        raise RuntimeError("Empty closed-surface representation")

    # Bring into world frame in case the node carries a parent transform.
    g = vtk.vtkGeneralTransform()
    slicer.vtkMRMLTransformNode.GetTransformBetweenNodes(
        seg_node.GetParentTransformNode(), None, g)
    tf = vtk.vtkTransformPolyDataFilter()
    tf.SetTransform(g)
    tf.SetInputData(poly)
    tf.Update()
    return tf.GetOutput()


def roi_clipping_planes(roi_node):
    """6 planes of the ROI box. vtkClipClosedSurface keeps the side the normal
    points to, so normals point INWARD (toward the box center) to keep the box interior."""
    center = [0.0, 0.0, 0.0]
    roi_node.GetCenterWorld(center)
    size = [0.0, 0.0, 0.0]
    roi_node.GetSizeWorld(size) if hasattr(roi_node, "GetSizeWorld") else roi_node.GetSize(size)

    axes = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    roi_node.GetXAxisWorld(axes[0])
    roi_node.GetYAxisWorld(axes[1])
    roi_node.GetZAxisWorld(axes[2])

    c = np.array(center)
    planes = vtk.vtkPlaneCollection()
    for i in range(3):
        a = np.array(axes[i])
        half = size[i] / 2.0
        for s in (+1.0, -1.0):
            p = vtk.vtkPlane()
            p.SetOrigin(*(c + s * half * a))   # face center
            p.SetNormal(*(-s * a))             # inward normal (toward box center)
            planes.AddItem(p)
    return planes


def clip_to_box(world_poly, planes):
    clip = vtk.vtkClipClosedSurface()
    clip.SetInputData(world_poly)
    clip.SetClippingPlanes(planes)
    clip.SetActivePlaneId(-1)
    clip.GenerateFacesOn()       # cap the cut so the STL stays closed
    clip.SetScalarModeToNone()
    clip.Update()
    return clip.GetOutput()


def write_stl(poly, path):
    w = vtk.vtkSTLWriter()
    w.SetFileName(path)
    w.SetInputData(poly)
    w.SetFileTypeToBinary()
    w.Write()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if "--scene" in sys.argv:
        scene_path = sys.argv[sys.argv.index("--scene") + 1]
        print(f"Loading scene: {scene_path}")
        slicer.util.loadScene(scene_path)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    roi = get_node(ROI_NAME)

    ok, failed = [], []
    for seg_name, selector, clean_islands in TARGETS:
        try:
            seg = get_node(seg_name)
            sid = resolve_segment_id(seg, selector)
            if clean_islands and ISLAND_MIN_SIZE > 0:
                remove_small_islands(seg, sid, ISLAND_MIN_SIZE)
            world_poly = segment_world_polydata(seg, sid)
            clipped = clip_to_box(world_poly, roi_clipping_planes(roi))

            if clipped.GetNumberOfCells() == 0:
                raise RuntimeError("clip produced empty mesh (ROI may not overlap the segment)")

            out_path = os.path.join(OUTPUT_DIR, f"{seg_name}.stl")
            write_stl(clipped, out_path)

            if ADD_MODELS_TO_SCENE:
                m = slicer.mrmlScene.AddNewNodeByClass(
                    "vtkMRMLModelNode", f"{seg_name}_cropped")
                m.SetAndObservePolyData(clipped)
                m.CreateDefaultDisplayNodes()

            print(f"  OK   {seg_name:24s} -> {out_path}  ({clipped.GetNumberOfCells()} cells)")
            ok.append(seg_name)
        except Exception as e:
            print(f"  FAIL {seg_name:24s} : {e}")
            failed.append((seg_name, str(e)))

    print(f"\nDone. {len(ok)}/{len(TARGETS)} exported to {OUTPUT_DIR}")
    if failed:
        print("Failures:")
        for name, err in failed:
            print(f"  - {name}: {err}")


main()
