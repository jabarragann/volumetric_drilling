"""
Split a Loop-x scan of several phantoms on one plate into one DICOM series per phantom.

The phantoms lie in a 2 x 2 grid in the sagittal plane. Names are given in reading
order as seen in 3D Slicer's sagittal view (anterior on the left, superior on top):
top-left, top-right, bottom-left, bottom-right.

    python split_phantoms.py --ct <DICOM folder> --out <processed folder> \
        --prefix 2026-10-14 --suffix D00 --names PL09 PL10 PL11 PL12

writes <out>/<prefix>_<name>_<suffix>/ for each phantom. Voxels are copied unchanged:
each crop keeps the physical position of the full scan and gets its own series UID.
The cuts are placed at the emptiest slice/row in the middle third of the scan; check
the printed occupancy, or give them with --cuts.
"""

import argparse
import os

import numpy as np
import pydicom
import SimpleITK as sitk
from pydicom.uid import generate_uid


def find_cut(occupancy):
    n = len(occupancy)
    smooth = np.convolve(occupancy.astype(float), np.ones(5) / 5, "same")
    return n // 3 + int(np.argmin(smooth[n // 3:2 * n // 3]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ct", required=True, help="DICOM folder with one series (the whole plate)")
    ap.add_argument("--out", required=True, help="output folder, e.g. phantoms/Loop-x/processed")
    ap.add_argument("--names", nargs=4, required=True, metavar=("TL", "TR", "BL", "BR"),
                    help="phantom names as seen in Slicer's sagittal view; '-' skips a position")
    ap.add_argument("--prefix", required=True, help="folder prefix, usually the scan date (YYYY-MM-DD)")
    ap.add_argument("--suffix", required=True, help="folder suffix, e.g. D00 before drilling, D01 after")
    ap.add_argument("--cuts", nargs=2, type=int, metavar=("SLICE", "ROW"),
                    help="override the automatic cuts: first slice of the bottom row, first image row of the left column")
    ap.add_argument("--patient-name", action="store_true",
                    help="also set PatientName and PatientID to <name>_<suffix>")
    args = ap.parse_args()

    r = sitk.ImageSeriesReader()
    ids = r.GetGDCMSeriesIDs(args.ct)
    if len(ids) != 1:
        raise SystemExit(f"{args.ct}: expected one DICOM series, found {len(ids)}")
    files = r.GetGDCMSeriesFileNames(args.ct, ids[0])   # sorted by position: index = slice k
    r.SetFileNames(files)
    occ = sitk.GetArrayFromImage(r.Execute()) > 0       # [k, j, i]; phantoms and plate are > 0
    nk, nj = occ.shape[:2]

    if args.cuts:
        K, J = args.cuts
    else:
        K, J = find_cut(occ.sum((1, 2))), find_cut(occ.sum((0, 2)))
    print(f"[split] {len(files)} slices x {nj} rows; cut at slice {K}, row {J}")
    print(f"        occupancy at the cuts {occ[K].sum()} / {occ[:, J].sum()} "
          f"(median slice {int(np.median(occ.sum((1, 2))))}, row {int(np.median(occ.sum((0, 2))))})")

    # Slicer sagittal: screen left = anterior = high row j; top = superior = low slice k
    quads = {"TL": ((0, K), (J, nj)), "TR": ((0, K), (0, J)), "BL": ((K, nk), (J, nj)), "BR": ((K, nk), (0, J))}
    for pos, name in zip(quads, args.names):
        if name == "-":
            continue
        (k0, k1), (j0, j1) = quads[pos]
        tag = f"{name}_{args.suffix}"
        od = os.path.join(args.out, f"{args.prefix}_{tag}")
        os.makedirs(od, exist_ok=False)
        suid = generate_uid()
        for n, k in enumerate(range(k0, k1)):
            d = pydicom.dcmread(files[k])
            px = d.pixel_array[j0:j1, :]
            d.PixelData = np.ascontiguousarray(px).tobytes()
            d.Rows = px.shape[0]
            ipp = [float(v) for v in d.ImagePositionPatient]
            col_dir = [float(v) for v in d.ImageOrientationPatient[3:]]
            sp = float(d.PixelSpacing[0])
            d.ImagePositionPatient = [f"{ipp[i] + j0 * sp * col_dir[i]:.6f}" for i in range(3)]
            d.SeriesInstanceUID = suid
            d.SOPInstanceUID = generate_uid()
            d.file_meta.MediaStorageSOPInstanceUID = d.SOPInstanceUID
            d.SeriesDescription = f"{d.get('SeriesDescription', '')} - {name} crop (k{k0}-{k1 - 1}, row{j0}-{j1 - 1})"
            d.InstanceNumber = n + 1
            if args.patient_name:
                d.PatientName = tag
                d.PatientID = tag
            d.save_as(os.path.join(od, f"{name}_{n:04d}.dcm"))
        print(f"[split] {pos} {name}: slices {k0}-{k1 - 1}, rows {j0}-{j1 - 1} -> {od}")


if __name__ == "__main__":
    main()
