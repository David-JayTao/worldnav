"""Run bookkeeping and evaluation, with model inputs separated from references."""
import csv
import datetime
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import time
from .data import load_observation,load_reference
from .evaluation import evaluate,load_metrics
from .geometry import integrate
from .protocol import validate

ROOT=Path(__file__).resolve().parents[2]
METRICS=('SR','ATE','RPE','full_route_fidelity','heading_turn_fidelity','Score')


def dump(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf8') as stream:
        json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write('\n')


def provenance():
    def git(*args):
        return subprocess.run(['git',*args],cwd=ROOT,text=True,capture_output=True).stdout.strip()
    versions={}
    for name in ('numpy','Pillow','torch','torchvision','transformers','peft','flash-attn','safetensors'):
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:versions[name]=None
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ('src','scripts') for p in (ROOT/folder).rglob('*.py')}
    return dict(git_commit=git('rev-parse','HEAD'),git_dirty=bool(git('status','--porcelain')),source_sha256=hashes,
                submodules=git('submodule','status'),dependencies=versions,
                timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())


def new_run(path,config,mode):
    path=Path(path);path.mkdir(parents=True,exist_ok=False)
    for folder in ('predictions','trajectories','failure_cases'): (path/folder).mkdir()
    dump(path/'config.json',config)
    dump(path/'provenance.json',dict(mode=mode,**provenance()))
    return path


def check_inputs(config,root):
    episodes=config['episodes']
    if len(episodes)!=100: raise ValueError('100-case config must contain exactly 100 episodes')
    keys=set();groups=set();counts={s:0 for s in ('val_seen','val_unseen')}
    for item in episodes:
        split,eid=item['split'],item['episode_id']
        if split not in counts: raise ValueError('Invalid validation split')
        key=(split,eid)
        if key in keys: raise ValueError('Duplicate manifest episode')
        keys.add(key);counts[split]+=1
        group=item['trajectory_sha256']
        if group in groups: raise ValueError('Repeated trajectory in 100-case manifest')
        groups.add(group)
        observation=load_observation(root,item)
        folder=Path(root)/'samples'/split/eid
        for filename,field in [('0.jpg','image_sha256'),('traj_data.pkl','metadata_sha256')]:
            if hashlib.sha256((folder/filename).read_bytes()).hexdigest()!=item[field]:
                raise ValueError(f'Input hash mismatch: {split}/{eid}/{filename}')
        # CPU audit may read labels; the policy is given ONLY Observation below.
        ref=load_reference(root,item)
        if observation.instruction!=ref['instruction']: raise ValueError('Prepared instruction differs from official metadata')
    if counts!={'val_seen':50,'val_unseen':50}: raise ValueError('Expected 50 seen and 50 unseen')
    return dict(episodes=100,counts=counts,unique_trajectory_groups=len(groups),official_manifest_verified=False)


def run_batch(policy,config,data_root,output,limit=None,mode='baseline_inference'):
    """Policy receives no ID, file path, reference poses, end frame or goal."""
    if mode not in ('baseline_inference','unit_test'): raise ValueError('Unknown run mode')
    rows=[]; predictions={s:[] for s in ('val_seen','val_unseen')}
    metric=load_metrics();started=time.perf_counter()
    episodes=config['episodes'][:limit] if limit else config['episodes']
    if not episodes: raise ValueError('Empty evaluation set')
    for index,item in enumerate(episodes):
        eid,split=item['episode_id'],item['split'];key=f'{split}__{eid}'
        row=dict(episode_id=eid,split=split,status='failed',action_count=None,
                 inference_seconds=None,evaluation_seconds=None,peak_gpu_memory_mib=None,termination=None,
                 **{k:None for k in METRICS},error='')
        start=time.perf_counter()
        try:
            obs=load_observation(data_root,item)
            t=time.perf_counter()
            result=policy.predict(obs,config['seed']+index)
            row['inference_seconds']=time.perf_counter()-t
            payload={'episode_id':eid,'actions':result['actions']}
            validate({'split':split,'episodes':[payload]},split,[eid],full=True)
            row.update(action_count=len(result['actions']),termination=result.get('termination'),
                       peak_gpu_memory_mib=result.get('peak_gpu_memory_mib'))
            dump(output/'predictions'/(key+'.json'),dict(split=split,episodes=[payload]))
            dump(output/'predictions'/(key+'.details.json'),result)
            predictions[split].append(payload)
            # Labels are accessed after inference and persistence, exclusively for scoring.
            t=time.perf_counter();ref=load_reference(data_root,item)
            row.update(evaluate(result['actions'],ref['position'],ref['yaw'],metric))
            xy,yaw=integrate(result['actions'])
            dump(output/'trajectories'/(key+'.json'),dict(frame='canonical_initial_body',xy=xy,yaw=yaw))
            row['evaluation_seconds']=time.perf_counter()-t;row['status']='ok'
        except Exception as exc:
            row['error']=f'{type(exc).__name__}: {exc}'
            dump(output/'failure_cases'/(key+'.json'),dict(episode_id=eid,split=split,error=row['error']))
        row['total_seconds']=time.perf_counter()-start;rows.append(row)
    for split,payloads in predictions.items():
        dump(output/'predictions'/(split+'.json'),dict(split=split,episodes=payloads))
    with (output/'per_episode.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    successful=[r for r in rows if r['status']=='ok']
    def mean(group): return {k:sum(r[k] for r in group)/len(group) if group else None for k in METRICS}
    per_split={s:dict(n=sum(r['split']==s for r in successful),metrics=mean([r for r in successful if r['split']==s])) for s in predictions}
    metrics=dict(kind='unit_test_only' if mode=='unit_test' else 'experimental_adapted_lcvn_uni',
        scorer='public_demonstration',private_scorer_equivalence_verified=False,
        average_step_source='reference',evaluated=len(successful),attempted=len(rows),
        failure_policy='exclude_and_report_counts',aggregate=mean(successful),per_split=per_split)
    if all(per_split[s]['n'] for s in per_split):
        metrics['equal_split_score']=sum(per_split[s]['metrics']['Score'] for s in per_split)/2
    dump(output/'metrics.json',metrics)
    dump(output/'summary.json',dict(mode=mode,attempted=len(rows),succeeded=len(successful),failed=len(rows)-len(successful),
        complete=len(rows)==len(successful),official_submission_ready=False))
    dump(output/'runtime.json',dict(total_seconds=time.perf_counter()-started,
        peak_gpu_memory_mib=max((r['peak_gpu_memory_mib'] for r in rows if r['peak_gpu_memory_mib'] is not None),default=None)))
    return metrics
