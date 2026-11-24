"""
Generate an AMBF digital twin of a drilled phantom by replaying a recording, then score it
against the ground-truth (post-drilling CT) segmentation. One run, fully unattended.

Replaces the manual workflow: SAINT GUI -> Run SAINT -> ros2 bag play -> Ctrl+L ->
Update Segmentation -> analyze_digital_twin_acc.py.

Steps
  1. Start ambf_simulator from <experiment>/config with the same arguments as the SAINT GUI's
     "Run SAINT" (taken from gui_config.yaml saint_run) plus --burr_diameter_mm and
     --voxel_removal_threshold.
  2. Wait for the volumetric drilling plugin's save_volume service.
  3. ros2 bag play <recording>/rosbag and wait for it to finish.
  4. Call save_volume to write the drilled volume as PNG slices into <out>/slices.
  5. Stop the simulator (SIGINT). AMBF currently aborts during shutdown even without these
     changes; that is ignored once the slices are saved.
  6. update_seg_nrrd_data_from_pngs.py -> <out>/<phantom>_D01_ambf.seg.nrrd
  7. analyze_digital_twin_acc.py -> <out>/<phantom>_D01_ambf_vs_gt.seg.nrrd + _metrics.json
  8. <out>/run.json with the parameters, removal statistics and headline metrics.

Inputs are derived from <experiment>/config/gui_config.yaml:
  twin reference (D00 seg)  = segmentation_path
  D00 markers               = fiducials_path
  ground truth              = <phantom models>/<phantom>_D01/<phantom>_D01_box_dental.seg.nrrd
                              and <phantom>_D01_M.mrk.json, where <phantom> (e.g. PL19) comes
                              from the segmentation file name.

Run from a shell with the SAINT workspace sourced (ambf_simulator and ros2 on PATH, the
python env with numpy/scipy/pynrrd/matplotlib active) and a display (the simulator does not
start with -g false):

    python replay_digital_twin.py \\
        --experiment .../pilot_experiments/P4/with-assistance \\
        --burr-mm 1.2 --threshold 30 \\
        --out .../pilot_experiments/P4/with-assistance/digital_twin/burr1.2_thr30
"""

import argparse
import datetime
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYZE_SCRIPT = os.path.join(HERE, "analyze_digital_twin_acc.py")
SERVICE_SUFFIX = "/volumetric_drilling/save_volume"
SERVICE_TYPE = "volumetric_drilling_msgs/srv/SaveVolume"


def log(msg):
    print(f"[replay {datetime.datetime.now():%H:%M:%S}] {msg}", flush=True)


# ------------------------------------------------------------------------ inputs

def load_gui_config(experiment):
    path = os.path.join(experiment, "config", "gui_config.yaml")
    with open(path) as f:
        return yaml.safe_load(f) or {}, path


def ambf_args(saint_run, burr_mm, threshold, show_gui):
    """Same arguments as the SAINT GUI's Run SAINT (RunSaintPanel._build_command in
    Saint-analysis-utils/src/saint_gui/saint_gui_main.py); keep the two in sync."""
    return [
        "--launch_file", "launch.yaml",
        "-l", "6,10,14",
        "--mute", "true",
        "--nt", "1",
        "--tf_list", "tf_config_drill.yaml",
        "--cpf", "main_camera_info.yaml",
        "--hmd_window_disp", str(saint_run.get("hmd_window_disp", 0.1)),
        "--fix_sagittal_slice", "true" if saint_run.get("fix_sagittal_slice", True) else "false",
        "--sagittal_slice_idx", str(saint_run.get("sagittal_slice_idx", 70)),
        "--hmd_window_offset_h", str(saint_run.get("hmd_window_offset_h", 0.0)),
        "--hmd_window_offset_v", str(saint_run.get("hmd_window_offset_v", 0.0)),
        "--burr_diameter_mm", str(burr_mm),
        "--voxel_removal_threshold", str(threshold),
        "-g", "true" if show_gui else "false",
    ]


def find_recording(experiment, recording):
    if recording:
        rec = recording
    else:
        candidates = sorted(os.path.dirname(p) for p in glob.glob(os.path.join(experiment, "rec*", "*", "rosbag")))
        if len(candidates) != 1:
            raise SystemExit(f"Pass --recording: found {len(candidates)} recordings under {experiment}/rec*: {candidates}")
        rec = candidates[0]
    bag = os.path.join(rec, "rosbag")
    if not os.path.isdir(bag):
        raise SystemExit(f"No rosbag folder in recording: {bag}")
    return rec, bag


def find_ground_truth(phantom, phantom_models):
    gt_dir = os.path.join(phantom_models, f"{phantom}_D01")
    seg = os.path.join(gt_dir, f"{phantom}_D01_box_dental.seg.nrrd")
    markers = os.path.join(gt_dir, f"{phantom}_D01_M.mrk.json")
    for p in (seg, markers):
        if not os.path.isfile(p):
            raise SystemExit(f"Ground-truth file not found: {p} (set --phantom-models or --gt/--gt-markers)")
    return seg, markers


# ------------------------------------------------------------------- processes

def wait_for_service(env, ambf_proc, timeout_s):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if ambf_proc.poll() is not None:
            raise RuntimeError(f"ambf_simulator exited early (code {ambf_proc.returncode}); see ambf.log")
        out = subprocess.run(["ros2", "service", "list"], env=env, capture_output=True, text=True).stdout
        for line in out.splitlines():
            if line.strip().endswith(SERVICE_SUFFIX):
                return line.strip()
        time.sleep(1.0)
    raise RuntimeError(f"save_volume service did not appear within {timeout_s} s; see ambf.log")


def call_save_volume(env, service, output_dir, timeout_s=300):
    req = "{output_dir: '%s'}" % output_dir
    res = subprocess.run(["ros2", "service", "call", service, SERVICE_TYPE, req],
                         env=env, capture_output=True, text=True, timeout=timeout_s)
    text = res.stdout + res.stderr
    ok = re.search(r"success=True", text) is not None
    n = re.search(r"num_slices=(\d+)", text)
    msg = re.search(r"message='([^']*)'", text)
    return ok, int(n.group(1)) if n else 0, msg.group(1) if msg else text.strip()


def parse_removal_stats(message):
    stats = {}
    for k, v in re.findall(r"(\w+)=([-\d.eE+]+)", message):
        stats[k] = float(v) if any(c in v for c in ".eE") else int(v)
    return stats


def stop(proc, name, timeout_s=15):
    if proc.poll() is not None:
        return
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout_s)
    except subprocess.TimeoutExpired:
        log(f"{name} did not exit after SIGINT, killing")
        proc.kill()
        proc.wait()


# ------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--experiment", required=True, help="Experiment folder (with config/gui_config.yaml)")
    ap.add_argument("--recording", default=None, help="Recording folder with rosbag/ (default: the only one under <experiment>/rec*/)")
    ap.add_argument("--burr-mm", type=float, required=True, help="Simulated burr diameter (mm)")
    ap.add_argument("--threshold", type=int, required=True, help="Voxel removal threshold (voxels per physics step)")
    ap.add_argument("--out", required=True, help="Output folder for this run")
    ap.add_argument("--phantom-models", default=None,
                    help="Folder with <phantom>_D01/ ground truth (default: <experiment>/../../phantom_models)")
    ap.add_argument("--gt", default=None, help="Ground-truth D01 .seg.nrrd (overrides --phantom-models)")
    ap.add_argument("--gt-markers", default=None, help="Ground-truth D01 markers .mrk.json (with --gt)")
    ap.add_argument("--bag-rate", type=float, default=1.0, help="ros2 bag play --rate (default 1.0)")
    ap.add_argument("--ros-domain-id", type=int, default=None,
                    help="ROS_DOMAIN_ID for this run (default: inherited). Use different ids to run in parallel.")
    ap.add_argument("--ambf", default=None, help="ambf_simulator executable (default: from PATH)")
    ap.add_argument("--no-gui", action="store_true", help="Pass -g false (currently crashes AMBF on load)")
    ap.add_argument("--startup-timeout", type=float, default=120.0)
    ap.add_argument("--settle-s", type=float, default=3.0, help="Wait after service appears / bag ends (s)")
    ap.add_argument("--physics-log", action="store_true",
                    help="Ask the drilling plugin for a per-physics-step diagnostic log (<out>/physics_log.csv): "
                         "step timing, tip contact, voxels removed, tip goal/proxy voxel position")
    ap.add_argument("--keep-slices", action="store_true", help="Keep the PNG slices (deleted after the seg.nrrd is written by default)")
    args = ap.parse_args()

    experiment = os.path.abspath(args.experiment)
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    slices_dir = os.path.join(out, "slices")
    if os.path.isdir(slices_dir) and os.listdir(slices_dir):
        raise SystemExit(f"{slices_dir} already has files; use a new --out")

    cfg, cfg_path = load_gui_config(experiment)
    config_dir = os.path.join(experiment, cfg.get("output_dir_structure", {}).get("config_dir", "config"))
    twin_ref = cfg["segmentation_path"]
    d00_markers = cfg["fiducials_path"]
    update_script = cfg["script_paths"]["update_seg_nrrd_script"]
    for p in (twin_ref, d00_markers, update_script, ANALYZE_SCRIPT, os.path.join(config_dir, "launch.yaml")):
        if not os.path.isfile(p):
            raise SystemExit(f"Not found: {p} (check {cfg_path})")

    m = re.match(r"(.+?)_D\d\d", os.path.basename(twin_ref))
    if not m:
        raise SystemExit(f"Cannot get phantom id from {twin_ref} (expected <phantom>_D00_...)")
    phantom = m.group(1)
    if args.gt:
        gt_seg, gt_markers = args.gt, args.gt_markers
        if not gt_markers:
            raise SystemExit("--gt needs --gt-markers")
    else:
        models = args.phantom_models or os.path.join(experiment, "..", "..", "phantom_models")
        gt_seg, gt_markers = find_ground_truth(phantom, os.path.abspath(models))
    rec, bag = find_recording(experiment, args.recording)

    ambf = args.ambf or shutil.which("ambf_simulator")
    if not ambf:
        raise SystemExit("ambf_simulator not on PATH (source the SAINT workspace) or pass --ambf")
    if shutil.which("ros2") is None:
        raise SystemExit("ros2 not on PATH (source the SAINT workspace)")
    if not args.no_gui and not os.environ.get("DISPLAY"):
        raise SystemExit("No DISPLAY set; the simulator needs a display (e.g. export DISPLAY=:1)")

    env = dict(os.environ)
    if args.ros_domain_id is not None:
        env["ROS_DOMAIN_ID"] = str(args.ros_domain_id)

    twin_seg = os.path.join(out, f"{phantom}_D01_ambf.seg.nrrd")
    run = {
        "experiment": experiment, "recording": rec, "phantom": phantom,
        "burr_diameter_mm": args.burr_mm, "voxel_removal_threshold": args.threshold,
        "bag_rate": args.bag_rate, "ros_domain_id": env.get("ROS_DOMAIN_ID"),
        "started": datetime.datetime.now().isoformat(timespec="seconds"),
        "twin_ref": twin_ref, "gt": gt_seg, "twin": twin_seg,
    }
    log(f"{phantom}: burr {args.burr_mm} mm, threshold {args.threshold}, recording {rec}")

    # 1-2. Simulator.
    cmd = [ambf] + ambf_args(cfg.get("saint_run", {}) or {}, args.burr_mm, args.threshold, not args.no_gui)
    if args.physics_log:
        run["physics_log"] = os.path.join(out, "physics_log.csv")
        cmd += ["--physics_log", run["physics_log"]]
    run["ambf_command"] = cmd
    ambf_log = open(os.path.join(out, "ambf.log"), "w")
    t0 = time.time()
    ambf_proc = subprocess.Popen(cmd, cwd=config_dir, env=env, stdout=ambf_log, stderr=subprocess.STDOUT)
    try:
        service = wait_for_service(env, ambf_proc, args.startup_timeout)
        log(f"simulator ready ({time.time() - t0:.0f} s), service {service}")
        time.sleep(args.settle_s)

        # 3. Replay.
        bag_cmd = ["ros2", "bag", "play", bag, "--rate", str(args.bag_rate)]
        log(f"playing {bag}")
        t1 = time.time()
        with open(os.path.join(out, "bag.log"), "w") as bag_log:
            bag_proc = subprocess.run(bag_cmd, env=env, stdout=bag_log, stderr=subprocess.STDOUT)
        run["bag_seconds"] = round(time.time() - t1, 1)
        if bag_proc.returncode != 0:
            raise RuntimeError(f"ros2 bag play failed (code {bag_proc.returncode}); see bag.log")
        if ambf_proc.poll() is not None:
            raise RuntimeError(f"ambf_simulator exited during replay (code {ambf_proc.returncode}); see ambf.log")
        log(f"replay done ({run['bag_seconds']} s)")
        time.sleep(args.settle_s)

        # 4. Save slices.
        ok, n, message = call_save_volume(env, service, slices_dir)
        run["save_volume"] = {"success": ok, "num_slices": n, "message": message}
        run["removal_stats"] = parse_removal_stats(message)
        if not ok:
            raise RuntimeError(f"save_volume failed: {message}")
        log(f"saved {n} slices; {message}")
    finally:
        # 5. Stop the simulator.
        stop(ambf_proc, "ambf_simulator")
        ambf_log.close()

    # 6. Slices -> seg.nrrd.
    log("updating segmentation from slices")
    subprocess.run([sys.executable, update_script, "-n", twin_ref, "-s", slices_dir, "-p", "plane00", "-o", twin_seg],
                   check=True, stdout=open(os.path.join(out, "update_seg.log"), "w"), stderr=subprocess.STDOUT)

    # 7. Compare with ground truth.
    log("comparing with ground truth")
    subprocess.run([sys.executable, ANALYZE_SCRIPT, "--twin", twin_seg, "--twin-ref", twin_ref,
                    "--twin-markers", d00_markers, "--gt", gt_seg, "--gt-markers", gt_markers],
                   check=True, stdout=open(os.path.join(out, "analyze.log"), "w"), stderr=subprocess.STDOUT)
    metrics_path = re.sub(r"\.seg\.nrrd$", "", twin_seg) + "_vs_gt_metrics.json"
    with open(metrics_path) as f:
        metrics = json.load(f)

    if not args.keep_slices:
        shutil.rmtree(slices_dir)

    # 8. Summary.
    run["metrics_file"] = metrics_path
    run["dice"] = metrics.get("dice", {})
    run["drilled"] = metrics.get("drilled", {})
    run["marker_rmse_mm"] = metrics["registration"]["marker_rmse_mm"]
    run["total_seconds"] = round(time.time() - t0, 1)
    with open(os.path.join(out, "run.json"), "w") as f:
        json.dump(run, f, indent=2)

    d = run["drilled"]
    log(f"DONE in {run['total_seconds']} s: drilled Dice {run['dice'].get('drilled', float('nan')):.4f}, "
        f"sim/real {d.get('sim_over_real', float('nan')):.3f}, real covered {100 * d.get('recall_real_covered_by_sim', float('nan')):.1f}%, "
        f"sim inside real {100 * d.get('precision_sim_inside_real', float('nan')):.1f}%")
    log(f"results in {out}")


if __name__ == "__main__":
    main()
