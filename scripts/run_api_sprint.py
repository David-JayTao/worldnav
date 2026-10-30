"""Bounded concurrent experiments with frozen prompts and reusable case results."""
import argparse
import concurrent.futures
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import os
import collections
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'src'),str(Path(__file__).resolve().parent)]
from worldnav.data import load_observation
from worldnav.data import load_reference
from worldnav.evaluation import load_metrics,evaluate
from worldnav.geometry import integrate
from worldnav.prompts import get_prompt
from worldnav.qwen_api import QwenAPIPolicy,RequestBudget,encode_image,parse_actions
from worldnav.runner import dump,provenance
from run_qwen_api import initialize,execute_case,key,summarize,update


def prepare(run,manifest_path,config_path,root):
    cfg=json.loads(config_path.read_text());manifest=json.loads(manifest_path.read_text())
    for item in manifest['episodes']:
        obs=load_observation(root,item)
        item['instruction']=obs.instruction
        item['initial_image_path']=str(Path('samples')/item['split']/item['episode_id']/'0.jpg')
    frozen=initialize(run,manifest,cfg)
    (run/'logs/system_prompt.txt').write_text(get_prompt(cfg['prompt_version'])+'\n')
    identity=dict(experiment_id=run.name,model_name=cfg['model'],provider=cfg['provider'],
        prompt_version=cfg['prompt_version'],protocol_version='track1_a52e43f_body_frame_v1',
        manifest_hash=hashlib.sha256((run/'manifest.json').read_bytes()).hexdigest(),
        prompt_hash=hashlib.sha256(get_prompt(cfg['prompt_version']).encode()).hexdigest(),
        timestamp_unix=time.time(),run_config=cfg)
    dump(run/'experiment.json',identity)
    # Keep exact source text, not only dirty Git hashes, for every new experiment.
    code={str(p.relative_to(Path.cwd())):p.read_text() for folder in ('src','scripts')
          for p in (Path.cwd()/folder).rglob('*.py')}
    dump(run/'logs/source_snapshot.json',code)
    return frozen,cfg


def import_valid_cases(source,run,manifest,cfg,root):
    original=json.loads((source/'api_config.json').read_text())
    for field in ('model','prompt_version','temperature','max_tokens','max_image_edge','jpeg_quality'):
        if original[field]!=cfg[field]:raise ValueError('Cannot reuse predictions from another inference configuration')
    previous={key(e):e for e in json.loads((source/'manifest.json').read_text())['episodes']}
    count=0
    for item in manifest['episodes']:
        name=key(item);case_path=source/'cases'/(name+'.json')
        if not case_path.exists():continue
        row=json.loads(case_path.read_text())
        if row['status']!='evaluated':continue
        if any(previous[name][f]!=item[f] for f in ('image_sha256','metadata_sha256','trajectory_sha256')):
            raise ValueError('Reused source data hashes differ')
        raw=json.loads((source/'raw_responses'/(name+'.json')).read_text())
        if raw['prompt_sha256']!=hashlib.sha256(get_prompt(cfg['prompt_version']).encode()).hexdigest():
            raise ValueError('Reused prompt hash differs')
        obs=load_observation(root,item);_,image=encode_image(obs.image,cfg['max_image_edge'],cfg['jpeg_quality'])
        if image!=raw['image_encoding'] or obs.instruction!=row['instruction']:
            raise ValueError('Reused image/instruction differs')
        row['reused_from']=str(source);row['experiment_id']=run.name
        for folder in ('predictions','trajectories','raw_responses'):
            src=source/folder/(name+'.json');dst=run/folder/(name+'.json')
            dump(dst,json.loads(src.read_text()))
        dump(run/'cases'/(name+'.json'),row)
        dump(run/'claims'/(name+'.json'),dict(episode_id=item['episode_id'],reused_from=str(source)))
        count+=1
    dump(run/'logs/reuse_audit.json',dict(reused_cases=count,source=str(source),
        source_provenance=json.loads((source/'logs/provenance.json').read_text())))
    return count


def sprint_summary(run,manifest,budget,cfg):
    result=summarize(run,manifest,budget)
    rows=[json.loads(p.read_text()) for p in (run/'cases').glob('*.json')]
    reused=[r for r in rows if 'reused_from' in r]
    reused_attempts=sum(len(json.loads((run/'raw_responses'/(key(r)+'.json')).read_text())['attempts']) for r in reused)
    denominator=budget.used+reused_attempts
    historical=[a for p in run.glob('history/*/attempt_*/raw_responses/*.json')
                for a in json.loads(p.read_text()).get('attempts',[])]
    current=[a for p in (run/'raw_responses').glob('*.json')
             for a in json.loads(p.read_text()).get('attempts',[])]
    all_attempts=historical+current
    success_count=sum(a['api_success'] for a in all_attempts)
    result.update(experiment_id=run.name,prompt_version=cfg['prompt_version'],
        reused_cases=len(reused),current_run_reserved_requests=budget.used,
        inherited_requests=reused_attempts,all_inference_request_count=denominator,
        api_success_requests=success_count,api_request_success_rate=success_count/denominator if denominator else None,
        spending_authorization='worldnav_sprint_20261031',
        stop_reason='complete' if len(rows)==len(manifest['episodes']) else 'in_progress_or_interrupted')
    result['historical_request_count']=len(historical)
    result['request_failure_counts']=dict(collections.Counter(
        str(a.get('http_status') or a.get('error_type') or 'unknown') for a in all_attempts if not a['api_success']))
    result['total_input_tokens']+=sum((a.get('raw_response',{}).get('usage') or {}).get('prompt_tokens',0) or 0 for a in historical)
    result['total_output_tokens']+=sum((a.get('raw_response',{}).get('usage') or {}).get('completion_tokens',0) or 0 for a in historical)
    result['total_api_latency_seconds']+=sum(a.get('latency_seconds',0) for a in historical)
    result['overall']['score_all_planned_failure_zero']=sum((r['evaluation_metrics'] or {}).get('Score',0) for r in rows)/len(manifest['episodes'])
    result['overall']['sr_all_planned_failure_zero']=sum((r['evaluation_metrics'] or {}).get('SR',0) for r in rows)/len(manifest['episodes'])
    for split,group in result['per_split'].items():
        n=sum(e['split']==split for e in manifest['episodes'])
        selected=[r for r in rows if r['split']==split]
        group['planned']=n
        group['score_all_planned_failure_zero']=sum((r['evaluation_metrics'] or {}).get('Score',0) for r in selected)/n
        group['sr_all_planned_failure_zero']=sum((r['evaluation_metrics'] or {}).get('SR',0) for r in selected)/n
    update(run/'summary.json',result)
    update(run/'remaining_tasks.json',dict(episodes=[e for e in manifest['episodes'] if not (run/'cases'/(key(e)+'.json')).exists()],
        note='Resume the frozen experiment; completed cases are never requested again.'))
    return result


def recover_persisted_response(run,item,root,metric):
    """Finish an interrupted case from a real response without another API call."""
    name=key(item);path=run/'raw_responses'/(name+'.json')
    if not path.exists():return False
    record=json.loads(path.read_text());attempts=record.get('attempts',[])
    if not attempts or not attempts[-1].get('raw_response'):return False
    raw=attempts[-1]['raw_response']
    try:
        choice=raw['choices'][0]
        if choice.get('finish_reason') not in ('stop',None):return False
        actions=parse_actions(choice['message']['content'])
    except (KeyError,IndexError,ValueError,TypeError):return False
    prediction=dict(split=item['split'],episodes=[dict(episode_id=item['episode_id'],actions=actions)])
    p=run/'predictions'/(name+'.json')
    if p.exists():
        if json.loads(p.read_text())!=prediction:raise ValueError('Interrupted prediction differs from real raw response')
    else:dump(p,prediction)
    xy,yaw=integrate(actions);p=run/'trajectories'/(name+'.json')
    if not p.exists():dump(p,dict(frame='canonical_initial_body',xy=xy,yaw=yaw))
    ref=load_reference(root,item);observation=load_observation(root,item)
    usage=[a['raw_response'].get('usage') or {} for a in attempts if a.get('raw_response')]
    row=dict(episode_id=item['episode_id'],split=item['split'],instruction_style=item['instruction_style'],
        prediction_valid=True,status='evaluated',failure_category=None,error_message=None,
        retry_count=len(attempts)-1,api_success=True,
        api_latency_seconds=sum(a.get('latency_seconds',0) for a in attempts),
        input_tokens=sum(u.get('prompt_tokens',0) or 0 for u in usage),
        output_tokens=sum(u.get('completion_tokens',0) or 0 for u in usage),
        image_path=str(Path('samples')/item['split']/item['episode_id']/'0.jpg'),instruction=observation.instruction,
        evaluation_metrics=evaluate(actions,ref['position'],ref['yaw'],metric),action_count=len(actions),
        recovered_from_persisted_response=True,total_seconds=None)
    dump(run/'cases'/(name+'.json'),row);return True


def archive_incomplete_or_failed(run,item):
    name=key(item);history=run/'history'/name
    history.mkdir(parents=True,exist_ok=True)
    number=len(list(history.glob('attempt_*')))+1
    if number>2:raise ValueError('Case already retried twice; inspect failures instead of looping')
    target=history/f'attempt_{number}';target.mkdir()
    for folder in ('claims','cases','raw_responses','predictions','trajectories'):
        source=run/folder/(name+'.json')
        if source.exists():
            (target/folder).mkdir();source.rename(target/folder/source.name)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--api-config',type=Path,required=True);p.add_argument('--data-root',type=Path,required=True)
    p.add_argument('--run-dir',type=Path,required=True);p.add_argument('--resume',action='store_true')
    p.add_argument('--seed-from',type=Path);p.add_argument('--summarize-only',action='store_true')
    p.add_argument('--recover-incomplete',action='store_true')
    p.add_argument('--retry-failed',action='store_true')
    args=p.parse_args()
    if args.resume:
        manifest=json.loads((args.run_dir/'manifest.json').read_text());cfg=json.loads((args.run_dir/'api_config.json').read_text())
        if cfg!=json.loads(args.api_config.read_text()):raise ValueError('Frozen API config changed')
    else:
        manifest,cfg=prepare(args.run_dir,args.manifest,args.api_config,args.data_root)
        if args.seed_from:print('Reused valid cases:',import_valid_cases(args.seed_from,args.run_dir,manifest,cfg,args.data_root),flush=True)
    budget=RequestBudget(args.run_dir/'logs/request_budget',cfg['max_requests'],cfg.get('spending_authorization'))
    if args.summarize_only:print(json.dumps(sprint_summary(args.run_dir,manifest,budget,cfg),indent=2));return
    with (args.run_dir/'logs/runner.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        update(args.run_dir/'logs/process.json',dict(pid=os.getpid(),started_unix=time.time(),state='running'))
        policy=QwenAPIPolicy(cfg,budget);metric=load_metrics()
        pending=[]
        for index,item in enumerate(manifest['episodes']):
            case=args.run_dir/'cases'/(key(item)+'.json')
            if case.exists():
                if args.retry_failed and json.loads(case.read_text())['status']!='evaluated':
                    archive_incomplete_or_failed(args.run_dir,item)
                else:continue
            if (args.run_dir/'claims'/(key(item)+'.json')).exists():
                if not args.recover_incomplete:raise ValueError('Interrupted claim found: use --recover-incomplete for explicit recovery')
                if recover_persisted_response(args.run_dir,item,args.data_root,metric):continue
                archive_incomplete_or_failed(args.run_dir,item)
            pending.append((index,item))
        with concurrent.futures.ThreadPoolExecutor(max_workers=cfg['max_concurrency']) as pool:
            futures={pool.submit(execute_case,policy,item,args.data_root,args.run_dir,manifest['seed']+index,metric):item for index,item in pending}
            for future in concurrent.futures.as_completed(futures):
                row=future.result();result=sprint_summary(args.run_dir,manifest,budget,cfg)
                print(json.dumps(dict(episode_id=row['episode_id'],status=row['status'],
                    completed=result['completed_records'],evaluated=result['evaluated_cases'],requests=budget.used)),flush=True)
        print(json.dumps(sprint_summary(args.run_dir,manifest,budget,cfg),indent=2),flush=True)
        update(args.run_dir/'logs/process.json',dict(pid=os.getpid(),finished_unix=time.time(),state='complete'))


if __name__=='__main__':main()
