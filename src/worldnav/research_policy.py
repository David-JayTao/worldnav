"""Independent structured-plan and verified-catalog vision comparison policies."""
from .qwen_api import QwenAPIPolicy
from .trajectory_plan import compile_plan

class StructuredRoutePolicy(QwenAPIPolicy):
    def decode_response(self,content):return compile_plan(content)
    repair_instruction='Return the same route as valid JSON with exactly segments and stop_condition, with landmark, turn_before, distance, step per segment. Respect the 64 compiled-action limit. No markdown.'

class VisionComparisonPolicy(QwenAPIPolicy):
    allowed_models={'qwen/qwen3-vl-32b-instruct','qwen/qwen3-vl-8b-instruct'}

def make_policy(config,budget,client=None):
    cls={'direct':QwenAPIPolicy,'structured_route':StructuredRoutePolicy,'vision_comparison':VisionComparisonPolicy}.get(config.get('policy_kind','direct'))
    if cls is None:raise ValueError('Unknown policy kind')
    return cls(config,budget,client)
