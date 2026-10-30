"""Resume a fixed 100-case Qwen API experiment, defaulting to <=10 paid requests."""
import argparse
import collections
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from worldnav.data import load_observation,load_reference
from worldnav.evaluation import evaluate,load_metrics
from worldnav.geometry import integrate,canonical_reference
from worldnav.protocol import validate,validate_zip
from worldnav.qwen_api import QwenAPIPolicy,RequestBudget,PredictionFailure,redact,SYSTEM_PROMPT
from worldnav.runner import check_inputs,provenance,dump,METRICS


def update(path,data):
    """Derived summaries may evolve; raw responses and predictions never overwrite."""
    path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(redact(data),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    tmp.replace(path)


def initialize(run,manifest,api_config):
    run.mkdir(parents=True,exist_ok=False)
    for name in ('predictions','raw_responses','trajectories','metrics','logs','cases','claims','figures'):
        (run/name).mkdir()
    # Interleave seen/unseen and retain style order before any inference/scoring.
    by_split=[[e for e in manifest['episodes'] if e['split']==s] for s in ('val_seen','val_unseen')]
    schedule=[e for pair in zip(*by_split) for e in pair]
    frozen=dict(manifest,episodes=schedule)
    dump(run/'manifest.json',frozen);dump(run/'api_config.json',api_config)
    dump(run/'logs/provenance.json',provenance())
    (run/'logs/system_prompt.txt').write_text(SYSTEM_PROMPT+'\n')
    return frozen


def key(item): return item['split']+'__'+item['episode_id']


def execute_case(policy,item,root,run,seed,metric):
    name=key(item);started=time.perf_counter()
    dump(run/'claims'/(name+'.json'),dict(episode_id=item['episode_id'],started_unix=time.time()))
    row=dict(episode_id=item['episode_id'],split=item['split'],instruction_style=item['instruction_style'],
        prediction_valid=False,status='failed',failure_category=None,error_message=None,retry_count=0,
        api_success=False,api_latency_seconds=None,input_tokens=None,output_tokens=None,
        image_path=str(Path('samples')/item['split']/item['episode_id']/'0.jpg'),evaluation_metrics=None)
    result=None
    try:
        observation=load_observation(root,item);row['instruction']=observation.instruction
        result=policy.predict(observation,seed)
        record=result['api_record'];actions=result['actions']
    except PredictionFailure as exc:
        record=exc.record;row.update(failure_category=exc.category,error_message=exc.category)
    except Exception as exc:
        record={'attempts':[]};row.update(failure_category='input_or_budget_error',error_message=redact(str(exc)))
    # Persist API result before loading reference labels or computing any metrics.
    dump(run/'raw_responses'/(name+'.json'),redact(record))
    attempts=record.get('attempts',[])
    if attempts:
        row['api_success']=any(a['api_success'] for a in attempts)
        row['api_latency_seconds']=sum(a['latency_seconds'] for a in attempts)
        usages=[a['raw_response'].get('usage') or {} for a in attempts if a.get('raw_response')]
        row['input_tokens']=sum(u.get('prompt_tokens',0) or 0 for u in usages) if any('prompt_tokens' in u for u in usages) else None
        row['output_tokens']=sum(u.get('completion_tokens',0) or 0 for u in usages) if any('completion_tokens' in u for u in usages) else None
        row['retry_count']=len(attempts)-1
    if result is not None:
        try:
            prediction={'split':item['split'],'episodes':[{'episode_id':item['episode_id'],'actions':actions}]}
            validate(prediction,item['split'],[item['episode_id']],full=True)
            dump(run/'predictions'/(name+'.json'),prediction)
            row['prediction_valid']=True;row['action_count']=len(actions)
            xy,yaw=integrate(actions)
            dump(run/'trajectories'/(name+'.json'),dict(frame='canonical_initial_body',xy=xy,yaw=yaw))
            ref=load_reference(root,item)
            row['evaluation_metrics']=evaluate(actions,ref['position'],ref['yaw'],metric)
            row['status']='evaluated'
        except Exception as exc:
            row.update(failure_category='evaluation_or_persistence_error',error_message=redact(str(exc)))
    row['total_seconds']=time.perf_counter()-started
    dump(run/'cases'/(name+'.json'),row)
    return row


def summarize(run,manifest,budget):
    rows=[json.loads(p.read_text()) for p in sorted((run/'cases').glob('*.json'))]
    attempted=len(list((run/'claims').glob('*.json')))
    unknown=attempted-len(rows)
    valid=[r for r in rows if r['prediction_valid']]
    scored=[r for r in rows if r['evaluation_metrics'] is not None]
    def group(values):
        ok=[r for r in values if r['evaluation_metrics'] is not None]
        return dict(attempted=len(values),evaluated=len(ok),
            metrics_on_evaluated={m:sum(r['evaluation_metrics'][m] for r in ok)/len(ok) if ok else None for m in METRICS},
            score_failure_zero=sum(r['evaluation_metrics']['Score'] for r in ok)/len(values) if values else None)
    attempts=[a for p in (run/'raw_responses').glob('*.json')
              for a in json.loads(p.read_text()).get('attempts',[])]
    calls_success=sum(a['api_success'] for a in attempts)
    summary=dict(experiment='Qwen API Zero-shot Policy (not LCVN-Uni)',model='qwen/qwen3.8-27b',
        dataset_manifest_sha256=hashlib.sha256((run/'manifest.json').read_bytes()).hexdigest(),
        manifest_kind=manifest['manifest_kind'],sources=manifest['sources'],
        planned_cases=len(manifest['episodes']),attempted_cases=attempted,completed_records=len(rows),
        evaluated_cases=len(scored),valid_predictions=len(valid),unknown_interrupted_cases=unknown,
        reserved_api_requests=budget.used,recorded_api_requests=len(attempts),api_success_requests=calls_success,
        api_request_success_rate=calls_success/budget.used if budget.used else None,
        legal_prediction_rate=len(valid)/attempted if attempted else None,
        evaluation_coverage_among_attempted=len(scored)/attempted if attempted else None,
        evaluation_coverage_of_100=len(scored)/len(manifest['episodes']),
        failure_counts=dict(collections.Counter(r['failure_category'] for r in rows if r['failure_category'])),
        overall=group(rows),per_split={s:group([r for r in rows if r['split']==s]) for s in ('val_seen','val_unseen')},
        total_input_tokens=sum(r['input_tokens'] or 0 for r in rows),
        total_output_tokens=sum(r['output_tokens'] or 0 for r in rows),
        total_api_latency_seconds=sum(r['api_latency_seconds'] or 0 for r in rows),
        scorer='pinned_public_demonstration',private_scorer_equivalence_verified=False,
        average_step_source='reference',cost=None,price_and_account_allowance_verified=False,
        gpu_used=False,official_submission_ready=False,
        stop_reason='unverified_cost_request_cap' if budget.used>=budget.limit else 'phase_boundary_or_failure')
    # Interrupted claims have no usable prediction; include them in the denominator.
    if attempted:
        summary['overall']['score_failure_zero']=sum(r['evaluation_metrics']['Score'] for r in scored)/attempted
        summary['overall']['sr_failure_zero']=sum(r['evaluation_metrics']['SR'] for r in scored)/attempted
    summary['unknown_usage_successful_requests']=sum(
        a['api_success'] and not (a.get('raw_response') or {}).get('usage') for a in attempts)
    summary['provider_reported_output_above_requested_max']=sum(
        ((a.get('raw_response') or {}).get('usage') or {}).get('completion_tokens',0)>4096 for a in attempts)
    update(run/'summary.json',summary);update(run/'metrics/aggregate.json',dict(overall=summary['overall'],per_split=summary['per_split']))
    fields=['episode_id','split','instruction_style','status','prediction_valid','api_success','api_latency_seconds',
            'input_tokens','output_tokens','retry_count','failure_category','error_message',*METRICS]
    with (run/'metrics/per_episode.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for row in rows:
            writer.writerow({**{f:row.get(f) for f in fields if f not in METRICS},
                             **{m:(row['evaluation_metrics'] or {}).get(m) for m in METRICS}})
    for split in ('val_seen','val_unseen'):
        predictions=[]
        for row in valid:
            if row['split']==split:
                predictions.extend(json.loads((run/'predictions'/(key(row)+'.json')).read_text())['episodes'])
        update(run/'predictions'/(split+'.json'),dict(split=split,episodes=predictions))
    remaining=[e for e in manifest['episodes'] if not (run/'claims'/(key(e)+'.json')).exists()]
    update(run/'remaining_tasks.json',dict(remaining_count=len(remaining),episodes=remaining,
        blocked_until='Verify provider price and account allowance; then explicitly authorize a larger spend budget'))
    # This ZIP only validates the local subset; it cannot be submitted as a full official manifest.
    archive_path=run/'predictions/LOCAL_SUBSET_NOT_SUBMISSION.zip'
    with zipfile.ZipFile(archive_path,'w') as archive:
        for split in ('val_seen','val_unseen'):archive.write(run/'predictions'/(split+'.json'),split+'.json')
    local_ids={s:[r['episode_id'] for r in valid if r['split']==s] for s in ('val_seen','val_unseen')}
    check=validate_zip(archive_path,1,local_ids)
    update(run/'metrics/local_zip_audit.json',dict(kind='local_subset_only',results=check))
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,default=Path('configs/eval_100.json'))
    p.add_argument('--api-config',type=Path,default=Path('configs/qwen_api.json'))
    p.add_argument('--data-root',type=Path,required=True)
    p.add_argument('--run-dir',type=Path,default=Path('runs/qwen_api_100case'))
    p.add_argument('--target-cases',type=int,choices=(1,3,10,100),default=1)
    p.add_argument('--resume',action='store_true')
    p.add_argument('--summarize-only',action='store_true')
    args=p.parse_args();cfg=json.loads(args.api_config.read_text())
    if args.resume:
        manifest=json.loads((args.run_dir/'manifest.json').read_text())
        if json.loads((args.run_dir/'api_config.json').read_text())!=cfg:raise ValueError('API config changed; keep frozen config to resume')
    else:
        original=json.loads(args.manifest.read_text());check_inputs(original,args.data_root)
        manifest=initialize(args.run_dir,original,cfg)
    budget=RequestBudget(args.run_dir/'logs/request_budget',cfg['max_requests_without_verified_budget'])
    check_inputs(manifest,args.data_root)
    if args.summarize_only:
        print(json.dumps(summarize(args.run_dir,manifest,budget),indent=2));return
    # Whole-run lock: never issue duplicate requests from simultaneous resumes.
    import fcntl
    with (args.run_dir/'logs/runner.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        policy=QwenAPIPolicy(cfg,budget);metric=load_metrics()
        for index,item in enumerate(manifest['episodes'][:args.target_cases]):
            if (args.run_dir/'claims'/(key(item)+'.json')).exists():continue
            if budget.used>=budget.limit:break
            row=execute_case(policy,item,args.data_root,args.run_dir,manifest['seed']+index,metric)
            summary=summarize(args.run_dir,manifest,budget)
            print(json.dumps({k:row[k] for k in ('episode_id','split','status','api_latency_seconds','input_tokens','output_tokens','failure_category')}),flush=True)
            if row['failure_category']=='api_error':break
        summary=summarize(args.run_dir,manifest,budget)
        print(json.dumps({k:summary[k] for k in ('attempted_cases','evaluated_cases','reserved_api_requests','stop_reason')},indent=2))


if __name__=='__main__':main()
