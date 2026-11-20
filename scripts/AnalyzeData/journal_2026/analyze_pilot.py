"""
Assistance vs no-assistance metrics for the study (P1-P8, phantoms PL09-PL28).

Reads the outputs of phantom_segmentation_tools/register_cad.py (each D01 run made
with --reference) and, where a recording exists, its session tags. All metrics are
measured on the D01 CT grid, against the route the operator was assigned, using the
CAD model of the version that phantom was printed from (v01, v03, v04).

"Spots" are the individual places where the operator went wrong: each connected
piece of forbidden stone deeper than TOLERANCE_MM past the route wall (excursion),
and each connected piece of PLA lost next to the channel (breach). Each spot is
located on the route (leg or corner, inner/outer side of the turn), next to the
nearest obstacle, and by depth.

Run (conda env saint-env):
    python analyze_pilot.py [--out <folder>]

Writes metrics.csv/json, spots.csv, summary.md, pilot_drilled.png, pilot_compare.png
and pilot_spots.png.
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import nrrd
import SimpleITK as sitk
from scipy import ndimage as ndi

ROOT = os.path.expanduser("~/research/saint_project")
sys.path.insert(0, os.path.join(ROOT, "volumetric_drilling_saint/scripts/phantom_segmentation_tools"))
import register_cad as rc  # noqa: E402

REG = os.path.join(ROOT, "phantoms/Loop-x/cad-registration")
EXP = os.path.join(ROOT, "experiments/experiment_2026-10-14")
STL_ROOT = os.path.expanduser("~/research/openscad_models/saint_phantom/stl")

# order = session order for that participant. P1/P2 from the recordings; P3/P4 confirmed
# by the user (2026-11-13). No recordings for P3-P8. P5-P8 (2026-11-13, v04) follow the final
# schedule: every participant starts with the left route, condition order alternates.
# P1 juan-assistance also has a 16 s false start (20261014_175203).
STUDY = [
    {"participant": "P1", "phantom": "PL09", "operator": "Juan", "condition": "no assistance", "route": "right",
     "order": 1, "version": "v01", "recording": "experiment_2026-10-14-juan-no-assit/recordings/20261014_173959"},
    {"participant": "P1", "phantom": "PL10", "operator": "Juan", "condition": "assistance", "route": "left",
     "order": 2, "version": "v01", "recording": "experiment_2026-10-14-juan-assistance/recordings/20261014_175256"},
    {"participant": "P2", "phantom": "PL11", "operator": "Brendan", "condition": "assistance", "route": "right",
     "order": 1, "version": "v01", "recording": "experiment_2026-10-14-t1-brendan-assist/recordings/20261014_184736"},
    {"participant": "P2", "phantom": "PL12", "operator": "Brendan", "condition": "no assistance", "route": "left",
     "order": 2, "version": "v01", "recording": "experiment_2026-10-14-t2-brendan-no-assist/recordings/20261014_190122"},
    {"participant": "P3", "phantom": "PL15", "operator": "Silvia", "condition": "no assistance", "route": "right",
     "order": 1, "version": "v03", "recording": None},
    {"participant": "P3", "phantom": "PL17", "operator": "Silvia", "condition": "assistance", "route": "left",
     "order": 2, "version": "v03", "recording": None},
    {"participant": "P4", "phantom": "PL19", "operator": "Obi", "condition": "assistance", "route": "right",
     "order": 1, "version": "v04", "recording": None},
    {"participant": "P4", "phantom": "PL20", "operator": "Obi", "condition": "no assistance", "route": "left",
     "order": 2, "version": "v04", "recording": None},
    {"participant": "P5", "phantom": "PL21", "operator": "Christine", "condition": "no assistance", "route": "left",
     "order": 1, "version": "v04", "recording": None},
    {"participant": "P5", "phantom": "PL22", "operator": "Christine", "condition": "assistance", "route": "right",
     "order": 2, "version": "v04", "recording": None},
    {"participant": "P6", "phantom": "PL23", "operator": "Mattia", "condition": "assistance", "route": "left",
     "order": 1, "version": "v04", "recording": None},
    {"participant": "P6", "phantom": "PL24", "operator": "Mattia", "condition": "no assistance", "route": "right",
     "order": 2, "version": "v04", "recording": None},
    {"participant": "P7", "phantom": "PL25", "operator": "Manish", "condition": "no assistance", "route": "left",
     "order": 1, "version": "v04", "recording": None},
    {"participant": "P7", "phantom": "PL26", "operator": "Manish", "condition": "assistance", "route": "right",
     "order": 2, "version": "v04", "recording": None},
    {"participant": "P8", "phantom": "PL27", "operator": "Lucia", "condition": "assistance", "route": "left",
     "order": 1, "version": "v04", "recording": None},
    {"participant": "P8", "phantom": "PL28", "operator": "Lucia", "condition": "no assistance", "route": "right",
     "order": 2, "version": "v04", "recording": None},
]
CONDITIONS = ("assistance", "no assistance")

OBSTACLE_NAMES = "ABCDEFG"    # same order as obstacles_xy in paths.json (v01 has no G)
OBSTACLE_MARGIN = 0.6         # mm, same as the "obstacle" class in register_cad.py
TOLERANCE_MM = 0.5            # forbidden stone deeper than this past the route wall (about FRE + 1 voxel)
COMMON_STONE_LEVEL = 750.0    # sensitivity check: one PLA|stone level for every scan
NOISE_FAR_MM = 3.0            # PLA loss this far from the channel can only be scan-to-scan noise
BREACH_NEAR_MM = 1.5          # PLA loss counts as a breach only this close to the channel: buried infill flickers
FLOOR_SKIN_MM = 1.0           # solid skin on top of the base; the lattice under it flickers and isn't counted
COVERAGE_MM = 1.5             # a centreline point is drilled if the channel is within this distance
SPOT_MIN_UL = {"excursion": 5.0, "breach": 2.0}   # smaller pieces are not counted as spots (breach: as register_cad)
CORNER_MM = 5.0               # a spot leaving the route within this distance (xy) of a route vertex is at that corner
                              # (the corridor is 7 mm wide, so its wall at a corner is ~3.5*sqrt(2) mm from the vertex)

COLORS = {"assistance": "#2a78d6", "no assistance": "#eb6834"}
MARKERS = {"P1": "o", "P2": "s", "P3": "^", "P4": "D", "P5": "v", "P6": "P", "P7": "X", "P8": "*"}
INK, INK2 = "#0b0b0b", "#52514e"


def load_segments(path):
    arr, h = nrrd.read(path)
    out = {}
    for i in range(arr.shape[0]):
        # file is [seg, i, j, k]; CT arrays are [k, j, i]
        out[h[f"Segment{i}_Name"]] = arr[i].transpose(2, 1, 0).astype(bool)
    return out


def session_seconds(rec):
    if rec is None:
        return None
    with open(os.path.join(EXP, rec, "session_tags.json")) as f:
        st = json.load(f)["stages"][0]
    return (st["end"]["cpu_ts"] - st["start"]["cpu_ts"]) / 1e9


def route_centreline(paths, route):
    left = paths["meshes"]["path_left"]["centreline"]
    if route == "left":
        return np.array(left, float)
    r = paths["meshes"]["path_right"]["centreline"]
    return np.array(left[:2] + r[1:] + left[-1:], float)   # shared entry and exit legs


def dist_to_polyline(p, line):
    best = np.full(len(p), np.inf)
    for a, b in zip(line[:-1], line[1:]):
        ab = b - a
        t = np.clip(((p - a) @ ab) / (ab @ ab), 0, 1)
        best = np.minimum(best, np.linalg.norm(p - (a + t[:, None] * ab), axis=1))
    return best


def rect_dist(p, rect):
    x0, y0, x1, y1 = rect
    return float(np.hypot(max(x0 - p[0], 0, p[0] - x1), max(y0 - p[1], 0, p[1] - y1)))


def load_model(version):
    d = os.path.join(STL_ROOT, version)
    with open(os.path.join(d, "paths.json")) as f:
        paths = json.load(f)
    obstacles = dict(zip(OBSTACLE_NAMES, paths["meshes"]["obstacles"]["obstacles_xy"]))
    pd_box = rc.read_stl(os.path.join(d, f"saint_phantom_{version}.stl"))
    b = np.array(pd_box.GetBounds()).reshape(3, 2)
    grid = rc.ModelGrid(b[:, 0] - 3, b[:, 1] + [3, 3, 6], rc.MODEL_STEP)
    occ = {r: grid.voxelise(rc.read_stl(os.path.join(d, f"saint_phantom_{version}_path_{r}.stl"))) for r in rc.ROUTES}
    obs_top = float(rc.read_stl(os.path.join(d, f"saint_phantom_{version}_obstacles.stl")).GetBounds()[5])
    return {"version": version, "paths": paths, "obstacles": obstacles, "grid": grid, "occ_route": occ,
            "obstacle_top_z": obs_top}


def locate(c, line, obstacles, obs_top):
    """Where on the route a spot at model point c is: corner/leg, turn side, nearest obstacle, depth."""
    out = {}
    verts = line[1:-1]
    dv = np.hypot(*(verts - c[:2]).T)
    k = int(dv.argmin())
    if dv[k] <= CORNER_MM:
        a, v, b = line[k], line[k + 1], line[k + 2]
        u_in, u_out = (v - a) / np.linalg.norm(v - a), (b - v) / np.linalg.norm(b - v)
        inner = (c[:2] - v) @ (u_out - u_in) > 0
        out["where"], out["corner_side"] = f"corner {k + 1}", "inner" if inner else "outer"
    else:
        dl = [dist_to_polyline(c[None, :2], line[i:i + 2])[0] for i in range(len(line) - 1)]
        i = int(np.argmin(dl))
        name = "entry leg" if i == 0 else "exit leg" if i == len(line) - 2 else f"leg {i + 1}"
        out["where"], out["corner_side"] = name, "-"
    od = {n: rect_dist(c, r) for n, r in obstacles.items()}
    n = min(od, key=od.get)
    out["nearest_obstacle"], out["obstacle_dist_mm"] = n, round(od[n], 2)
    out["above_obstacle"] = od[n] == 0 and c[2] > obs_top
    out["depth"] = "above obstacle tops" if c[2] > obs_top else "obstacle layer"
    return out


def spots_of(mask, kind, xyz, vv, dist, line, model, s, zones):
    """zones: name -> bool mask; an excursion is labelled by the zone holding most of its volume."""
    labs, n = ndi.label(mask, structure=np.ones((3, 3, 3)))
    rows = []
    for i in range(1, n + 1):
        sel = labs == i
        vol = float(sel.sum() * vv)
        if vol < SPOT_MIN_UL[kind]:
            continue
        q = xyz[sel]
        c = q.mean(axis=0)
        # where the operator left the route: the spot's point nearest the route centreline
        exit_pt = q[dist_to_polyline(q[:, :2], line).argmin()]
        share = {z: float((sel & zm).sum() / sel.sum()) for z, zm in zones.items()}
        into = max(share, key=share.get)
        into = into if share[into] >= 0.3 else "beside the route"
        r = {"participant": s["participant"], "phantom": s["phantom"], "operator": s["operator"],
             "condition": s["condition"], "route": s["route"], "order": s["order"], "version": s["version"],
             "kind": kind, "volume_uL": round(vol, 1),
             "x_mm": round(float(c[0]), 1), "y_mm": round(float(c[1]), 1), "z_mm": round(float(c[2]), 1),
             "z_min_mm": round(float(q[:, 2].min()), 1),
             "excursion_max_mm": round(float(dist[sel].max()), 2) if kind == "excursion" else "",
             "into": into if kind == "excursion" else "",
             "exit_x_mm": round(float(exit_pt[0]), 1), "exit_y_mm": round(float(exit_pt[1]), 1)}
        loc = locate(exit_pt if kind == "excursion" else c, line, model["obstacles"], model["obstacle_top_z"])
        near_obs = locate(c, line, model["obstacles"], model["obstacle_top_z"])   # obstacle/depth from the spot centre
        for k in ("nearest_obstacle", "obstacle_dist_mm", "above_obstacle", "depth"):
            loc[k] = near_obs[k]
        r.update(loc)
        rows.append(r)
    return rows


def analyze(s, model):
    paths, grid, occ_route, obstacles = model["paths"], model["grid"], model["occ_route"], model["obstacles"]
    p, r = s["phantom"], s["route"]
    n0, n1 = f"{p}_D00", f"{p}_D01"
    d0, d1 = os.path.join(REG, n0), os.path.join(REG, n1)
    with open(os.path.join(d0, f"{n0}_report.json")) as f:
        rep0 = json.load(f)
    with open(os.path.join(d1, f"{n1}_report.json")) as f:
        rep1 = json.load(f)
    for rep, n in ((rep0, n0), (rep1, n1)):
        v = rep.get("model", {}).get("version") or rep.get("version")
        if v != s["version"]:
            raise SystemExit(f"{n}: registered with model {v}, STUDY says {s['version']}")
    img1, img0 = sitk.ReadImage(os.path.join(d1, f"{n1}_ct.nrrd")), sitk.ReadImage(os.path.join(d0, f"{n0}_ct.nrrd"))
    v1 = sitk.GetArrayFromImage(img1).astype(np.float32)
    a0 = sitk.GetArrayFromImage(img0).astype(np.float32)
    g1, g0 = rc.CTGeom(img1), rc.CTGeom(img0)
    M1, M0 = np.loadtxt(os.path.join(d1, f"{n1}_model_to_ct_LPS.txt")), np.loadtxt(os.path.join(d0, f"{n0}_model_to_ct_LPS.txt"))
    shape = v1.shape
    pts = rc.apply(rc.inv(M1), g1.all_centres())
    v0 = rc.sample_ct(a0, g0, rc.apply(M0, pts)).reshape(shape)
    xyz = pts.reshape(shape + (3,))
    vv = float(np.prod(g1.spacing))   # mm^3 (= uL) per voxel
    ml = lambda m: float(m.sum() * vv / 1000)

    seg = load_segments(os.path.join(d1, f"{n1}_all_combinations.seg.nrrd"))
    drilled, box = seg["drilled"], seg["box"] | seg["box_damage"]
    # the channel is the largest component; small patches elsewhere aren't drilling
    lb, _ = ndi.label(drilled)
    sz = np.bincount(lb.ravel())
    sz[0] = 0
    channel = lb == sz.argmax()
    stray = drilled & ~channel
    good, bad = seg[f"{r}_drilled_allowed"] & channel, seg[f"{r}_drilled_forbidden"] & channel
    route_stone = seg[f"{r}_drilled_allowed"] | seg[f"{r}_allowed"]

    m = {k: s[k] for k in ("participant", "phantom", "operator", "condition", "route", "order", "version")}
    m["voxel_mm"] = float(g1.spacing[0])
    drilled = channel
    m["drilled_voxels"], m["drilled_mL"] = int(drilled.sum()), ml(drilled)
    m["stray_patches_voxels"] = int(stray.sum())
    m["forbidden_voxels"], m["forbidden_mL"] = int(bad.sum()), ml(bad)
    m["forbidden_pct_of_drilled"] = 100 * bad.sum() / drilled.sum()
    m["route_completion_pct"] = 100 * good.sum() / route_stone.sum()
    m["route_dice"] = 2 * good.sum() / (drilled.sum() + route_stone.sum())

    # how far past the route wall the forbidden stone reaches
    region = (grid.sample(occ_route[r], pts) >= 0.5).reshape(shape)
    dist = ndi.distance_transform_edt(~region, sampling=g1.spacing[::-1])
    m["excursion_max_mm"] = float(dist[bad].max()) if bad.any() else 0.0
    m["excursion_p95_mm"] = float(np.percentile(dist[bad], 95)) if bad.any() else 0.0
    beyond = bad & (dist > TOLERANCE_MM)
    m["forbidden_beyond_tol_voxels"], m["forbidden_beyond_tol_mL"] = int(beyond.sum()), ml(beyond)
    labs, n = ndi.label(ndi.binary_opening(beyond))
    m["excursion_events"] = int(n)

    # stone removed on top of an obstacle vs beside the route
    xy = xyz[..., :2]
    footprint = np.zeros(shape, bool)
    for (x0, y0, x1, y1) in obstacles.values():
        footprint |= (xy[..., 0] >= x0) & (xy[..., 0] <= x1) & (xy[..., 1] >= y0) & (xy[..., 1] <= y1)
    m["forbidden_above_obstacle_mL"] = ml(bad & footprint)
    m["forbidden_beside_route_mL"] = ml(bad & ~footprint)

    line = route_centreline(paths, r)
    dc = dist_to_polyline(xyz[drilled][:, :2], line)
    m["centreline_dist_mean_mm"], m["centreline_dist_p95_mm"] = float(dc.mean()), float(np.percentile(dc, 95))

    # coverage: share of the route centreline the channel reaches (the drill is narrower
    # than the 7 mm corridor, so route_completion_pct can't reach 100)
    seg_len = np.linalg.norm(np.diff(line, axis=0), axis=1)
    samples = np.concatenate([a + np.outer(np.arange(0, 1, .5 / l), b - a) for a, b, l in zip(line[:-1], line[1:], seg_len)])
    cov = np.mean([np.hypot(*(xyz[drilled][:, :2] - c).T).min() <= COVERAGE_MM for c in samples])
    m["centreline_coverage_pct"] = 100 * float(cov)

    # PLA breaches: material in D00, air in D01, one level for both scans
    z_floor = paths["region_z_range"][0]
    level = 0.5 * (rep0["thresholds"]["modes"]["air"] + rep0["thresholds"]["modes"]["pla"])
    lost = box & (v0 > level) & (v1 <= level)
    dch = ndi.distance_transform_edt(~drilled, sampling=g1.spacing[::-1])
    near, far = dch <= BREACH_NEAR_MM, dch > NOISE_FAR_MM
    z = xyz[..., 2]
    o = OBSTACLE_MARGIN
    obs_any = np.zeros(shape, bool)
    per_obs = {}
    for name, (x0, y0, x1, y1) in obstacles.items():
        mask = (xy[..., 0] >= x0 - o) & (xy[..., 0] <= x1 + o) & (xy[..., 1] >= y0 - o) & (xy[..., 1] <= y1 + o) & (z >= z_floor)
        obs_any |= mask
        n_hit = int((lost & near & mask).sum())
        if n_hit:
            per_obs[name] = n_hit
    obs_vox = int((lost & near & obs_any).sum())
    m["obstacle_breach_voxels"] = obs_vox
    m["obstacle_breach_uL"] = obs_vox * vv
    m["obstacle_breach_by_obstacle"] = per_obs
    m["obstacles_breached"] = "".join(k for k, v in per_obs.items() if v >= 2 / vv) or "-"   # >= 2 uL, as in register_cad
    # same rule, same material, away from the channel = what scan noise alone gives
    obs_near, obs_far = box & near & obs_any, box & far & obs_any
    m["obstacle_noise_expected_voxels"] = float((lost & obs_far).sum() / obs_far.sum() * obs_near.sum())

    skin = box & (z >= z_floor - FLOOR_SKIN_MM) & (z < z_floor)
    m["floor_skin_lost_voxels"] = int((lost & skin & near).sum())
    m["floor_skin_lost_uL"] = m["floor_skin_lost_voxels"] * vv
    m["floor_skin_noise_expected_voxels"] = float((lost & skin & far).sum() / (skin & far).sum() * (skin & near).sum())
    m["channel_bottom_z_mm"] = float(np.percentile(z[drilled], 0.5))
    m["box_damage_spots_uL"] = [round(b["volume_uL"], 1) for b in rep1["pla_damage"]["blobs"] if b["warning"]]

    # spots: individual excursions past the wall and individual PLA breaches
    other = "left" if r == "right" else "right"
    zones = {f"other route ({other})": (grid.sample(occ_route[other], pts) >= 0.5).reshape(shape) & ~region}
    for name, (x0, y0, x1, y1) in obstacles.items():
        zones[f"above obstacle {name}"] = ((xy[..., 0] >= x0) & (xy[..., 0] <= x1) & (xy[..., 1] >= y0) & (xy[..., 1] <= y1)
                                           & ~zones[f"other route ({other})"])
    spots = spots_of(ndi.binary_opening(beyond), "excursion", xyz, vv, dist, line, model, s, zones)
    breach = spots_of(lost & near & (obs_any | skin), "breach", xyz, vv, dist, line, model, s, zones)
    for b in breach:   # name the breach after the part it hit
        b["hit"] = "floor skin" if b["z_mm"] < z_floor else f"obstacle {b['nearest_obstacle']}"
    for e in spots:
        e["hit"] = "-"
    spots += breach
    m["excursion_spots"] = sum(x["kind"] == "excursion" for x in spots)
    m["breach_spots"] = len(breach)

    # sensitivity: same stone level in both scans, independent of the per-scan thresholds
    zone = (xy[..., 0] > 5) & (xy[..., 0] < 55) & (xy[..., 1] > 22) & (xy[..., 1] < 72) & (xyz[..., 2] >= z_floor) & ~box
    # (PL22/PL23: their D00 stone hadn't set, so use the --stone-min level of the D01 run)
    lvl = rep1["thresholds"].get("stone_min") or COMMON_STONE_LEVEL
    m["sens_stone_level"] = float(lvl)
    common = ndi.binary_opening((v0 > lvl) & (v1 <= lvl) & zone)
    lb, _ = ndi.label(common)
    sz = np.bincount(lb.ravel())
    sz[0] = 0
    common = lb == sz.argmax()
    m["sens_drilled_mL"] = ml(common)
    m["sens_forbidden_mL"] = ml(common & ~region)

    m["fre_D00_mm"], m["fre_D01_mm"] = rep0["fiducials"]["fre_rms_mm"], rep1["fiducials"]["fre_rms_mm"]
    m["final_pose_D00"] = rep0["icp"]["final"]
    same = rep1["reference"]["same_phantom_check"]
    m["same_phantom_dice"], m["same_phantom_ncc"] = same["dice"], same["ncc"]
    m["task_seconds"] = session_seconds(s["recording"])
    m["removal_mL_per_min"] = m["drilled_mL"] / (m["task_seconds"] / 60) if m["task_seconds"] else None

    x, y = np.meshgrid(np.arange(0, 60, .25), np.arange(15, 80, .25))
    maps = {}
    for key, mask in (("good", good), ("bad", bad), ("damage", lost & near & (obs_any | skin))):
        u = np.zeros(x.shape, bool)
        if mask.any():
            q = xyz[mask]
            ix, iy = ((q[:, 0]) / .25).astype(int), ((q[:, 1] - 15) / .25).astype(int)
            ok = (ix >= 0) & (ix < x.shape[1]) & (iy >= 0) & (iy < x.shape[0])
            u[iy[ok], ix[ok]] = True
            u = ndi.binary_closing(u, iterations=2)
        maps[key] = u
    return m, maps, spots


COMPARE = [("forbidden_mL", "Forbidden stone (mL)"), ("excursion_max_mm", "Max excursion (mm)"),
           ("excursion_spots", "Excursion spots (n)"), ("breach_spots", "PLA breach spots (n)"),
           ("obstacle_breach_uL", "Obstacle PLA lost (uL)"), ("floor_skin_lost_uL", "Floor skin lost (uL)"),
           ("route_completion_pct", "Route completed (%)"), ("centreline_coverage_pct", "Centreline coverage (%)"),
           ("task_seconds", "Task time (s)")]


def style(ax):
    ax.tick_params(colors=INK2, labelsize=8, length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)


def draw_layout(ax, obstacles, label=True):
    for name, (x0, y0, x1, y1) in obstacles.items():
        ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec=INK2, lw=1))
        if label:
            ax.text(x0 + 1, y0 + 1, name, color=INK2, fontsize=8)


def fig_maps(rows, maps, models, path):
    parts = sorted({m["participant"] for m in rows}, key=lambda p: int(p[1:]))
    ncol = min(4, len(parts))                       # wrap: 4 participants per band of 2 rows
    nb = -(-len(parts) // ncol)
    fig, axs = plt.subplots(2 * nb, ncol, figsize=(3.4 * ncol, 4.75 * 2 * nb), sharex=True, sharey=True,
                            facecolor="#fcfcfb", squeeze=False)
    for ax in axs.ravel():
        ax.set_visible(False)
    for jj, pt in enumerate(parts):
        band, j = divmod(jj, ncol)
        for i, cond in enumerate(CONDITIONS):
            ax = axs[2 * band + i, j]
            ax.set_visible(True)
            m = next(r for r in rows if r["participant"] == pt and r["condition"] == cond)
            u, mod = maps[m["phantom"]], models[m["version"]]
            im = np.ones(u["good"].shape + (3,))
            im[u["good"]] = (0.75, 0.80, 0.83)
            im[u["bad"]] = matplotlib.colors.to_rgb("#e34948")
            im[u["damage"]] = (0.10, 0.10, 0.10)
            ax.imshow(im, origin="lower", extent=(0, 60, 15, 80))
            draw_layout(ax, mod["obstacles"])
            c = route_centreline(mod["paths"], m["route"])
            ax.plot(c[:, 0], c[:, 1], color=INK, lw=1, ls="--")
            ax.set_title(f"{pt} {m['phantom']} ({m['version']}), {cond}\n{m['route']} route, session {m['order']}",
                         fontsize=9, color=COLORS[cond])
            style(ax)
    for ax in axs[-1]:
        ax.set_xlabel("x (model mm)", color=INK2, fontsize=9)
    for ax in axs[:, 0]:
        ax.set_ylabel("y (model mm)", color=INK2, fontsize=9)
    h = [plt.Rectangle((0, 0), 1, 1, fc=(0.75, 0.80, 0.83)), plt.Rectangle((0, 0), 1, 1, fc="#e34948"),
         plt.Rectangle((0, 0), 1, 1, fc=(0.1, 0.1, 0.1)), plt.Line2D([], [], color=INK, ls="--", lw=1)]
    fig.legend(h, ["drilled, allowed", "drilled, forbidden", "PLA breach (obstacle or floor skin)", "route centreline"],
               loc="lower center", ncol=4, frameon=False, fontsize=9, labelcolor=INK2)
    fig.tight_layout(rect=(0, .03, 1, 1))
    fig.savefig(path, dpi=130)
    plt.close(fig)


def fig_compare(rows, path):
    parts = sorted({m["participant"] for m in rows}, key=lambda p: int(p[1:]))
    fig, axs = plt.subplots(3, 3, figsize=(11, 3 * (0.9 + 0.3 * len(parts))), facecolor="#fcfcfb")
    for ax, (k, title) in zip(axs.ravel(), COMPARE):
        for i, pt in enumerate(parts):
            a = next(r for r in rows if r["participant"] == pt and r["condition"] == "assistance")
            b = next(r for r in rows if r["participant"] == pt and r["condition"] == "no assistance")
            if a[k] is None or b[k] is None:
                ax.text(0, i, "  no recording", va="center", color=INK2, fontsize=8)
                continue
            ax.plot([b[k], a[k]], [i, i], color="#c9c8c2", lw=2, zorder=1, solid_capstyle="round")
            ax.scatter(b[k], i, s=70, color=COLORS["no assistance"], marker="s", edgecolor="#fcfcfb", lw=2, zorder=2)
            ax.scatter(a[k], i, s=80, color=COLORS["assistance"], marker="o", edgecolor="#fcfcfb", lw=2, zorder=2)
        ax.set_yticks(range(len(parts)), [f"{p} ({next(r['operator'] for r in rows if r['participant'] == p)})" for p in parts],
                      color=INK2, fontsize=9)
        ax.set_ylim(-.6, len(parts) - .4)
        ax.invert_yaxis()
        ax.set_xlim(left=0)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        ax.grid(axis="x", color="#e8e7e2", lw=.8)
        ax.set_axisbelow(True)
        style(ax)
    h = [plt.Line2D([], [], marker="o", ls="", color=COLORS["assistance"], ms=8),
         plt.Line2D([], [], marker="s", ls="", color=COLORS["no assistance"], ms=8)]
    fig.legend(h, ["assistance", "no assistance"], loc="lower center", ncol=2, frameon=False, fontsize=9, labelcolor=INK2)
    fig.tight_layout(rect=(0, .04, 1, 1))
    fig.savefig(path, dpi=130)
    plt.close(fig)


def fig_spots(spots, models, path):
    """All spots in the model frame: rows = condition, columns = route. v04 layout drawn, routes of every version dashed."""
    fig, axs = plt.subplots(2, 2, figsize=(9.5, 10.5), sharex=True, sharey=True, facecolor="#fcfcfb")
    for i, cond in enumerate(CONDITIONS):
        for j, route in enumerate(("left", "right")):
            ax = axs[i, j]
            draw_layout(ax, models["v04"]["obstacles"])
            for v, mod in models.items():
                c = route_centreline(mod["paths"], route)
                ax.plot(c[:, 0], c[:, 1], color="#b9b8b2", lw=1, ls="--", zorder=1)
            sel = [s for s in spots if s["condition"] == cond and s["route"] == route]
            for s in sel:
                big = np.sqrt(s["volume_uL"]) * 4
                if s["kind"] == "excursion":
                    ax.scatter(s["x_mm"], s["y_mm"], s=big, marker=MARKERS[s["participant"]], color="#e34948",
                               alpha=.55, edgecolor=INK, lw=.6, zorder=2)
                else:
                    ax.scatter(s["x_mm"], s["y_mm"], s=max(big, 25), marker="x", color=INK, lw=1.6, zorder=3)
            whos = sorted({(s["participant"], s["phantom"]) for s in sel} |
                          {(r["participant"], r["phantom"]) for r in STUDY if r["condition"] == cond and r["route"] == route})
            ax.set_title(f"{cond}, {route} route\n" + ", ".join(f"{p} {ph}" for p, ph in whos), fontsize=9, color=COLORS[cond])
            ax.set_xlim(0, 60)
            ax.set_ylim(15, 80)
            ax.set_aspect("equal")
            style(ax)
    for ax in axs[-1]:
        ax.set_xlabel("x (model mm)", color=INK2, fontsize=9)
    for ax in axs[:, 0]:
        ax.set_ylabel("y (model mm)", color=INK2, fontsize=9)
    h = [plt.Line2D([], [], marker=mk, ls="", color="#e34948", mec=INK, ms=8, alpha=.7) for mk in MARKERS.values()]
    h += [plt.Line2D([], [], marker="x", ls="", color=INK, ms=8, mew=1.6)]
    fig.legend(h, [f"excursion {p}" for p in MARKERS] + ["PLA breach"], loc="lower center", ncol=5, frameon=False,
               fontsize=9, labelcolor=INK2)
    fig.suptitle("Spots (size ~ volume); obstacles of v04, route centrelines of v01/v03/v04", fontsize=10, color=INK)
    fig.tight_layout(rect=(0, .04, 1, .97))
    fig.savefig(path, dpi=130)
    plt.close(fig)


def spot_tables(spots):
    """Markdown tables: spot counts/volumes by condition, by location and by obstacle."""
    L = []
    for kind, title in (("excursion", "Excursion spots (forbidden stone > %.1f mm past the wall, >= %g uL)" % (TOLERANCE_MM, SPOT_MIN_UL["excursion"])),
                        ("breach", "PLA breach spots (>= %g uL)" % SPOT_MIN_UL["breach"])):
        ks = [s for s in spots if s["kind"] == kind]
        L += [f"### {title}", "", "| | " + " | ".join(CONDITIONS) + " |", "|---|---|---|"]
        tot = lambda f: [sum(s["volume_uL"] for s in ks if s["condition"] == c and f(s)) for c in CONDITIONS]
        cnt = lambda f: [sum(1 for s in ks if s["condition"] == c and f(s)) for c in CONDITIONS]
        rowf = lambda name, f: L.append(f"| {name} | " + " | ".join(f"{n} ({v:.0f} uL)" for n, v in zip(cnt(f), tot(f))) + " |")
        rowf("all", lambda s: True)
        for p in sorted({s["participant"] for s in STUDY}, key=lambda p: int(p[1:])):
            rowf(p, lambda s, p=p: s["participant"] == p)
        rowf("left route", lambda s: s["route"] == "left")
        rowf("right route", lambda s: s["route"] == "right")
        rowf("at a corner", lambda s: s["where"].startswith("corner"))
        rowf("  inner side of the turn", lambda s: s["corner_side"] == "inner")
        rowf("  outer side of the turn", lambda s: s["corner_side"] == "outer")
        rowf("on a straight leg", lambda s: not s["where"].startswith("corner"))
        if kind == "breach":
            rowf("above obstacle tops", lambda s: s["depth"] == "above obstacle tops")
            rowf("in the obstacle layer", lambda s: s["depth"] == "obstacle layer")
        if kind == "excursion":
            for z in sorted({s["into"] for s in ks}):
                rowf(f"into: {z}", lambda s, z=z: s["into"] == z)
        if kind == "breach":
            rowf("floor skin", lambda s: s["hit"] == "floor skin")
            rowf("obstacle wall", lambda s: s["hit"] != "floor skin")
        L += [""]
        by = defaultdict(lambda: defaultdict(list))
        for s in ks:
            tag = f" {s['into'].replace('above obstacle ', 'over ')}" if kind == "excursion" else f" {s['hit']}"
            by[(s["route"], s["where"])][s["condition"]].append(f"{s['participant']} {s['volume_uL']:.0f}{tag}")
        if by:
            L += [f"{kind.capitalize()} spots by where they left the route (participant, uL, what they went into):", "",
                  "| route | place | " + " | ".join(CONDITIONS) + " |", "|---|---|---|---|"]
            # walk the route: entry leg (leg 1), corner 1, leg 2, corner 2, ..., exit leg
            def order(k):
                if k[1] == "entry leg":
                    return (k[0], 2)
                if k[1] == "exit leg":
                    return (k[0], 99)
                n = int(k[1].split()[-1])
                return (k[0], 2 * n + k[1].startswith("corner"))
            for k in sorted(by, key=order):
                L.append(f"| {k[0]} | {k[1]} | " + " | ".join(", ".join(by[k][c]) or "-" for c in CONDITIONS) + " |")
            L += [""]
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "experiments/pilot_study_analysis"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    models = {v: load_model(v) for v in sorted({s["version"] for s in STUDY} | {"v04"})}
    rows, maps, spots = [], {}, []
    for s in STUDY:
        m, u, sp = analyze(s, models[s["version"]])
        rows.append(m)
        maps[s["phantom"]] = u
        spots += sp
        print(f"[{m['participant']} {m['phantom']}] drilled {m['drilled_mL']:.2f} mL, forbidden {m['forbidden_mL']:.3f} mL, "
              f"excursion spots {m['excursion_spots']}, breach spots {m['breach_spots']}")

    with open(os.path.join(args.out, "metrics.json"), "w") as f:
        json.dump(rows, f, indent=2)
    keys = [k for k in rows[0] if k != "obstacle_breach_by_obstacle"]
    with open(os.path.join(args.out, "metrics.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    skeys = ["participant", "phantom", "operator", "condition", "route", "order", "version", "kind", "hit", "volume_uL",
             "where", "corner_side", "nearest_obstacle", "obstacle_dist_mm", "above_obstacle", "depth",
             "into", "x_mm", "y_mm", "z_mm", "z_min_mm", "exit_x_mm", "exit_y_mm", "excursion_max_mm"]
    with open(os.path.join(args.out, "spots.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, skeys)
        w.writeheader()
        w.writerows(spots)

    fmt = lambda v: "-" if v is None else f"{v:.3f}" if isinstance(v, float) else str(v)
    L = ["# Pilot study: assistance vs no assistance", "",
         f"n = {len({s['participant'] for s in STUDY})} participants, one phantom per condition: descriptive only, "
         "no significance tests. Routes per condition: " + "; ".join(
             f"{c} {sum(1 for s in STUDY if s['condition'] == c and s['route'] == 'left')} left, "
             f"{sum(1 for s in STUDY if s['condition'] == c and s['route'] == 'right')} right" for c in CONDITIONS) + ". "
         "Task time only where a recording exists.", "",
         "## Per phantom", "",
         "| Metric | " + " | ".join(f"{r['participant']} {r['phantom']} ({r['condition']}, {r['route']})" for r in rows) + " |",
         "|---|" + "---|" * len(rows)]
    for k in keys:
        if k in ("phantom", "operator", "condition", "route", "participant"):
            continue
        L.append(f"| {k} | " + " | ".join(fmt(r[k]) for r in rows) + " |")
    L += ["", "## By condition (mean over participants; paired difference assistance - no assistance)", "",
          "| Metric | assistance | no assistance | paired diff per participant |", "|---|---|---|---|"]
    for k, title in COMPARE:
        a = {r["participant"]: r[k] for r in rows if r["condition"] == "assistance"}
        b = {r["participant"]: r[k] for r in rows if r["condition"] == "no assistance"}
        ok = [p for p in a if a[p] is not None and b[p] is not None]
        if not ok:
            continue
        diffs = ", ".join(f"{p} {a[p] - b[p]:+.3g}" for p in sorted(ok))
        L.append(f"| {title} | {np.mean([a[p] for p in ok]):.3g} | {np.mean([b[p] for p in ok]):.3g} | {diffs} |")
    L += ["", "## Spots", "", "See spots.csv for every spot and pilot_spots.png for the map.", ""]
    L += spot_tables(spots)
    with open(os.path.join(args.out, "summary.md"), "w") as f:
        f.write("\n".join(L) + "\n")
    fig_maps(rows, maps, models, os.path.join(args.out, "pilot_drilled.png"))
    fig_compare(rows, os.path.join(args.out, "pilot_compare.png"))
    fig_spots(spots, models, os.path.join(args.out, "pilot_spots.png"))
    print(f"[done] {args.out}")


if __name__ == "__main__":
    main()
