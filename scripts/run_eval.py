"""100-case preflight (default) or explicitly approved future model inference."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from worldnav.checkpoint import verify_checkpoint
from worldnav.runner import check_inputs,new_run,dump,run_batch


def require_idle_gpu(index):
    fields=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.free','--format=csv,noheader,nounits'],text=True)
    devices={int(row.split(',')[0]):row.split(',') for row in fields.strip().splitlines()}
    if index not in devices: raise ValueError('GPU index not found')
    uuid=devices[index][1].strip()
    processes=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid','--format=csv,noheader'],text=True)
    if uuid in processes: raise ValueError('Target GPU has a compute process; refusing to share')
    if int(devices[index][2])<20000: raise ValueError('Target GPU has less than 20000 MiB free')
    os.environ['CUDA_VISIBLE_DEVICES']=str(index)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--data-root',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--mode',choices=['preflight','infer'],default='preflight')
    parser.add_argument('--checkpoint-manifest',type=Path)
    parser.add_argument('--gpu-approved',action='store_true',help='Only after explicit user approval in a later session')
    parser.add_argument('--gpu',type=int,default=0)
    parser.add_argument('--limit',type=int,choices=[3,9,100],default=100)
    args=parser.parse_args()
    resource_policy=json.loads((Path(__file__).resolve().parents[1]/'configs/resource_policy.json').read_text())
    if args.mode=='infer' and not resource_policy['gpu_inference_allowed']:
        parser.error('CPU-only policy: allocated GPU count is 0; wait for explicit user allocation before updating resource policy')
    cfg=json.loads(args.config.read_text())
    root=str(args.data_root) if args.data_root else os.path.expandvars(cfg['data_root'])
    if '$' in root: parser.error('Set WORLDNAV_DATA_ROOT or pass --data-root')
    output=args.output or Path('outputs')/(args.mode+'_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    run=new_run(output,cfg,args.mode)
    try:
        inputs=check_inputs(cfg,root);dump(run/'inputs_audit.json',inputs)
        cp=args.checkpoint_manifest or cfg['model'].get('checkpoint_manifest')
        verified=verify_checkpoint(cp)
        dump(run/'checkpoint_audit.json',dict(manifest_sha256=verified['manifest_sha256'],verified=True))
        if args.mode=='preflight':
            dump(run/'summary.json',dict(status='INPUTS_AND_CHECKPOINT_READY_GPU_NOT_RUN',model_forward_completed=False))
            print(str(run));return 0
        if not args.gpu_approved: raise ValueError('Inference requires explicit future user confirmation and --gpu-approved')
        require_idle_gpu(args.gpu)
        if cfg['model']['backend']!='lcvn_uni':
            raise ValueError('Only the experimental LCVN-Uni backend is implemented; Cosmos has no validated model loader')
        from worldnav.uni import UniPolicy
        policy=UniPolicy(cfg['model'],cp)
        result=run_batch(policy,cfg,root,run,limit=args.limit)
        print(json.dumps(result,indent=2));return 0 if result['attempted']==result['evaluated'] else 1
    except Exception as exc:
        # Runs are exclusive directories, so prior results are never overwritten.
        dump(run/'summary.json',dict(status='BLOCKED',model_forward_completed=False,error=f'{type(exc).__name__}: {exc}'))
        dump(run/'metrics.json',dict(evaluated=0,baseline_metrics=None))
        dump(run/'runtime.json',dict(model_inference_seconds=None,peak_gpu_memory_mib=None))
        print(f'BLOCKED: {exc}; artifacts: {run}',file=sys.stderr);return 2


if __name__=='__main__':sys.exit(main())
