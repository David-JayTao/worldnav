"""Read official data; expose only an initial image and instruction to policies."""
from dataclasses import dataclass
import io
import json
from pathlib import Path
import pickle
import re
import numpy as np
from PIL import Image


class RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        allowed = {
            ("numpy", "ndarray"): np.ndarray,
            ("numpy", "dtype"): np.dtype,
            ("numpy.core.multiarray", "_reconstruct"): np.core.multiarray._reconstruct,
            ("numpy.core.multiarray", "scalar"): np.core.multiarray.scalar,
            ("numpy._core.multiarray", "_reconstruct"): np.core.multiarray._reconstruct,
            ("numpy._core.multiarray", "scalar"): np.core.multiarray.scalar,
            ("numpy.core.numeric", "_frombuffer"): np.core.numeric._frombuffer,
            ("numpy._core.numeric", "_frombuffer"): np.core.numeric._frombuffer,
        }
        if (module,name) not in allowed:
            raise pickle.UnpicklingError(f"Disallowed pickle global: {module}.{name}")
        return allowed[module,name]


def read_reference_bytes(content):
    raw = RestrictedUnpickler(io.BytesIO(content)).load()
    if not isinstance(raw, dict):
        raise ValueError("Trajectory metadata must be a mapping")
    pos = np.asarray(raw["position"],dtype=float)
    yaw = np.asarray(raw["yaw"],dtype=float).reshape(-1)
    if pos.shape != (len(yaw),2) or len(yaw)<2 or not np.isfinite(pos).all() or not np.isfinite(yaw).all():
        raise ValueError("Invalid reference position/yaw")
    if not isinstance(raw.get("instruction"),str) or not raw["instruction"].strip():
        raise ValueError("Instruction must be nonempty text")
    return raw


def safe_episode_id(eid):
    if not isinstance(eid,str) or not re.fullmatch(r"[A-Za-z0-9_.-]+",eid) or eid in {".",".."}:
        raise ValueError("Unsafe episode ID")
    return eid


@dataclass(frozen=True)
class Observation:
    """The sole model input boundary: no reference pose, goal or future frames."""
    image: Image.Image
    instruction: str


def load_observation(root, item):
    folder = Path(root)/"samples"/item["split"]/safe_episode_id(item["episode_id"])
    instruction = json.loads((folder/"input.json").read_text())["instruction"]
    with Image.open(folder/"0.jpg") as img:
        image = img.convert("RGB").copy()
    return Observation(image=image,instruction=instruction)


def load_reference(root, item):
    path = Path(root)/"samples"/item["split"]/safe_episode_id(item["episode_id"])/"traj_data.pkl"
    return read_reference_bytes(path.read_bytes())
