"""CPU-only experimental Cosmos prompt/output contract; no model loader.

This contract is project-designed, not an NVIDIA navigation policy. Real model
compliance and navigation accuracy have not been validated.
"""
from .data import Observation
from .protocol import load_json,validate

SYSTEM_PROMPT = '''You plan an open-loop robot route from one initial RGB image and an instruction.
Return only a JSON object {"actions": [[dx, dy, dyaw], ...]}.
Each action translates in the robot's CURRENT body frame (x forward, y left),
then updates yaw counterclockwise in radians. Do not use world-frame deltas.
Use at most 64 actions. Each translation must have Euclidean length <= 2.46
in dataset units, and absolute dyaw <= 6.29. An empty list means stop.
No future images, reference trajectory, numeric starting pose, or map are available.
Do not invent observations. Do not output reasoning, markdown or additional keys.'''


def build_messages(observation):
    if not isinstance(observation,Observation): raise TypeError('Expected isolated Observation')
    return [{'role':'system','content':[{'type':'text','text':SYSTEM_PROMPT}]},
            {'role':'user','content':[{'type':'image','image':observation.image},
                                     {'type':'text','text':observation.instruction}]}]


def parse_actions(text):
    """Strict JSON body-frame actions, deliberately separate from LCVN tokens."""
    result=load_json(text)
    if not isinstance(result,dict) or set(result)!={'actions'}:
        raise ValueError('Cosmos experimental contract requires exactly the actions key')
    validate({'split':'test','episodes':[{'episode_id':'parse_check','actions':result['actions']}]},'test')
    return result['actions']
