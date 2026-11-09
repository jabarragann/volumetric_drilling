# Running the segmentation on a new phantom

Step-by-step procedure for a new scan pair, with `PL09` as the example name.
For the method and the full list of outputs, see [README.md](README.md).

The pipeline is **split → register_cad** (register, align with the box, segment, crop):

| Folder | Holds | Written by |
|---|---|---|
| `phantoms/Loop-x/raw/` | Loop-x exports, whole plate | the scanner |
| `phantoms/Loop-x/processed/` | one DICOM series per phantom, **not aligned** | `split_phantoms.py` |
| `phantoms/Loop-x/cad-registration/` | registration, segmentations, CT **with the box tilt removed and cropped** (scanner frame kept) | `register_cad.py` |
| `phantoms/organized_phantoms/` | copies of the cad-registration files used in experiments | you (step 6) |

## 1. Before you start

- **CT:** the DICOM series (one series per folder) in `phantoms/Loop-x/processed/`,
  e.g. `2026-11-05_PL09_D00` and later `..._PL09_D01`. Each folder must contain
  only that scan's series.
- **Several phantoms in one scan:** split it first. The phantoms must lie in a
  ROWS × COLS grid on the plate (default 2 × 2). Give the names in reading order as
  seen in Slicer's sagittal view (anterior on the left, superior on top): the top row
  left to right, then the next row. `-` skips a position. Add `--dry-run` to see the
  cuts first:
  ```bash
  $PY $TOOLS/split_phantoms.py --ct <raw Series folder> --out $DATA/processed \
      --prefix 2026-11-05 --suffix D00 --names PL09 PL10 PL11 PL12
  # 6 phantoms, 3 rows x 2 columns
  $PY $TOOLS/split_phantoms.py --ct <raw Series folder> --out $DATA/processed \
      --prefix 2026-11-06 --suffix D00 --grid 3 2 --names PL13 PL14 PL16 PL18 PL19 PL20
  ```
  Each cut goes at the emptiest position between two rows (columns) of phantoms.
  Check that the printed occupancy at the cuts is far below the median, or set them
  with `--row-cuts` / `--col-cuts`. If you're unsure which phantom is which, register
  each tile with the candidate model versions: the wrong version gives FRE ≈ 1 mm on
  the base divots M-1…M-3 (v02 vs v03/v04), and a re-scanned phantom matches its
  earlier scan's stone (fill level, bubbles). Phantoms can be moved or rotated between the pre- and
  post-drilling scans, so check the names: `register_cad.py --reference` stops with
  exit code 3 if a post-drilling scan doesn't match its pre-drilling phantom.
- **Model version:** know which version of the model was printed (`v01` … `v04`). Its folder `~/research/openscad_models/saint_phantom/stl/<version>/`
  must contain the STLs, the fiducial and surface CSVs, `version.json` and
  `paths.json`. If they're missing, generate them in that repo with
  `scripts/registration_points.py` and `scripts/export_path_meshes.py`.
- **Python:** the conda env `saint-env`.

Set these once per terminal:

```bash
PY=/opt/miniconda3/envs/saint-env/bin/python
TOOLS=~/research/saint_project/volumetric_drilling_saint/scripts/phantom_segmentation_tools
STL=~/research/openscad_models/saint_phantom/stl
DATA=~/research/saint_project/phantoms/Loop-x
```

## 2. Pre-drilling scan (D00)

```bash
$PY $TOOLS/register_cad.py --version v01 --stl-dir $STL/v01 \
    --ct $DATA/processed/2026-11-05_PL09_D00 \
    --name PL09_D00 --out $DATA/cad-registration/PL09_D00
```

The CT in the output folder keeps the scanner's frame and orientation (same view in
Slicer as the `processed/` DICOM), with the box's tilt removed so the segmentation runs
along the voxel axes, and is cropped to the box plus 5 voxels in-plane and 20 voxels
along the box normal. Use `--no-align` to keep the scanner grid instead.

## 3. Check the D00 result

Open `cad-registration/PL09_D00/PL09_D00_report.md`:

- **Pose candidates:** the chosen pose should find 9/9 divot pockets, and the
  180° pose about 4/9.
- **FRE (divot fit error):** about 0.1 mm per divot. A single large value means
  a divot was missed.
- **ICP RMS:** about 0.2–0.4 mm. If the fiducial distance after ICP is ≥ 0.5 mm
  and the box corners move ~1 mm, ICP has pulled the model off the divots: re-run
  with `--no-icp` (needed for PL09 and the v02 prints PL13/PL14).
- **`[align]` line:** the tilt removed (a few degrees) and where the model axes point
  (`model_z` is the stone normal, e.g. `+L`).
- **`[crop]` line:** the margins around the box should be [20, 20] on the axis that
  carries model z and [5, 5] on the other two.
- **Images in `qa/`:**
  - `*_overlay.png`: the red mesh contours should sit on the CT edges.
  - `*_divots.png`: each cross should be in its pocket.
  - `*_histogram.png`: the two dashed thresholds should fall in the valleys
    between the air, PLA and stone peaks.

If a D00 run warns "empty space … looks like a drilled scan", that scan has
gaps in the stone. Look at the overlay before going on.

## 4. Post-drilling scan (D01): same flags plus `--reference`

```bash
$PY $TOOLS/register_cad.py --version v01 --stl-dir $STL/v01 \
    --ct $DATA/processed/2026-12-01_PL09_D01 \
    --name PL09_D01 --out $DATA/cad-registration/PL09_D01 \
    --reference $DATA/cad-registration/PL09_D00
```

- `--reference` must point to the D00 output folder of the **same phantom**, so
  step 2 must be done first. If you point it at another phantom, the run stops
  with `ERROR: ... DOES NOT LOOK LIKE THE SAME PHANTOM` (exit code 3), because the
  stone away from the drilled channel doesn't match.
- Add `--strict` if you want the run to fail (exit code 2) when PLA damage is
  found, which is useful in batch scripts.

## 5. Check the D01 result

- **Terminal or top of `PL09_D01_report.md`:** look for a
  `PLA DAMAGE DETECTED` warning. If there is one, check
  `qa/PL09_D01_damage.png`: each spot is shown before and after drilling, with
  its location in model and CT coordinates.
- **"Drilling" section of the report:** the removed stone per route, allowed and
  forbidden.
- **`qa/PL09_D01_drilled.png`:** the drilled channel in green (allowed) and red
  (forbidden).

## 6. Use the results

- **Slicer:** drag in `<name>_ct.nrrd` and one of the `.seg.nrrd` files, or load
  everything at once:
  ```bash
  /Applications/Slicer.app/Contents/MacOS/Slicer --python-script $TOOLS/load_in_slicer.py \
      --out $DATA/cad-registration/PL09_D01 --name PL09_D01
  ```
- **Experiment files:** copy the files used in experiments into
  `phantoms/organized_phantoms/PL09_D01/` yourself (the script never writes there):
  ```bash
  N=PL09_D01; mkdir -p ~/research/saint_project/phantoms/organized_phantoms/$N
  cp $DATA/cad-registration/$N/${N}_{box_dental,box_dental_left_path,box_dental_right_path}.seg.nrrd \
     $DATA/cad-registration/$N/${N}_ct.nrrd $DATA/cad-registration/$N/${N}_M.mrk.json \
     ~/research/saint_project/phantoms/organized_phantoms/$N/
  ```

## If something fails

| Problem | Fix |
|---|---|
| `orientation is ambiguous`, divot margin just under 0.3 but obstacles agree by ≥ 0.5 | Re-run with `--divot-margin-min 0.1` and check the FRE (~0.2 mm) and `qa/*_divots.png`. |
| `orientation is ambiguous` | Click the 9 divots in Slicer (M-1…M-9, at the centre of each pocket opening), save them as `.mrk.json`, and re-run with `--ct-fiducials clicks.mrk.json`. RAS or LPS are both fine. |
| Thresholds look wrong in the histogram | Re-run with `--thresholds <air_pla> <pla_stone>`, using values read off the histogram. |
| `version mismatch` or `sha256 differs` | `--version` and `--stl-dir` don't match, or the STLs were regenerated. Use the version that was actually printed. |
| `no stone peak found in the histogram` | Look at `qa`/the CT: if the fill is ordinary stone but scarce, pass `--thresholds`; if its density is uneven (domed, faint near the walls), it can't be segmented by threshold. |
| `orientation is ambiguous` and every candidate matches < 120/200 points | The tile is mostly mounting plate: re-run with `--pca-erode 8`. |
| `split_phantoms.py`: `expected N phantoms along this axis` | The occupancy profile didn't show N separate rows/columns: check `--grid`, or give `--row-cuts` / `--col-cuts`. |
| `aligned crop: ... segment voxels fall outside the crop` | Increase `--margin-xy` / `--margin-z`, or check the registration (a segment far from the box). |
| `expected one DICOM series` | The `--ct` folder holds more than one series. Give each scan its own folder. |

Every run writes the model version, the commits and the STL hashes into
`report.json`, so each result can be traced back to its exact inputs.
