"""Offline response replay, public-metric verification and trajectory figures."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import textwrap
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from worldnav.qwen_api import parse_actions
from worldnav.data import load_reference,load_observation
from worldnav.geometry import integrate,canonical_reference
from worldnav.evaluation import evaluate,load_metrics
from run_qwen_api import key,update


def replay(run,root):
    manifest=json.loads((run/'manifest.json').read_text());metric=load_metrics();records=[]
    for item in manifest['episodes']:
        name=key(item);path=run/'cases'/(name+'.json')
        if not path.exists():continue
        row=json.loads(path.read_text());raw=json.loads((run/'raw_responses'/(name+'.json')).read_text())
        if not row['prediction_valid']:
            records.append(dict(episode_id=item['episode_id'],status='failure_preserved',category=row['failure_category']))
            continue
        attempts=[a for a in raw['attempts'] if a.get('raw_response')]
        actions=parse_actions(attempts[-1]['raw_response']['choices'][0]['message']['content'])
        saved=json.loads((run/'predictions'/(name+'.json')).read_text())['episodes'][0]['actions']
        if actions!=saved:raise ValueError('Saved prediction differs from raw response')
        ref=load_reference(root,item);metrics=evaluate(actions,ref['position'],ref['yaw'],metric)
        if row['evaluation_metrics'] is not None and any(abs(metrics[k]-row['evaluation_metrics'][k])>1e-10 for k in metrics):
            raise ValueError('Replayed metrics differ from stored metrics')
        xy,yaw=integrate(actions);stored=json.loads((run/'trajectories'/(name+'.json')).read_text())
        if xy!=stored['xy'] or yaw!=stored['yaw']:raise ValueError('Reconstructed trajectory differs from saved trajectory')
        records.append(dict(episode_id=item['episode_id'],status='raw_actions_trajectory_metrics_match'))
    update(run/'metrics/offline_replay.json',dict(model_api_calls=0,records=records,
        verified_predictions=sum(r['status']=='raw_actions_trajectory_metrics_match' for r in records)))
    return records


def figures(run,root):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    manifest=json.loads((run/'manifest.json').read_text());items={key(x):x for x in manifest['episodes']}
    api_config=json.loads((run/'api_config.json').read_text())
    model_label=api_config.get('model','unknown')+' / '+api_config.get('prompt_version','unknown')
    rows=[json.loads(p.read_text()) for p in (run/'cases').glob('*.json')]
    valid=[r for r in rows if r['evaluation_metrics'] is not None]
    if not valid:return []
    best=max(valid,key=lambda r:r['evaluation_metrics']['Score'])
    worst=min(valid,key=lambda r:r['evaluation_metrics']['Score'])
    turning=[]
    for row in valid:
        acts=json.loads((run/'predictions'/(key(row)+'.json')).read_text())['episodes'][0]['actions']
        turning.append((sum(abs(a[2]) for a in acts),row))
    turn=max(turning,key=lambda pair:pair[0])[1]
    roles=[('best_valid_prediction',best),('lowest_score_prediction',worst),('turning_prediction',turn)]
    success=[r for r in valid if r['evaluation_metrics']['SR']==1]
    if success:roles.append(('navigation_success',success[0]))
    selections=[]
    for role,row in roles:
        item=items[key(row)];observation=load_observation(root,item);ref=load_reference(root,item)
        saved=json.loads((run/'trajectories'/(key(row)+'.json')).read_text());xy=saved['xy']
        rxy,_=canonical_reference(ref['position'],ref['yaw']);m=row['evaluation_metrics']
        fig,axes=plt.subplots(1,2,figsize=(12,5));axes[0].imshow(observation.image);axes[0].axis('off')
        axes[0].set_title('Initial RGB (only image sent to API)')
        axes[1].plot([p[0] for p in rxy],[p[1] for p in rxy],'-o',ms=3,label='Ground Truth (evaluation only)')
        axes[1].plot([p[0] for p in xy],[p[1] for p in xy],'-x',ms=4,label='Qwen API prediction')
        axes[1].scatter([0],[0],c='black',s=25,label='Start');axes[1].axis('equal');axes[1].grid(alpha=.25)
        axes[1].set_xlabel('X / dataset units');axes[1].set_ylabel('Y / dataset units');axes[1].legend(fontsize=8)
        axes[1].set_title(f"SR={m['SR']} ATE={m['ATE']:.3f} RPE={m['RPE']:.3f}\nF={m['full_route_fidelity']:.3f} H={m['heading_turn_fidelity']:.3f} Score={m['Score']:.3f}")
        fig.suptitle(f"{model_label}\n{role}: {row['episode_id']} ({row['split']})",fontsize=9)
        fig.text(.02,.02,textwrap.fill(observation.instruction,110),fontsize=8,va='bottom');fig.tight_layout(rect=(0,.12,1,.88))
        target=run/'figures'/(role+'.png');fig.savefig(target,dpi=150);plt.close(fig)
        selections.append(dict(role=role,episode_id=row['episode_id'],split=row['split'],
                               navigation_success=bool(m['SR']),file=str(target.relative_to(run)),metrics=m))
    failures=[r for r in rows if r['failure_category']]
    if failures:
        row=failures[0];obs=load_observation(root,items[key(row)])
        fig,ax=plt.subplots(figsize=(7,4));ax.imshow(obs.image);ax.axis('off')
        ax.set_title(f"{row['episode_id']} ({row['split']})\n{row['failure_category']}: no usable prediction; no fabricated route",fontsize=9)
        target=run/'figures/api_failure.png';fig.savefig(target,dpi=150,bbox_inches='tight');plt.close(fig)
        selections.append(dict(role='api_failure',episode_id=row['episode_id'],file=str(target.relative_to(run))))
    update(run/'figures/index.json',dict(navigation_success_count=len(success),selections=selections,
        note='Best valid prediction denotes successful generation; it does not imply navigation success.'))
    return selections


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--data-root',type=Path,required=True);args=p.parse_args()
    records=replay(args.run_dir,args.data_root);selections=figures(args.run_dir,args.data_root)
    print(json.dumps(dict(replayed=len(records),figures=len(selections),api_calls=0),indent=2))


if __name__=='__main__':main()
