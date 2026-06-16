# Sim-vs-Real Segmentation Accuracy Analysis (Claude)

Two-stage pipeline that turns segmentations into cropped surface meshes and then
measures/colorizes the distance between the **simulated** and **real** drilling
results for patient P01, drills D09–D12.

```
3D Slicer scene                 $MESHES/                             $MESHES/meshlab_colorized/
(.mrb)            stage 1        P01_D09_real_seg.stl     stage 2     P01_D09_sim_v2_dist.ply
  segmentations  ──────────►     P01_D09_sim_v2.stl     ──────────►   P01_D10_sim_v2_dist.ply
  + ROI "R"     slicer_crop      ... (8 STLs total)    meshlab_dist   ... (4 PLYs total)
                _export.py                             _colorize.py
```

`$MESHES` is the shared data directory both stages use (Stage 1 writes STLs here,
Stage 2 reads them and writes PLYs into its `meshlab_colorized/` subfolder):

```
/home/juan95/research/discovery_grant/saint_2026/experiments/experiment_2026-06-03/experiment_2026-06-03_accuracy/meshes
```

It is set as `OUTPUT_DIR` in `slicer_crop_export.py` and `STL_DIR` in
`meshlab_dist_colorize.py` — **keep those two in sync** if you move the data.

- **Stage 1** runs *inside 3D Slicer* (5.8.1). Crops each segmentation to the ROI,
  cleans stray voxels from the sim meshes, and writes 8 STL files.
- **Stage 2** runs with *pymeshlab* (plain Python). For each drill it measures the
  per-vertex distance from the sim surface to the real surface and colorizes it,
  writing 4 colored PLY files.

Files in this folder:

| File | What it is |
|------|------------|
| `slicer_crop_export.py`            | Stage 1 — run inside 3D Slicer |
| `meshlab_dist_colorize.py`         | Stage 2 — run with pymeshlab |
| `calculate_dist_and_colorized.mlx` | MeshLab filter script used by Stage 2 |

---

## Prerequisites

- **3D Slicer 5.8.1** with the scene open (or a `.mrb` to load). The scene must contain:
  - segmentations named `P01_D{09..12}_real_seg` (each with a segment named `bone`)
  - segmentations named `P01_D{09..12}_sim_v2`
  - one ROI markup named `R` defining the crop box
- **pymeshlab** for Stage 2: `pip install pymeshlab`

---

## Stage 1 — crop + clean + export STL (in 3D Slicer)

What it does, per target (8 total = 4 real + 4 sim):
1. Looks up the segmentation node and picks the segment
   (`bone` for real; the only segment for sim).
2. **Sim only:** removes disconnected "flying voxel" islands smaller than
   `ISLAND_MIN_SIZE` voxels (default **200**).
3. Clips the segment's surface to the ROI box `R` (handles a rotated ROI; caps
   the cut so the STL stays watertight; real meshes are first baked into the
   D08/world frame via their transforms).
4. Writes `$MESHES/<node_name>.stl` and adds a `<node_name>_cropped`
   model to the scene so you can eyeball the result.

### Run it

Open **View → Python Console** in Slicer (scene already loaded), then:

```python
exec(open('/home/juan95/research/discovery_grant/volumetric_drilling/'
          'scripts/AnalyzeData/journal_2026/slicer_crop_export.py').read())
```

Or headless from a terminal (loads the scene itself):

```bash
Slicer --no-main-window --no-splash \
    --python-script scripts/AnalyzeData/journal_2026/slicer_crop_export.py \
    --scene /path/to/P01.mrb
```

Expect 8 `OK ...` lines. `FAIL ... empty mesh` means that segment did not overlap
the ROI. Output: 8 STL files in `$MESHES/`.

### Settings to tweak (top of `slicer_crop_export.py`)

| Variable | Default | Meaning |
|----------|---------|---------|
| `OUTPUT_DIR`       | `$MESHES` (the path above) | where STLs are written (Stage 2 reads here) |
| `ROI_NAME`         | `"R"`                 | name of the crop ROI markup |
| `DRILLS`           | `["09","10","11","12"]` | which drills to process |
| `ISLAND_MIN_SIZE`  | `200`                 | min island size in **voxels**; `0` disables cleanup |
| `ADD_MODELS_TO_SCENE` | `True`             | also add `*_cropped` models for inspection |

### Choosing `ISLAND_MIN_SIZE` (do this once in the GUI)

1. Segment Editor → enable the **Undo/Redo** checkbox; turn on **Show 3D**.
2. Select a sim segment → **Islands** effect → **Remove small islands**.
3. Set **Minimum size (voxels)**, **Apply**, look at the 3D view; **Ctrl+Z** to
   undo and retry. Pick the largest value that removes all specks but keeps the bone.
4. (Principled alternative) Islands → **Split islands to segments**, then run the
   **Segment Statistics** module and read each island's voxel count — pick a
   threshold between the specks and the bone.
5. Put that number in `ISLAND_MIN_SIZE` and re-run Stage 1.

> Note: *Remove small islands* deletes **every** component below the threshold. If a
> sim bone is legitimately in two pieces, keep the threshold below the smaller piece.

---

## Stage 2 — distance + colorize (pymeshlab)

What it does, per drill:
1. Loads `P01_D{xx}_real_seg.stl` as layer 0 (reference) and
   `P01_D{xx}_sim_v2.stl` as layer 1 (measured).
2. Applies `calculate_dist_and_colorized.mlx`:
   - **Distance from Reference Mesh** — per-vertex distance of sim → real, stored as vertex *quality*.
   - **Colorize by vertex Quality** — fixed range **0–2 mm**, Turbo colormap (same scale for all 4 drills, so they're comparable).
3. Saves `$MESHES/meshlab_colorized/P01_D{xx}_sim_v2_dist.ply`.

### Run it

```bash
pip install pymeshlab    # once
python scripts/AnalyzeData/journal_2026/meshlab_dist_colorize.py
```

Output: 4 colored PLY files in `$MESHES/meshlab_colorized/`. Open them in
MeshLab (or any PLY viewer) — color is baked into the vertices, and the raw distance
is kept in vertex *quality/scalar* (PLY `quality` property) so you can re-colormap later
without recomputing. (pymeshlab renamed "quality" to "scalar" across versions; the script
handles both the read-back, `vertex_scalar_array()`, and the save flag automatically.)

For each drill the script also prints the distance stats it read back from the mesh,
e.g. `D09 distance(mm): min=0.0000 max=3.5272 mean=0.6619 RMS=0.9603 (n=12649)` —
this doubles as a check that the quality field is actually present before saving.

### Settings to tweak (top of `meshlab_dist_colorize.py`)

| Variable | Default | Meaning |
|----------|---------|---------|
| `STL_DIR` | `$MESHES` (the path above) | where Stage 1 wrote the STLs |
| `OUT_DIR` | `$MESHES/meshlab_colorized` | where colored PLYs go |
| `MLX`     | `calculate_dist_and_colorized.mlx` (next to the script) | the filter script |
| `DRILLS`  | `["09","10","11","12"]` | which drills to process |

To change the distance/color behavior (signed vs unsigned distance, color range,
colormap), edit `calculate_dist_and_colorized.mlx` — easiest is to redo it once in the
MeshLab GUI (**Filters → Show current filter script → Save Script**) and overwrite the file.

---

## Important notes

- **STL cannot store color or quality** — that's why Stage 2 outputs **PLY**, not STL.
- **Layer order matters in Stage 2.** Real must load before sim so the `.mlx`'s
  `RefMesh=0` / `MeasureMesh=1` line up. The script already loads them in that order.
- The whole pipeline is keyed off the `P01_D{xx}_..` naming. For other patients/drills,
  adjust `DRILLS` (and the name templates in the scripts) in both stages.
