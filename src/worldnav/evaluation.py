"""Invoke pinned public demonstration.py, not the private CodaBench scorer."""
import importlib.util
import math
from pathlib import Path
from .geometry import canonical_reference, integrate

ROOT = Path(__file__).resolve().parents[2]


def load_metrics(path=None):
    path = Path(path or ROOT/"vendor/track1/demonstration.py")
    spec = importlib.util.spec_from_file_location("worldnav_official_metrics",path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluate(actions, position, yaw, metric=None):
    metric = metric or load_metrics()
    ref, ref_yaw = canonical_reference(position,yaw)
    pred,pred_yaw = integrate(actions)
    average = sum(math.dist(a,b) for a,b in zip(ref,ref[1:]))/(len(ref)-1)
    sr = metric.success_rate(pred,ref[-1],average)
    ate = metric.absolute_trajectory_error(pred,ref)
    rpe = metric.relative_pose_error(pred,ref)
    f = metric.full_route_fidelity(pred,ref)
    h = metric.heading_and_turn_fidelity(pred,pred_yaw,ref,ref_yaw)
    score = 100*f*(1+h)/2*(.7+.1*sr+.1/(1+ate)+.1/(1+rpe))
    return dict(SR=sr,ATE=ate,RPE=rpe,full_route_fidelity=f,heading_turn_fidelity=h,Score=score)
