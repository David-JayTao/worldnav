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
    if version=='research_structured_v1':
        return STRUCTURED_PROMPT
    extra=RESEARCH_VARIANTS.get(version)
    if extra is not None:return get_prompt('qwen_worldnav_scale_v3')+extra
    raise ValueError('Unknown frozen prompt version')


# New hypotheses frozen before development runs; old V1/V2/V3 text unchanged.
RESEARCH_VARIANTS={
'research_scale_v1':"""
Scale-only ablation: estimate the extent of EACH route segment from the visible
corridor or outdoor path. Distinguish nearby (0.1-0.25), middle (0.25-0.5), and
far straight travel (0.5-0.8) action granularity. Subdivide longer segments into
bounded actions rather than multiplying a whole route by one scale. Do not
add distance merely to reach a target action count. State no intermediate plan.""",
'research_stop_v1':"""
Stop-only ablation: resolve the exact terminal clause (stop, end, until, before,
at, just past) and the named target landmark. Distinguish reaching a target from
passing it. Plan a final approach separately: use short 0.1-0.2 increments near
the target, and stop on the specified side. Do not continue an otherwise plausible
corridor beyond the requested endpoint. Keep every earlier route instruction.""",
'research_turn_v1':"""
Turn-only ablation: ground every turn in its ordered landmark. Account explicitly
for the approach BEFORE turning and the departure AFTER turning. Use rotation-only
actions at the actual turn location, positive yaw for left, negative for right;
a gradual bend should distribute small yaw over the bend instead. Keep terminal
heading consistent with the instruction. Do not turn early merely because the
next named landmark is not in the initial field of view.""",
'research_json_v1':'',
}
STRUCTURED_PROMPT="""You are a visual open-loop route planner. Input is ONLY the initial RGB image and
a navigation instruction; no future frames or map are available. Return ONLY JSON:
{"segments":[{"landmark":"approach to the named turn","turn_before":0.0,"distance":1.2,"step":0.3}],"stop_condition":"requested terminal landmark"}.
The example illustrates the schema only, not the route or correct distances.
Use 1..16 ordered segments grounded in the actual image and instruction. For each
segment first rotate turn_before radians IN PLACE, then travel distance forward
in the newly oriented body frame. Left is positive and right negative; a quarter
turn is approximately 1.57 radians. Separate approach/turn/departure segments.
Use dataset meter-like units, infer distances conservatively from visible geometry:
nearby indoor travel usually uses 0.15..0.35-unit granularity, outdoor 0.3..0.8.
Choose distance in [0,40], step in [0.05,2.46], abs(turn_before)<=6.29. A compiler
splits distance into ceil(distance/step) equal forward actions, with one extra
rotation-only action for nonzero turn_before. Total compiled actions MUST be <=64.
The last segment must end at the requested stop landmark, not beyond it. End of
list is stop; no dummy zero actions. Do not emit actions, comments, or extra keys."""
