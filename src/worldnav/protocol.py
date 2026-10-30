"""Local checks based on the public WorldNav rules; private scorer not reproduced."""
import argparse
import json
import math
from pathlib import Path
import zipfile


def load_json(text):
    def invalid(value):
        raise ValueError(f"Non-finite JSON constant: {value}")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(text, parse_constant=invalid, object_pairs_hook=unique)


def validate(data, split, expected_ids=None, full=False):
    if split not in {"val_seen", "val_unseen", "test"}:
        raise ValueError("Unknown split")
    if not isinstance(data, dict) or data.get("split") != split:
        raise ValueError("Incorrect split")
    episodes = data.get("episodes")
    if not isinstance(episodes, list):
        raise ValueError("episodes must be a list")
    ids = set()
    for episode in episodes:
        if not isinstance(episode, dict):
            raise ValueError("Episode must be an object")
        eid = episode.get("episode_id")
        if not isinstance(eid, str) or not eid or eid in ids:
            raise ValueError(f"Missing or duplicate episode_id: {eid}")
        ids.add(eid)
        actions = episode.get("actions")
        if not isinstance(actions, list) or len(actions) > 64:
            raise ValueError(f"{eid}: actions must be a list with at most 64 entries")
        for action in actions:
            if not isinstance(action, list) or len(action) != 3:
                raise ValueError(f"{eid}: action must be [dx, dy, dyaw]")
            if any(type(v) not in (int, float) or not math.isfinite(v) for v in action):
                raise ValueError(f"{eid}: actions require finite numbers, excluding bool")
            dx, dy, dyaw = action
            if math.hypot(dx, dy) > 2.46 or abs(dyaw) > 6.29:
                raise ValueError(f"{eid}: public action limit exceeded")
    if expected_ids is not None:
        expected_ids = list(expected_ids)
        expected = set(expected_ids)
        if len(expected) != len(expected_ids):
            raise ValueError("Duplicate IDs in manifest")
        if ids - expected:
            raise ValueError("Unknown episode IDs")
        if full and ids != expected:
            raise ValueError(f"Missing {len(expected - ids)} episodes")
    elif full:
        raise ValueError("Full validation requires the official manifest")
    return {"split": split, "episodes": len(ids),
            "manifest_checked": expected_ids is not None, "full": full}


def validate_zip(path, phase, manifests):
    if phase not in (1,2):
        raise ValueError("phase must be 1 or 2")
    required = {"val_seen.json", "val_unseen.json"} if phase == 1 else {"test.json"}
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(required) or set(names) != required:
            raise ValueError(f"Required root files: {sorted(required)}; got {names}")
        return [validate(load_json(archive.read(name)), name[:-5],
                         manifests.get(name[:-5]), full=True) for name in sorted(required)]
