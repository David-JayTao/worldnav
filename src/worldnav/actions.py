"""Strict parsing of LCVN-Uni bin tokens; no missing-component zero fallback."""
import re
from .geometry import world_delta_to_local, wrap_angle


def decode_action(text, bin_step=.01):
    prefix = text.split("<image>",1)[0].strip()
    if prefix.lower() == "stop":
        return None
    if re.search(r"\bstop\b",prefix,re.I):
        raise ValueError("Ambiguous Stop mixed with other output")
    matches = re.findall(r"<(dx|dy|dyaw)_(pos|neg)_bin_(\d+)>",prefix)
    values = {}
    for axis,sign,index in matches:
        if axis in values:
            raise ValueError(f"Duplicate action component: {axis}")
        if int(index) > (282 if axis=="dyaw" else 246):
            raise ValueError(f"Action bin outside trained vocabulary: {axis}")
        values[axis] = round(int(index)*bin_step*(1 if sign=="pos" else -1),8)
    if set(values) != {"dx","dy","dyaw"}:
        raise ValueError("Missing or malformed action tokens")
    return [values[k] for k in ("dx","dy","dyaw")]


def adapt_action(action, frame, predicted_yaw):
    if frame == "canonical_world":
        return world_delta_to_local(action,predicted_yaw)
    if frame == "local":
        return [float(action[0]),float(action[1]),wrap_angle(action[2])]
    raise ValueError("model_action_frame must be canonical_world or local")


def normalize_generation_output(result):
    # The pinned official wrapper returns (response_ids, None), not a bare tensor.
    if isinstance(result,tuple):
        if len(result)!=2:
            raise ValueError("Unexpected generation tuple")
        result = result[0]
    if hasattr(result,"sequences"):
        result = result.sequences
    if getattr(result,"ndim",None)!=2 or result.shape[0]!=1:
        raise ValueError("Expected generated IDs with shape [1, tokens]")
    return result
