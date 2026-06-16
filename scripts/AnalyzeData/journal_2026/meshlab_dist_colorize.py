"""
Batch: for each drill, measure sim-vs-real surface distance and colorize, in MeshLab.

For each pair:
  reference = P01_D{xx}_real_seg.stl   (loaded as layer 0)
  measured  = P01_D{xx}_sim_v2.stl     (loaded as layer 1, current)
Applies the two filters you ran by hand (Distance from Reference Mesh -> per-vertex
quality, then Colorize by vertex Quality) via a MeshLab .mlx script, and saves a
colored PLY (STL can't hold vertex color/quality).

Install once:  pip install pymeshlab
Run:           python meshlab_dist_colorize.py
"""

import os
import numpy as np
import pymeshlab as ml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Must match OUTPUT_DIR in slicer_crop_export.py (where Stage 1 wrote the STLs).
STL_DIR = "/home/juan95/research/discovery_grant/saint_2026/experiments/experiment_2026-06-03/experiment_2026-06-03_accuracy/meshes"
OUT_DIR = os.path.join(STL_DIR, "meshlab_colorized")
MLX     = os.path.join(SCRIPT_DIR, "calculate_dist_and_colorized.mlx")   # lives next to this script
DRILLS  = ["09", "10", "11", "12"]

os.makedirs(OUT_DIR, exist_ok=True)

for xx in DRILLS:
    real = os.path.join(STL_DIR, f"P01_D{xx}_real_seg.stl")
    sim  = os.path.join(STL_DIR, f"P01_D{xx}_sim_v2.stl")
    out  = os.path.join(OUT_DIR, f"P01_D{xx}_sim_v2_dist.ply")

    ms = ml.MeshSet()
    ms.load_new_mesh(real)            # layer 0 -> reference
    ms.load_new_mesh(sim)             # layer 1 -> measured
    ms.set_current_mesh(1)            # filters act on / are sampled from the sim mesh

    ms.load_filter_script(MLX)
    ms.apply_filter_script()

    # The distance lives in vertex quality. Read it back to (a) confirm it exists
    # and (b) report the same stats MeshLab prints (min/max/mean/RMS).
    q = ms.current_mesh().vertex_scalar_array()
    if q.size == 0:
        raise RuntimeError(f"D{xx}: no vertex quality found -- distance filter did not run")
    rms = float(np.sqrt(np.mean(q ** 2)))
    print(f"D{xx} distance(mm): min={q.min():.4f} max={q.max():.4f} "
          f"mean={q.mean():.4f} RMS={rms:.4f}  (n={q.size})")

    # The scalar/quality save flag was renamed across pymeshlab versions; use whichever exists.
    save_kwargs = dict(save_vertex_color=True, binary=False)
    for scalar_flag in ("save_vertex_scalar", "save_vertex_quality"):
        try:
            ms.save_current_mesh(out, **save_kwargs, **{scalar_flag: True})
            break
        except (TypeError, ml.PyMeshLabException):
            continue
    else:
        raise RuntimeError(f"D{xx}: could not save with a vertex scalar/quality flag")
    print(f"saved {out}")

print(f"\nDone. {len(DRILLS)} colorized meshes in {OUT_DIR}")
