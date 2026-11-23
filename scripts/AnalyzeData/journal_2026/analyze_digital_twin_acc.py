"""
Digital-twin accuracy: compare a simulated (AMBF) drilled segmentation against the
real drilled phantom (ground truth), and write one .seg.nrrd to inspect in 3D Slicer.

Inputs
  twin       AMBF digital twin .seg.nrrd, e.g. PL19_D01_ambf.seg.nrrd. It lives on the
             pre-drilling (D00) CT grid, in the D00 frame.
  twin-ref   The D00 .seg.nrrd the twin was started from (same grid as the twin). Used to
             get what the simulation removed (D00 minus twin). Optional.
  gt         Ground-truth post-drilling .seg.nrrd (D01), with segments box, stone and
             optionally drilled / box_damage.
  markers    Fiducials M-1..M-n (.mrk.json) for D00 and D01, matched by label.

Pipeline
  1. Rigid transform D00 -> D01 from the markers (least squares / Kabsch). The marker
     residuals are printed; they bound how well the two scans can be compared.
  2. Resample the twin (and the sim-removed mask) onto the exact D01 grid: each GT voxel
     centre is mapped back to D00 and the twin is sampled there (trilinear on each binary
     mask, then >= 0.5).
  3. Write a layered .seg.nrrd on the GT grid. Each segment has its own layer, so
     segments may overlap:
        gt_*                  the GT segments, copied as they are (GT 'drilled' is written
                              as gt_drilled_stone and 'box_damage' as gt_drilled_box)
        twin_box, twin_stone  the twin, resampled
        twin_drilled_stone    stone the simulation removed (twin-ref stone minus twin stone)
        twin_drilled_box      box the simulation removed (twin-ref box minus twin box)
        stone_both            stone in both GT and twin
        stone_gt_only         GT has stone, twin does not -> sim removed stone the real
                              drill left (sim over-drilled)
        stone_twin_only       twin has stone, GT does not -> real drill removed stone the
                              sim left (sim under-drilled)
        box_gt_only / box_twin_only   the same for the box (PLA)
        drilled_both / drilled_real_only / drilled_sim_only
                              overlap of twin_drilled_stone with gt_drilled_stone (needs
                              twin-ref and a GT 'drilled' segment). Stone only: box damage
                              is not scored (unreliable in the GT).
  4. Print metrics (volumes, Dice, voxel counts) and save them as JSON next to the output,
     so a run can be scored when tuning simulation parameters.

Run (any env with numpy, scipy, pynrrd):
    python analyze_digital_twin_acc.py \\
        --twin   .../P4/with-assistance/ambf_models/PL19_D01_ambf.seg.nrrd \\
        --twin-ref .../P4/with-assistance/input_backup/PL19_D00_box_dental.seg.nrrd \\
        --twin-markers .../P4/with-assistance/input_backup/PL19_D00_M.mrk.json \\
        --gt     .../phantom_models/PL19_D01/PL19_D01_box_dental.seg.nrrd \\
        --gt-markers .../phantom_models/PL19_D01/PL19_D01_M.mrk.json \\
        [--out <file>.seg.nrrd]

Default output: <twin dir>/<twin name>_vs_gt.seg.nrrd (+ _metrics.json).
"""

import argparse
import json
import os
import re
from collections import OrderedDict

import nrrd
import numpy as np
from scipy import ndimage as ndi


# Colors (RGB 0-1) for the segments this script creates. GT segments keep their own.
COLORS = {
    "twin_box": (0.55, 0.55, 0.50),
    "twin_stone": (0.30, 0.40, 0.80),
    "twin_drilled_stone": (0.95, 0.60, 0.10),
    "twin_drilled_box": (0.80, 0.45, 0.25),
    "stone_both": (0.55, 0.65, 0.95),
    "stone_gt_only": (0.90, 0.10, 0.60),
    "stone_twin_only": (0.10, 0.80, 0.80),
    "box_gt_only": (0.60, 0.20, 0.90),
    "box_twin_only": (0.20, 0.90, 0.20),
    "drilled_both": (0.20, 0.70, 0.20),
    "drilled_real_only": (0.90, 0.20, 0.20),
    "drilled_sim_only": (0.20, 0.40, 0.95),
}


# Output names for GT segments that are not written as gt_<name>.
GT_NAMES = {"drilled": "gt_drilled_stone", "box_damage": "gt_drilled_box"}


# --------------------------------------------------------------------------- I/O

class SegVolume:
    """A Slicer .seg.nrrd: spatial geometry plus one binary mask per segment name."""

    def __init__(self, path):
        self.path = path
        data, hdr = nrrd.read(path)
        self.hdr = hdr
        dirs = np.array(hdr["space directions"], dtype=float)
        if data.ndim == 4:
            dirs = dirs[1:4]
        elif data.ndim != 3:
            raise ValueError(f"{path}: unsupported data dimension {data.ndim}")
        space = hdr.get("space", "").lower()
        if space not in ("left-posterior-superior", "lps"):
            raise ValueError(f"{path}: expected LPS space, got '{hdr.get('space')}'")
        self.dirs = dirs                                       # row n = step of voxel axis n (mm)
        self.origin = np.array(hdr["space origin"], dtype=float)
        self.shape = data.shape[-3:]
        self.voxel_mm3 = abs(np.linalg.det(dirs))
        self.masks = OrderedDict()
        self.colors = {}
        for seg in self._segment_keys(hdr):
            name = hdr[f"{seg}_Name"]
            label = int(hdr.get(f"{seg}_LabelValue", 1))
            if data.ndim == 4:
                layer = int(hdr.get(f"{seg}_Layer", 0))
                mask = data[layer] == label
            else:
                mask = data == label
            self.masks[name] = mask
            self.colors[name] = tuple(float(c) for c in hdr[f"{seg}_Color"].split()[:3])

    @staticmethod
    def _segment_keys(hdr):
        idx = sorted({int(m.group(1)) for k in hdr for m in [re.match(r"Segment(\d+)_ID$", k)] if m})
        return [f"Segment{i}" for i in idx]

    def same_grid(self, other, tol=1e-4):
        return (self.shape == other.shape
                and np.allclose(self.dirs, other.dirs, atol=tol)
                and np.allclose(self.origin, other.origin, atol=tol))

    def mask(self, name):
        if name not in self.masks:
            raise KeyError(f"{self.path}: no segment named '{name}' (has {list(self.masks)})")
        return self.masks[name]


def load_markers(path):
    with open(path) as f:
        markup = json.load(f)["markups"][0]
    cs = markup.get("coordinateSystem", "LPS").upper()
    pts = {}
    for p in markup["controlPoints"]:
        xyz = np.array(p["position"], dtype=float)
        if cs == "RAS":
            xyz = xyz * np.array([-1.0, -1.0, 1.0])
        pts[p["label"]] = xyz
    return pts


def write_layered_seg(path, ref, segments):
    """Write `segments` [(name, mask, color)] as a layered seg.nrrd on the grid of `ref`.

    One layer per segment (label 1), so segments may overlap.
    """
    data = np.zeros((len(segments),) + tuple(ref.shape), dtype=np.uint8)
    hdr = OrderedDict()
    hdr["type"] = "unsigned char"
    hdr["dimension"] = 4
    hdr["space"] = "left-posterior-superior"
    hdr["sizes"] = np.array(data.shape)
    hdr["space directions"] = np.vstack([np.full(3, np.nan), ref.dirs])
    hdr["kinds"] = ["list", "domain", "domain", "domain"]
    hdr["encoding"] = "gzip"
    hdr["space origin"] = ref.origin
    # Keep the reference's Segmentation_* settings (geometry, master representation, ...).
    for k, v in ref.hdr.items():
        if k.startswith("Segmentation_"):
            hdr[k] = v
    extent = " ".join(f"0 {s - 1}" for s in ref.shape)
    for i, (name, mask, color) in enumerate(segments):
        data[i][mask] = 1
        seg = f"Segment{i}"
        hdr[f"{seg}_Color"] = " ".join(f"{c:.3f}" for c in color)
        hdr[f"{seg}_ColorAutoGenerated"] = "0"
        hdr[f"{seg}_Extent"] = extent
        hdr[f"{seg}_ID"] = name
        hdr[f"{seg}_LabelValue"] = "1"
        hdr[f"{seg}_Layer"] = str(i)
        hdr[f"{seg}_Name"] = name
        hdr[f"{seg}_NameAutoGenerated"] = "0"
        hdr[f"{seg}_Tags"] = "Segmentation.Status:completed|"
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    nrrd.write(path, data, hdr)


# --------------------------------------------------------------------- geometry

def rigid_from_markers(src, dst):
    """Least-squares rigid transform (R, t) with dst ~= R @ src + t (Kabsch)."""
    labels = sorted(set(src) & set(dst))
    if len(labels) < 3:
        raise ValueError(f"Need >= 3 shared markers, got {labels}")
    missing = sorted(set(src) ^ set(dst))
    if missing:
        print(f"WARN! Markers present in only one file (ignored): {missing}")
    a = np.array([src[k] for k in labels])
    b = np.array([dst[k] for k in labels])
    ca, cb = a.mean(0), b.mean(0)
    u, _, vt = np.linalg.svd((a - ca).T @ (b - cb))
    d = np.sign(np.linalg.det(vt.T @ u.T))
    r = vt.T @ np.diag([1.0, 1.0, d]) @ u.T
    t = cb - r @ ca
    residuals = {k: float(np.linalg.norm(r @ src[k] + t - dst[k])) for k in labels}
    return r, t, residuals


def resample_masks(src, masks, dst, r, t):
    """Sample binary `masks` (on src's grid) at dst's voxel centres.

    (r, t) maps src world -> dst world. Trilinear on each mask, threshold 0.5.
    """
    # World coordinates of every dst voxel centre: origin + idx @ dirs.
    idx = np.indices(dst.shape, dtype=np.float64).reshape(3, -1).T
    world_dst = dst.origin + idx @ dst.dirs
    world_src = (world_dst - t) @ r            # inverse rigid: r^T (p - t), row-vector form
    src_idx = (world_src - src.origin) @ np.linalg.inv(src.dirs)
    coords = src_idx.T
    out = {}
    for name, m in masks.items():
        v = ndi.map_coordinates(m.astype(np.float32), coords, order=1, mode="constant", cval=0.0)
        out[name] = (v >= 0.5).reshape(dst.shape)
    return out


# ----------------------------------------------------------------------- metrics

def dice(a, b):
    s = a.sum() + b.sum()
    return float(2.0 * (a & b).sum() / s) if s else float("nan")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--twin", required=True, help="AMBF digital twin .seg.nrrd (D00 frame)")
    ap.add_argument("--twin-markers", required=True, help="D00 fiducials .mrk.json")
    ap.add_argument("--twin-ref", default=None,
                    help="D00 .seg.nrrd the twin started from (same grid). Enables twin_drilled_* "
                         "and the drilled_* comparison.")
    ap.add_argument("--gt", required=True, help="Ground-truth D01 .seg.nrrd")
    ap.add_argument("--gt-markers", required=True, help="D01 fiducials .mrk.json")
    ap.add_argument("--out", default=None, help="Output .seg.nrrd (default: <twin>_vs_gt.seg.nrrd)")
    args = ap.parse_args()

    out = args.out or re.sub(r"(\.seg)?\.nrrd$", "", args.twin) + "_vs_gt.seg.nrrd"

    twin = SegVolume(args.twin)
    gt = SegVolume(args.gt)
    print(f"INFO! twin {twin.shape} segments {list(twin.masks)}")
    print(f"INFO! gt   {gt.shape} segments {list(gt.masks)}")

    # 1. D00 -> D01 from markers.
    r, t, res = rigid_from_markers(load_markers(args.twin_markers), load_markers(args.gt_markers))
    rot_deg = float(np.degrees(np.arccos(np.clip((np.trace(r) - 1) / 2, -1, 1))))
    rmse = float(np.sqrt(np.mean(np.square(list(res.values())))))
    print(f"INFO! D00->D01 rigid: rotation {rot_deg:.3f} deg, translation {np.round(t, 3).tolist()} mm")
    print("INFO! marker residuals (mm): " + ", ".join(f"{k}={v:.3f}" for k, v in res.items()))
    print(f"INFO! marker RMSE {rmse:.3f} mm (voxel size {np.linalg.norm(gt.dirs, axis=1).round(3).tolist()} mm)")

    # 2. Resample twin (and sim-removed stone) onto the GT grid.
    to_resample = {"twin_box": twin.mask("box"), "twin_stone": twin.mask("stone")}
    if args.twin_ref:
        ref = SegVolume(args.twin_ref)
        if not ref.same_grid(twin):
            raise ValueError("--twin-ref must be on the same grid as --twin")
        to_resample["twin_drilled_stone"] = ref.mask("stone") & ~twin.mask("stone")
        to_resample["twin_drilled_box"] = ref.mask("box") & ~twin.mask("box")
    rs = resample_masks(twin, to_resample, gt, r, t)

    # 3. Segments to write.
    gt_box, gt_stone = gt.mask("box"), gt.mask("stone")
    tw_box, tw_stone = rs["twin_box"], rs["twin_stone"]
    segments = [(GT_NAMES.get(n, f"gt_{n}"), m, gt.colors[n]) for n, m in gt.masks.items()]
    derived = OrderedDict([
        ("twin_box", tw_box),
        ("twin_stone", tw_stone),
    ])
    for n in ("twin_drilled_stone", "twin_drilled_box"):
        if n in rs:
            derived[n] = rs[n]
    derived["stone_both"] = gt_stone & tw_stone
    derived["stone_gt_only"] = gt_stone & ~tw_stone
    derived["stone_twin_only"] = tw_stone & ~gt_stone
    derived["box_gt_only"] = gt_box & ~tw_box
    derived["box_twin_only"] = tw_box & ~gt_box
    has_drilled = "twin_drilled_stone" in rs and "drilled" in gt.masks
    if has_drilled:
        real_d, sim_d = gt.mask("drilled"), rs["twin_drilled_stone"]
        derived["drilled_both"] = real_d & sim_d
        derived["drilled_real_only"] = real_d & ~sim_d
        derived["drilled_sim_only"] = sim_d & ~real_d
    segments += [(n, m, COLORS[n]) for n, m in derived.items()]

    write_layered_seg(out, gt, segments)
    print(f"INFO! Wrote {out} ({len(segments)} segments)")

    # 4. Metrics.
    v = gt.voxel_mm3

    def vol(m):
        return {"voxels": int(m.sum()), "mm3": round(float(m.sum()) * v, 3)}

    metrics = OrderedDict()
    metrics["inputs"] = {"twin": args.twin, "twin_ref": args.twin_ref, "gt": args.gt,
                         "twin_markers": args.twin_markers, "gt_markers": args.gt_markers}
    metrics["registration"] = {"rotation_deg": rot_deg, "translation_mm": t.tolist(),
                               "marker_rmse_mm": rmse, "marker_residuals_mm": res}
    metrics["voxel_mm3"] = v
    metrics["volumes"] = OrderedDict((name, vol(m)) for name, m, _ in segments)
    metrics["dice"] = OrderedDict([
        ("stone", dice(gt_stone, tw_stone)),
        ("box", dice(gt_box, tw_box)),
    ])
    if has_drilled:
        metrics["dice"]["drilled"] = dice(real_d, sim_d)
        real_mm3, sim_mm3 = real_d.sum() * v, sim_d.sum() * v
        metrics["drilled"] = {
            "real_mm3": round(float(real_mm3), 3),
            "sim_mm3": round(float(sim_mm3), 3),
            "sim_over_real": float(sim_mm3 / real_mm3) if real_mm3 else float("nan"),
            "recall_real_covered_by_sim": float((real_d & sim_d).sum() / real_d.sum()) if real_d.sum() else float("nan"),
            "precision_sim_inside_real": float((real_d & sim_d).sum() / sim_d.sum()) if sim_d.sum() else float("nan"),
        }

    print("INFO! Dice: " + ", ".join(f"{k}={val:.4f}" for k, val in metrics["dice"].items()))
    if has_drilled:
        d = metrics["drilled"]
        print(f"INFO! Drilled volume: real {d['real_mm3']:.1f} mm3, sim {d['sim_mm3']:.1f} mm3 "
              f"(sim/real {d['sim_over_real']:.3f}); real covered by sim "
              f"{100 * d['recall_real_covered_by_sim']:.1f}%, sim inside real "
              f"{100 * d['precision_sim_inside_real']:.1f}%")
    for name in derived:
        if name.endswith("_only"):
            print(f"INFO! {name:18s} {metrics['volumes'][name]['voxels']:8d} voxels "
                  f"{metrics['volumes'][name]['mm3']:10.1f} mm3")

    metrics_path = re.sub(r"\.seg\.nrrd$|\.nrrd$", "", out) + "_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"INFO! Wrote {metrics_path}")


if __name__ == "__main__":
    main()
