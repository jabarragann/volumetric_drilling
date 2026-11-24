# Digital twin accuracy metrics

Metrics comparing the AMBF digital twin of a drilled phantom with the real drilled phantom (ground truth, GT).

The scripts are in this folder:

| Script | Role |
|---|---|
| `replay_digital_twin.py` | Replays a recording in SAINT and saves the twin (`<phantom>_D01_ambf.seg.nrrd`). |
| `analyze_digital_twin_acc.py` | Overlap and volume metrics. Writes `<twin>_vs_gt.seg.nrrd` and `_metrics.json`. |
| `analyze_twin_hausdorff.py` | Directed Hausdorff metrics. Writes `_hausdorff.json` and Slicer lines in `hausdorff_lines/`. |
| `analyze_registration.py` | Intraoperative and postoperative registration FRE / TRE. Writes `<exp>/registration_metrics.json`. |

## 1. Inputs and alignment

| Input | Description |
|---|---|
| D00 | Pre-drilling CT segmentation (`box`, `stone`). The twin starts from it. |
| Twin | AMBF volume saved after replaying the recording. It is on the D00 grid. |
| D01 (GT) | Post-drilling CT segmentation (`box`, `stone`, `drilled`, `box_damage`). |
| Markers | Fiducials M-1…M-n in D00 and D01 (`.mrk.json`). |

The twin is mapped to D01 with the rigid transform from the markers (least squares, Kabsch). It is then resampled onto the D01 grid: trilinear interpolation on each binary mask, thresholded at 0.5. All metrics below are computed on the D01 grid, with 0.35 mm isotropic voxels.

## 2. Sets

All sets are **stone only**. Box (PLA) damage is not scored because it is not detected reliably in the GT.

| Symbol | Name | Definition | Segment in `_vs_gt.seg.nrrd` |
|---|---|---|---|
| $X$ | Real cut | Stone the real drill removed (D00 stone minus D01 stone) | `gt_drilled_stone` |
| $Y$ | Twin cut | Stone the simulated drill removed (D00 stone minus twin stone). This is what navigation showed as removed. | `twin_drilled_stone` |
| $B = X \cap Y$ | Removed in both | Stone removed in reality and in the twin | `drilled_both` |
| $R = X \setminus Y$ | Real only | Stone removed in reality but not in the twin: navigation did not show it as removed | `drilled_real_only` |
| $S = Y \setminus X$ | Twin only | Stone removed in the twin but not in reality: navigation showed it as removed, but it is still there | `drilled_sim_only` |

So $X = B \cup R$ and $Y = B \cup S$:

```
        Real cut X              Twin cut Y
   ┌───────────────┐       ┌───────────────┐
   │       R       │  B    │       S       │
   │   real only   │ both  │   twin only   │
   └───────────────┘       └───────────────┘
```

$|\cdot|$ is the volume of a set: voxel count × voxel volume. In these tables "sim" and "twin" mean the same thing.

Other segments in `_vs_gt.seg.nrrd`:
- `gt_box`, `gt_stone`, `gt_drilled_box`: the GT.
- `twin_box`, `twin_stone`, `twin_drilled_box`: the twin, resampled.
- `stone_both`, `stone_gt_only`, `stone_twin_only`, `box_gt_only`, `box_twin_only`: the remaining material compared between GT and twin.

## 3. Overlap and volume metrics (`analyze_digital_twin_acc.py`)

These are computed on the full cuts, without the component filter of section 5.

### Drilled Dice

$$\mathrm{Dice}(X, Y) = \frac{2\,|X \cap Y|}{|X| + |Y|}$$

The overlap of the real and twin cuts: 1 means identical, 0 means no overlap. Extra and missing voxels count equally.

Key in `_metrics.json`: `dice.drilled`.

### Volume ratio (sim / real)

$$\frac{|Y|}{|X|}$$

Volume only, ignoring position. Above 1, the twin removed more stone than the real drill; below 1, less. A ratio of 1 does not mean the cuts are in the same place.

Keys: `drilled.sim_over_real`, with the volumes in `drilled.real_mm3` and `drilled.sim_mm3`.

### Real cut covered (recall)

$$\mathrm{Recall} = \frac{|X \cap Y|}{|X|} = 1 - \frac{|R|}{|X|}$$

The share of the bone actually removed that the twin also shows as removed. **This is the clinically important one:** low coverage means navigation missed bone that was really drilled.

Key: `drilled.recall_real_covered_by_sim`.

### Sim cut inside real (precision)

$$\mathrm{Precision} = \frac{|X \cap Y|}{|Y|} = 1 - \frac{|S|}{|Y|}$$

The share of the twin cut that was really drilled. The rest is bone that navigation showed as removed but that is still there.

Key: `drilled.precision_sim_inside_real`.

Dice is the harmonic mean of recall and precision:

$$\mathrm{Dice} = \frac{2 \cdot \mathrm{Recall} \cdot \mathrm{Precision}}{\mathrm{Recall} + \mathrm{Precision}}$$

### Stone Dice

$$\mathrm{Dice}(\text{GT stone after drilling},\ \text{twin stone after drilling})$$

The overlap of the **remaining** stone. Most of the stone is never drilled, so this value is always high (about 0.90–0.98) and mostly checks the alignment and the segmentation. Use it as a sanity check, not as a measure of drilling accuracy.

Key: `dice.stone`. `dice.box` is the same for the box.

### Reading the overlap metrics together

| Pattern | Interpretation |
|---|---|
| Recall ≈ precision, both high | Good match |
| Recall < precision, sim/real < 1 | The twin under-drills: navigation misses bone |
| Precision < recall, sim/real > 1 | The twin over-drills |
| Both low, sim/real ≈ 1 | Similar volume in a shifted place, which suggests a registration or tracking offset |

## 4. Directed Hausdorff metrics (`analyze_twin_hausdorff.py`)

The overlap metrics say *how many* voxels are wrong. The Hausdorff metrics say *how far* the wrong voxels are from the other cut.

### Point-to-set distance

$$d(p, A) = \min_{q \in A} \lVert p - q \rVert$$

The Euclidean distance in mm from voxel $p$ to the nearest voxel of set $A$, measured between voxel centres. The resolution is about one voxel (0.35 mm). The nearest voxel of $A$ always lies on the surface of $A$.

### hd(real→twin): the dangerous direction

$$\mathrm{hd}(\text{real}\to\text{twin}) = \max_{p \in X} d(p, Y) = \max_{p \in R} d(p, Y)$$

The largest distance from any stone voxel removed only by the real drill to the nearest voxel of the twin cut. In other words, **the farthest the real drill went beyond the bone navigation showed as removed.** These are the problematic voxels clinically: bone removed without the navigation system accounting for it, which can lead to injury.

The two forms are equal because $d(p, Y) = 0$ for every voxel the two cuts share. So this is exactly the textbook directed Hausdorff distance from the real cut to the twin cut.

The distance is measured to the whole twin cut $Y$, not only to $B$, because navigation displays all of $Y$. A real-only voxel next to a twin-only voxel was effectively shown to the surgeon.

### hd(twin→real)

$$\mathrm{hd}(\text{twin}\to\text{real}) = \max_{p \in Y} d(p, X) = \max_{p \in S} d(p, X)$$

The largest distance from any stone voxel removed only in the twin to the nearest voxel of the real cut. In other words, the farthest navigation showed bone as removed where real bone remained. This is leftover bone, which is less dangerous.

### Hausdorff distance

$$H(X, Y) = \max\big(\mathrm{hd}(\text{real}\to\text{twin}),\ \mathrm{hd}(\text{twin}\to\text{real})\big)$$

The standard symmetric Hausdorff distance, for comparison with the literature.

### hd95 and mean distance

$$\mathrm{hd}_{95}(\text{real}\to\text{twin}) = P_{95}\{\, d(p, Y) : p \in R \,\}$$

$$\bar d(\text{real}\to\text{twin}) = \frac{1}{|R|} \sum_{p \in R} d(p, Y)$$

These are the 95th percentile and the mean of the distances over the real-only voxels. hd(twin→real) uses the same definitions with $S$ and $X$. The maximum depends on a single voxel; hd95 is robust to a few outlier voxels.

> **Note:** these are taken over the one-sided voxels ($R$ or $S$) only, **not** over the whole cut or its surface as in the textbook HD95 and mean surface distance. The shared voxels would add zeros there, so the textbook values are smaller. Ours answers "among the voxels navigation missed, how far is a typical bad one?" It is not directly comparable with published HD95 values.

The smallest possible distance is one voxel, 0.35 mm, so the means are typically about 0.4–0.5 mm when the agreement is good.

### Size of the region holding the maximum

The number of voxels (and mm³) in the 26-connected region of $R$ (or $S$) that contains the maximum. A large region means the maximum is a real excursion; a few voxels point to noise.

### Keys in `_hausdorff.json`

| Metric | real→twin | twin→real |
|---|---|---|
| hd (max) | `real_to_twin.hd_max_mm` | `twin_to_real.hd_max_mm` |
| hd95 | `real_to_twin.hd95_mm` | `twin_to_real.hd95_mm` |
| mean | `real_to_twin.mean_mm` | `twin_to_real.mean_mm` |
| one-sided voxels ($\lvert R \rvert$, $\lvert S \rvert$) | `real_to_twin.voxels` | `twin_to_real.voxels` |
| region holding the max | `real_to_twin.max_component_voxels` / `_mm3` | `twin_to_real.max_component_voxels` / `_mm3` |

The top-level keys are `hausdorff_mm` ($H$) and `hd95_mm` (the larger of the two hd95 values). The summary for all runs is `pilot_experiments/twin_hausdorff_summary.csv`.

### Slicer lines (`hausdorff_lines/`)

Each line goes from a voxel of $R$ (or $S$) to its nearest voxel of $Y$ (or $X$). The files are named `<base>_hd_<direction>_<kind>.mrk.json`, with `<direction>` either `real_to_twin` or `twin_to_real`.

| `<kind>` | Line | Colour (real_to_twin / twin_to_real) |
|---|---|---|
| `max` | at the maximum, hd | red / blue |
| `max_inplane` | the in-plane line closest to hd | magenta / purple |
| `hd95` | a voxel at hd95 (random among ties, fixed seed) | light red / light blue |
| `hd95_inplane` | the in-plane line closest to hd95 | orange / cyan |

The in-plane lines are still exact nearest-voxel pairs, so their length is a true 3D distance. They are chosen among the pairs whose two ends share one voxel index, so each lies entirely in one axial, coronal or sagittal slice. The plane is in the point labels. Clicking a point in the Markups module table jumps that slice view to a slice containing the whole line.

## 5. Component filter (Hausdorff only)

Before $R$ and $S$ are formed, $X$ and $Y$ are each reduced to their largest 26-connected component. Isolated segmentation islands therefore cannot set the maximum. The number of dropped voxels is reported in `component_filter_details`, and the filter can be turned off with `--keep-all-components`.

The overlap metrics of section 3 use the unfiltered cuts.

## 6. Simulation diagnostics

### Capped steps

$$\frac{\text{physics steps where removal hit the cap}}{\text{physics steps with voxel removal}}$$

Reported by the volumetric drilling plugin through the `save_volume` service. Each physics step removes at most `voxel_removal_threshold` voxels (30 by default). This is the share of steps where the burr touched more voxels than that, so removal was rate-limited. High values mean the twin may under-drill because of the cap.

Key in `run.json`: `removal_stats.capped_pct`.

## 7. Registration metrics (`analyze_registration.py`)

Two rigid registrations limit how well the twin can match reality:

| Registration | From → to | Points | Matters for |
|---|---|---|---|
| **Intraoperative** | CT model (D00 markers) → optical tracker (Atracsys) | `config/registration_output.json`: `source_points` = D00 marker positions placed in the AMBF world (m); `target_points` = pointer-tip positions measured with the Atracsys (m). The point order follows `name of points` in `config/registration_config_pointer.yaml`. | Where the drill is placed in the model during surgery and the replay, and therefore the twin itself |
| **Postoperative** | D00 CT markers → D01 CT markers | D00 and D01 `.mrk.json` (mm) | Comparing the twin with the GT (section 1) |

The source points are the D00 markers: their pairwise distances match the D00 `.mrk.json` within about 0.001 mm (`source_vs_d00_shape_max_mm`).

### FRE and TRE

Each registration is refitted (rigid, least squares / Kabsch) on the **fiducial markers** $F$ only and evaluated on the **target markers** $T$, which are not used in the fit:

| Set | Markers | Role |
|---|---|---|
| $F$ (fiducials) | M-1, M-3, M-4, M-5, M-9 | Used to fit the registration |
| $T$ (targets) | M-2, M-7, M-8 | Evaluation only |

$$(\mathbf{R}_{\mathrm{reg}}, t_{\mathrm{reg}}) = \arg\min_{\mathbf{R}, t} \sum_{i \in F} \big\lVert \mathbf{R}\,s_i + t - g_i \big\rVert^2$$

$$e_i = \big\lVert \mathbf{R}_{\mathrm{reg}}\,s_i + t_{\mathrm{reg}} - g_i \big\rVert$$

$$\mathrm{FRE} = \sqrt{\frac{1}{|F|}\sum_{i \in F} e_i^2} \qquad \mathrm{TRE} = \sqrt{\frac{1}{|T|}\sum_{i \in T} e_i^2}$$

Here $s_i$ is the source position of marker $i$ and $g_i$ its target position. $\mathbf{R}_{\mathrm{reg}}$ is a rotation, not the set $R$.

- **FRE** (fiducial registration error) measures how well the fitted markers agree. A low FRE does not by itself guarantee accuracy elsewhere.
- **TRE** (target registration error) is the error at points not used in the fit. It is the better estimate of the error at the drilling site.

The maxima over $F$ and $T$, and $e_i$ for each marker, are also reported. M-6 is in neither set.

> SAINT fitted the intraoperative registration on all points in the pointer config, and `analyze_digital_twin_acc.py` aligns D00 to D01 on all shared markers. The FRE/TRE refits are for evaluation only and do not change those alignments.

Keys in `registration_metrics.json`: `intraoperative.*` and `postoperative.*`, each with `fre_rms_mm`, `fre_max_mm`, `tre_rms_mm`, `tre_max_mm` and `per_marker_mm`. The summary for all runs is `pilot_experiments/registration_summary.csv`.

### Postoperative marker fit (all markers)

$$\mathrm{RMSE} = \sqrt{\frac{1}{n}\sum_{i=1}^{n} \big\lVert \mathbf{R}_{\mathrm{reg}}\,m_i^{D00} + t_{\mathrm{reg}} - m_i^{D01} \big\rVert^2}$$

This is the residual of the D00 → D01 alignment actually used by `analyze_digital_twin_acc.py`, fitted on all $n$ shared markers. It is the "Marker fit" column in the earlier tables. Typical values are 0.05–0.12 mm, below the 0.35 mm voxel.

Keys: `registration.marker_rmse_mm` and `registration.marker_residuals_mm` in `_metrics.json`.
