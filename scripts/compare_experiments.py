"""Paired offline comparison of the same fixed cases; no model calls or tuning."""
import argparse
import json
from pathlib import Path
import numpy as np
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_qwen_api import update,key


def compare(base,opt):
    manifests=[json.loads((r/'manifest.json').read_text()) for r in (base,opt)]
    if {key(e) for e in manifests[0]['episodes']}!={key(e) for e in manifests[1]['episodes']}:
        raise ValueError('Paired comparison requires identical episode sets')
    second={key(e):e for e in manifests[1]['episodes']}
    for item in manifests[0]['episodes']:
        other=second[key(item)]
        for field in ('image_sha256','metadata_sha256','trajectory_sha256','instruction'):
            if field not in item or item[field]!=other.get(field):
                raise ValueError('Paired case data or instruction differs')
    rows=[]
    for item in manifests[0]['episodes']:
        name=key(item);paths=[r/'cases'/(name+'.json') for r in (base,opt)]
        if not all(p.exists() for p in paths):raise ValueError('Both experiments must finish every planned case')
        a,b=[json.loads(p.read_text()) for p in paths];ma=a['evaluation_metrics'] or {};mb=b['evaluation_metrics'] or {}
        rows.append(dict(episode_id=item['episode_id'],split=item['split'],
            base_valid=a['prediction_valid'],optimized_valid=b['prediction_valid'],
            base_score=ma.get('Score',0),optimized_score=mb.get('Score',0),
            score_delta=mb.get('Score',0)-ma.get('Score',0),base_SR=ma.get('SR',0),optimized_SR=mb.get('SR',0)))
    delta=np.asarray([r['score_delta'] for r in rows]);rng=np.random.default_rng(20261031)
    bootstrap=delta[rng.integers(0,len(rows),size=(5000,len(rows)))].mean(axis=1)
    decomposition={}
    for a_valid,b_valid in [(True,True),(False,True),(True,False),(False,False)]:
        group=[r for r in rows if r['base_valid']==a_valid and r['optimized_valid']==b_valid]
        decomposition[f'{int(a_valid)}_to_{int(b_valid)}']={'cases':len(group),
            'conditional_mean_delta':sum(r['score_delta'] for r in group)/len(group) if group else None,
            'contribution_to_planned_mean':sum(r['score_delta'] for r in group)/len(rows)}
    return dict(coverage_decomposition=decomposition,cases=len(rows),failure_score_policy='zero_for_no_usable_prediction',
        score_mean_delta=float(delta.mean()),paired_bootstrap_95ci=[float(x) for x in np.quantile(bootstrap,[.025,.975])],
        improved=int(np.count_nonzero(delta>1e-10)),worsened=int(np.count_nonzero(delta< -1e-10)),tied=int(np.count_nonzero(np.abs(delta)<=1e-10)),
        sr_gained=sum(r['optimized_SR']==1 and r['base_SR']==0 for r in rows),
        sr_lost=sum(r['optimized_SR']==0 and r['base_SR']==1 for r in rows),
        per_split={s:float(np.mean([r['score_delta'] for r in rows if r['split']==s])) for s in ('val_seen','val_unseen')},rows=rows)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True)
    p.add_argument('--optimized',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();result=compare(args.base,args.optimized);args.output.parent.mkdir(parents=True,exist_ok=True)
    update(args.output,result);print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    summaries=[json.loads((r/'summary.json').read_text()) for r in (args.base,args.optimized)]
    fig,axes=plt.subplots(1,2,figsize=(10,4));x=np.arange(2)
    for i,(label,summary) in enumerate(zip(('Qwen Base','Qwen Selected'),summaries)):
        for ax,field,title in zip(axes,('score_all_planned_failure_zero','sr_all_planned_failure_zero'),('Composite Score','Success rate')):
            values=[summary['per_split'][s][field] for s in ('val_seen','val_unseen')]
            ax.bar(x+(i-.5)*.34,values,.34,label=label)
            ax.set_xticks(x,['Seen','Unseen']);ax.set_title(title);ax.grid(axis='y',alpha=.2)
    axes[0].legend();axes[1].set_ylim(0,1);fig.suptitle('Same fixed 100 cases; unusable predictions counted as zero')
    fig.tight_layout();fig.savefig(args.output.parent/'metrics.png',dpi=180);plt.close(fig)


if __name__=='__main__':main()
