# Running the segmentation on a new phantom

Step-by-step procedure for a new scan pair, with `PL09` as the example name.
For the method and the full list of outputs, see [README.md](README.md).

## 1. Before you start

- **CT:** the DICOM series (one series per folder) in `phantoms/Loop-x/processed/`,
  e.g. `2026-11-05_PL09_D00` and later `..._PL09_D01`. Each folder must contain
  only that scan's series.
- **Model version:** know which version of the model was printed (`v01`, `v02`,
  `v03`). Its folder `~/research/openscad_models/saint_phantom/stl/<version>/`
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

## 3. Check the D00 result

Open `cad-registration/PL09_D00/PL09_D00_report.md`:

- **Pose candidates:** the chosen pose should find 9/9 divot pockets, and the
  180° pose about 4/9.
- **FRE (divot fit error):** about 0.1 mm per divot. A single large value means
  a divot was missed.
- **ICP RMS:** about 0.2–0.4 mm.
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
- **Experiment files:** copy what you need (e.g. the `box_dental*.seg.nrrd` files
  and `_M.mrk.json`) into `phantoms/organized_phantoms/PL09_D01/` yourself. The
  script never writes there.

## If something fails

| Problem | Fix |
|---|---|
| `orientation is ambiguous` | Click the 9 divots in Slicer (M-1…M-9, at the centre of each pocket opening), save them as `.mrk.json`, and re-run with `--ct-fiducials clicks.mrk.json`. RAS or LPS are both fine. |
| Thresholds look wrong in the histogram | Re-run with `--thresholds <air_pla> <pla_stone>`, using values read off the histogram. |
| `version mismatch` or `sha256 differs` | `--version` and `--stl-dir` don't match, or the STLs were regenerated. Use the version that was actually printed. |
| `expected one DICOM series` | The `--ct` folder holds more than one series. Give each scan its own folder. |

Every run writes the model version, the commits and the STL hashes into
`report.json`, so each result can be traced back to its exact inputs.
