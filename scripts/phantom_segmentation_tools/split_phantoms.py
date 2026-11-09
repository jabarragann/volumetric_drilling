"""
Split a Loop-x scan of several phantoms on one plate into one DICOM series per phantom.

This is step 1 of the pipeline (split -> register_cad, see HOW_TO_RUN.md). The output
DICOMs are plain crops of the scan: no resampling, no rotation. Aligning the volume
with the box axes and cropping tightly around the box happens later, in register_cad.py.

Layout
------
The phantoms lie on a mounting plate in a ROWS x COLS grid in the sagittal plane
(plate normal along patient left-right). Names are given in reading order as seen in
3D Slicer's sagittal view (anterior on the left, superior on top): the top row from
left to right, then the next row, and so on. For a 3 x 2 grid:

    TL TR          names: TL TR ML MR BL BR
    ML MR
    BL BR

The axes are found from the DICOM direction matrix, so this works whether the
superior/anterior directions run along the slices, the image rows or the image
columns (Loop-x exports differ between protocols).

    python split_phantoms.py --ct <DICOM folder> --out <processed folder> \
        --prefix 2026-11-06 --suffix D00 --grid 3 2 \
        --names PL13 PL14 PL16 PL18 PL19 PL20

writes <out>/<prefix>_<name>_<suffix>/ for each phantom ('-' skips a position).

Voxels are copied unchanged: each crop keeps the physical position of the full scan
and gets its own SeriesInstanceUID.

Cuts
----
Along each in-plane axis the occupancy profile (voxels > 0 per slice/row/column) has
one plateau per grid row/column, separated by gaps where only the thin plate is
present. The plateaus are found by thresholding the smoothed profile halfway between
its 5th and 95th percentiles; each cut goes at the emptiest position of the gap
between two plateaus. The outer tiles extend to the edge of the scan. Check the
printed occupancy at each cut (it should be far below the median), or give the cuts
with --row-cuts / --col-cuts.
"""

import argparse
import os

import numpy as np
import pydicom
import SimpleITK as sitk
from pydicom.uid import generate_uid

AXIS_NAMES = ("column i", "row j", "slice k")   # sitk index order (x, y, z) = DICOM (column, row, slice)


def find_cuts(occupancy, n, min_run=10):
    """Return the n-1 cut positions that separate n plateaus of an occupancy profile.

    A cut c means the first tile ends at c-1 and the next one starts at c.
    Raises SystemExit if the profile does not have exactly n plateaus.
    """
    if n == 1:
        return []
    smooth = np.convolve(occupancy.astype(float), np.ones(5) / 5, "same")
    lo, hi = np.percentile(smooth, [5, 95])
    occupied = smooth > lo + 0.5 * (hi - lo)
    # runs of occupied positions, shorter ones dropped (noise, plate edges)
    edges = np.flatnonzero(np.diff(np.r_[0, occupied.astype(int), 0]))
    runs = [(a, b) for a, b in zip(edges[::2], edges[1::2]) if b - a >= min_run]
    if len(runs) != n:
        raise SystemExit(f"expected {n} phantoms along this axis, found {len(runs)} plateaus {runs}; "
                         f"pass the cuts explicitly (--row-cuts / --col-cuts)")
    return [int(b0 + np.argmin(smooth[b0:a1])) for (_, b0), (a1, _) in zip(runs[:-1], runs[1:])]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ct", required=True, help="DICOM folder with one series (the whole plate)")
    ap.add_argument("--out", required=True, help="output folder, e.g. phantoms/Loop-x/processed")
    ap.add_argument("--grid", nargs=2, type=int, default=(2, 2), metavar=("ROWS", "COLS"),
                    help="phantom grid as seen in Slicer's sagittal view (default 2 2)")
    ap.add_argument("--names", nargs="+", required=True,
                    help="ROWS*COLS phantom names in Slicer-sagittal reading order "
                         "(top row left to right, then the next row); '-' skips a position")
    ap.add_argument("--prefix", required=True, help="folder prefix, usually the scan date (YYYY-MM-DD)")
    ap.add_argument("--suffix", required=True, help="folder suffix, e.g. D00 before drilling, D01 after")
    ap.add_argument("--row-cuts", nargs="+", type=int, metavar="IDX",
                    help="override the cuts between grid rows: ROWS-1 indices along the superior-inferior "
                         "index axis (first index of each lower tile)")
    ap.add_argument("--col-cuts", nargs="+", type=int, metavar="IDX",
                    help="override the cuts between grid columns: COLS-1 indices along the anterior-posterior "
                         "index axis (first index of each tile with the higher index)")
    ap.add_argument("--patient-name", action="store_true",
                    help="also set PatientName and PatientID to <name>_<suffix>")
    ap.add_argument("--dry-run", action="store_true", help="print the cuts and tiles, write nothing")
    args = ap.parse_args()
    nrow, ncol = args.grid
    if len(args.names) != nrow * ncol:
        raise SystemExit(f"--grid {nrow} {ncol} needs {nrow * ncol} names, got {len(args.names)}")

    r = sitk.ImageSeriesReader()
    ids = r.GetGDCMSeriesIDs(args.ct)
    if len(ids) != 1:
        raise SystemExit(f"{args.ct}: expected one DICOM series, found {len(ids)}")
    files = r.GetGDCMSeriesFileNames(args.ct, ids[0])   # sorted by position: index = slice k
    r.SetFileNames(files)
    img = r.Execute()
    occ = sitk.GetArrayFromImage(img) > 0               # [k, j, i]; phantoms and plate are > 0
    size = img.GetSize()                                # (ni, nj, nk)
    D = np.array(img.GetDirection()).reshape(3, 3)      # column a = LPS direction of index axis a

    # which index axis runs superior-inferior (LPS z) and anterior-posterior (LPS y)
    ax_s = int(np.argmax(np.abs(D[2])))
    ax_a = int(np.argmax(np.abs(D[1])))
    if ax_s == ax_a or min(abs(D[2, ax_s]), abs(D[1, ax_a])) < 0.9:
        raise SystemExit(f"scan axes are not aligned with the patient axes (direction {D.ravel().round(3)})")
    # occupancy profile along index axis a: sum over the other two ([k, j, i] array axis = 2 - a)
    prof = {a: occ.sum(tuple(x for x in range(3) if x != 2 - a)) for a in (ax_s, ax_a)}
    rc = args.row_cuts if args.row_cuts else find_cuts(prof[ax_s], nrow)
    cc = args.col_cuts if args.col_cuts else find_cuts(prof[ax_a], ncol)
    if len(rc) != nrow - 1 or len(cc) != ncol - 1:
        raise SystemExit("need ROWS-1 row cuts and COLS-1 column cuts")
    for what, a, cuts in (("rows", ax_s, rc), ("columns", ax_a, cc)):
        print(f"[split] grid {what} along {AXIS_NAMES[a]} ({size[a]}): cuts at {cuts}; occupancy there "
              f"{[int(prof[a][c]) for c in cuts]} (median {int(np.median(prof[a]))})")

    # index ranges of each grid row (top = superior) and column (left = anterior)
    def spans(cuts, n, increasing_first):
        b = [0] + list(cuts) + [n]
        s = [(b[t], b[t + 1]) for t in range(len(b) - 1)]
        return s if increasing_first else s[::-1]
    row_spans = spans(rc, size[ax_s], D[2, ax_s] < 0)   # top = superior = highest LPS z
    col_spans = spans(cc, size[ax_a], D[1, ax_a] > 0)   # left = anterior = lowest LPS y

    for t, name in enumerate(args.names):
        if name == "-":
            continue
        rng = [(0, size[0]), (0, size[1]), (0, size[2])]   # per index axis (i, j, k)
        rng[ax_s] = row_spans[t // ncol]
        rng[ax_a] = col_spans[t % ncol]
        (i0, i1), (j0, j1), (k0, k1) = rng
        tag = f"{name}_{args.suffix}"
        od = os.path.join(args.out, f"{args.prefix}_{tag}")
        print(f"[split] row {t // ncol + 1} col {t % ncol + 1} {name}: columns {i0}-{i1 - 1}, rows {j0}-{j1 - 1}, "
              f"slices {k0}-{k1 - 1} -> {od}")
        if args.dry_run:
            continue
        os.makedirs(od, exist_ok=False)
        suid = generate_uid()
        for n, k in enumerate(range(k0, k1)):
            d = pydicom.dcmread(files[k])
            px = d.pixel_array[j0:j1, i0:i1]
            d.PixelData = np.ascontiguousarray(px).tobytes()
            d.Rows, d.Columns = px.shape
            iop = [float(v) for v in d.ImageOrientationPatient]
            ipp = np.array([float(v) for v in d.ImagePositionPatient])
            # PixelSpacing = [row spacing (between rows, along the column direction), column spacing]
            sp_row, sp_col = (float(v) for v in d.PixelSpacing)
            ipp = ipp + i0 * sp_col * np.array(iop[:3]) + j0 * sp_row * np.array(iop[3:])
            d.ImagePositionPatient = [f"{v:.6f}" for v in ipp]
            d.SeriesInstanceUID = suid
            d.SOPInstanceUID = generate_uid()
            d.file_meta.MediaStorageSOPInstanceUID = d.SOPInstanceUID
            # crop first, then as much of the original description as fits (LO: 64 characters)
            d.SeriesDescription = (f"{name} c{i0}-{i1 - 1} r{j0}-{j1 - 1} k{k0}-{k1 - 1} | "
                                   f"{d.get('SeriesDescription', '')}")[:64]
            d.InstanceNumber = n + 1
            if args.patient_name:
                d.PatientName = tag
                d.PatientID = tag
            d.save_as(os.path.join(od, f"{name}_{n:04d}.dcm"))


if __name__ == "__main__":
    main()
