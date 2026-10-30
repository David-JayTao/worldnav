"""Offline diagnostics from persisted predictions; never tunes a policy."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'src'),str(Path(__file__).resolve().parent)]
from worldnav.data import load_reference
from worldnav.geometry import canonical_reference,integrate,wrap_angle,reference_actions
from analyze_qwen_run import replay,figures
from run_qwen_api import update,key


def diagnose(run,root):
    manifest=json.loads((run/'manifest.json').read_text());rows=[]
    for item in manifest['episodes']:
        p=run/'predictions'/(key(item)+'.json')
        if not p.exists():continue
        actions=json.loads(p.read_text())['episodes'][0]['actions'];ref=load_reference(root,item)
        xy,yaw=integrate(actions);rxy,ryaw=canonical_reference(ref['position'],ref['yaw'])
        ref_actions=reference_actions(ref['position'],ref['yaw'])
        length=sum(math.dist(a,b) for a,b in zip(xy,xy[1:]));rlength=sum(math.dist(a,b) for a,b in zip(rxy,rxy[1:]))
        rows.append(dict(episode_id=item['episode_id'],split=item['split'],instruction_style=item['instruction_style'],
            predicted_action_count=len(actions),reference_action_count=len(ref_actions),
            predicted_path_length=length,reference_path_length=rlength,
            path_length_ratio=length/rlength if rlength>1e-12 else None,
            endpoint_error=math.dist(xy[-1],rxy[-1]),final_heading_error=abs(wrap_angle(yaw[-1]-ryaw[-1])),
            predicted_abs_turn=sum(abs(wrap_angle(a[2])) for a in actions),reference_abs_turn=sum(abs(a[2]) for a in ref_actions),
            predicted_net_turn=sum(wrap_angle(a[2]) for a in actions),reference_net_turn=sum(a[2] for a in ref_actions),
            predicted_zero_steps=sum(a==[0,0,0] for a in actions)))
    def aggregate(group):
        fields=['predicted_action_count','reference_action_count','predicted_path_length','reference_path_length',
                'path_length_ratio','endpoint_error','final_heading_error','predicted_abs_turn','reference_abs_turn']
        return {f:statistics.mean(r[f] for r in group if r[f] is not None) if any(r[f] is not None for r in group) else None for f in fields}
    result=dict(episodes=len(rows),evaluation_only=True,used_for_prompt_selection=False,
                overall=aggregate(rows),per_split={s:aggregate([r for r in rows if r['split']==s]) for s in ('val_seen','val_unseen')},rows=rows)
    update(run/'metrics/diagnostics.json',result)
    if rows:
        with (run/'metrics/diagnostics.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--data-root',type=Path,required=True);args=p.parse_args()
    replay(args.run_dir,args.data_root);diagnose(args.run_dir,args.data_root);figures(args.run_dir,args.data_root)
    print('Offline replay, diagnostics and figures saved; API calls: 0')


if __name__=='__main__':main()
