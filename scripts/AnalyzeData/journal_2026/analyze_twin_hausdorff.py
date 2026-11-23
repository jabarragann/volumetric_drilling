"""
Directed Hausdorff distances between the real and the digital-twin drilled stone, from a
<twin>_vs_gt.seg.nrrd written by analyze_digital_twin_acc.py.

Definitions (voxel sets on the GT grid, stone only, after the component filter below):
  X = real cut  = gt_drilled_stone     stone the real drill removed
  Y = twin cut  = twin_drilled_stone   stone the simulated drill removed (what navigation showed)
  R = X minus Y                        removed in reality only
  S = Y minus X                        removed in the twin only
  d(p, Y) = min over q in Y of |p - q|  (Euclidean, mm, between voxel centres)

  h(real -> twin) = max over p in X of d(p, Y) = max over p in R of d(p, Y)
                    -> farthest the real drill went beyond the bone navigation showed as
                       removed (the clinically dangerous direction)
  h(twin -> real) = max over p in S of d(p, X)
                    -> farthest navigation showed bone removed where real bone remained
  Hausdorff H     = max of the two

  h95 and mean are the 95th percentile and mean of d(p, Y) over R (and of d(p, X) over S).
  NOTE: these are taken over the one-sided voxels only, not over the whole cut or its
  surface as in the textbook HD95 / mean surface distance, so they are larger than those.
  Also reported: the size of the connected R (or S) region that holds the maximum.

Component filter (default on): each cut is reduced to its largest 26-connected component
before R and S are formed, so stray segmentation islands do not set the maximum. Dropped
voxels are reported. Disable with --keep-all-components.

Outputs (<base> = input file name without .seg.nrrd):
  <base>_hausdorff.json                     next to the input
  hausdorff_lines/<base>_hd_<dir>_<kind>.mrk.json   Slicer line markups (LPS, length shown)
    <dir>  real_to_twin  line from a voxel of R to its nearest voxel of Y
           twin_to_real  line from a voxel of S to its nearest voxel of X
    <kind> max           the voxel at h (the maximum)
           max_inplane   closest to h among lines that lie fully in one standard
                         (axial/coronal/sagittal) slice
           hd95          a voxel at h95 (closest to the percentile, random among ties)
           hd95_inplane  closest to h95 among the in-plane lines
  In-plane lines are still exact nearest-voxel pairs (3D distance): pairs whose two ends
  share one voxel index. Their point labels name the plane; clicking a point in the Markups
  table jumps that slice view to a slice containing the whole line.
  Colors: real_to_twin red / magenta / light red / orange; twin_to_real blue / purple /
  light blue / cyan (max / max_inplane / hd95 / hd95_inplane).

Run:
  python analyze_twin_hausdorff.py <twin>_vs_gt.seg.nrrd
  python analyze_twin_hausdorff.py --all <pilot_experiments> [--summary out.csv]
      (every <exp>/ambf_models/replay_*/*_vs_gt.seg.nrrd; summary CSV default:
       <pilot_experiments>/twin_hausdorff_summary.csv)
"""

import argparse
import csv
import glob
import json
import os
import re
from collections import OrderedDict

import numpy as np
from scipy import ndimage as ndi

from analyze_digital_twin_acc import SegVolume

REAL, TWIN = "gt_drilled_stone", "twin_drilled_stone"
STRUCT = np.ones((3, 3, 3), dtype=bool)   # 26-connectivity
LINES_DIR = "hausdorff_lines"
LINE_KINDS = ("max", "max_inplane", "hd95", "hd95_inplane")
LINE_COLORS = {
    ("real_to_twin", "max"): (0.90, 0.10, 0.10),
    ("real_to_twin", "max_inplane"): (0.90, 0.10, 0.60),
    ("real_to_twin", "hd95"): (1.00, 0.55, 0.55),
    ("real_to_twin", "hd95_inplane"): (1.00, 0.55, 0.00),
    ("twin_to_real", "max"): (0.10, 0.30, 0.95),
    ("twin_to_real", "max_inplane"): (0.55, 0.20, 0.90),
    ("twin_to_real", "hd95"): (0.55, 0.70, 1.00),
    ("twin_to_real", "hd95_inplane"): (0.00, 0.85, 0.85),
}
PLANE_OF_LPS_AXIS = {0: "sagittal", 1: "coronal", 2: "axial"}   # plane of constant L, P, S


def largest_component(mask):
    lab, n = ndi.label(mask, STRUCT)
    if n <= 1:
        return mask, {"components": int(n), "dropped_components": 0, "dropped_voxels": 0}
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    keep = int(sizes.argmax())
    out = lab == keep
    dropped = sizes[1:].copy()
    dropped[keep - 1] = 0
    return out, {"components": int(n), "dropped_components": int(n - 1),
                 "dropped_voxels": int(dropped.sum()),
                 "dropped_sizes": sorted((int(s) for s in dropped if s), reverse=True)}


def directed(only, target, seg, spacing, rng):
    """Distances from each voxel of `only` to the nearest voxel of `target`."""
    if not only.any():
        return None
    if not target.any():
        raise ValueError("target cut is empty")
    dist, nearest = ndi.distance_transform_edt(~target, sampling=spacing, return_indices=True)
    idx = np.argwhere(only)
    d = dist[only]
    hd95 = float(np.percentile(d, 95))

    nb = nearest[:, idx[:, 0], idx[:, 1], idx[:, 2]].T   # nearest target voxel of each voxel

    def endpoints(i):
        a, b = idx[i], nb[i]
        return {"distance_mm": float(d[i]),
                "from_ijk": a.tolist(), "to_ijk": b.tolist(),
                "from_lps": (seg.origin + a @ seg.dirs).tolist(),
                "to_lps": (seg.origin + b @ seg.dirs).tolist()}

    i_max = int(d.argmax())
    # HD95 representative: a voxel whose distance is closest to the percentile (random among ties).
    gap = np.abs(d - hd95)
    i_95 = int(rng.choice(np.flatnonzero(gap == gap.min())))

    # In-plane lines: pairs whose ends share a voxel index lie in one standard slice.
    shared = nb == idx
    cand = np.flatnonzero(shared.any(1))

    def inplane_closest_to(value):
        if not cand.size:
            return None
        g = np.abs(d[cand] - value)
        i_ip = int(rng.choice(cand[g == g.min()]))
        axis = int(np.flatnonzero(shared[i_ip])[0])
        lps_axis = int(np.abs(seg.dirs[axis]).argmax())
        line = endpoints(i_ip)
        line["plane"] = PLANE_OF_LPS_AXIS[lps_axis]
        line["slice_index"] = {"axis": axis, "index": int(idx[i_ip][axis])}
        line["candidates"] = int(cand.size)
        return line

    lab, _ = ndi.label(only, STRUCT)
    comp = lab[tuple(idx[i_max])]
    comp_vox = int((lab == comp).sum())
    return OrderedDict([
        ("hd_max_mm", float(d.max())),
        ("hd95_mm", hd95),
        ("mean_mm", float(d.mean())),
        ("voxels", int(only.sum())),
        ("max_component_voxels", comp_vox),
        ("max_component_mm3", round(comp_vox * seg.voxel_mm3, 3)),
        ("max_line", endpoints(i_max)),
        ("max_inplane_line", inplane_closest_to(float(d.max()))),
        ("hd95_line", endpoints(i_95)),
        ("hd95_inplane_line", inplane_closest_to(hd95)),
    ])


def write_line(path, name, line, color, description, plane=None):
    markup = {
        "@schema": "https://raw.githubusercontent.com/slicer/slicer/master/Modules/Loadable/Markups/Resources/Schema/markups-schema-v1.0.3.json#",
        "markups": [{
            "type": "Line",
            "coordinateSystem": "LPS",
            "coordinateUnits": "mm",
            "locked": True,
            "labelFormat": "%N-%d",
            "controlPoints": [
                {"id": "1", "label": f"{plane}-from" if plane else f"{name}-from", "description": description,
                 "position": line["from_lps"], "locked": True, "visibility": True,
                 "positionStatus": "defined"},
                {"id": "2", "label": f"{plane}-to" if plane else f"{name}-to", "description": description,
                 "position": line["to_lps"], "locked": True, "visibility": True,
                 "positionStatus": "defined"},
            ],
            "measurements": [{"name": "length", "enabled": True, "units": "mm", "printFormat": "%-#4.4g%s"}],
            "display": {"visibility": True, "color": list(color), "selectedColor": list(color),
                        "propertiesLabelVisibility": True, "pointLabelsVisibility": False,
                        "lineThickness": 0.4, "glyphScale": 1.5},
        }],
    }
    with open(path, "w") as f:
        json.dump(markup, f, indent=2)


def analyze(path, keep_all=False, seed=0):
    seg = SegVolume(path)
    dirs = seg.dirs
    if not np.allclose(dirs @ dirs.T, np.diag(np.diag(dirs @ dirs.T)), atol=1e-6):
        raise ValueError(f"{path}: grid axes are not orthogonal")
    spacing = np.linalg.norm(dirs, axis=1)
    real, twin = seg.mask(REAL), seg.mask(TWIN)
    filt = {}
    if not keep_all:
        real, filt["real_cut"] = largest_component(real)
        twin, filt["twin_cut"] = largest_component(twin)
    r_only, s_only = real & ~twin, twin & ~real

    rng = np.random.default_rng(seed)
    res = OrderedDict()
    res["input"] = path
    res["voxel_spacing_mm"] = spacing.tolist()
    res["component_filter"] = "off" if keep_all else "largest 26-connected component of each cut"
    res["component_filter_details"] = filt
    res["real_cut_voxels"], res["twin_cut_voxels"] = int(real.sum()), int(twin.sum())
    res["real_to_twin"] = directed(r_only, twin, seg, spacing, rng)
    res["twin_to_real"] = directed(s_only, real, seg, spacing, rng)
    hds = [res[k]["hd_max_mm"] for k in ("real_to_twin", "twin_to_real") if res[k]]
    res["hausdorff_mm"] = max(hds) if hds else 0.0
    h95 = [res[k]["hd95_mm"] for k in ("real_to_twin", "twin_to_real") if res[k]]
    res["hd95_mm"] = max(h95) if h95 else 0.0

    base = re.sub(r"(\.seg)?\.nrrd$", "", path)
    lines_dir = os.path.join(os.path.dirname(os.path.abspath(path)), LINES_DIR)
    os.makedirs(lines_dir, exist_ok=True)
    name = os.path.basename(base)
    for tag, what in (("real_to_twin", "real-only voxel -> nearest twin-cut voxel"),
                      ("twin_to_real", "twin-only voxel -> nearest real-cut voxel")):
        r = res[tag]
        for kind in LINE_KINDS:
            out = os.path.join(lines_dir, f"{name}_hd_{tag}_{kind}.mrk.json")
            line = r[f"{kind}_line"] if r else None
            if line is None:
                if os.path.exists(out):
                    os.remove(out)
                continue
            plane = line.get("plane")
            desc = f"{kind} directed distance, {what}" + (f", lies in one {plane} slice" if plane else "")
            write_line(out, f"{tag}_{kind}", line, LINE_COLORS[(tag, kind)], desc, plane)
    with open(f"{base}_hausdorff.json", "w") as f:
        json.dump(res, f, indent=2)
    return res


def fmt(r):
    if r is None:
        return "none"
    def ip(k):
        line = r[f"{k}_inplane_line"]
        return f"in-plane {line['distance_mm']:.2f} {line['plane']}" if line else "no in-plane"
    return (f"max {r['hd_max_mm']:.2f} mm ({ip('max')}), HD95 {r['hd95_mm']:.2f} ({ip('hd95')}), "
            f"mean {r['mean_mm']:.2f} (max in a {r['max_component_voxels']}-voxel region)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("seg", nargs="?", help="<twin>_vs_gt.seg.nrrd")
    ap.add_argument("--all", default=None, help="pilot_experiments folder: run every replay_*/*_vs_gt.seg.nrrd")
    ap.add_argument("--summary", default=None, help="Summary CSV for --all")
    ap.add_argument("--keep-all-components", action="store_true", help="Disable the largest-component filter")
    ap.add_argument("--seed", type=int, default=0, help="Seed for picking the HD95 line among ties")
    a = ap.parse_args()
    if bool(a.seg) == bool(a.all):
        ap.error("give one .seg.nrrd or --all <folder>")

    if a.seg:
        r = analyze(a.seg, a.keep_all_components, a.seed)
        print(f"real -> twin: {fmt(r['real_to_twin'])}")
        print(f"twin -> real: {fmt(r['twin_to_real'])}")
        print(f"Hausdorff {r['hausdorff_mm']:.2f} mm, HD95 {r['hd95_mm']:.2f} mm")
        return

    root = os.path.abspath(a.all)
    files = sorted(f for f in glob.glob(os.path.join(root, "*", "*", "ambf_models", "replay_*", "*_vs_gt.seg.nrrd")))
    rows = []
    for f in files:
        rel = os.path.relpath(f, root).split(os.sep)
        participant, condition, run = rel[0], rel[1], rel[3]
        r = analyze(f, a.keep_all_components, a.seed)
        m = f.replace(".seg.nrrd", "_metrics.json")
        dice = json.load(open(m))["dice"].get("drilled", float("nan")) if os.path.exists(m) else float("nan")
        filt = r["component_filter_details"]
        row = OrderedDict(participant=participant, condition=condition, run=run,
                          phantom=os.path.basename(f).split("_")[0], drilled_dice=round(dice, 4))
        for key, tag in (("real_to_twin", "real_to_twin"), ("twin_to_real", "twin_to_real")):
            d = r[key] or {}
            row[f"{tag}_max_mm"] = round(d.get("hd_max_mm", 0.0), 3)
            row[f"{tag}_hd95_mm"] = round(d.get("hd95_mm", 0.0), 3)
            row[f"{tag}_mean_mm"] = round(d.get("mean_mm", 0.0), 3)
            row[f"{tag}_max_component_voxels"] = d.get("max_component_voxels", 0)
            for k in ("max", "hd95"):
                ip = d.get(f"{k}_inplane_line") or {}
                row[f"{tag}_{k}_inplane_mm"] = round(ip.get("distance_mm", float("nan")), 3)
                row[f"{tag}_{k}_inplane_plane"] = ip.get("plane", "")
        row["hausdorff_mm"] = round(r["hausdorff_mm"], 3)
        row["hd95_mm"] = round(r["hd95_mm"], 3)
        row["dropped_real_voxels"] = filt.get("real_cut", {}).get("dropped_voxels", 0)
        row["dropped_twin_voxels"] = filt.get("twin_cut", {}).get("dropped_voxels", 0)
        rows.append(row)
        print(f"{participant}/{condition}/{run}: real->twin {fmt(r['real_to_twin'])}; "
              f"twin->real {fmt(r['twin_to_real'])}")
    out = a.summary or os.path.join(root, "twin_hausdorff_summary.csv")
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out} ({len(rows)} runs)")


if __name__ == "__main__":
    main()
