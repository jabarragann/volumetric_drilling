"""
Registration accuracy (FRE / TRE) for a SAINT experiment, for two registrations:

  intraoperative   CT model (D00 markers) -> optical tracker (Atracsys pointer measurements).
                   From <exp>/config/registration_output.json:
                     source_points = D00 marker positions in the AMBF world (m)
                     target_points = pointer-tip positions measured with the Atracsys (m)
                   Point order = 'name of points' in config/registration_config_pointer.yaml.
  postoperative    D00 CT markers -> D01 (post-drilling) CT markers (.mrk.json, mm).

Each registration is refitted here (rigid, least squares / Kabsch) on the fiducial markers
only, and evaluated on the target markers that were not used in the fit:
  FRE = RMS over fiducial markers of |T(source_i) - target_i|   (default M-1,3,4,5,9)
  TRE = RMS over target markers   of |T(source_i) - target_i|   (default M-2,7,8)
Per-marker errors and the maximum are also reported. Distances in mm.

NOTE: SAINT itself fitted the intraoperative registration on all points listed in the
pointer config, and analyze_digital_twin_acc.py aligns D00 to D01 on all shared markers.
The refits here are for evaluation only and do not change those alignments.

Run:
  python analyze_registration.py <experiment dir>
  python analyze_registration.py --all <pilot_experiments> [--summary out.csv]
Outputs <exp>/registration_metrics.json (and the summary CSV for --all; default
<pilot_experiments>/registration_summary.csv).
"""

import argparse
import csv
import glob
import json
import os
import re
from collections import OrderedDict

import numpy as np
import yaml

FIDUCIALS = ["M-1", "M-3", "M-4", "M-5", "M-9"]
TARGETS = ["M-2", "M-7", "M-8"]


def norm_label(name):
    m = re.search(r"(\d+)$", name)
    return f"M-{int(m.group(1))}" if m else name


def load_mrk(path):
    markup = json.load(open(path))["markups"][0]
    flip = np.array([-1.0, -1.0, 1.0]) if markup.get("coordinateSystem", "LPS").upper() == "RAS" else 1.0
    return {norm_label(p["label"]): np.array(p["position"], float) * flip for p in markup["controlPoints"]}


def load_registration_output(exp):
    """Returns (source, target) dicts label -> position in mm."""
    path = os.path.join(exp, "config", "registration_output.json")
    txt = re.sub(r",(\s*[\]}])", r"\1", open(path).read())   # plugin writes trailing commas
    data = json.loads(txt)
    names = yaml.safe_load(open(os.path.join(exp, "config", "registration_config_pointer.yaml")))["pointer"]["name of points"]
    src = [np.array([p[k] for k in "xyz"], float) * 1000.0 for p in data["source_points"]]
    tgt = [np.array([p[k] for k in "xyz"], float) * 1000.0 for p in data["target_points"]]
    if not (len(names) == len(src) == len(tgt)):
        raise ValueError(f"{path}: {len(src)} source / {len(tgt)} target points for {len(names)} names")
    labels = [norm_label(n) for n in names]
    return dict(zip(labels, src)), dict(zip(labels, tgt)), path


def kabsch(a, b):
    ca, cb = a.mean(0), b.mean(0)
    u, _, vt = np.linalg.svd((a - ca).T @ (b - cb))
    d = np.sign(np.linalg.det(vt.T @ u.T))
    r = vt.T @ np.diag([1.0, 1.0, d]) @ u.T
    return r, cb - r @ ca


def fre_tre(src, tgt, fiducials, targets):
    missing = [k for k in fiducials + targets if k not in src or k not in tgt]
    if missing:
        raise ValueError(f"markers missing: {missing}")
    r, t = kabsch(np.array([src[k] for k in fiducials]), np.array([tgt[k] for k in fiducials]))
    err = {k: float(np.linalg.norm(r @ src[k] + t - tgt[k])) for k in fiducials + targets}
    rms = lambda ks: float(np.sqrt(np.mean([err[k] ** 2 for k in ks])))
    return OrderedDict([
        ("fre_rms_mm", rms(fiducials)),
        ("fre_max_mm", max(err[k] for k in fiducials)),
        ("tre_rms_mm", rms(targets)),
        ("tre_max_mm", max(err[k] for k in targets)),
        ("per_marker_mm", OrderedDict((k, err[k]) for k in fiducials + targets)),
    ])


def phantom_of(exp):
    cfg = yaml.safe_load(open(os.path.join(exp, "config", "gui_config.yaml")))
    d00 = cfg["fiducials_path"]
    return os.path.basename(d00).split("_")[0], d00


def analyze(exp, phantom_models, fiducials, targets):
    phantom, d00_path = phantom_of(exp)
    d01_path = os.path.join(phantom_models, f"{phantom}_D01", f"{phantom}_D01_M.mrk.json")
    src, tgt, reg_path = load_registration_output(exp)
    d00, d01 = load_mrk(d00_path), load_mrk(d01_path)

    res = OrderedDict()
    res["experiment"] = exp
    res["phantom"] = phantom
    res["fiducial_markers"] = fiducials
    res["target_markers"] = targets
    res["intraoperative"] = fre_tre(src, tgt, fiducials, targets)
    res["intraoperative"]["inputs"] = {"registration_output": reg_path,
                                       "source": "D00 markers in AMBF world", "target": "Atracsys pointer"}
    # Sanity check: source points must be the D00 markers (same shape, up to a rigid motion).
    labels = [k for k in src if k in d00]
    pd = lambda pts: np.linalg.norm(pts[:, None] - pts[None], axis=2)
    res["intraoperative"]["source_vs_d00_shape_max_mm"] = float(np.abs(
        pd(np.array([src[k] for k in labels])) - pd(np.array([d00[k] for k in labels]))).max())
    res["postoperative"] = fre_tre(d00, d01, fiducials, targets)
    res["postoperative"]["inputs"] = {"d00_markers": d00_path, "d01_markers": d01_path}
    with open(os.path.join(exp, "registration_metrics.json"), "w") as f:
        json.dump(res, f, indent=2)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("experiment", nargs="?", help="Experiment folder (with config/)")
    ap.add_argument("--all", default=None, help="pilot_experiments folder: every P*/<condition>/")
    ap.add_argument("--phantom-models", default=None, help="Default: <experiment>/../../phantom_models")
    ap.add_argument("--fiducials", default=",".join(FIDUCIALS), help="Markers used to fit (FRE)")
    ap.add_argument("--targets", default=",".join(TARGETS), help="Markers for evaluation only (TRE)")
    ap.add_argument("--summary", default=None, help="Summary CSV for --all")
    a = ap.parse_args()
    if bool(a.experiment) == bool(a.all):
        ap.error("give one experiment folder or --all <folder>")
    fid = [norm_label(x) for x in a.fiducials.split(",")]
    tar = [norm_label(x) for x in a.targets.split(",")]

    exps = ([os.path.abspath(a.experiment)] if a.experiment else
            sorted(os.path.dirname(os.path.dirname(p)) for p in
                   glob.glob(os.path.join(os.path.abspath(a.all), "P*", "*", "config", "registration_output.json"))))
    rows = []
    for exp in exps:
        models = a.phantom_models or os.path.join(exp, "..", "..", "phantom_models")
        r = analyze(exp, os.path.abspath(models), fid, tar)
        i, p = r["intraoperative"], r["postoperative"]
        print(f"{os.path.relpath(exp, os.path.dirname(os.path.dirname(exp)))} {r['phantom']}: "
              f"intraop FRE {i['fre_rms_mm']:.3f} TRE {i['tre_rms_mm']:.3f} mm; "
              f"postop FRE {p['fre_rms_mm']:.3f} TRE {p['tre_rms_mm']:.3f} mm")
        rows.append(OrderedDict(
            participant=os.path.basename(os.path.dirname(exp)), condition=os.path.basename(exp), phantom=r["phantom"],
            intraop_fre_rms_mm=round(i["fre_rms_mm"], 4), intraop_fre_max_mm=round(i["fre_max_mm"], 4),
            intraop_tre_rms_mm=round(i["tre_rms_mm"], 4), intraop_tre_max_mm=round(i["tre_max_mm"], 4),
            postop_fre_rms_mm=round(p["fre_rms_mm"], 4), postop_fre_max_mm=round(p["fre_max_mm"], 4),
            postop_tre_rms_mm=round(p["tre_rms_mm"], 4), postop_tre_max_mm=round(p["tre_max_mm"], 4)))
    if a.all:
        out = a.summary or os.path.join(os.path.abspath(a.all), "registration_summary.csv")
        with open(out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {out} ({len(rows)} experiments)")


if __name__ == "__main__":
    main()
