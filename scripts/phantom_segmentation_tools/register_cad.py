#!/usr/bin/env python3
"""Register the Saint Phantom CAD model to a CT scan and segment box, stone and routes.

Pipeline (see README.md for details):
  1. load the CT (DICOM folder or NRRD) in LPS physical space
  2. thresholds air/PLA/stone from a 3-class Otsu of the in-FOV histogram
  3. initial pose: principal axes of the phantom mask, all 4 proper rotations
     (never a reflection), each refined by ICP; the winner is picked by how
     well the obstacle layout matches the holes in the stone
  4. divots: located in the CT by template matching around their predicted
     positions (or read from --ct-fiducials); paired-point fit + FRE
  5. refinement: robust point-to-plane ICP of the 200 surface points onto the
     CT air/PLA iso-surface, started from the fiducial fit
  6. model meshes mapped into CT space and voxelised on the CT grid; segments
     box, stone, <route>_allowed, <route>_forbidden
  7. outputs: .seg.nrrd, labelmaps, transforms (.h5/.tfm/4x4), meshes and
     markups in CT space, QA figures, report.json and report.md

Coordinates: model mm == LPS (as Slicer loads STL). ITK physical space is LPS.

Usage (conda env saint-env: numpy, scipy, SimpleITK, vtk, pynrrd, matplotlib):
  python register_cad.py --version v01 \
      --stl-dir ~/research/openscad_models/saint_phantom/stl/v01 \
      --ct ~/research/saint_project/phantoms/Loop-x/processed/2026-08-04_PL07_D00 \
      --name PL07_D00 --out ~/research/saint_project/phantoms/Loop-x/cad-registration/PL07_D00
"""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

import numpy as np
import SimpleITK as sitk
import vtk
from vtk.util import numpy_support as vnp
from scipy import ndimage as ndi
from scipy.signal import fftconvolve, find_peaks
from scipy.spatial import cKDTree

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROUTES = ("left", "right")
# segmentation files written per scan: suffix -> segments it contains
SEG_FILES = {
    "all_combinations": ("box", "stone", "left_allowed", "left_forbidden", "right_allowed", "right_forbidden"),
    "box_dental": ("box", "stone"),
    "box_dental_left_path": ("box", "left_allowed", "left_forbidden"),
    "box_dental_right_path": ("box", "right_allowed", "right_forbidden"),
}
MODEL_STEP = 0.2       # mm, model-frame voxelisation grid
ABOVE_RIM = 3.0        # mm of stone accepted above the rim
BOX_DILATION = 1.0     # mm around the box mesh accepted as PLA
DAMAGE_MIN_UL = 2.0    # PLA lost next to the drilled channel above this size (uL) raises the warning
EMPTY_WARN_ML = 0.5    # empty space in the stone (below its top) that suggests a drilled scan
SEG_COLORS = {
    "box": (0.85, 0.85, 0.80),
    "stone": (0.55, 0.65, 0.95),
    "left_allowed": (0.20, 0.80, 0.30),
    "left_forbidden": (0.90, 0.30, 0.25),
    "right_allowed": (0.15, 0.60, 0.90),
    "right_forbidden": (0.95, 0.60, 0.15),
    "drilled": (0.95, 0.95, 0.20),
    "left_drilled_allowed": (0.40, 1.00, 0.50),
    "left_drilled_forbidden": (1.00, 0.10, 0.60),
    "right_drilled_allowed": (0.40, 0.85, 1.00),
    "right_drilled_forbidden": (1.00, 0.35, 0.00),
    "box_damage": (1.00, 0.00, 0.00),
}


def log(msg):
    print(msg, flush=True)


# ----------------------------------------------------------------------------
# Geometry helpers
# ----------------------------------------------------------------------------

def rigid(R, t):
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = t
    return M


def apply(M, p):
    return p @ M[:3, :3].T + M[:3, 3]


def inv(M):
    R, t = M[:3, :3], M[:3, 3]
    return rigid(R.T, -R.T @ t)


def assert_proper(M, what):
    d = np.linalg.det(M[:3, :3])
    if not (abs(d - 1) < 1e-6 and np.allclose(M[:3, :3] @ M[:3, :3].T, np.eye(3), atol=1e-6)):
        raise RuntimeError(f"{what}: not a proper rotation (det={d:.6f})")


def rot_angle_deg(R):
    return float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))


def kabsch(src, dst, w=None):
    """Proper rigid fit dst ~ R src + t. Reflection is explicitly excluded."""
    w = np.ones(len(src)) if w is None else w
    cs = (w[:, None] * src).sum(0) / w.sum()
    cd = (w[:, None] * dst).sum(0) / w.sum()
    H = ((src - cs) * w[:, None]).T @ (dst - cd)
    U, _, Vt = np.linalg.svd(H)
    D = np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))])
    R = Vt.T @ D @ U.T
    return rigid(R, cd - R @ cs)


def expmap(w):
    th = np.linalg.norm(w)
    K = np.array([[0, -w[2], w[1]], [w[2], 0, -w[0]], [-w[1], w[0], 0]])
    if th < 1e-12:
        return np.eye(3) + K
    return np.eye(3) + np.sin(th) / th * K + (1 - np.cos(th)) / th ** 2 * K @ K


# ----------------------------------------------------------------------------
# CT image helpers (sitk array is [z, y, x]; index vectors are (x, y, z))
# ----------------------------------------------------------------------------

class CTGeom:
    def __init__(self, img):
        self.origin = np.array(img.GetOrigin())
        self.spacing = np.array(img.GetSpacing())
        self.D = np.array(img.GetDirection()).reshape(3, 3)
        self.size = np.array(img.GetSize())

    def idx_to_phys(self, ijk):
        return self.origin + (ijk * self.spacing) @ self.D.T

    def phys_to_idx(self, p):
        return ((p - self.origin) @ self.D) / self.spacing

    def all_centres(self):
        k, j, i = np.meshgrid(*[np.arange(n) for n in self.size[::-1]], indexing="ij")
        ijk = np.stack([i.ravel(), j.ravel(), k.ravel()], 1).astype(np.float64)
        return self.idx_to_phys(ijk)


def sample_ct(arr, geom, pts, order=1, cval=-1024.0):
    ijk = geom.phys_to_idx(pts)
    return ndi.map_coordinates(arr, [ijk[:, 2], ijk[:, 1], ijk[:, 0]], order=order,
                               cval=cval, mode="constant")


def load_ct(path):
    if os.path.isdir(path):
        r = sitk.ImageSeriesReader()
        ids = r.GetGDCMSeriesIDs(path)
        if len(ids) != 1:
            raise RuntimeError(f"{path}: expected one DICOM series, found {len(ids)}")
        files = r.GetGDCMSeriesFileNames(path, ids[0])
        r.SetFileNames(files)
        img = r.Execute()
        src = {"type": "dicom", "files": len(files), "series_uid": ids[0]}
    else:
        img = sitk.ReadImage(path)
        src = {"type": "file"}
    return sitk.Cast(img, sitk.sitkFloat32), src


# ----------------------------------------------------------------------------
# Mesh helpers
# ----------------------------------------------------------------------------

def read_stl(path):
    r = vtk.vtkSTLReader()
    r.SetFileName(path)
    c = vtk.vtkCleanPolyData()
    c.SetInputConnection(r.GetOutputPort())
    c.Update()
    return c.GetOutput()


def mesh_volume_mL(pd):
    t = vtk.vtkTriangleFilter()
    t.SetInputData(pd)
    m = vtk.vtkMassProperties()
    m.SetInputConnection(t.GetOutputPort())
    m.Update()
    return m.GetVolume() / 1000.0


def divot_bottoms(pd, fids, normals, max_depth=5.0):
    """Bottom of each divot pocket: first mesh hit along -normal from the opening centre."""
    loc = vtk.vtkCellLocator()
    loc.SetDataSet(pd)
    loc.BuildLocator()
    out = []
    for f, n in zip(fids, normals):
        n = n / np.linalg.norm(n)
        t, x, pc, sub = vtk.reference(0.0), [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], vtk.reference(0)
        # first hit from the opening centre along the inward normal
        if not loc.IntersectWithLine((f - 0.01 * n).tolist(), (f - max_depth * n).tolist(), 1e-6, t, x, pc, sub):
            raise RuntimeError(f"no divot bottom found below {f}")
        out.append(np.array(x))
    return np.array(out)


def transform_mesh(pd, M):
    pts = vnp.vtk_to_numpy(pd.GetPoints().GetData()).astype(np.float64)
    out = vtk.vtkPolyData()
    out.DeepCopy(pd)
    p = vtk.vtkPoints()
    p.SetData(vnp.numpy_to_vtk(apply(M, pts), deep=True))
    out.SetPoints(p)
    return out


def write_stl(pd, path):
    w = vtk.vtkSTLWriter()
    w.SetFileName(path)
    w.SetInputData(pd)
    w.SetFileTypeToBinary()
    w.Write()


class ModelGrid:
    """Regular grid in model coordinates; arrays indexed [ix, iy, iz]."""

    def __init__(self, lo, hi, step):
        self.lo = np.asarray(lo, float)
        self.step = step
        self.shape = tuple(int(np.ceil((h - l) / step)) + 1 for l, h in zip(lo, hi))
        self._f32 = {}

    def axis(self, k):
        return self.lo[k] + self.step * np.arange(self.shape[k])

    def voxelise(self, pd):
        s = vtk.vtkPolyDataToImageStencil()
        s.SetInputData(pd)
        s.SetOutputOrigin(*self.lo)
        s.SetOutputSpacing(self.step, self.step, self.step)
        s.SetOutputWholeExtent(0, self.shape[0] - 1, 0, self.shape[1] - 1, 0, self.shape[2] - 1)
        s.SetTolerance(1e-4)
        c = vtk.vtkImageStencilToImage()
        c.SetInputConnection(s.GetOutputPort())
        c.SetInsideValue(1)
        c.SetOutsideValue(0)
        c.SetOutputScalarTypeToUnsignedChar()
        c.Update()
        a = vnp.vtk_to_numpy(c.GetOutput().GetPointData().GetScalars())
        return a.reshape(self.shape[::-1]).transpose(2, 1, 0).astype(bool)

    def sample(self, arr, pts, order=1):
        if arr.dtype != np.float32:
            key = id(arr)
            if key not in self._f32:
                self._f32[key] = (arr, arr.astype(np.float32))
            arr = self._f32[key][1]
        c = (pts - self.lo) / self.step
        return ndi.map_coordinates(arr, c.T, order=order, cval=0.0, mode="constant")

    def sample2d(self, arr2, pts, order=1):
        c = (pts[:, :2] - self.lo[:2]) / self.step
        return ndi.map_coordinates(arr2.astype(np.float32), c.T, order=order, cval=0.0, mode="constant")

    def centres(self, mask):
        return self.lo + np.argwhere(mask) * self.step


# ----------------------------------------------------------------------------
# Markups
# ----------------------------------------------------------------------------

def read_points_csv(path):
    rows = np.genfromtxt(path, delimiter=",", names=True, dtype=None, encoding="utf-8")
    labels = [str(l) for l in rows["label"]]
    xyz = np.stack([rows["x"], rows["y"], rows["z"]], 1).astype(float)
    n = np.stack([rows["nx"], rows["ny"], rows["nz"]], 1).astype(float)
    return labels, xyz, n


def read_markups(path):
    """Read a Slicer .mrk.json; returns {label: LPS position}. RAS is converted."""
    with open(path) as f:
        js = json.load(f)
    m = js["markups"][0]
    cs = m.get("coordinateSystem", "LPS")
    out = {}
    for cp in m["controlPoints"]:
        p = np.array(cp["position"], float)
        if cs == "RAS":
            p = p * [-1, -1, 1]
        elif cs != "LPS":
            raise RuntimeError(f"{path}: unknown coordinateSystem {cs}")
        out[cp["label"]] = p
    return out, cs


def write_markups(path, labels, pts, desc=None):
    cps = []
    for i, (l, p) in enumerate(zip(labels, pts)):
        cps.append({"id": str(i + 1), "label": l, "description": (desc or {}).get(l, ""),
                    "associatedNodeID": "", "position": [float(v) for v in p],
                    "orientation": [1, 0, 0, 0, 1, 0, 0, 0, 1], "selected": True,
                    "locked": True, "visibility": True, "positionStatus": "defined"})
    js = {"@schema": "https://raw.githubusercontent.com/slicer/slicer/master/Modules/Loadable/"
                     "Markups/Resources/Schema/markups-schema-v1.0.3.json#",
          "markups": [{"type": "Fiducial", "coordinateSystem": "LPS", "coordinateUnits": "mm",
                       "locked": True, "labelFormat": "%N-%d", "controlPoints": cps,
                       "display": {"glyphScale": 1.5, "textScale": 2.0}}]}
    with open(path, "w") as f:
        json.dump(js, f, indent=2)


# ----------------------------------------------------------------------------
# Thresholds
# ----------------------------------------------------------------------------

def find_thresholds(arr):
    """air|PLA from a 3-class Otsu; PLA|stone halfway between the PLA and stone peaks.

    The stone peak is the highest-intensity prominent peak of the smoothed log
    histogram. After drilling, the channel walls add many partial-volume voxels
    between PLA and stone, and Otsu's upper threshold would land inside them.
    """
    vals = arr[arr > -1000].astype(np.float32)   # in field of view
    lo, hi = np.percentile(vals, [0.01, 99.99])
    v = np.clip(vals, lo, hi)
    f = sitk.OtsuMultipleThresholdsImageFilter()
    f.SetNumberOfThresholds(2)
    f.SetNumberOfHistogramBins(256)
    f.Execute(sitk.GetImageFromArray(v.reshape(1, 1, -1)))
    t_air, t_otsu_hi = sorted(f.GetThresholds())
    hist, edges = np.histogram(v, bins=256)
    centres = 0.5 * (edges[1:] + edges[:-1])
    lh = ndi.gaussian_filter1d(np.log1p(hist.astype(float)), 2)
    peaks, _ = find_peaks(lh[:-3], prominence=0.3)
    peaks = peaks[centres[peaks] > t_air]
    if not len(peaks):
        raise RuntimeError("no stone peak found in the histogram; pass --thresholds")
    stone = float(centres[peaks[-1]])

    def mode(a, b):
        sel = (centres > a) & (centres < b)
        return float(centres[sel][np.argmax(hist[sel])])
    modes = {"air": mode(lo, t_air), "pla": mode(t_air, 0.5 * (t_air + stone)), "stone": stone}
    t_stone = 0.5 * (modes["pla"] + modes["stone"])
    return float(t_air), float(t_stone), modes, (hist, edges), float(t_otsu_hi)


# ----------------------------------------------------------------------------
# CT iso-surface (ICP target)
# ----------------------------------------------------------------------------

def iso_surface(arr, geom, level, roi_mask, sigma_mm=0.35):
    """Air/PLA iso-surface points with outward (towards air) unit normals, LPS."""
    sm = ndi.gaussian_filter(arr, sigma_mm / geom.spacing[::-1])
    zz, yy, xx = np.nonzero(roi_mask)
    k0, j0, i0 = zz.min(), yy.min(), xx.min()
    k1, j1, i1 = zz.max() + 1, yy.max() + 1, xx.max() + 1
    sub = np.ascontiguousarray(sm[k0:k1, j0:j1, i0:i1])
    im = vtk.vtkImageData()
    im.SetDimensions(sub.shape[2], sub.shape[1], sub.shape[0])
    im.GetPointData().SetScalars(vnp.numpy_to_vtk(sub.ravel(), deep=True))
    fe = vtk.vtkFlyingEdges3D()
    fe.SetInputData(im)
    fe.SetValue(0, level)
    fe.ComputeNormalsOff()
    fe.Update()
    ijk = vnp.vtk_to_numpy(fe.GetOutput().GetPoints().GetData()).astype(np.float64) + [i0, j0, k0]
    pts = geom.idx_to_phys(ijk)
    # gradient in physical space -> outward normal = -grad
    g = np.gradient(sm, *geom.spacing[::-1])           # d/dz_idx, d/dy_idx, d/dx_idx (per mm)
    gi = np.stack([ndi.map_coordinates(g[a], [ijk[:, 2], ijk[:, 1], ijk[:, 0]], order=1)
                   for a in (2, 1, 0)], 1)             # along index axes x, y, z
    n = -(gi @ geom.D.T)
    nn = np.linalg.norm(n, axis=1)
    ok = nn > 1e-6
    return pts[ok], n[ok] / nn[ok, None]


# ----------------------------------------------------------------------------
# ICP
# ----------------------------------------------------------------------------

def icp_point_to_plane(src, src_n, tgt_tree, tgt, tgt_n, M0, iters=60,
                       max_dist=(4.0, 2.0, 1.0), huber=0.3, normal_cos=0.6, k=12):
    """Robust (Huber IRLS) point-to-plane ICP with normal compatibility.

    Returns (M, stats). M maps model -> CT and is always a proper rotation.
    """
    M = M0.copy()
    sched = np.repeat(max_dist, int(np.ceil(iters / len(max_dist))))[:iters]
    hist = []
    for it, dmax in enumerate(sched):
        p = apply(M, src)
        n = src_n @ M[:3, :3].T
        d, idx = tgt_tree.query(p, k=k, distance_upper_bound=dmax)
        valid = np.isfinite(d)
        cos = np.where(valid, np.einsum("ij,ikj->ik", n, tgt_n[np.minimum(idx, len(tgt) - 1)]), -1)
        ok = valid & (cos > normal_cos)
        first = np.argmax(ok, axis=1)
        has = ok[np.arange(len(p)), first]
        j = idx[np.arange(len(p)), first][has]
        ps, q, m = p[has], tgt[j], tgt_n[j]
        r = np.einsum("ij,ij->i", ps - q, m)
        w = np.where(np.abs(r) <= huber, 1.0, huber / np.maximum(np.abs(r), 1e-9))
        A = np.hstack([np.cross(ps, m), m])
        b = -r
        H = (A * w[:, None]).T @ A + 1e-6 * np.eye(6)
        x = np.linalg.solve(H, (A * w[:, None]).T @ b)
        dR = expmap(x[:3])
        M = rigid(dR, x[3:]) @ M
        hist.append((it, float(dmax), int(has.sum()), float(np.sqrt(np.mean(r ** 2)))))
        if np.linalg.norm(x[:3]) < 1e-6 and np.linalg.norm(x[3:]) < 1e-5 and dmax == sched[-1]:
            break
    assert_proper(M, "ICP result")
    return M, hist


def surface_residuals(M, src, src_n, tgt_tree, tgt, tgt_n, dmax=2.0, normal_cos=0.6, k=12):
    p = apply(M, src)
    n = src_n @ M[:3, :3].T
    d, idx = tgt_tree.query(p, k=k, distance_upper_bound=dmax)
    valid = np.isfinite(d)
    cos = np.where(valid, np.einsum("ij,ikj->ik", n, tgt_n[np.minimum(idx, len(tgt) - 1)]), -1)
    ok = valid & (cos > normal_cos)
    first = np.argmax(ok, axis=1)
    has = ok[np.arange(len(p)), first]
    r = np.full(len(p), np.nan)
    j = idx[np.arange(len(p)), first][has]
    r[has] = np.einsum("ij,ij->i", p[has] - tgt[j], tgt_n[j])
    return r


def rms_stats(r):
    f = r[np.isfinite(r)]
    return {"n_matched": int(len(f)), "n_total": int(len(r)),
            "rms_mm": float(np.sqrt(np.mean(f ** 2))) if len(f) else None,
            "median_abs_mm": float(np.median(np.abs(f))) if len(f) else None,
            "p95_abs_mm": float(np.percentile(np.abs(f), 95)) if len(f) else None}


# ----------------------------------------------------------------------------
# Divot detection
# ----------------------------------------------------------------------------

def pocket_contrast(arr, geom, M, fid, normal, modes, depth=0.75, side=2.2):
    """How much a divot pocket shows under pose M: 1 = air in the pocket, PLA beside it; 0 = no pocket.

    Compares the CT 0.75 mm below the opening centre with points 2.2 mm to
    either side along model y (inside the base margin or along the rim).
    """
    n = normal / np.linalg.norm(normal)
    c = fid - depth * n
    off = 0.25 * np.array([[0, 0, 0], [1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0]])
    centre = sample_ct(arr, geom, apply(M, c + off)).mean()
    ring = sample_ct(arr, geom, apply(M, c + np.array([[0, side, 0], [0, -side, 0]]))).mean()
    return float(np.clip((ring - centre) / (modes["pla"] - modes["air"]), -1, 2))


def detect_divot(arr, geom, M, fid, box_grid, box_occ, cav_fp, half=(3.5, 3.5, 2.5), search=(1.8, 1.8, 1.0),
                 step=0.1):
    """Locate one divot by masked NCC of the local model geometry against the CT.

    The CT is resampled in the model frame around the predicted divot (current
    pose M); the template is the box mesh occupancy there (PLA = 1, air or
    pocket = 0), restricted to a window around the pocket. Returns the shift (model mm)
    that best aligns the CT with the template, i.e. the divot's position error
    under M, plus the NCC score.
    """
    hx, hy, hz = half
    sx, sy, sz = search
    ax = [np.arange(-h - s, h + s + step / 2, step) for h, s in zip(half, search)]
    X, Y, Z = np.meshgrid(*ax, indexing="ij")
    pts_m = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1) + fid
    ct = sample_ct(arr, geom, apply(M, pts_m)).reshape(X.shape)
    tax = [np.arange(-h, h + step / 2, step) for h in half]
    TX, TY, TZ = np.meshgrid(*tax, indexing="ij")
    tp = np.stack([TX.ravel(), TY.ravel(), TZ.ravel()], 1) + fid
    T = box_grid.sample(box_occ, tp).reshape(TX.shape)
    # window: within 3 mm of the axis, from 2 mm below to 1.5 mm above the opening
    W = ((TX ** 2 + TY ** 2) <= 3.0 ** 2) & (TZ >= -2.0) & (TZ <= 1.5)
    W &= (box_grid.sample2d(cav_fp, tp) < 0.5).reshape(TX.shape)   # ignore the stone side of the rim
    W = W.astype(np.float64)
    n = W.sum()
    Tw = (T - (T * W).sum() / n) * W
    Tn = np.sqrt((Tw ** 2).sum())
    flip = lambda a: a[::-1, ::-1, ::-1]
    num = fftconvolve(ct, flip(Tw), mode="valid")
    s1 = fftconvolve(ct, flip(W), mode="valid")
    s2 = fftconvolve(ct ** 2, flip(W), mode="valid")
    var = np.maximum(s2 - s1 ** 2 / n, 1e-9)
    ncc = num / (Tn * np.sqrt(var))
    pk = np.array(np.unravel_index(np.argmax(ncc), ncc.shape))
    sub = np.zeros(3)
    for a in range(3):   # quadratic sub-step refinement
        if 0 < pk[a] < ncc.shape[a] - 1:
            i0 = list(pk); i1 = list(pk); i0[a] -= 1; i1[a] += 1
            ym, y0, yp = ncc[tuple(i0)], ncc[tuple(pk)], ncc[tuple(i1)]
            den = ym - 2 * y0 + yp
            if den < 0:
                sub[a] = 0.5 * (ym - yp) / den
    # ncc index 0 corresponds to shift -search
    shift = (pk + sub) * step - np.array(search)
    on_edge = bool(np.any((pk == 0) | (pk == np.array(ncc.shape) - 1)))
    return shift, float(ncc.max()), on_edge, (ct, T, W)


# ----------------------------------------------------------------------------
# Segmentation output
# ----------------------------------------------------------------------------

def nrrd_header_space(geom):
    dirs = (geom.D * geom.spacing).T   # row a = direction of index axis a * spacing
    return dirs


def write_seg_nrrd(path, geom, segs, ref_name):
    import nrrd
    names = list(segs)
    data = np.stack([segs[n].transpose(2, 1, 0).astype(np.uint8) for n in names], 0)
    sd = np.vstack([np.full((1, 3), np.nan), nrrd_header_space(geom)])
    ext = " ".join(f"0 {s - 1}" for s in geom.size)
    hdr = {"space": "left-posterior-superior", "space directions": sd,
           "kinds": ["list", "domain", "domain", "domain"], "encoding": "gzip",
           "space origin": geom.origin,
           "Segmentation_MasterRepresentation": "Binary labelmap",
           "Segmentation_ContainedRepresentationNames": "Binary labelmap|",
           "Segmentation_ReferenceImageExtentOffset": "0 0 0",
           "Segmentation_ConversionParameters": "",
           "PatientName": ref_name}
    for i, n in enumerate(names):
        c = SEG_COLORS.get(n, (0.5, 0.5, 0.5))
        hdr.update({f"Segment{i}_ID": n, f"Segment{i}_Name": n,
                    f"Segment{i}_NameAutoGenerated": "0",
                    f"Segment{i}_Color": " ".join(f"{v:.3f}" for v in c),
                    f"Segment{i}_ColorAutoGenerated": "0",
                    f"Segment{i}_Layer": str(i), f"Segment{i}_LabelValue": "1",
                    f"Segment{i}_Extent": ext,
                    f"Segment{i}_Tags": "Segmentation.Status:completed|"})
    nrrd.write(path, data, hdr, index_order="F")   # array axes = (segment, i, j, k)


def write_labelmap(path, geom, lab, ref_img):
    img = sitk.GetImageFromArray(lab.astype(np.uint8))
    img.CopyInformation(ref_img)
    sitk.WriteImage(img, path, True)


# ----------------------------------------------------------------------------
# Provenance
# ----------------------------------------------------------------------------

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def script_commit():
    d = os.path.dirname(os.path.abspath(__file__))
    try:
        return subprocess.run(["git", "-C", d, "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return None


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", required=True, help="phantom version, e.g. v01")
    ap.add_argument("--stl-dir", required=True, help="stl/<version> folder of the saint_phantom repo")
    ap.add_argument("--ct", required=True, help="DICOM folder or NRRD/NIfTI file")
    ap.add_argument("--name", required=True, help="scan name used as output prefix, e.g. PL07_D00")
    ap.add_argument("--out", required=True, help="output folder")
    ap.add_argument("--ct-fiducials", help="optional .mrk.json with M-1..M-9 clicked in the CT "
                                           "(LPS or RAS; checked); replaces automatic divot detection")
    ap.add_argument("--reference", help="after drilling only: output folder of the same phantom's pre-drilling "
                                        "run (e.g. cad-registration/PL07_D00). Adds the drilled-stone segments "
                                        "and the PLA damage check")
    ap.add_argument("--strict", action="store_true", help="with --reference: exit with code 2 if PLA damage is found")
    ap.add_argument("--thresholds", nargs=2, type=float, metavar=("AIR_PLA", "PLA_STONE"),
                    help="override the histogram-derived thresholds")
    args = ap.parse_args()

    v = args.version
    sd = os.path.expanduser(args.stl_dir)
    out = args.out
    os.makedirs(out, exist_ok=True)
    pre = os.path.join(out, args.name)
    rep = {"name": args.name, "version": v, "run_at": datetime.datetime.now().astimezone().isoformat(),
           "script": os.path.abspath(__file__), "script_commit": script_commit(),
           "script_sha256": sha256(os.path.abspath(__file__)),
           "ct_input": os.path.abspath(args.ct), "stl_dir": os.path.abspath(sd)}

    # ---- provenance -------------------------------------------------------
    with open(os.path.join(sd, "version.json")) as f:
        vj = json.load(f)
    with open(os.path.join(sd, "paths.json")) as f:
        pj = json.load(f)
    if vj["version"] != v or pj["version"] != v:
        raise RuntimeError(f"version mismatch: arg {v}, version.json {vj['version']}, paths.json {pj['version']}")
    f_box = os.path.join(sd, vj["stl"])
    f_obs = os.path.join(sd, pj["meshes"]["obstacles"]["file"])
    f_route = {r: os.path.join(sd, pj["meshes"][f"path_{r}"]["file"]) for r in ROUTES}
    hashes = {"box": (f_box, vj["stl_sha256"]), "obstacles": (f_obs, pj["meshes"]["obstacles"]["sha256"])}
    hashes.update({r: (f_route[r], pj["meshes"][f"path_{r}"]["sha256"]) for r in ROUTES})
    prov = {}
    for k, (fp, want) in hashes.items():
        got = sha256(fp)
        prov[k] = {"file": os.path.basename(fp), "sha256": got, "matches_record": got == want}
        if got != want:
            raise RuntimeError(f"{fp}: sha256 differs from the recorded value")
    rep["model"] = {"version_commit": vj["commit"], "version_commit_subject": vj.get("commit_subject"),
                    "paths_scad_commit": pj["scad_commit"],
                    "paths_scad_modified_since_commit": pj.get("scad_modified_since_commit"),
                    "obstacles_from_commit": pj["meshes"]["obstacles"].get("from_commit"),
                    "files": prov}
    log(f"[model] {v}: box commit {vj['commit'][:7]}, routes from scad {pj['scad_commit'][:7]}; hashes OK")

    fid_labels, fid_m, fid_n = read_points_csv(os.path.join(sd, f"saint_phantom_{v}_fiducials.csv"))
    _, surf_m, surf_n = read_points_csv(os.path.join(sd, f"saint_phantom_{v}_surface.csv"))
    log(f"[model] {len(fid_labels)} fiducials, {len(surf_m)} surface points")

    # ---- model voxelisation -----------------------------------------------
    pd_box = read_stl(f_box)
    pd_obs = read_stl(f_obs)
    pd_route = {r: read_stl(f_route[r]) for r in ROUTES}
    b = np.array(pd_box.GetBounds()).reshape(3, 2)
    z_floor, z_rim = pj["region_z_range"]
    grid = ModelGrid(b[:, 0] - 3, b[:, 1] + [3, 3, 3 + ABOVE_RIM], MODEL_STEP)
    occ_box = grid.voxelise(pd_box)
    occ_obs = grid.voxelise(pd_obs)
    occ_route = {r: grid.voxelise(pd_route[r]) for r in ROUTES}
    zax = grid.axis(2)
    # cavity footprint: enclosed by the wall just below the rim (above the obstacles)
    obs_top = np.array(pd_obs.GetBounds())[5]
    iz = int(np.argmin(np.abs(zax - (z_rim - 1.0))))
    ring = occ_box[:, :, iz]
    outer = ndi.binary_fill_holes(ring)
    cav_fp = outer & ~ring
    cav_fp = ndi.label(cav_fp)[0] == np.argmax(np.bincount(ndi.label(cav_fp)[0].ravel())[1:]) + 1
    zin = (zax >= z_floor) & (zax <= z_rim)
    cavity = cav_fp[:, :, None] & zin[None, None, :]
    vox_mL = MODEL_STEP ** 3 / 1000
    geo = {"box_mesh_mL": mesh_volume_mL(pd_box), "obstacles_mesh_mL": mesh_volume_mL(pd_obs),
           "cavity_gross_mL": float(cavity.sum() * vox_mL),
           "cavity_footprint_mm2": float(cav_fp.sum() * MODEL_STEP ** 2),
           "z_floor": z_floor, "z_rim": z_rim, "obstacle_top_z": float(obs_top)}
    for r in ROUTES:
        geo[f"{r}_region_mesh_mL"] = mesh_volume_mL(pd_route[r])
        geo[f"{r}_region_voxel_mL"] = float(occ_route[r].sum() * vox_mL)
        geo[f"{r}_region_expected_mL"] = pj["meshes"][f"path_{r}"]["volume_mL"]
    rep["model_geometry"] = geo
    log(f"[model] cavity {geo['cavity_gross_mL']:.2f} mL gross, footprint {geo['cavity_footprint_mm2']:.0f} mm2; "
        + ", ".join(f"{r} region {geo[f'{r}_region_mesh_mL']:.2f} mL (expected {geo[f'{r}_region_expected_mL']})"
                    for r in ROUTES))

    # ---- CT -----------------------------------------------------------------
    img, src = load_ct(args.ct)
    geom = CTGeom(img)
    assert np.linalg.det(geom.D) > 0, "CT direction matrix is left-handed"
    arr = sitk.GetArrayFromImage(img)
    rep["ct"] = {**src, "size": geom.size.tolist(), "spacing_mm": geom.spacing.tolist(),
                 "origin_lps": geom.origin.tolist(), "direction": geom.D.ravel().tolist()}
    log(f"[ct] size {geom.size.tolist()} spacing {np.round(geom.spacing, 4).tolist()}")
    sitk.WriteImage(img if img.GetPixelID() == sitk.sitkInt16 else sitk.Cast(img, sitk.sitkInt16),
                    pre + "_ct.nrrd", True)

    t_air, t_stone, modes, (hist, edges), t_otsu_hi = find_thresholds(arr)
    if args.thresholds:
        t_air, t_stone = args.thresholds
    rep["thresholds"] = {"air_pla": t_air, "pla_stone": t_stone, "modes": modes, "otsu_upper_for_reference": t_otsu_hi,
                         "method": "override" if args.thresholds else
                         "air|PLA: 3-class Otsu of in-FOV voxels (> -1000); PLA|stone: midpoint of the PLA and "
                         "stone histogram peaks"}
    log(f"[thr] air|PLA {t_air:.0f}, PLA|stone {t_stone:.0f}; modes {', '.join(f'{k} {v:.0f}' for k, v in modes.items())}")

    # phantom mask: largest component above the air threshold, holes filled
    lab, nl = ndi.label(arr > t_air)
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    phantom = lab == np.argmax(sizes)
    phantom = ndi.binary_fill_holes(phantom)
    stone_ct = (arr > t_stone) & phantom
    vv = np.prod(geom.spacing) / 1000
    log(f"[ct] phantom mask {phantom.sum() * vv:.1f} mL; stone-intensity voxels {stone_ct.sum() * vv:.2f} mL")

    # ---- ICP target ----------------------------------------------------------
    roi = ndi.binary_dilation(phantom, iterations=6)
    iso_level = 0.5 * (modes["air"] + modes["pla"])
    tgt, tgt_n = iso_surface(arr, geom, iso_level, roi)
    tree = cKDTree(tgt)
    rep["icp_target"] = {"iso_level": iso_level, "points": int(len(tgt))}
    log(f"[icp] iso-surface at {iso_level:.0f} (midway air/PLA modes): {len(tgt)} points")

    # ---- initial pose: PCA of masks, 4 proper rotations, each ICP-refined -----
    model_solid = occ_box | cavity
    pm = grid.centres(model_solid)
    pc = geom.idx_to_phys(np.argwhere(phantom)[:, ::-1].astype(float))
    cm, cc = pm.mean(0), pc.mean(0)
    _, Em = np.linalg.eigh(np.cov((pm - cm).T))
    _, Ec = np.linalg.eigh(np.cov((pc - cc)[::7].T))
    Em = Em * np.sign(np.linalg.det(Em))
    Ec = Ec * np.sign(np.linalg.det(Ec))
    # free stone space in the obstacle layer: decides between the near-symmetric poses
    layer = (zax > z_floor + 0.5) & (zax < obs_top - 0.5)
    # interiors only (1 mm in from every side), so blur at the edges doesn't count
    xy = np.zeros((3, 3, 1), bool)
    xy[:, :, 0] = True
    n_er = int(round(1.0 / MODEL_STEP))
    free_layer = ndi.binary_erosion(cavity & ~occ_obs, xy, iterations=n_er) & layer[None, None, :]
    obs_layer = ndi.binary_erosion(occ_obs, xy, iterations=n_er) & layer[None, None, :]
    st_pts = geom.idx_to_phys(np.argwhere(stone_ct)[:, ::-1].astype(float))

    def obstacle_score(M):
        pmod = apply(inv(M), st_pts)
        in_obs = grid.sample(obs_layer, pmod, order=0) > 0.5
        in_free = grid.sample(free_layer, pmod, order=0) > 0.5
        ratio = np.prod(geom.spacing) / MODEL_STEP ** 3
        frac_free_filled = in_free.sum() / free_layer.sum() * ratio
        frac_obs_stone = in_obs.sum() / obs_layer.sum() * ratio
        return float(frac_free_filled - frac_obs_stone), float(frac_free_filled), float(frac_obs_stone)

    cands = []
    if args.ct_fiducials:
        ct_fid, cs = read_markups(args.ct_fiducials)
        missing = [l for l in fid_labels if l not in ct_fid]
        if missing:
            raise RuntimeError(f"--ct-fiducials lacks {missing}")
        M0 = kabsch(fid_m, np.array([ct_fid[l] for l in fid_labels]))
        log(f"[init] from {args.ct_fiducials} (coordinateSystem {cs}{', converted RAS->LPS' if cs == 'RAS' else ''})")
        rep["init"] = {"method": "user CT fiducials", "file": os.path.abspath(args.ct_fiducials),
                       "coordinateSystem": cs}
        M_init = M0
    else:
        for signs in [(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)]:
            R = Ec @ np.diag(signs) @ Em.T
            M0 = rigid(R, cc - R @ cm)
            assert_proper(M0, "PCA candidate")
            M1, _ = icp_point_to_plane(surf_m, surf_n, tree, tgt, tgt_n, M0, iters=60,
                                       max_dist=(8.0, 4.0, 2.0))
            st = rms_stats(surface_residuals(M1, surf_m, surf_n, tree, tgt, tgt_n))
            sc = obstacle_score(M1)
            # divots: the base has 3 at one end and 2 at the other, so a wrong pose
            # leaves most base divots without a pocket; drilling can't change this
            pk = [pocket_contrast(arr, geom, M1, f, n, modes) for f, n in zip(fid_m, fid_n)]
            cands.append({"signs": signs, "M": M1, "icp": st, "obstacle_score": sc[0],
                          "free_filled": sc[1], "obstacle_stone": sc[2],
                          "divot_pockets_mean": float(np.mean(pk)), "divot_pockets_found": int(np.sum(np.array(pk) > 0.5))})
            log(f"[init] signs {signs}: ICP rms {st['rms_mm']:.3f} mm ({st['n_matched']}/200 matched), "
                f"obstacle cores: free filled {sc[1]:.2f}, obstacles with stone {sc[2]:.2f} -> score {sc[0]:+.2f}; "
                f"divot pockets found {np.sum(np.array(pk) > 0.5)}/9 (contrast mean {np.mean(pk):.2f})")
        by_div = sorted(cands, key=lambda c: -c["divot_pockets_mean"])
        by_obs = sorted(cands, key=lambda c: -c["obstacle_score"])
        best = by_div[0]
        div_margin = by_div[0]["divot_pockets_mean"] - by_div[1]["divot_pockets_mean"]
        obs_margin = by_obs[0]["obstacle_score"] - by_obs[1]["obstacle_score"]
        agree = by_obs[0] is best
        log(f"[init] divots choose {best['signs']} (contrast margin {div_margin:.2f}); obstacles choose "
            f"{by_obs[0]['signs']} (margin {obs_margin:.2f}) -> {'agree' if agree else 'DISAGREE'}")
        if not agree or div_margin < 0.3:
            raise RuntimeError("orientation is ambiguous (divot and obstacle checks disagree, or divot contrast "
                               "margin < 0.3); annotate the divots and pass --ct-fiducials")
        rep["init"] = {"method": "PCA (4 proper rotations) + ICP; chosen by divot match, confirmed by the "
                                 "obstacle-core match",
                       "candidates": [{k: (v.tolist() if isinstance(v, np.ndarray) else v)
                                       for k, v in c.items() if k != "M"} |
                                      {"rotation_from_chosen_deg": rot_angle_deg(c["M"][:3, :3] @ best["M"][:3, :3].T)}
                                      for c in by_div],
                       "divot_margin": div_margin, "obstacle_margin": obs_margin}
        M_init = best["M"]

    # ---- divots -------------------------------------------------------------
    det = {}
    if args.ct_fiducials:
        ct_fid_pts = np.array([ct_fid[l] for l in fid_labels])
        fid_src = "user"
    else:
        # two passes: detect at ICP pose, re-detect at the fiducial pose
        M_d = M_init
        for p in range(2):
            pts = []
            for l, f in zip(fid_labels, fid_m):
                s, score, edge, patch = detect_divot(arr, geom, M_d, f, grid, occ_box, cav_fp)
                det[l] = {"shift_model_mm": s.tolist(), "ncc": score, "on_search_edge": edge, "patch": patch}
                pts.append(apply(M_d, (f + s)[None])[0])
            ct_fid_pts = np.array(pts)
            M_d = kabsch(fid_m, ct_fid_pts)
        fid_src = "auto"
    good = np.array([not det.get(l, {}).get("on_search_edge", False) and det.get(l, {}).get("ncc", 1) > 0.3
                     for l in fid_labels])
    M_fid = kabsch(fid_m[good], ct_fid_pts[good])
    assert_proper(M_fid, "fiducial fit")
    fre = np.linalg.norm(apply(M_fid, fid_m) - ct_fid_pts, axis=1)
    rep["fiducials"] = {"source": fid_src, "used": [l for l, g in zip(fid_labels, good) if g],
                        "fre_mm": dict(zip(fid_labels, fre.round(3).tolist())),
                        "fre_rms_mm": float(np.sqrt(np.mean(fre[good] ** 2))),
                        "ct_positions_lps": dict(zip(fid_labels, ct_fid_pts.round(3).tolist()))}
    if det:
        rep["fiducials"]["detection"] = {l: {k: v for k, v in d.items() if k != "patch"} for l, d in det.items()}
    # mirror check: best fit of the x-mirrored model fiducials (proper rotation only)
    mir = fid_m * [-1, 1, 1]
    perm = []
    for p in mir:   # mirrored partner label (same location after mirroring in x about the centre)
        q = p + [2 * np.mean(fid_m[:, 0]), 0, 0]
        perm.append(int(np.argmin(np.linalg.norm(fid_m - q, axis=1))))
    M_mir = kabsch(fid_m[perm], ct_fid_pts)
    fre_mir = np.linalg.norm(apply(M_mir, fid_m[perm]) - ct_fid_pts, axis=1)
    rep["fiducials"]["mislabel_check_mirror_fre_rms_mm"] = float(np.sqrt(np.mean(fre_mir ** 2)))
    log("[fid] FRE per fiducial (mm): " + ", ".join(f"{l} {e:.2f}" for l, e in zip(fid_labels, fre))
        + f"; RMS {rep['fiducials']['fre_rms_mm']:.3f}")
    log(f"[fid] if labels were mirrored in x the best proper fit would have RMS "
        f"{rep['fiducials']['mislabel_check_mirror_fre_rms_mm']:.2f} mm")
    for l in fid_labels:
        if l in det:
            d = det[l]
            log(f"      {l}: NCC {d['ncc']:.2f}, shift vs pose {np.round(d['shift_model_mm'], 2).tolist()}"
                + (" ON SEARCH EDGE" if d["on_search_edge"] else ""))

    # ---- refinement ---------------------------------------------------------
    r0 = surface_residuals(M_fid, surf_m, surf_n, tree, tgt, tgt_n)
    M_icp, icp_hist = icp_point_to_plane(surf_m, surf_n, tree, tgt, tgt_n, M_fid, iters=60,
                                         max_dist=(3.0, 2.0, 1.0))
    r1 = surface_residuals(M_icp, surf_m, surf_n, tree, tgt, tgt_n)
    dM = M_icp @ inv(M_fid)
    corners = np.array([[x, y, z] for x in b[0] for y in b[1] for z in b[2]])
    move = np.linalg.norm(apply(M_icp, corners) - apply(M_fid, corners), axis=1).max()
    fre_icp = np.linalg.norm(apply(M_icp, fid_m) - ct_fid_pts, axis=1)
    st0, st1 = rms_stats(r0), rms_stats(r1)
    diverged = (st1["n_matched"] < 0.6 * len(surf_m)) or move > 2.0
    M = M_fid if diverged else M_icp
    rep["icp"] = {"before": st0, "after": st1, "iterations": len(icp_hist),
                  "max_corner_move_vs_fiducial_fit_mm": float(move),
                  "rotation_vs_fiducial_fit_deg": rot_angle_deg(dM[:3, :3]),
                  "fiducial_distance_after_icp_mm": dict(zip(fid_labels, fre_icp.round(3).tolist())),
                  "fiducial_distance_after_icp_rms_mm": float(np.sqrt(np.mean(fre_icp[good] ** 2))),
                  "diverged": bool(diverged), "final": "fiducial fit" if diverged else "ICP"}
    log(f"[icp] RMS {st0['rms_mm']:.3f} -> {st1['rms_mm']:.3f} mm "
        f"(matched {st0['n_matched']} -> {st1['n_matched']}/200); bbox corners move {move:.2f} mm "
        f"vs fiducial fit; fiducial RMS distance after ICP {rep['icp']['fiducial_distance_after_icp_rms_mm']:.3f} mm"
        + ("; DIVERGED, keeping fiducial fit" if diverged else ""))
    assert_proper(M, "final transform")

    # ---- map model to CT grid -------------------------------------------------
    pts_ct = geom.all_centres()
    pts_mod = apply(inv(M), pts_ct)
    shape = tuple(geom.size[::-1])

    def to_ct(occ):
        return (grid.sample(occ, pts_mod, order=1) >= 0.5).reshape(shape)

    box_m = to_ct(occ_box)
    region = {r: to_ct(occ_route[r]) for r in ROUTES}
    cav_ct = to_ct(cavity)
    zt = pts_mod[:, 2].reshape(shape)
    xy_c = grid.sample2d(cav_fp, pts_mod).reshape(shape) >= 0.5
    xy_o = grid.sample2d(outer, pts_mod).reshape(shape) >= 0.5
    stone_zone = (xy_c & (zt >= z_floor - 0.5) & (zt <= z_rim + ABOVE_RIM)) | \
                 (xy_o & (zt >= z_rim) & (zt <= z_rim + ABOVE_RIM))
    box_zone = ndi.binary_dilation(box_m, iterations=max(1, int(round(BOX_DILATION / geom.spacing.min()))))

    # ---- segments -------------------------------------------------------------
    pla_int = (arr > t_air) & (arr <= t_stone)
    stone_int = arr > t_stone
    # PLA-intensity voxels near the mesh, but never below its bottom plane: the
    # mounting plate / table touches the base there and has PLA-like values
    z_bottom = b[2, 0]
    extra = pla_int & box_zone & ~box_m & (zt >= z_bottom)
    rejected_below = pla_int & box_zone & ~box_m & (zt < z_bottom)
    box = box_m | extra
    stone = stone_int & stone_zone & ~box
    labs, _ = ndi.label(stone)
    cs_ = np.bincount(labs.ravel())
    cs_[0] = 0
    stone = np.isin(labs, np.nonzero(cs_ >= 30)[0])
    segs = {"box": box, "stone": stone}
    for r in ROUTES:
        segs[f"{r}_allowed"] = stone & region[r]
        segs[f"{r}_forbidden"] = stone & ~region[r]

    # ---- after drilling: compare with the pre-drilling run ---------------------
    damage_blobs = []
    if args.reference:
        ref = load_reference(args.reference, v)
        # both runs are registered to the CAD: D01 voxel -> model -> D00 CT
        v0 = sample_ct(ref["arr"], ref["geom"], apply(ref["M"], pts_mod)).reshape(shape)
        th0 = ref["thresholds"]
        stone0 = (v0 > th0["pla_stone"]) & stone_zone & ~box_m
        drilled = ndi.binary_opening(stone0 & ~stone_int)
        labs, _ = ndi.label(drilled)
        cs_ = np.bincount(labs.ravel())
        cs_[0] = 0
        drilled = np.isin(labs, np.nonzero(cs_ >= 30)[0])
        # PLA damage: material in D00, air in D01, inside the mesh and touching the
        # drilled channel (lattice flicker elsewhere is ignored)
        mat0 = v0 > 0.5 * (th0["modes"]["air"] + th0["modes"]["pla"])
        mat1 = arr > 0.5 * (modes["air"] + modes["pla"])
        # no opening: drill damage is often in the thin (~2 voxel) shells. Fragments
        # within ~1 mm of each other count as one spot
        lost = box_m & mat0 & ~mat1
        near = ndi.binary_dilation(drilled, iterations=2)
        labl, _ = ndi.label(ndi.binary_dilation(lost, iterations=1))
        labl[~lost] = 0
        hit = np.unique(labl[near & lost])
        damage = np.zeros(shape, bool)
        obs_near = ndi.binary_dilation(occ_obs, iterations=3)   # obstacle or within 0.6 mm of one
        for h_ in hit[hit > 0]:
            blob = labl == h_
            c_m = pts_mod.reshape(shape + (3,))[blob].mean(0)
            uL = float(blob.sum() * vv * 1000)
            part = ("cavity floor" if c_m[2] < z_floor else
                    "obstacle" if grid.sample(obs_near, c_m[None], order=0)[0] > 0.5 else "wall")
            damage_blobs.append({"volume_uL": uL, "centre_model_mm": c_m.round(2).tolist(),
                                 "centre_ct_lps": apply(M, c_m[None])[0].round(2).tolist(), "part": part,
                                 "warning": uL >= DAMAGE_MIN_UL})
            if uL >= DAMAGE_MIN_UL:
                damage |= blob
        damage_blobs.sort(key=lambda d: -d["volume_uL"])
        box = box & ~damage
        segs["box"] = box
        segs["box_damage"] = damage
        segs["drilled"] = drilled
        for r in ROUTES:
            segs[f"{r}_drilled_allowed"] = drilled & region[r]
            segs[f"{r}_drilled_forbidden"] = drilled & ~region[r]
        D = M @ inv(ref["M"])
        warn = [d for d in damage_blobs if d["warning"]]
        rep["reference"] = {"dir": os.path.abspath(args.reference), "name": ref["name"],
                            "ref_ct_to_this_ct_LPS": D.tolist(), "rotation_deg": rot_angle_deg(D[:3, :3]),
                            "ref_thresholds": th0}
        rep["drilled_mL"] = {k: float(segs[k].sum() * vv) for k in
                             ["drilled"] + [f"{r}_drilled_{a}" for r in ROUTES for a in ("allowed", "forbidden")]}
        rep["pla_damage"] = {"detected": bool(warn), "min_blob_uL": DAMAGE_MIN_UL,
                             "total_uL": float(sum(d["volume_uL"] for d in warn)), "blobs": damage_blobs}
        log(f"[ref] {ref['name']} mapped through the CAD frame; drilled stone " + ", ".join(
            f"{k} {x:.2f}" for k, x in rep["drilled_mL"].items()) + " mL")
        if warn:
            bar = "!" * 78
            log(bar)
            log(f"!!! WARNING: PLA DAMAGE DETECTED: {len(warn)} spot(s), {rep['pla_damage']['total_uL']:.1f} uL "
                f"of PLA removed next to the drilled channel")
            for d in warn:
                log(f"!!!   {d['volume_uL']:6.1f} uL  {d['part']:<12} model {d['centre_model_mm']}  CT LPS {d['centre_ct_lps']}")
            log("!!! These voxels are removed from 'box' and saved as segment 'box_damage'; see qa/*_damage.png")
            log(bar)
        else:
            log(f"[ref] no PLA damage >= {DAMAGE_MIN_UL} uL next to the drilled channel")

    # fill level from the stone top in the model frame
    zs = zt[stone & xy_c]
    fill_top = float(np.percentile(zs, 99.5)) if len(zs) else None
    above = stone & (zt > z_rim)
    voids = cav_ct & ~stone & ~box & (zt < (fill_top - 1.0 if fill_top else z_rim))
    vol = {k: float(m.sum() * vv) for k, m in segs.items()}
    vol.update({"stone_above_rim": float(above.sum() * vv),
                "voids_in_stone_below_top": float(voids.sum() * vv),
                "box_mesh_on_ct_grid": float(box_m.sum() * vv),
                "box_added_outside_mesh": float(extra.sum() * vv),
                "pla_like_below_bottom_rejected": float(rejected_below.sum() * vv)})
    for r in ROUTES:
        vol[f"{r}_region_on_ct_grid"] = float(region[r].sum() * vv)
    h = (min(fill_top, z_rim) - z_floor) if fill_top else 0
    exp = {"stone_full_fill_mL": None, "fill_top_z_model": fill_top, "fill_height_mm": h}
    exp["cavity_net_to_fill_mL"] = float(((cav_ct & ~box_m) & (zt <= (fill_top or 0))).sum() * vv)
    for r in ROUTES:
        exp[f"{r}_region_to_fill_mL"] = float((region[r] & (zt <= (fill_top or 0))).sum() * vv)
        exp[f"{r}_region_full_mL"] = pj["meshes"][f"path_{r}"]["volume_mL"]
    exp["stone_full_fill_mL"] = float(((cav_ct & ~box_m)).sum() * vv)
    rep["volumes_mL"] = vol
    rep["expected_mL"] = exp
    log("[seg] " + ", ".join(f"{k} {v:.2f}" for k, v in vol.items()))
    log(f"[seg] stone top at z = {fill_top:.2f} (rim {z_rim}); cavity net up to that level "
        f"{exp['cavity_net_to_fill_mL']:.2f} mL, full {exp['stone_full_fill_mL']:.2f} mL")
    rep["warnings"] = []
    if not args.reference and vol["voids_in_stone_below_top"] >= EMPTY_WARN_ML:
        msg = (f"{vol['voids_in_stone_below_top']:.2f} mL of empty space in the stone (below its top): this looks "
               f"like a drilled scan. Re-run with --reference <pre-drilling output folder> to get the drilled "
               f"segments and the PLA damage check")
        rep["warnings"].append(msg)
        bar = "!" * 78
        log(bar)
        log(f"!!! WARNING: {msg}")
        log(bar)

    # ---- outputs ----------------------------------------------------------------
    seg_files = {k: list(names) for k, names in SEG_FILES.items()}
    if args.reference:
        seg_files["all_combinations"] += ["drilled"] + [f"{r}_drilled_{a}" for r in ROUTES
                                                        for a in ("allowed", "forbidden")] + ["box_damage"]
        seg_files["box_dental"] += ["drilled", "box_damage"]
        for r in ROUTES:
            seg_files[f"box_dental_{r}_path"] += [f"{r}_drilled_allowed", f"{r}_drilled_forbidden", "box_damage"]
    for suffix, names in seg_files.items():
        write_seg_nrrd(f"{pre}_{suffix}.seg.nrrd", geom, {k: segs[k] for k in names}, args.name)
    for r in ROUTES:
        lm = np.zeros(shape, np.uint8)
        lm[box] = 1
        lm[segs[f"{r}_forbidden"]] = 2
        lm[segs[f"{r}_allowed"]] = 3
        if args.reference:
            lm[segs[f"{r}_drilled_forbidden"]] = 4
            lm[segs[f"{r}_drilled_allowed"]] = 5
            lm[segs["box_damage"]] = 6
        write_labelmap(f"{pre}_labels_{r}.nrrd", geom, lm, img)
    F = np.diag([-1, -1, 1, 1])
    tr = {"convention": "x_ct = M_model_to_ct @ x_model (homogeneous, mm). "
                        "model coordinates are the STL/markup coordinates (LPS in Slicer)",
          "model_to_ct_LPS": M.tolist(), "ct_to_model_LPS": inv(M).tolist(),
          "model_to_ct_RAS_slicer_matrix": (F @ M @ F).tolist(),
          "fiducial_fit_model_to_ct_LPS": M_fid.tolist(),
          "rotation_deg": rot_angle_deg(M[:3, :3]), "det": float(np.linalg.det(M[:3, :3]))}
    with open(pre + "_transform.json", "w") as f:
        json.dump(tr, f, indent=2)
    np.savetxt(pre + "_model_to_ct_LPS.txt", M, fmt="%.9f")
    # ITK file convention: maps fixed (CT) points to moving (model) points; Slicer
    # applies it to model nodes as model -> CT.
    t_itk = sitk.AffineTransform(3)
    Mi = inv(M)
    t_itk.SetMatrix(Mi[:3, :3].ravel().tolist())
    t_itk.SetTranslation(Mi[:3, 3].tolist())
    sitk.WriteTransform(t_itk, pre + "_model_to_ct.h5")
    sitk.WriteTransform(t_itk, pre + "_model_to_ct.tfm")
    rep["transform"] = {k: tr[k] for k in ("model_to_ct_LPS", "rotation_deg", "det")}
    rep["transform"]["files"] = {"json": os.path.basename(pre + "_transform.json"),
                                 "itk": os.path.basename(pre + "_model_to_ct.h5"),
                                 "itk_note": "ITK resampling convention (CT point -> model point). "
                                             "In Slicer, put model nodes under it to move them into CT space."}
    meshes_dir = os.path.join(out, "meshes_in_ct")
    os.makedirs(meshes_dir, exist_ok=True)
    for k, pd in [("box", pd_box), ("obstacles", pd_obs)] + [(f"path_{r}", pd_route[r]) for r in ROUTES]:
        write_stl(transform_mesh(pd, M), os.path.join(meshes_dir, f"{args.name}_{k}.stl"))
    write_markups(pre + "_fiducials_ct.mrk.json", fid_labels, ct_fid_pts,
                  {l: f"FRE {e:.2f} mm" for l, e in zip(fid_labels, fre)})
    write_markups(pre + "_fiducials_model_in_ct.mrk.json", [l + "m" for l in fid_labels], apply(M, fid_m))
    # divot bottoms: offset from each CT divot centre by the mesh's centre->bottom vector
    bot_m = divot_bottoms(pd_box, fid_m, fid_n)
    depth = np.linalg.norm(bot_m - fid_m, axis=1)
    bot_ct = ct_fid_pts + (bot_m - fid_m) @ M[:3, :3].T
    write_markups(pre + "_M.mrk.json", fid_labels, bot_ct,
                  {l: f"divot bottom, {d:.2f} mm below the opening centre" for l, d in zip(fid_labels, depth)})
    rep["fiducials"]["divot_bottom_depth_mm"] = dict(zip(fid_labels, depth.round(3).tolist()))
    rep["fiducials"]["divot_bottoms_ct_lps"] = dict(zip(fid_labels, bot_ct.round(3).tolist()))
    log("[fid] divot bottoms written (depth from mesh: " + ", ".join(f"{d:.2f}" for d in depth) + " mm)")

    # ---- QA figures -----------------------------------------------------------
    qa = os.path.join(out, "qa")
    os.makedirs(qa, exist_ok=True)
    figs = qa_figures(qa, args.name, arr, geom, M, grid, occ_box, occ_obs, occ_route, segs, hist, edges,
                      t_air, t_stone, modes, iso_level, det, fid_labels, fid_m, ct_fid_pts, fre, r0, r1, z_floor,
                      z_rim, fill_top, zt, pts_mod, shape)
    if args.reference:
        figs.update(drilling_figures(qa, args.name, arr, geom, M, grid, occ_box, occ_route, segs, modes, ref,
                                     damage_blobs, z_floor))
    rep["qa_figures"] = figs
    with open(pre + "_report.json", "w") as f:
        json.dump(rep, f, indent=2, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else str(o))
    write_markdown(pre + "_report.md", rep, figs)
    log(f"[done] outputs in {out}")
    if args.strict and rep.get("pla_damage", {}).get("detected"):
        log("[strict] exiting with code 2 because PLA damage was detected")
        sys.exit(2)


def load_reference(ref_dir, version):
    reps = [f for f in os.listdir(ref_dir) if f.endswith("_report.json")]
    if len(reps) != 1:
        raise RuntimeError(f"{ref_dir}: expected one *_report.json, found {len(reps)}")
    with open(os.path.join(ref_dir, reps[0])) as f:
        rr = json.load(f)
    if rr["version"] != version:
        raise RuntimeError(f"reference is phantom version {rr['version']}, this run is {version}")
    if "reference" in rr:
        raise RuntimeError("the reference must be a pre-drilling run (it was itself run with --reference)")
    name = rr["name"]
    img = sitk.ReadImage(os.path.join(ref_dir, f"{name}_ct.nrrd"))
    return {"name": name, "arr": sitk.GetArrayFromImage(img).astype(np.float32), "geom": CTGeom(img),
            "M": np.loadtxt(os.path.join(ref_dir, f"{name}_model_to_ct_LPS.txt")),
            "thresholds": {"pla_stone": rr["thresholds"]["pla_stone"], "modes": rr["thresholds"]["modes"]}}


# ----------------------------------------------------------------------------
# QA
# ----------------------------------------------------------------------------

def resample_model_plane(arr, geom, M, axis, value, lo, hi, step=0.1):
    """CT intensities on a plane of the model frame (axis fixed at value)."""
    other = [a for a in range(3) if a != axis]
    u = np.arange(lo[other[0]], hi[other[0]] + step / 2, step)
    w = np.arange(lo[other[1]], hi[other[1]] + step / 2, step)
    U, W = np.meshgrid(u, w, indexing="xy")
    p = np.zeros(U.shape + (3,))
    p[..., other[0]] = U
    p[..., other[1]] = W
    p[..., axis] = value
    vals = sample_ct(arr, geom, apply(M, p.reshape(-1, 3))).reshape(U.shape)
    return vals, (u[0], u[-1], w[0], w[-1]), p.reshape(-1, 3), U.shape


def qa_figures(qa, name, arr, geom, M, grid, occ_box, occ_obs, occ_route, segs, hist, edges, t_air, t_stone,
               modes, iso_level, det, fid_labels, fid_m, ct_fid_pts, fre, r0, r1, z_floor, z_rim, fill_top,
               zt, pts_mod, shape):
    figs = {}
    # 1. histogram
    fig, ax = plt.subplots(figsize=(9, 4))
    c = 0.5 * (edges[1:] + edges[:-1])
    ax.semilogy(c, np.maximum(hist, 1), color="0.2", lw=1)
    for x, lab, col in [(t_air, f"air|PLA {t_air:.0f}", "tab:orange"), (t_stone, f"PLA|stone {t_stone:.0f}", "tab:blue"),
                        (iso_level, f"ICP iso {iso_level:.0f}", "tab:green")]:
        ax.axvline(x, color=col, ls="--", label=lab)
    for k, x in modes.items():
        ax.annotate(k, (x, hist[np.argmin(np.abs(c - x))]), textcoords="offset points", xytext=(0, 6), ha="center")
    ax.set_xlabel("CT value (scanner units, not calibrated HU)")
    ax.set_ylabel("voxels (in FOV)")
    ax.set_title(f"{name}: histogram and 3-class Otsu thresholds")
    ax.legend(frameon=False)
    fig.tight_layout()
    figs["histogram"] = f"qa/{name}_histogram.png"
    fig.savefig(os.path.join(qa, f"{name}_histogram.png"), dpi=110)
    plt.close(fig)

    # 2. overlays in the model frame
    lo = grid.lo + 1.5
    hi = grid.lo + np.array(grid.shape) * grid.step - 1.5
    planes = [(2, z_floor + 2.0, "z = %.1f (obstacle layer)"), (2, 0.5 * (10 + z_rim), "z = %.1f (above obstacles)"),
              (2, z_rim - 0.3, "z = %.1f (just below rim top)"), (2, 3.0, "z = %.1f (base plate)"),
              (0, 30.0, "x = %.1f"), (1, 40.0, "y = %.1f (route leg)")]
    vmin, vmax = modes["air"], modes["stone"] + 0.3 * (modes["stone"] - modes["pla"])
    rgb = {"box": (0.9, 0.9, 0.2), "left_allowed": (0.2, 0.9, 0.3), "right_allowed": (0.2, 0.6, 1.0)}
    fig, axes = plt.subplots(2, len(planes), figsize=(4.2 * len(planes), 8.5))
    for col, (axis, val, title) in enumerate(planes):
        vals, extent, p, shp = resample_model_plane(arr, geom, M, axis, val, lo, hi)
        for row in range(2):
            ax = axes[row, col]
            ax.imshow(vals, cmap="gray", vmin=vmin, vmax=vmax, origin="lower", extent=extent)
            pm = p
            if row == 0:
                for occ, cl in [(occ_box, "red"), (occ_obs, "yellow")]:
                    o = grid.sample(occ, pm).reshape(shp)
                    ax.contour(o, levels=[0.5], colors=cl, linewidths=0.7, origin="lower", extent=extent)
                for r, cl in zip(ROUTES, ["lime", "magenta"]):
                    o = grid.sample(occ_route[r], pm).reshape(shp)
                    ax.contour(o, levels=[0.5], colors=cl, linewidths=0.8, linestyles="--", origin="lower", extent=extent)
            else:
                ijk = geom.phys_to_idx(apply(M, pm))
                ov = np.zeros(shp + (4,))
                for k in ("box", "stone", "left_allowed", "right_allowed"):
                    s = ndi.map_coordinates(segs[k].astype(np.float32), [ijk[:, 2], ijk[:, 1], ijk[:, 0]], order=0)
                    s = s.reshape(shp) > 0.5
                    if k == "stone":
                        ov[s] = (0.9, 0.3, 0.25, 0.45)   # forbidden unless overwritten
                    elif k == "left_allowed":
                        ov[s] = (0.2, 0.9, 0.3, 0.45)
                    elif k == "right_allowed":
                        both = s & (ov[..., 1] > 0.85)
                        ov[s] = (0.2, 0.6, 1.0, 0.45)
                        ov[both] = (0.0, 0.9, 0.9, 0.5)
                    else:
                        ov[s] = (*rgb[k], 0.35)
                ax.imshow(ov, origin="lower", extent=extent)
            ax.set_title(title % val, fontsize=9)
            ax.set_xlabel("xyz"[[a for a in range(3) if a != axis][0]] + " (model mm)", fontsize=8)
            ax.tick_params(labelsize=7)
    axes[0, 0].set_ylabel("contours: box red, obstacles yellow,\nleft route green, right route magenta", fontsize=8)
    axes[1, 0].set_ylabel("segments: box yellow, forbidden red,\nleft green, right blue, both cyan", fontsize=8)
    fig.suptitle(f"{name}: CT resampled in the model frame (registered)")
    fig.tight_layout()
    figs["overlay"] = f"qa/{name}_overlay.png"
    fig.savefig(os.path.join(qa, f"{name}_overlay.png"), dpi=90)
    plt.close(fig)

    # 3. divots
    fig, axes = plt.subplots(2, len(fid_labels), figsize=(2.1 * len(fid_labels), 4.6))
    for i, (l, f) in enumerate(zip(fid_labels, fid_m)):
        for row, zoff in enumerate([-0.6, None]):
            ax = axes[row, i]
            if zoff is not None:
                vals, ext, _, _ = resample_model_plane(arr, geom, M, 2, f[2] + zoff, f - 4, f + 4, step=0.05)
                ax.imshow(vals, cmap="gray", vmin=vmin, vmax=vmax, origin="lower", extent=ext)
                ax.set_title(f"{l} FRE {fre[i]:.2f}", fontsize=8)
                q = apply(inv(M), ct_fid_pts[i][None])[0]
                ax.plot(f[0], f[1], "r+", ms=10)
                ax.plot(q[0], q[1], "cx", ms=7)
                ax.add_patch(plt.Circle((q[0], q[1]), 1.5, fill=False, color="c", lw=0.6))
            else:
                vals, ext, _, _ = resample_model_plane(arr, geom, M, 0, f[0], f - 4, f + 4, step=0.05)
                ax.imshow(vals, cmap="gray", vmin=vmin, vmax=vmax, origin="lower", extent=ext)
                q = apply(inv(M), ct_fid_pts[i][None])[0]
                ax.plot(f[1], f[2], "r+", ms=10)
                ax.plot(q[1], q[2], "cx", ms=7)
                ax.add_patch(plt.Circle((q[1], q[2]), 1.5, fill=False, color="c", lw=0.6))
                if l in det:
                    ax.set_xlabel(f"NCC {det[l]['ncc']:.2f}", fontsize=8)
            ax.set_xticks([]); ax.set_yticks([])
    axes[0, 0].set_ylabel("xy, 0.6 mm\nbelow opening", fontsize=8)
    axes[1, 0].set_ylabel("yz section", fontsize=8)
    fig.suptitle(f"{name}: divots (red + model under final pose, cyan x CT divot centre)", fontsize=10)
    fig.tight_layout()
    figs["divots"] = f"qa/{name}_divots.png"
    fig.savefig(os.path.join(qa, f"{name}_divots.png"), dpi=110)
    plt.close(fig)

    # 4. stone top height map (model frame)
    st = segs["stone"].ravel()
    pm = pts_mod[st]
    step = 0.5
    xe = np.arange(grid.lo[0], grid.lo[0] + grid.shape[0] * grid.step, step)
    ye = np.arange(grid.lo[1], grid.lo[1] + grid.shape[1] * grid.step, step)
    ix = np.clip(np.digitize(pm[:, 0], xe) - 1, 0, len(xe) - 2)
    iy = np.clip(np.digitize(pm[:, 1], ye) - 1, 0, len(ye) - 2)
    top = np.full((len(ye) - 1, len(xe) - 1), np.nan)
    np.fmax.at(top, (iy, ix), pm[:, 2])
    fig, ax = plt.subplots(figsize=(5.5, 6.5))
    im = ax.imshow(top, origin="lower", extent=(xe[0], xe[-1], ye[0], ye[-1]), cmap="viridis",
                   vmin=z_floor, vmax=z_rim + 1)
    for r, cl in zip(ROUTES, ["lime", "magenta"]):
        o = occ_route[r].any(axis=2).T
        ax.contour(grid.axis(0), grid.axis(1), o.astype(float), levels=[0.5], colors=cl, linewidths=0.8)
    plt.colorbar(im, ax=ax, label="highest stone voxel z (model mm)")
    ax.set_xlim(0, 60); ax.set_ylim(15, 79)
    ax.set_title(f"{name}: stone top (rim at z = {z_rim})", fontsize=10)
    fig.tight_layout()
    figs["stone_top"] = f"qa/{name}_stone_top.png"
    fig.savefig(os.path.join(qa, f"{name}_stone_top.png"), dpi=110)
    plt.close(fig)

    # 5. ICP residuals
    fig, ax = plt.subplots(figsize=(6, 3.5))
    bins = np.linspace(-1.5, 1.5, 61)
    ax.hist(r0[np.isfinite(r0)], bins, alpha=0.5, label="fiducial fit")
    ax.hist(r1[np.isfinite(r1)], bins, alpha=0.5, label="after ICP")
    ax.set_xlabel("signed point-to-plane distance (mm, + = model outside CT surface)")
    ax.set_ylabel("surface points")
    ax.legend(frameon=False)
    fig.tight_layout()
    figs["icp_residuals"] = f"qa/{name}_icp_residuals.png"
    fig.savefig(os.path.join(qa, f"{name}_icp_residuals.png"), dpi=110)
    plt.close(fig)
    return figs


def drilling_figures(qa, name, arr, geom, M, grid, occ_box, occ_route, segs, modes, ref, blobs, z_floor):
    figs = {}
    lo = np.array([0, 15, 0.0])
    hi = np.array([60, 79, 16.0])
    vmin, vmax = modes["air"], modes["stone"]
    fig, axes = plt.subplots(len(ROUTES), 3, figsize=(15, 6.2 * len(ROUTES)))
    for row, r in enumerate(ROUTES):
        for col, zz in enumerate([z_floor + 1.5, z_floor + 3.5, z_floor + 5.5]):
            ax = axes[row, col]
            vals, ext, p, shp = resample_model_plane(arr, geom, M, 2, zz, lo, hi, step=0.1)
            ax.imshow(vals, cmap="gray", vmin=vmin, vmax=vmax, origin="lower", extent=ext)
            ijk = geom.phys_to_idx(apply(M, p))
            ov = np.zeros(shp + (4,))
            for k, c in [(f"{r}_drilled_allowed", (0.2, 0.9, 0.3, 0.6)), (f"{r}_drilled_forbidden", (1.0, 0.1, 0.2, 0.7)),
                         ("box_damage", (1.0, 1.0, 0.0, 1.0))]:
                s = ndi.map_coordinates(segs[k].astype(np.float32), [ijk[:, 2], ijk[:, 1], ijk[:, 0]], order=0)
                ov[s.reshape(shp) > 0.5] = c
            ax.imshow(ov, origin="lower", extent=ext)
            o = grid.sample(occ_route[r], p).reshape(shp)
            ax.contour(o, levels=[0.5], colors="cyan", linewidths=0.8, linestyles="--", origin="lower", extent=ext)
            o = grid.sample(occ_box, p).reshape(shp)
            ax.contour(o, levels=[0.5], colors="orange", linewidths=0.6, origin="lower", extent=ext)
            ax.set_title(f"{r} route, z = {zz:.1f}: drilled allowed green, forbidden red, PLA damage yellow", fontsize=8)
    fig.suptitle(f"{name}: stone removed since {ref['name']} (route region cyan, box mesh orange)")
    fig.tight_layout()
    figs["drilled"] = f"qa/{name}_drilled.png"
    fig.savefig(os.path.join(qa, f"{name}_drilled.png"), dpi=80)
    plt.close(fig)
    warn = [b for b in blobs if b["warning"]]
    if warn:
        n = len(warn)
        fig, axes = plt.subplots(2, n, figsize=(4 * n, 8), squeeze=False)
        for c, b in enumerate(warn):
            pc = np.array(b["centre_model_mm"])
            axis = 2 if pc[2] > z_floor + 0.5 else 0
            for rr_, (lab, a_, g_, M_, mm) in enumerate([(ref["name"], ref["arr"], ref["geom"], ref["M"], ref["thresholds"]["modes"]),
                                                         (name, arr, geom, M, modes)]):
                vals, ext, p, shp = resample_model_plane(a_, g_, M_, axis, pc[axis], pc - 6, pc + 6, step=0.05)
                ax = axes[rr_, c]
                ax.imshow(vals, cmap="gray", origin="lower", extent=ext, vmin=mm["air"], vmax=mm["stone"])
                ax.contour(grid.sample(occ_box, p).reshape(shp), [0.5], colors="r", linewidths=0.8, origin="lower",
                           extent=ext)
                u, w = [k for k in range(3) if k != axis]
                ax.plot(pc[u], pc[w], "y+", ms=14)
                ax.set_title(f"{lab}: {b['volume_uL']:.1f} uL, {b['part']}\n{'xyz'[axis]} = {pc[axis]:.1f}", fontsize=9)
        fig.suptitle(f"{name}: PLA damage (red = CAD mesh; top before drilling, bottom after)")
        fig.tight_layout()
        figs["damage"] = f"qa/{name}_damage.png"
        fig.savefig(os.path.join(qa, f"{name}_damage.png"), dpi=80)
        plt.close(fig)
    return figs


def write_markdown(path, rep, figs):
    f = rep["fiducials"]
    v = rep["volumes_mL"]
    e = rep["expected_mL"]
    g = rep["model_geometry"]
    L = [f"# {rep['name']}: CAD registration and segmentation", "",
         f"- Model {rep['version']}, box commit `{rep['model']['version_commit'][:7]}`, route regions from scad "
         f"commit `{rep['model']['paths_scad_commit'][:7]}`; STL hashes match the records.",
         f"- CT: {rep['ct']['size']} voxels, spacing {[round(s, 3) for s in rep['ct']['spacing_mm']]} mm. "
         f"Run {rep['run_at']}.", ""]
    for w in rep.get("warnings", []):
        L += ["> [!WARNING]", f"> {w}.", ""]
    if "pla_damage" in rep:
        pdm = rep["pla_damage"]
        if pdm["detected"]:
            L += ["> [!WARNING]", f"> **PLA DAMAGE DETECTED**: {sum(b['warning'] for b in pdm['blobs'])} spot(s), "
                  f"{pdm['total_uL']:.1f} uL of PLA removed next to the drilled channel (blobs >= {pdm['min_blob_uL']} uL). "
                  "They are removed from `box` and saved as `box_damage`. See the Drilling section.", ""]
        else:
            L += [f"No PLA damage >= {pdm['min_blob_uL']} uL next to the drilled channel.", ""]
    L += [
         "## Thresholds", "",
         f"Air|PLA {rep['thresholds']['air_pla']:.0f}, PLA|stone {rep['thresholds']['pla_stone']:.0f} "
         f"({rep['thresholds']['method']}). Modes: "
         + ", ".join(f"{k} {x:.0f}" for k, x in rep["thresholds"]["modes"].items()) + ".", "",
         f"![histogram]({figs['histogram']})", "",
         "## Registration", ""]
    if "candidates" in rep["init"]:
        L += ["Initial pose candidates (PCA axes, proper rotations only, each refined by ICP). Chosen by the divot "
              "match and confirmed by the obstacle-core match:", "",
              "| signs | ICP RMS (mm) | matched | divot pockets found (contrast) | free cores filled | obstacle cores with stone "
              "| obstacle score | rotation from chosen |",
              "|---|---|---|---|---|---|---|---|"]
        for c in rep["init"]["candidates"]:
            L.append(f"| {tuple(c['signs'])} | {c['icp']['rms_mm']:.3f} | {c['icp']['n_matched']} | "
                     f"{c['divot_pockets_found']}/9 ({c['divot_pockets_mean']:.2f}) | "
                     f"{c['free_filled']:.2f} | {c['obstacle_stone']:.2f} | {c['obstacle_score']:+.2f} | "
                     f"{c['rotation_from_chosen_deg']:.0f}° |")
        L.append("")
    L += [f"Fiducials ({f['source']}): FRE RMS **{f['fre_rms_mm']:.3f} mm**. A fit with the labels mirrored in x "
          f"would give {f['mislabel_check_mirror_fre_rms_mm']:.2f} mm.", "",
          "| label | FRE (mm) | distance after ICP (mm) |" + (" NCC |" if "detection" in f else ""),
          "|---|---|---|" + ("---|" if "detection" in f else "")]
    for l, x in f["fre_mm"].items():
        row = f"| {l} | {x:.2f} | {rep['icp']['fiducial_distance_after_icp_mm'][l]:.2f} |"
        if "detection" in f:
            row += f" {f['detection'][l]['ncc']:.2f} |"
        L.append(row)
    i = rep["icp"]
    L += ["", f"ICP (200 surface points, point-to-plane, Huber): RMS {i['before']['rms_mm']:.3f} → "
          f"**{i['after']['rms_mm']:.3f} mm**, matched {i['before']['n_matched']} → {i['after']['n_matched']}. "
          f"Change from the fiducial fit: {i['rotation_vs_fiducial_fit_deg']:.2f}°, at most "
          f"{i['max_corner_move_vs_fiducial_fit_mm']:.2f} mm at the box corners. Final transform: **{i['final']}**.", "",
          f"![divots]({figs['divots']})", "", f"![icp]({figs['icp_residuals']})", "",
          "## Segments (mL)", "",
          "| segment | volume | reference |", "|---|---|---|",
          f"| box | {v['box']:.2f} | box mesh {g['box_mesh_mL']:.2f} (+{v['box_added_outside_mesh']:.2f} PLA voxels "
          f"within {BOX_DILATION} mm outside it; {v['pla_like_below_bottom_rejected']:.2f} below the base rejected) |",
          f"| stone | {v['stone']:.2f} | cavity net up to stone top {e['cavity_net_to_fill_mL']:.2f}; full {e['stone_full_fill_mL']:.2f} |"]
    for r in ("left", "right"):
        L += [f"| {r}_allowed | {v[f'{r}_allowed']:.2f} | region up to stone top {e[f'{r}_region_to_fill_mL']:.2f}; "
              f"full {e[f'{r}_region_full_mL']:.2f} (on CT grid {v[f'{r}_region_on_ct_grid']:.2f}) |",
              f"| {r}_forbidden | {v[f'{r}_forbidden']:.2f} | |"]
    L += [f"| stone above rim | {v['stone_above_rim']:.2f} | |",
          f"| voids in the stone (below top − 1 mm) | {v['voids_in_stone_below_top']:.2f} | |", "",
          f"Stone top (99.5th percentile of stone z, model frame): z = {e['fill_top_z_model']:.2f} mm "
          f"(floor {g['z_floor']}, rim {g['z_rim']}).", "",
          f"![overlay]({figs['overlay']})", "", f"![stone top]({figs['stone_top']})", ""]
    if "drilled_mL" in rep:
        d = rep["drilled_mL"]
        L += ["## Drilling", "", f"Stone removed since `{rep['reference']['name']}` (mapped through the CAD frame; "
              f"rotation between the scans {rep['reference']['rotation_deg']:.1f}°):", "",
              "| | removed (mL) | allowed (mL) | forbidden (mL) |", "|---|---|---|---|"]
        for r in ("left", "right"):
            L.append(f"| {r} route | {d['drilled']:.2f} | {d[f'{r}_drilled_allowed']:.2f} | "
                     f"{d[f'{r}_drilled_forbidden']:.2f} |")
        L += ["", f"![drilled]({figs['drilled']})", ""]
        blobs = rep["pla_damage"]["blobs"]
        if blobs:
            L += ["PLA lost next to the drilled channel (warning at >= "
                  f"{rep['pla_damage']['min_blob_uL']} uL):", "",
                  "| volume (uL) | part | centre, model (mm) | centre, CT LPS (mm) | warning |", "|---|---|---|---|---|"]
            for b in blobs:
                L.append(f"| {b['volume_uL']:.1f} | {b['part']} | {b['centre_model_mm']} | {b['centre_ct_lps']} | "
                         f"{'**yes**' if b['warning'] else 'no'} |")
            L.append("")
        if "damage" in figs:
            L += [f"![damage]({figs['damage']})", ""]
    with open(path, "w") as fh:
        fh.write("\n".join(L))


if __name__ == "__main__":
    main()
