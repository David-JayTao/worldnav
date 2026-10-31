"""Strict route-plan compiler. No labels, images, endpoint fitting, or repair."""
import math
from .protocol import load_json
from .qwen_api import parse_actions

def compile_plan(content):
    plan=load_json(content)
    if not isinstance(plan,dict) or set(plan)!={'segments','stop_condition'}:
        raise ValueError('Expected segments and stop_condition only')
    if not isinstance(plan['stop_condition'],str) or not plan['stop_condition'].strip():
        raise ValueError('Missing semantic stop condition')
    if not isinstance(plan['segments'],list) or not 1<=len(plan['segments'])<=16:
        raise ValueError('Expected 1..16 route segments')
    actions=[]
    for seg in plan['segments']:
        if not isinstance(seg,dict) or set(seg)!={'landmark','turn_before','distance','step'}:
            raise ValueError('Invalid segment fields')
        if not isinstance(seg['landmark'],str) or not seg['landmark'].strip():raise ValueError('Missing landmark')
        for field in ('turn_before','distance','step'):
            if type(seg[field]) not in (int,float) or not math.isfinite(seg[field]):raise ValueError('Nonfinite or nonnumeric segment')
        yaw,distance,step=[seg[k] for k in ('turn_before','distance','step')]
        if abs(yaw)>6.29 or not 0<=distance<=40 or not 0.05<=step<=2.46:raise ValueError('Segment outside protocol bounds')
        if yaw:actions.append([0,0,yaw])
        n=math.ceil(distance/step)
        # Equal subdivision preserves model-planned distance and endpoint exactly.
        if n:actions.extend([[distance/n,0,0] for _ in range(n)])
        if len(actions)>64:raise ValueError('Compiled route exceeds 64 actions; no truncation')
    if not actions:raise ValueError('Empty structured route; not a substitute prediction')
    return parse_actions(__import__('json').dumps({'actions':actions}))
