"""Frozen zero-shot prompt variants, selected only with a separate development set."""


def get_prompt(version):
    from .qwen_api import SYSTEM_PROMPT
    if version=='qwen_worldnav_zero_shot_v1':return SYSTEM_PROMPT
    if version=='qwen_worldnav_structured_v2':
        return SYSTEM_PROMPT+'''
Before emitting the JSON, internally identify the traversable corridor/path, the
instruction's ordered landmarks, the intended side of each turn, and the stop
landmark. Keep this analysis private. Match the route's shape to those visible
landmarks. A right turn requires negative yaw and a left turn positive yaw.
Represent each major turn explicitly with rotation followed by movement.
Use short commands near turns. Do not replace a multi-part instruction with one
straight line. Stop at the instructed landmark instead of extending the route.
Return only the final actions JSON, without an intermediate plan or explanation.'''
    if version=='qwen_worldnav_scale_v3':
        return SYSTEM_PROMPT+'''
Use conservative metric-scale navigation grounded in the actual image, not the
largest legal displacement. The 2.46 limit is a bound, NOT a default step length.
For indoor scenes, begin with small 0.15-0.35 unit translation increments; for
outdoor paths begin with 0.3-0.8 unit increments, adjusting from apparent geometry
and instruction distance. These are planning priors, not reference labels.
Preserve all turns and route segments described in the instruction. Do not
interpret a command count as a physical distance. Rotation-only actions are
appropriate before a turn: roughly +/-1.57 rad is a 90 degree left/right turn.
For a gradual bend use small signed yaw changes. Avoid unintended lateral drift.
Choose enough commands to cover the described route, up to 64, and end precisely
at the requested landmark. Do not output your analysis; only the actions JSON.'''
    raise ValueError('Unknown frozen prompt version')
