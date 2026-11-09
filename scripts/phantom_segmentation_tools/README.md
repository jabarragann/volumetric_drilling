# Phantom segmentation tools

Register the Saint Phantom CAD model (`openscad_models/saint_phantom`) to a CT
of the printed phantom, align the CT with the box, then segment the box, the dental
stone, and the allowed / forbidden stone for each navigation route.

## Pipeline and folders

```
raw/<export>/Series..   ──split_phantoms.py──▶  processed/<date>_<PL>_<Dxx>/      one DICOM series per phantom,
 (whole plate, Loop-x)                                                         plain crops: NOT aligned
                        ──register_cad.py───▶  cad-registration/<PL>_<Dxx>/      registered, box tilt REMOVED
                                                                               (scanner frame kept), cropped;
                                                                               segmentations
                        ──copy by hand──────▶  organized_phantoms/<PL>_<Dxx>/    copies of the files used in
                                                                               experiments (see HOW_TO_RUN.md)
```

`register_cad.py` registers on the original scanner grid (best accuracy), then
removes the box's small tilt (typically ~2°) relative to the patient axes, keeping the
scanner's coordinate frame and axis directions: in Slicer the stone normal still points
to patient left, the 3-divot end anterior, and the sagittal view is a straight top-down
view of the box. It segments on that grid and crops it to the box segmentation plus 5
voxels in x/y and 20 voxels along the box normal (the box is centred). `--no-align`
turns this off.

> [!IMPORTANT]
> **Pre-drilling and post-drilling scans need different flags.**
>
> | Scan | Flags | Adds |
> |---|---|---|
> | Before drilling (`D00`) | the base flags only | registration and segments |
> | After drilling (`D01`, …) | the base flags **+ `--reference <D00 output folder>`** (optionally `--strict`) | drilled-stone segments and the **PLA damage warning** |
>
> Run the pre-drilling scan first; its output folder is the reference for the
> post-drilling run. Without `--reference` a post-drilling scan still registers
> and segments the remaining stone, but it gets no drilled segments and no damage check.
> If a run without `--reference` finds ≥ 0.5 mL of empty space in the stone
> (`EMPTY_WARN_ML`; 0 mL in intact scans, about 2 mL after drilling), it prints a
> warning that the scan looks drilled.

```bash
PY=/opt/miniconda3/envs/saint-env/bin/python
STL=~/research/openscad_models/saint_phantom/stl
DATA=~/research/saint_project/phantoms/Loop-x

# 1. before drilling
$PY register_cad.py --version v01 --stl-dir $STL/v01 \
    --ct $DATA/processed/2026-08-04_PL07_D00 \
    --name PL07_D00 --out $DATA/cad-registration/PL07_D00

# 2. after drilling: same flags + --reference to the run above
$PY register_cad.py --version v01 --stl-dir $STL/v01 \
    --ct $DATA/processed/2026-09-17_PL07_D01 \
    --name PL07_D01 --out $DATA/cad-registration/PL07_D01 \
    --reference $DATA/cad-registration/PL07_D00
```

| File | Purpose |
|---|---|
| `register_cad.py` | The pipeline, one run per scan |
| `load_in_slicer.py` | Loads a run's outputs into 3D Slicer (optional) |
| `split_phantoms.py` | Splits a scan of several phantoms on one plate (any ROWS × COLS grid) into one DICOM series per phantom (run first) |
| `modify_dicom_info.py` | Rewrites `PatientName` and `PatientID` in a DICOM folder (optional) |

## Arguments

Environment: conda `saint-env` (NumPy, SciPy, SimpleITK, VTK, pynrrd, matplotlib).
It runs outside Slicer. A run takes about 20–40 s.

| Argument | Required | Meaning |
|---|---|---|
| `--version` | yes | Phantom version, e.g. `v01`. Must match `version.json` and `paths.json` in `--stl-dir` |
| `--stl-dir` | yes | `stl/<version>/` folder of the saint_phantom repo. STL sha256 values are checked against its records, and its commits are recorded in the report |
| `--ct` | yes | DICOM folder (one series) or a volume file (`.nrrd`, `.nii`, …) |
| `--name` | yes | Scan name: prefix of every output file and `PatientName` in the segmentations |
| `--out` | yes | Output folder (created if missing; earlier files are overwritten) |
| `--reference DIR` | post-drilling | Output folder of the same phantom's pre-drilling run. Must be the same `--version`, and must not itself have been run with `--reference`. A reference whose stone doesn't match this scan is rejected (exit code 3) |
| `--same-ncc-min X` | no | With `--reference`: minimum stone CT correlation of the same-phantom check (default 0.85). Scans from different sessions correlate less (the stone dries): PL15/PL17 D01 (2026-11-03) vs D00 (2026-10-23) gave 0.76–0.77 against 0.42–0.66 for the other phantoms. Lower it (0.7 was used) only after running the scan against every candidate reference and seeing a clear best match |
| `--strict` | no | With `--reference`: exit with code 2 when PLA damage is found (for batch runs) |
| `--no-icp` | no | Keep the fiducial fit as the final transform. ICP is still run and reported. Use it when ICP tilts the pose: fiducial distance after ICP ≥ 0.5 mm, RMS not improved, and the `--reference` check fails only because of this scan |
| `--ct-fiducials FILE` | no | Divots clicked in Slicer (M-1…M-9) instead of automatic detection. `coordinateSystem` is read; RAS is converted to LPS |
| `--thresholds AIR_PLA PLA_STONE` | no | Override the histogram thresholds. Also works when the histogram has no stone peak (the stone mode is then inferred from PLA\|stone) |
| `--divot-margin-min M` | no | Minimum divot-contrast margin of the chosen pose over the next one (default 0.3). Lower it (e.g. 0.1) only when the obstacle check agrees with a margin ≥ 0.5 and the FRE is ~0.2 mm; otherwise click the divots (`--ct-fiducials`) |
| `--pca-erode N` | no | Erode the phantom mask by N voxels before the principal axes (initial pose only). For tiles that are mostly mounting plate (e.g. the bottom row of a scan with an empty lower part), where every pose candidate matches < 60 % of the surface points. 8 worked for PL30 |
| `--no-align` | no | Skip the align-and-crop step: segment and write the CT on the scanner grid (the behaviour before 2026-11) |
| `--margin-xy N`, `--margin-z N` | no | Voxels kept around the box segmentation in the aligned crop (defaults 5 and 20, on each side) |
| `--spacing MM` | no | Voxel size of the aligned CT (default: the CT's smallest spacing, 0.35 mm on the Loop-x) |

## Method

1. **CT** read in LPS physical space (DICOM folder or NRRD).
2. **Thresholds.** Loop-x values aren't calibrated HU and the scale differs
   between scans, so each scan gets its own: air|PLA from a 3-class Otsu of the
   in-FOV histogram, and PLA|stone halfway between the PLA and stone peaks (the
   stone peak is the highest-intensity prominent peak). The midpoint rule
   matters after drilling: the channel walls add many partial-volume voxels
   between PLA and stone, and Otsu's upper threshold would land among them.
   See `qa/<name>_histogram.png`.
3. **Initial pose, automatic.** Principal axes of the phantom mask, the 4 proper
   rotations (never a reflection), each refined by ICP. The box outline alone
   can't separate the 180°-about-z pose (its ICP RMS is as good). Two independent
   checks do, and they must agree:
   - **divot pockets** (decides): CT contrast between the pocket centre and the PLA
     beside it, for each divot. The base has 3 divots at one end and 2 at the
     other, so the rotated pose finds only the 4 rim pockets. Drilling can't
     affect this. Margin must be ≥ 0.3 (`--divot-margin-min`).
   - **obstacle cores** (confirms): stone should fill the free space between
     obstacles and not the obstacles, scored on their interiors (1 mm in from
     every side). Drilling lowers this margin (0.3–0.4 after drilling, about 0.8
     before) but not its sign.
4. **Divots.** Each pocket is located by masked normalized cross-correlation of
   the local mesh geometry against the CT, within ±1.8 mm (xy) / ±1 mm (z) of its
   predicted position. Then a Kabsch fit (det = +1 enforced) and FRE per
   fiducial. Divots with NCC < 0.3 or a peak on the search edge are dropped from
   the fit. The report also gives the FRE a mirrored labelling would have.
5. **Refinement.** Point-to-plane ICP (Huber, normal-compatible matches) of the
   200 surface points onto the CT air/PLA iso-surface (level midway between the
   air and PLA modes), started from the fiducial fit. If ICP matches < 60 % of the
   points or moves a box corner > 2 mm, the fiducial fit is kept.
6. **Align** (skipped with `--no-align`). Each model axis is snapped to the nearest
   patient axis (a signed permutation P, e.g. model z → +L, y → +P, x → −S for the
   2026-11-06 scan); the remaining rotation R·Pᵀ is the box's tilt. The CT is resampled
   (linear interpolation, values rounded to integers) by that tilt about the box
   centre, onto a grid with the scanner's own direction matrix. The box centre keeps
   its scanner coordinates, other points move by at most ~1.5 mm (tilt × distance from
   the centre), and the box edges now run along the voxel axes. Model → CT becomes
   P plus a translation. The registration to the scanner CT is kept in
   `<name>_model_to_scanner_LPS.txt`, and the tilt correction (aligned → scanner) in
   `<name>_aligned_to_scanner_LPS.txt`. All later steps run on this grid. A warning is
   printed if the box is tilted so far (> ~25°) that the snapped orientation is unclear.
7. **Segments** on the CT grid (meshes voxelised at 0.2 mm in the model frame,
   then sampled):
   - `box` = registered box mesh (lattice infill filled) ∪ PLA-intensity voxels
     within 1 mm outside it, but not below the base's bottom plane, where the
     mounting plate/table touches. With `--reference`, PLA damage is removed from it.
   - `stone` = stone-intensity voxels in the cavity footprint, from the floor to
     3 mm above the rim (also over the wall above the rim), minus `box`.
     Components < 30 voxels are removed.
   - `<route>_allowed` = `stone` ∩ route region; `<route>_forbidden` = `stone` − allowed.
8. **After drilling (`--reference`).** Both runs are registered to the CAD, so
   the pre-drilling CT is mapped onto this scan's grid through the model frame
   (no image-to-image registration), and each scan keeps its own thresholds.
   - **Same-phantom check:** the boxes are printed identically, but every stone
     pour differs (fill level, surface, bubbles). Stone more than 3 mm from the
     drilled channel and 1 mm from the box must match between the reference and
     this scan: Dice ≥ 0.97 (`SAME_DICE_MIN`) and CT intensity correlation
     NCC ≥ 0.85 (`SAME_NCC_MIN`). Otherwise the run prints an error banner and
     exits with code 3 before writing the segmentations. Measured on PL07/PL08:
     same phantom Dice 0.987–0.990, NCC 0.91–0.93; swapped references Dice
     0.93–0.96, NCC 0.67–0.75. The values are in `report.json` under
     `reference.same_phantom_check`.
   - `drilled` = stone in the reference, not stone now (opened, components ≥ 30
     voxels); `<route>_drilled_allowed` = `drilled` ∩ route region,
     `<route>_drilled_forbidden` = `drilled` − allowed.
   - **PLA damage:** PLA inside the CAD mesh in the reference that is air now
     (one material level for both scans, from the reference),
     *and touching the drilled channel*. Requiring contact with the channel
     removes the scan-to-scan flicker of the lattice infill, which otherwise gives
     hundreds of tiny "lost" blobs across the box. Fragments within ~1 mm are
     grouped into one spot. A spot of ≥ 2 µL (`DAMAGE_MIN_UL`) raises the warning:
     a banner in the terminal, a warning box at the top of `report.md`,
     `pla_damage` in `report.json`, the `box_damage` segment and
     `qa/<name>_damage.png` (before/after crops of each spot). Smaller contacts
     are listed in the report without a warning.
9. **Crop** (with 6). The aligned grid is cut to the bounding box of the `box`
   segment plus `--margin-xy` voxels in x and y and `--margin-z` voxels in z, the same
   on both sides, so the box is centred and the empty space is the same for every
   scan. The volume size still varies by a voxel or two between scans, because it
   follows the segmentation. The margins actually left are in `report.json` under
   `alignment.margins_voxels`; a warning is raised if any segment voxel falls outside
   the crop.

## Outputs (`--out`)

| File | Content |
|---|---|
| `<name>_ct.nrrd` | The CT. By default with the box tilt removed and cropped (scanner frame and axis directions kept); with `--no-align` the scanner grid |
| `<name>_all_combinations.seg.nrrd` | Slicer segmentation: `box`, `stone`, `left_allowed`, `left_forbidden`, `right_allowed`, `right_forbidden` (one layer each; allowed regions overlap). With `--reference` also `drilled`, `<route>_drilled_allowed`, `<route>_drilled_forbidden`, `box_damage` |
| `<name>_box_dental.seg.nrrd` | `box`, `stone` (+ `drilled`, `box_damage` with `--reference`) |
| `<name>_box_dental_left_path.seg.nrrd` | `box`, `left_allowed`, `left_forbidden` (+ `left_drilled_allowed`, `left_drilled_forbidden`, `box_damage` with `--reference`) |
| `<name>_box_dental_right_path.seg.nrrd` | `box`, `right_allowed`, `right_forbidden` (+ the right-route equivalents with `--reference`) |
| `<name>_labels_<route>.nrrd` | Labelmap per route: 1 box, 2 forbidden, 3 allowed; with `--reference` also 4 drilled forbidden, 5 drilled allowed, 6 PLA damage |
| `<name>_transform.json`, `<name>_model_to_ct_LPS.txt` | 4×4 **model → CT** (LPS): `x_ct = M x_model`; also its inverse and the RAS matrix for Slicer's Transforms module. With alignment, an axis permutation plus translation |
| `<name>_model_to_scanner_LPS.txt` | 4×4 model → **original scanner CT** (the `processed/` DICOM), i.e. the registration itself |
| `<name>_aligned_to_scanner_LPS.txt` | 4×4 aligned CT → original scanner CT: the tilt correction, a small rotation about the box centre (aligned runs only) |
| `<name>_model_to_ct.h5` / `.tfm` | Same transform as an ITK file. ITK stores the resampling direction (CT point → model point), so in Slicer you **put model nodes under it** to move them into CT space |
| `meshes_in_ct/*.stl` | Box, obstacles and route regions already in CT space (LPS) |
| `<name>_fiducials_ct.mrk.json` | Divot centres found in the CT (LPS; FRE in each description) |
| `<name>_M.mrk.json` | Bottom of each divot pocket, M-1…M-9 (LPS): the CT divot centre moved by the mesh's opening-centre → pocket-bottom vector |
| `<name>_fiducials_model_in_ct.mrk.json` | Model fiducials mapped with the final transform |
| `<name>_report.json`, `<name>_report.md` | Thresholds, pose candidates, FRE, ICP RMS, volumes vs expected, provenance; with `--reference` also drilled volumes, PLA damage spots and the reference → this-scan transform |
| `qa/*.png` | Histogram, divot crops, ICP residuals, overlays in the model frame, stone-top height map; with `--reference` also `*_drilled.png` and, if damage is found, `*_damage.png` |

## Slicer

```bash
Slicer --python-script load_in_slicer.py --out <out> --name <name> [--stl-dir <stl/v01>]
```

or in Slicer's Python console set `OUT`, `NAME` (and optionally `STL_DIR`), then
`exec(open(".../load_in_slicer.py").read())`. Add `--check` to print the segment
volumes and verify the `.h5` transform direction without the GUI.

## Notes

- Aligned outputs stay in scanner coordinates (minus the tilt). To put a point of the
  aligned CT, its markups or segmentations back on the `processed/` DICOM, apply
  `<name>_aligned_to_scanner_LPS.txt`.
- `--reference` works between aligned and `--no-align` runs in any combination: the
  reference CT is sampled through the model frame with its own transform.
- The crop margins are per voxel axis: the axis along the box normal gets
  `--margin-z`, the other two `--margin-xy`; `report.json` → `alignment.margins_voxels`
  lists them with the model axis each one carries.
- v02 prints (PL13, PL14): the outer shell of the box is 0.3–1.1 mm larger than the
  CAD on every side, while the divots fit to ~0.2 mm. ICP centres the model in the
  larger shell and moves the obstacles off their CT position (corners move ~0.9 mm),
  so these were run with `--no-icp`. PL14's divot margin is 0.12 (two weak pockets);
  it was run with `--divot-margin-min 0.1` (obstacle margin 0.58, FRE 0.19 mm).

- The stone/PLA boundary is assigned to `box`. CT blur spreads the bright stone
  up to about 1 mm into the registered mesh (about 3 mL of stone-intensity voxels).
  Those voxels count as `box`, so `stone` is about 3 mL below a pure-intensity
  count. None of them lies deeper than 1.5 mm, so no stone seeped into the infill.
- "Expected" allowed volumes in the report are the route region up to the
  stone-top level (99.5th percentile of stone z). The stone surface isn't flat,
  so treat them as approximate. See `qa/<name>_stone_top.png`.
- `box_damage` spots below the cavity floor can be lattice flicker that touches the
  channel: on PL12 the floor skin was intact in the CT. Check them in `*_damage.png`.
- A divot dropped from the fit (NCC < 0.3 or peak on the search edge, e.g. a pocket
  filled with stone) gets its `_M.mrk.json` point from the registered model instead of
  the wandered detection; its description says `NOT DETECTED`, and `report.json` lists
  it under `fiducials.M_from_model_not_detected`.
- "No stone peak" and a flat histogram from ~500 to the maximum mean the fill isn't
  ordinary set dental stone (2026-11-06: PL23, PL24, PL27, PL28 had a domed fill whose
  density fell from ~1300 at the floor to ~0 at the top; PL30 was dense only in the
  centre). No single threshold separates such fill from PLA; those scans weren't segmented.
- The "looks like a drilled scan" warning also fires on intact stone whose top is uneven
  and below the rim (PL19, PL21, PL22): check the overlay for a channel.
- The PLA damage check can only see damage next to the drilled channel. It
  needs the pre-drilling scan: without it, damage can't be told apart from the
  hollow lattice infill.
