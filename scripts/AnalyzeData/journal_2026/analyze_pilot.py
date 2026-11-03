"""
Assistance vs no-assistance metrics for the 2026-10-14 pilot (phantoms PL09-PL12).

Reads the outputs of phantom_segmentation_tools/register_cad.py (each D01 run made
with --reference) and the recordings' session tags. All metrics are measured on the
D01 CT grid, against the route the operator was assigned.

Run (conda env saint-env):
    python analyze_pilot.py [--out <folder>]

Writes metrics.csv, metrics.json, summary.md and pilot_drilled.png / pilot_compare.png.
"""

import argparse
import csv
import json
import os
import sys

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
STL = os.path.expanduser("~/research/openscad_models/saint_phantom/stl/v01")

# Recording = the drilling session; juan-assistance also has a 16 s false start (20261014_175203)
STUDY = [
    {"phantom": "PL09", "operator": "Juan", "condition": "no assistance", "route": "right", "order": 1,
     "recording": "experiment_2026-10-14-juan-no-assit/recordings/20261014_173959"},
    {"phantom": "PL10", "operator": "Juan", "condition": "assistance", "route": "left", "order": 2,
     "recording": "experiment_2026-10-14-juan-assistance/recordings/20261014_175256"},
    {"phantom": "PL11", "operator": "Brendan", "condition": "assistance", "route": "right", "order": 1,
     "recording": "experiment_2026-10-14-t1-brendan-assist/recordings/20261014_184736"},
    {"phantom": "PL12", "operator": "Brendan", "condition": "no assistance", "route": "left", "order": 2,
     "recording": "experiment_2026-10-14-t2-brendan-no-assist/recordings/20261014_190122"},
]

OBSTACLE_NAMES = "ABCDEF"     # v01 has no obstacle G; same order as obstacles_xy in paths.json
OBSTACLE_MARGIN = 0.6         # mm, same as the "obstacle" class in register_cad.py
TOLERANCE_MM = 0.5            # forbidden stone deeper than this past the route wall (about FRE + 1 voxel)
COMMON_STONE_LEVEL = 750.0    # sensitivity check: one PLA|stone level for every scan
NOISE_FAR_MM = 3.0            # PLA loss this far from the channel can only be scan-to-scan noise
BREACH_NEAR_MM = 1.5          # PLA loss counts as a breach only this close to the channel: buried infill flickers
FLOOR_SKIN_MM = 1.0           # solid skin on top of the base; the lattice under it flickers and isn't counted
COVERAGE_MM = 1.5             # a centreline point is drilled if the channel is within this distance

COLORS = {"assistance": "#2a78d6", "no assistance": "#eb6834"}
INK, INK2 = "#0b0b0b", "#52514e"


def load_segments(path):
    arr, h = nrrd.read(path)
    out = {}
    for i in range(arr.shape[0]):
        # file is [seg, i, j, k]; CT arrays are [k, j, i]
        out[h[f"Segment{i}_Name"]] = arr[i].transpose(2, 1, 0).astype(bool)
    return out


def session_seconds(rec):
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


def analyze(s, paths, grid, occ_route, obstacles):
    p, r = s["phantom"], s["route"]
    n0, n1 = f"{p}_D00", f"{p}_D01"
    d0, d1 = os.path.join(REG, n0), os.path.join(REG, n1)
    with open(os.path.join(d0, f"{n0}_report.json")) as f:
        rep0 = json.load(f)
    with open(os.path.join(d1, f"{n1}_report.json")) as f:
        rep1 = json.load(f)
    img1, img0 = sitk.ReadImage(os.path.join(d1, f"{n1}_ct.nrrd")), sitk.ReadImage(os.path.join(d0, f"{n0}_ct.nrrd"))
    v1 = sitk.GetArrayFromImage(img1).astype(np.float32)
    a0 = sitk.GetArrayFromImage(img0).astype(np.float32)
    g1, g0 = rc.CTGeom(img1), rc.CTGeom(img0)
    M1, M0 = np.loadtxt(os.path.join(d1, f"{n1}_model_to_ct_LPS.txt")), np.loadtxt(os.path.join(d0, f"{n0}_model_to_ct_LPS.txt"))
    shape = v1.shape
    pts = rc.apply(rc.inv(M1), g1.all_centres())
    v0 = rc.sample_ct(a0, g0, rc.apply(M0, pts)).reshape(shape)
    xyz = pts.reshape(shape + (3,))
    vv = float(np.prod(g1.spacing))   # mL per 1000: mm^3 per voxel
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

    m = {k: s[k] for k in ("phantom", "operator", "condition", "route", "order")}
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
    m["floor_skin_noise_expected_voxels"] = float((lost & skin & far).sum() / (skin & far).sum() * (skin & near).sum())
    m["channel_bottom_z_mm"] = float(np.percentile(z[drilled], 0.5))
    m["box_damage_spots_uL"] = [round(b["volume_uL"], 1) for b in rep1["pla_damage"]["blobs"] if b["warning"]]

    # sensitivity: same stone level in both scans, independent of the per-scan thresholds
    zone = (xy[..., 0] > 5) & (xy[..., 0] < 55) & (xy[..., 1] > 22) & (xy[..., 1] < 72) & (xyz[..., 2] >= z_floor) & ~box
    common = ndi.binary_opening((v0 > COMMON_STONE_LEVEL) & (v1 <= COMMON_STONE_LEVEL) & zone)
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
    m["removal_mL_per_min"] = m["drilled_mL"] / (m["task_seconds"] / 60)

    x, y = np.meshgrid(np.arange(0, 60, .25), np.arange(15, 80, .25))
    maps = {}
    for key, mask in (("good", good), ("bad", bad), ("damage", lost & near & obs_any)):
        idx = np.argwhere(mask)
        u = np.zeros(x.shape, bool)
        if len(idx):
            q = xyz[mask]
            ix, iy = ((q[:, 0]) / .25).astype(int), ((q[:, 1] - 15) / .25).astype(int)
            ok = (ix >= 0) & (ix < x.shape[1]) & (iy >= 0) & (iy < x.shape[0])
            u[iy[ok], ix[ok]] = True
            u = ndi.binary_closing(u, iterations=2)
        maps[key] = u
    return m, maps


COMPARE = [("forbidden_mL", "Forbidden stone (mL)"), ("excursion_max_mm", "Max excursion (mm)"),
           ("obstacle_breach_voxels", "Obstacle voxels breached"), ("route_completion_pct", "Route completed (%)"),
           ("route_dice", "Route overlap (Dice)"), ("task_seconds", "Task time (s)")]


def fig_maps(rows, maps, obstacles, paths, path):
    fig, axs = plt.subplots(1, 4, figsize=(14, 5.2), sharey=True, facecolor="#fcfcfb")
    for ax, m in zip(axs, rows):
        u = maps[m["phantom"]]
        im = np.ones(u["good"].shape + (3,))
        im[u["good"]] = (0.75, 0.80, 0.83)
        im[u["bad"]] = matplotlib.colors.to_rgb("#e34948")
        im[u["damage"]] = (0.10, 0.10, 0.10)
        ax.imshow(im, origin="lower", extent=(0, 60, 15, 80))
        for name, (x0, y0, x1, y1) in obstacles.items():
            ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec=INK2, lw=1))
            ax.text(x0 + 1, y0 + 1, name, color=INK2, fontsize=8)
        c = route_centreline(paths, m["route"])
        ax.plot(c[:, 0], c[:, 1], color=INK, lw=1, ls="--")
        ax.set_title(f"{m['phantom']}  {m['operator']}, {m['condition']}\n{m['route']} route", fontsize=10, color=INK)
        ax.set_xlabel("x (model mm)", color=INK2, fontsize=9)
        ax.tick_params(colors=INK2, labelsize=8)
        for sp in ax.spines.values():
            sp.set_visible(False)
    axs[0].set_ylabel("y (model mm)", color=INK2, fontsize=9)
    h = [plt.Rectangle((0, 0), 1, 1, fc=(0.75, 0.80, 0.83)), plt.Rectangle((0, 0), 1, 1, fc="#e34948"),
         plt.Rectangle((0, 0), 1, 1, fc=(0.1, 0.1, 0.1)), plt.Line2D([], [], color=INK, ls="--", lw=1)]
    fig.legend(h, ["drilled, allowed", "drilled, forbidden", "PLA breach", "route centreline"], loc="lower center",
               ncol=4, frameon=False, fontsize=9, labelcolor=INK2)
    fig.tight_layout(rect=(0, .06, 1, 1))
    fig.savefig(path, dpi=130)


def fig_compare(rows, path):
    fig, axs = plt.subplots(2, 3, figsize=(11, 6), facecolor="#fcfcfb")
    ops = ["Juan", "Brendan"]
    for ax, (k, title) in zip(axs.ravel(), COMPARE):
        for i, op in enumerate(ops):
            a = next(r for r in rows if r["operator"] == op and r["condition"] == "assistance")
            b = next(r for r in rows if r["operator"] == op and r["condition"] == "no assistance")
            ax.plot([b[k], a[k]], [i, i], color="#c9c8c2", lw=2, zorder=1, solid_capstyle="round")
            ax.scatter(b[k], i, s=70, color=COLORS["no assistance"], marker="s", edgecolor="#fcfcfb", lw=2, zorder=2)
            ax.scatter(a[k], i, s=80, color=COLORS["assistance"], marker="o", edgecolor="#fcfcfb", lw=2, zorder=2)
        ax.set_yticks(range(len(ops)), ops, color=INK2, fontsize=9)
        ax.set_ylim(-.6, 1.6)
        ax.set_xlim(left=0)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        ax.grid(axis="x", color="#e8e7e2", lw=.8)
        ax.set_axisbelow(True)
        ax.tick_params(colors=INK2, labelsize=8, length=0)
        for sp in ax.spines.values():
            sp.set_visible(False)
    h = [plt.Line2D([], [], marker="o", ls="", color=COLORS["assistance"], ms=8),
         plt.Line2D([], [], marker="s", ls="", color=COLORS["no assistance"], ms=8)]
    fig.legend(h, ["assistance", "no assistance"], loc="lower center", ncol=2, frameon=False, fontsize=9, labelcolor=INK2)
    fig.tight_layout(rect=(0, .05, 1, 1))
    fig.savefig(path, dpi=130)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(EXP, "analysis"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    with open(os.path.join(STL, "paths.json")) as f:
        paths = json.load(f)
    obstacles = dict(zip(OBSTACLE_NAMES, paths["meshes"]["obstacles"]["obstacles_xy"]))
    pd_box = rc.read_stl(os.path.join(STL, "saint_phantom_v01.stl"))
    b = np.array(pd_box.GetBounds()).reshape(3, 2)
    grid = rc.ModelGrid(b[:, 0] - 3, b[:, 1] + [3, 3, 6], rc.MODEL_STEP)
    occ_route = {r: grid.voxelise(rc.read_stl(os.path.join(STL, f"saint_phantom_v01_path_{r}.stl"))) for r in rc.ROUTES}

    rows, maps = [], {}
    for s in STUDY:
        m, u = analyze(s, paths, grid, occ_route, obstacles)
        rows.append(m)
        maps[s["phantom"]] = u
        print(f"[{m['phantom']}] drilled {m['drilled_mL']:.2f} mL, forbidden {m['forbidden_mL']:.3f} mL, "
              f"obstacle voxels {m['obstacle_breach_voxels']}, floor skin voxels {m['floor_skin_lost_voxels']}")

    with open(os.path.join(args.out, "metrics.json"), "w") as f:
        json.dump(rows, f, indent=2)
    keys = [k for k in rows[0] if k != "obstacle_breach_by_obstacle"]
    with open(os.path.join(args.out, "metrics.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    L = ["# Pilot 2026-10-14: assistance vs no assistance", "",
         "n = 2 operators, one phantom per condition: descriptive only, no significance tests.", "",
         "| Metric | " + " | ".join(f"{r['phantom']} {r['operator']} ({r['condition']}, {r['route']})" for r in rows) + " |",
         "|---|" + "---|" * len(rows)]
    for k in keys:
        if k in ("phantom", "operator", "condition", "route"):
            continue
        fmt = lambda v: f"{v:.3f}" if isinstance(v, float) else str(v)
        L.append(f"| {k} | " + " | ".join(fmt(r[k]) for r in rows) + " |")
    with open(os.path.join(args.out, "summary.md"), "w") as f:
        f.write("\n".join(L) + "\n")
    fig_maps(rows, maps, obstacles, paths, os.path.join(args.out, "pilot_drilled.png"))
    fig_compare(rows, os.path.join(args.out, "pilot_compare.png"))
    print(f"[done] {args.out}")


if __name__ == "__main__":
    main()
