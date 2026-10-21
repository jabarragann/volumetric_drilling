"""Load the outputs of register_cad.py into 3D Slicer.

In Slicer's Python console:
    OUT, NAME = "/path/to/cad-registration/PL07_D00", "PL07_D00"
    exec(open("/path/to/load_in_slicer.py").read())

or from a shell:
    Slicer --python-script load_in_slicer.py --out <dir> --name <name> [--stl-dir <stl/v01>] [--check]

Loads the CT, the segmentation, the meshes and fiducials already in CT space.
With --stl-dir it also loads the original model STL under <name>_model_to_ct.h5,
which shows the transform direction: model nodes go under it to land in CT space.
--check compares that transformed STL with the pre-transformed one, prints the
segment volumes and exits (for testing the files without the GUI).
"""
import glob
import os
import sys

import numpy as np
import slicer
import vtk


def load(out, name, stl_dir=None):
    pre = os.path.join(out, name)
    nodes = {"ct": slicer.util.loadVolume(pre + "_ct.nrrd")}
    seg = slicer.util.loadSegmentation(pre + "_all_combinations.seg.nrrd")
    seg.SetReferenceImageGeometryParameterFromVolumeNode(nodes["ct"])
    seg.CreateClosedSurfaceRepresentation()
    nodes["seg"] = seg
    for f in sorted(glob.glob(os.path.join(out, "meshes_in_ct", "*.stl"))):
        m = slicer.util.loadModel(f)   # STL is read as LPS, same as the outputs
        m.GetDisplayNode().SetOpacity(0.4)
        nodes[os.path.basename(f)] = m
    nodes["fid_ct"] = slicer.util.loadMarkups(pre + "_fiducials_ct.mrk.json")
    if stl_dir:
        tr = slicer.util.loadTransform(pre + "_model_to_ct.h5")
        stl = glob.glob(os.path.join(stl_dir, "saint_phantom_v??.stl"))[0]
        m = slicer.util.loadModel(stl)
        m.SetAndObserveTransformNodeID(tr.GetID())
        nodes["transform"], nodes["model_under_transform"] = tr, m
    slicer.util.setSliceViewerLayers(background=nodes["ct"], fit=True)
    return nodes


def check(nodes, out, name):
    seg = nodes["seg"]
    s = seg.GetSegmentation()
    ct = nodes["ct"]
    sp = np.prod(ct.GetSpacing())
    for i in range(s.GetNumberOfSegments()):
        sid = s.GetNthSegmentID(i)
        a = slicer.util.arrayFromSegmentBinaryLabelmap(seg, sid, ct)
        print(f"CHECK segment {s.GetSegment(sid).GetName()}: {a.sum() * sp / 1000:.2f} mL")
    m = nodes["model_under_transform"]
    m.HardenTransform()
    p1 = slicer.util.arrayFromModelPoints(m)
    ref = nodes[f"{name}_box.stl"]
    p2 = slicer.util.arrayFromModelPoints(ref)
    print(f"CHECK original STL under .h5 vs mesh written in CT space: max point distance "
          f"{np.abs(p1 - p2).max():.4f} mm ({len(p1)} points)")
    fid = nodes["fid_ct"]
    print("CHECK first CT fiducial (RAS in Slicer):", [round(v, 3) for v in fid.GetNthControlPointPosition(0)])


if __name__ == "__main__" and "--out" in sys.argv:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--stl-dir")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(sys.argv[1:])
    n = load(a.out, a.name, a.stl_dir)
    if a.check:
        check(n, a.out, a.name)
        slicer.util.exit(0)
elif "OUT" in globals() and "NAME" in globals():
    load(OUT, NAME, globals().get("STL_DIR"))
