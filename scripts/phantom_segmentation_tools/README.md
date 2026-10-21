# Phantom segmentation tools

Register the Saint Phantom CAD model (`openscad_models/saint_phantom`) to a CT
of the printed phantom, then segment the box, the dental stone, and the allowed /
forbidden stone for each navigation route.

| File | Purpose |
|---|---|
| `register_cad.py` | The pipeline, one run per scan |
| `load_in_slicer.py` | Loads a run's outputs into 3D Slicer (optional) |

## Running

Environment: conda `saint-env` (NumPy, SciPy, SimpleITK, VTK, pynrrd, matplotlib).
It runs outside Slicer.

```bash
PY=/opt/miniconda3/envs/saint-env/bin/python
STL=~/research/openscad_models/saint_phantom/stl
DATA=~/research/saint_project/phantoms/Loop-x

$PY register_cad.py --version v01 --stl-dir $STL/v01 \
    --ct $DATA/processed/2026-08-04_PL07_D00 \
    --name PL07_D00 --out $DATA/cad-registration/PL07_D00
```

Options:
- `--ct-fiducials clicks.mrk.json`: use divots you clicked in Slicer (M-1…M-9)
  instead of automatic detection. The file's `coordinateSystem` is read and RAS is
  converted to LPS.
- `--thresholds AIR_PLA PLA_STONE`: override the histogram thresholds.

`--version` must match `version.json` and `paths.json` in `--stl-dir`. The STL
sha256 values are checked against those files, and their commits are recorded
in the report.

## Method

1. **CT** read in LPS physical space (DICOM folder or NRRD).
2. **Thresholds** from a 3-class Otsu of the in-FOV histogram (air / PLA / stone),
   because Loop-x values aren't calibrated HU and the scale differs between scans.
   See `qa/<name>_histogram.png`.
3. **Initial pose, automatic.** Principal axes of the phantom mask, the 4 proper
   rotations (never a reflection), each refined by ICP. The box outline alone
   can't separate the 180°-about-z pose (its ICP RMS is as good). The obstacle
   layout can: the chosen pose is the one whose obstacles coincide with the holes
   in the stone. The run aborts if the margin is < 0.3.
4. **Divots.** Each pocket is located by masked normalized cross-correlation of
   the local mesh geometry against the CT, within ±1.8 mm (xy) / ±1 mm (z) of its
   predicted position. Then a Kabsch fit (det = +1 enforced) and FRE per
   fiducial. Divots with NCC < 0.3 or a peak on the search edge are dropped from
   the fit. The report also gives the FRE a mirrored labelling would have.
5. **Refinement.** Point-to-plane ICP (Huber, normal-compatible matches) of the
   200 surface points onto the CT air/PLA iso-surface (level midway between the
   air and PLA modes), started from the fiducial fit. If ICP matches < 60 % of the
   points or moves a box corner > 2 mm, the fiducial fit is kept.
6. **Segments** on the CT grid (meshes voxelised at 0.2 mm in the model frame,
   then sampled):
   - `box` = registered box mesh (lattice infill filled) ∪ PLA-intensity voxels
     within 1 mm outside it, but not below the base's bottom plane, where the
     mounting plate/table touches.
   - `stone` = stone-intensity voxels in the cavity footprint, from the floor to
     3 mm above the rim (also over the wall above the rim), minus `box`.
     Components < 30 voxels are removed.
   - `<route>_allowed` = `stone` ∩ route region; `<route>_forbidden` = `stone` − allowed.

## Outputs (`--out`)

| File | Content |
|---|---|
| `<name>_ct.nrrd` | The CT |
| `<name>_all_combinations.seg.nrrd` | Slicer segmentation: `box`, `stone`, `left_allowed`, `left_forbidden`, `right_allowed`, `right_forbidden` (one layer each; allowed regions overlap) |
| `<name>_box_dental.seg.nrrd` | `box`, `stone` |
| `<name>_box_dental_left_path.seg.nrrd` | `box`, `left_allowed`, `left_forbidden` |
| `<name>_box_dental_right_path.seg.nrrd` | `box`, `right_allowed`, `right_forbidden` |
| `<name>_labels_<route>.nrrd` | Labelmap per route: 1 box, 2 forbidden, 3 allowed |
| `<name>_transform.json`, `<name>_model_to_ct_LPS.txt` | 4×4 **model → CT** (LPS): `x_ct = M x_model`; also its inverse and the RAS matrix for Slicer's Transforms module |
| `<name>_model_to_ct.h5` / `.tfm` | Same transform as an ITK file. ITK stores the resampling direction (CT point → model point), so in Slicer you **put model nodes under it** to move them into CT space |
| `meshes_in_ct/*.stl` | Box, obstacles and route regions already in CT space (LPS) |
| `<name>_fiducials_ct.mrk.json` | Divot centres found in the CT (LPS; FRE in each description) |
| `<name>_M.mrk.json` | Bottom of each divot pocket, M-1…M-9 (LPS): the CT divot centre moved by the mesh's opening-centre → pocket-bottom vector |
| `<name>_fiducials_model_in_ct.mrk.json` | Model fiducials mapped with the final transform |
| `<name>_report.json`, `<name>_report.md` | Thresholds, pose candidates, FRE, ICP RMS, volumes vs expected, provenance |
| `qa/*.png` | Histogram, divot crops, ICP residuals, overlays in the model frame, stone-top height map |

## Slicer

```bash
Slicer --python-script load_in_slicer.py --out <out> --name <name> [--stl-dir <stl/v01>]
```

or in Slicer's Python console set `OUT`, `NAME` (and optionally `STL_DIR`), then
`exec(open(".../load_in_slicer.py").read())`. Add `--check` to print the segment
volumes and verify the `.h5` transform direction without the GUI.

## Notes

- The stone/PLA boundary is assigned to `box`. CT blur spreads the bright stone
  up to about 1 mm into the registered mesh (about 3 mL of stone-intensity voxels).
  Those voxels count as `box`, so `stone` is about 3 mL below a pure-intensity
  count. None of them lies deeper than 1.5 mm, so no stone seeped into the infill.
- "Expected" allowed volumes in the report are the route region up to the
  stone-top level (99.5th percentile of stone z). The stone surface isn't flat,
  so treat them as approximate. See `qa/<name>_stone_top.png`.
- A run takes about 20 s.
