"""CPU reference-label round trip. Never produces model/baseline results."""
import argparse
import datetime
import json
import math
from pathlib import Path
import sys
import time
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from worldnav.data import load_reference
from worldnav.geometry import reference_actions,integrate
from worldnav.evaluation import evaluate,load_metrics
from worldnav.runner import new_run,dump


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--data-root',type=Path,required=True)
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    config=json.loads(args.config.read_text())
    output=args.output or Path('outputs')/('reference_check_'+datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    out=new_run(output,config,'reference_control_not_baseline')
    metric=load_metrics();rows=[];started=time.perf_counter()
    for item in config['episodes']:
        raw=load_reference(args.data_root,item)
        acts=reference_actions(raw['position'],raw['yaw'])
        xy,_=integrate(acts,[*raw['position'][0],raw['yaw'][0]])
        error=float(np.max(np.abs(np.asarray(xy)-raw['position'])))
        result=evaluate(acts,raw['position'],raw['yaw'],metric)
        if error>1e-9 or result['Score']<99.99999:raise ValueError(f'Reference round trip failed: {item["episode_id"]}')
        rows.append(dict(episode_id=item['episode_id'],split=item['split'],reference_action_count=len(acts),
                         max_step=max(math.hypot(a[0],a[1]) for a in acts),
                         world_position_max_error=error,reference_control_metrics=result))
    dump(out/'controls.json',rows)
    summary=dict(kind='reference_control_not_baseline',episodes=len(rows),seconds=time.perf_counter()-started,
        max_world_position_error=max(x['world_position_max_error'] for x in rows),model_forward_count=0,
        reference_steps_over_64=sum(x['reference_action_count']>64 for x in rows),
        reference_steps_exceed_translation_limit=sum(x['max_step']>2.46 for x in rows))
    dump(out/'summary.json',summary)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
