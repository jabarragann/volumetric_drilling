"""Rewrite PatientName and PatientID in every DICOM file of a folder (optional helper).

    python modify_dicom_info.py -i <DICOM folder> -o <output folder> -n PL13_D00

Files are read recursively from --input and written flat into --output under their
original file names (so files with the same name in different subfolders overwrite
each other). Files that pydicom can't read are skipped silently. Pixel data and all
other tags are unchanged. split_phantoms.py --patient-name does the same while splitting.
"""
import argparse
from pathlib import Path
import pydicom


parser = argparse.ArgumentParser(description="Modify PatientName and PatientID in DICOM files.")
parser.add_argument("-i", "--input", required=True, type=Path,
                    help="Input directory containing DICOM files.")
parser.add_argument("-o", "--output", required=True, type=Path,
                    help="Output directory for modified DICOM files.")
parser.add_argument("-n", "--patient-name", required=True,
                    help="New PatientName to write into the DICOM files.")
args = parser.parse_args()

input_dir = args.input
output_dir = args.output
output_dir.mkdir(parents=True, exist_ok=True)

new_name = args.patient_name

for file in input_dir.rglob("*"):
    if not file.is_file():
        continue

    try:
        ds = pydicom.dcmread(file)

        ds.PatientName = new_name
        ds.PatientID = new_name

        output_file = output_dir / file.name
        ds.save_as(output_file)

        print(f"Modified {file.name}")

    except Exception:   # not a DICOM file (e.g. DICOMDIR leftovers, .DS_Store)
        pass
