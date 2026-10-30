"""Real data and official metric smoke test. Does NOT run a navigation model."""
import copy
import datetime
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import pickle
import sys
import subprocess
import tarfile
import time
import urllib.request
import zipfile

import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from validate_predictions import validate, validate_zip, load_json

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("WORLDNAV_SMOKE_OUTPUT", ROOT / "outputs" / ("smoke_" + datetime.datetime.now().strftime("%Y%m%dT%H%M%S%f"))))
DATA = ROOT / "data/lcvn"


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def reconstruct(actions, initial_pose):
    """Translate in the CURRENT body frame, then add wrapped yaw increment."""
    x, y, yaw = map(float, initial_pose)
    xy, yaws = [[x, y]], [yaw]
    for dx, dy, dyaw in actions:
        x, y = x + math.cos(yaw)*dx - math.sin(yaw)*dy, y + math.sin(yaw)*dx + math.cos(yaw)*dy
        yaw += math.atan2(math.sin(dyaw), math.cos(dyaw))
        xy.append([x, y])
        yaws.append(yaw)  # continuous yaw for the official heading metric
    return xy, yaws


def official_metrics(metric, actions, pos, yaw):
    pred, pred_yaw = reconstruct(actions, [*pos[0], yaw[0]])
    avg_step = float(np.linalg.norm(np.diff(pos, axis=0), axis=1).mean())
    sr = metric.success_rate(pred, pos[-1], avg_step)
    ate = metric.absolute_trajectory_error(pred, pos)
    rpe = metric.relative_pose_error(pred, pos)
    f = metric.full_route_fidelity(pred, pos)
    h = metric.heading_and_turn_fidelity(pred, pred_yaw, pos.tolist(), yaw.tolist())
    score = 100*f*(1+h)/2*(.70+.10*sr+.10/(1+ate)+.10/(1+rpe))
    return dict(SR=sr, ATE=ate, RPE=rpe, full_route_fidelity=f,
                heading_turn_fidelity=h, Score=score), pred


def prepare_data():
    prefix = ROOT / "outputs/first_round/val_seen_prefix.tar"
    if not prefix.exists():
        prefix = OUT / "val_seen_prefix.tar"
    url = "https://huggingface.co/datasets/fly1113/LCVN/resolve/main/val_seen.tar"
    if not prefix.exists():
        req = urllib.request.Request(url, headers={"Range": "bytes=0-16777215"})
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status != 206 or not response.headers.get("Content-Range", "").startswith("bytes 0-"):
                raise RuntimeError("Server did not honor the byte range; refusing full download")
            prefix.write_bytes(response.read(16777216))
    selected, routes = [], set()
    with tarfile.open(prefix, mode="r:") as archive:
        for member in archive:
            if not member.isfile():
                continue
            path = Path(member.name)
            if len(path.parts) != 3 or path.parts[0] != "val_seen" or ".." in path.parts:
                raise ValueError(f"Unexpected archive path: {member.name}")
            eid = path.parts[1]
            route = eid.rsplit("_", 1)[0]
            if route not in routes:
                if len(routes) == 3:
                    break
                routes.add(route)
            dest = DATA / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            content = archive.extractfile(member).read()
            if dest.exists():
                if dest.read_bytes() != content:
                    raise ValueError(f"Existing sample differs; preserved: {dest}")
            else:
                dest.write_bytes(content)
            if path.name == "traj_data.pkl":
                selected.append(eid)
    if len(selected) != 9:
        raise RuntimeError(f"Expected 3 routes x 3 instruction styles; got {len(selected)}")
    write(OUT / "data_provenance.json", dict(url=url, archive_total_bytes=7409704960,
          downloaded_bytes=prefix.stat().st_size, range="bytes=0-16777215",
          prefix_sha256=hashlib.sha256(prefix.read_bytes()).hexdigest(),
          selected_episode_ids=selected, unique_routes=len(routes),
          selection="first three trajectory groups in archive, all three styles; not random"))
    return selected


def entry_preflight():
    # No weights are supplied: stop on missing dependencies; never download a base model.
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="", HF_HUB_OFFLINE="1",
               TRANSFORMERS_OFFLINE="1", WANDB_MODE="disabled")
    uni_args = ["train.py", "--model", "anole", "--data", "val_seen", "--data_dir", str(DATA),
                "--decoder_type", "anole", "--image_seq_length", "784", "--input_format", "anole",
                "--output", str(OUT / "baseline_attempt"), "--note", "first_round",
                "--report_to", "none", "--do_task_level_eval"]
    attempts = []
    for name, folder, args in [("uni_entry_attempt", "lcvn-uni", uni_args),
        ("ac_entry_attempt", "lcvn-ac", ["-m", "lcvn_ac.scripts.test_single_trajectory_real_dfot", "--help"])]:
        started = time.monotonic()
        cmd = [sys.executable, *args]
        result = subprocess.run(cmd, cwd=ROOT / "vendor/LCVN" / folder, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=45)
        (OUT / f"{name}.log").write_text("$ " + " ".join(cmd) +
            "\nCPU-only offline entry preflight; not successful inference.\n" + result.stdout)
        attempts.append(dict(name=name, command=cmd, exit_code=result.returncode,
                             seconds=time.monotonic()-started, forward_pass_completed=False))
        if result.returncode == 0:
            raise RuntimeError("Environment changed: inspect entry before proceeding without checkpoint")
    write(OUT / "entry_attempts.json", attempts)
    return attempts


def main():
    started = time.monotonic()
    OUT.mkdir(parents=True, exist_ok=False)
    selected = prepare_data()
    metric = module("official_worldnav_metrics", ROOT / "vendor/track1/demonstration.py")
    action = module("official_action_utils", ROOT / "vendor/LCVN/lcvn-uni/scripts/action_utils.py")
    samples, controls, checks = [], [], []
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    plotted = set()
    for eid in selected:
        folder = DATA / "val_seen" / eid
        # These pickles came only from the explicitly requested official dataset archive.
        with (folder / "traj_data.pkl").open("rb") as stream:
            raw = pickle.load(stream)
        pos, yaw, delta = np.asarray(raw["position"]), np.asarray(raw["yaw"]), np.asarray(raw["delta"])
        assert pos.shape == (len(yaw), 2) and delta.shape == (len(yaw)-1, 3)
        assert np.isfinite(pos).all() and np.isfinite(yaw).all() and np.isfinite(delta).all()
        diff = np.diff(pos, axis=0)
        local = np.column_stack((np.cos(yaw[:-1])*diff[:, 0]+np.sin(yaw[:-1])*diff[:, 1],
                                 -np.sin(yaw[:-1])*diff[:, 0]+np.cos(yaw[:-1])*diff[:, 1],
                                 np.arctan2(np.sin(np.diff(yaw)), np.cos(np.diff(yaw)))))
        local = local.tolist()
        # Reference-derived controls ONLY: never model predictions.
        metrics, recovered = official_metrics(metric, local, pos, yaw)
        wrong_metrics, wrong = official_metrics(metric, delta.tolist(), pos, yaw)
        error = float(np.max(np.abs(np.asarray(recovered)-pos)))
        assert error < 1e-10 and metrics["ATE"] < 1e-10 and metrics["Score"] > 99.99999
        global_error = float(np.max(np.abs(delta[:, :2] - diff)))
        checks.append(dict(episode_id=eid, delta_global_difference_max_error=global_error,
                           reference_roundtrip_max_position_error=error,
                           reference_roundtrip_metrics=metrics,
                           incorrect_global_as_local_metrics=wrong_metrics))
        with Image.open(folder / "0.jpg") as image:
            image.load()
            image_info = dict(mode=image.mode, size=list(image.size))
            rgb = image.convert("RGB").resize((256, 256))
            assert rgb.size == (256, 256) and rgb.mode == "RGB"
        samples.append(dict(episode_id=eid, source="official val_seen.tar partial range",
            initial_image=str((folder / "0.jpg").relative_to(ROOT)), image=image_info,
            instruction=raw["instruction"], pkl_fields={k: dict(type=type(v).__name__,
                shape=list(v.shape)) if hasattr(v, "shape") else dict(type=type(v).__name__)
                for k, v in raw.items()}, reference_action_count=len(local),
            reference_first_global_delta=delta[0].tolist(), reference_first_local_action=local[0],
            official_reference_action_token=action.action_to_text(delta[0].tolist()),
            model_forward_completed=False, predicted_action_count=None, prediction=None))
        controls.append(dict(episode_id=eid, actions=local))
        route = eid.rsplit("_", 1)[0]
        if route not in plotted:
            ax = axes[len(plotted)]
            ax.plot(pos[:, 0], pos[:, 1], "k-o", ms=3, label="Recorded reference")
            ax.plot(np.asarray(recovered)[:, 0], np.asarray(recovered)[:, 1], "g--", label="Reference round-trip")
            ax.plot(np.asarray(wrong)[:, 0], np.asarray(wrong)[:, 1], "r--", label="Wrong frame control")
            ax.set_title(f"Route {len(plotted)+1} (not model output)")
            ax.set_aspect("equal", adjustable="datalim")
            ax.set_xlabel("X (dataset units)"); ax.set_ylabel("Y (dataset units)")
            plotted.add(route)
    axes[0].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(OUT / "coordinate_controls.png", dpi=150); plt.close(fig)
    write(OUT / "samples.json", samples)
    write(OUT / "coordinate_checks.json", checks)
    oracle = dict(split="val_seen", episodes=controls)
    write(OUT / "controls/reference_roundtrip_val_seen.json", oracle)
    validate(load_json(json.dumps(oracle)), "val_seen", selected, full=True)
    placeholder = dict(split="val_seen", episodes=[dict(episode_id=x, actions=[[0., 0., 0.]]) for x in selected])
    write(OUT / "controls/format_only_val_seen.json", placeholder)
    local_validation = validate(load_json(json.dumps(placeholder)), "val_seen", selected, full=True)
    # 'selected' is a LOCAL sample list, not the unavailable official full manifest.
    local_validation["manifest_scope"] = "local extracted samples only, NOT official full manifest"
    local_validation["official_full_manifest_checked"] = False
    with zipfile.ZipFile(OUT / "LOCAL_FORMAT_ONLY_NOT_SUBMISSION.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("val_seen.json", json.dumps(placeholder, allow_nan=False))
    rejected = {}
    invalid_cases = {}
    for name, replacement in [("NaN", [float("nan"), 0, 0]), ("Inf", [float("inf"), 0, 0]),
        ("bool", [True, 0, 0]), ("string", ["0", 0, 0]), ("wrong_shape", [0, 0]),
        ("translation_norm", [2., 2., 0]), ("yaw_limit", [0, 0, 6.3])]:
        value = copy.deepcopy(placeholder); value["episodes"][0]["actions"] = [replacement]; invalid_cases[name] = value
    value = copy.deepcopy(placeholder); value["episodes"].append(value["episodes"][0]); invalid_cases["duplicate_id"] = value
    value = copy.deepcopy(placeholder); value["episodes"].pop(); invalid_cases["missing_local_id"] = value
    value = copy.deepcopy(placeholder); value["episodes"][0]["actions"] *= 65; invalid_cases["too_many_actions"] = value
    value = copy.deepcopy(placeholder); value["split"] = "test"; invalid_cases["wrong_split"] = value
    for name, data in invalid_cases.items():
        try: validate(data, "val_seen", selected, full=True)
        except ValueError as exc: rejected[name] = str(exc)
        else: raise AssertionError(f"Failed to reject {name}")
    try: validate_zip(OUT / "LOCAL_FORMAT_ONLY_NOT_SUBMISSION.zip", 1, {})
    except ValueError as exc: rejected["incomplete_phase1_zip"] = str(exc)
    else: raise AssertionError("Accepted an incomplete submission ZIP")
    try: validate(placeholder, "val_seen", full=True)
    except ValueError as exc: rejected["full_validation_without_manifest"] = str(exc)
    else: raise AssertionError("Full validation needs official manifest")
    write(OUT / "format_checks.json", dict(local_sample_check=local_validation,
        official_full_manifest_verified=False, formal_submission_ready=False,
        official_example_download="HTTP 404 from the UI's published download routes; unauthenticated dataset API HTTP 403",
        expected_public_counts={"val_seen":10806,"val_unseen":4500}, negative_cases_rejected=rejected))
    attempts = entry_preflight()
    versions = {}
    for package in ["torch", "torchvision", "transformers", "numpy", "scipy", "Pillow", "matplotlib", "diffusers", "flash-attn", "peft"]:
        try: versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError: versions[package] = "MISSING"
    write(OUT / "software_versions.json", versions)
    status = dict(timestamp=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),
        status="SMOKE_TEST_ONLY_BASELINE_BLOCKED", real_input_episodes=len(samples), unique_trajectory_groups=len(plotted),
        model_inference_episodes=0, baseline_evaluated_episodes=0,
        baseline_metrics={k:None for k in ["SR","ATE","RPE","full_route_fidelity","heading_turn_fidelity","Score"]},
        GPU_used=False, model_peak_GPU_memory_MiB=None, OOM_observed=False,
        smoke_seconds=time.monotonic()-started, entry_attempts=attempts,
        blockers=["No usable trained LCVN checkpoint found in inspected local/official sources",
                  "Uni fork Transformers dependency and FlashAttention unavailable",
                  "Official full CodaBench manifest download unavailable without a working download/session"],
        controls="Reference-derived round-trip only, NOT model output or baseline scores")
    write(OUT / "status.json", status)
    print(json.dumps(status, indent=2, ensure_ascii=False))
    print("PASS: 9 real episodes, coordinate round-trip and official metric functions; 13 negative format cases rejected.")


if __name__ == "__main__":
    main()
