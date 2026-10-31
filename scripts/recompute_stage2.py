"""Read-only replay of frozen cases, independently aggregating public metrics."""
import sys,json,hashlib,collections,math
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from worldnav.qwen_api import parse_actions,encode_image
from worldnav.data import load_observation,load_reference
from worldnav.geometry import integrate
from worldnav.evaluation import load_metrics,evaluate
from compare_experiments import compare
from run_qwen_api import key

def recompute(run,root):
 manifest=json.loads((run/'manifest.json').read_text());cfg=json.loads((run/'api_config.json').read_text());rows=[];attempts=[]
 assert len({key(x) for x in manifest['episodes']})==len(manifest['episodes'])
 for item in manifest['episodes']:
  k=key(item);old=json.loads((run/'cases'/(k+'.json')).read_text());raw=json.loads((run/'raw_responses'/(k+'.json')).read_text());attempts+=raw['attempts']
  assert old['episode_id']==item['episode_id'] and old['split']==item['split']
  from worldnav.prompts import get_prompt
  assert raw['prompt_sha256']==hashlib.sha256(get_prompt(cfg['prompt_version']).encode()).hexdigest()
  ref_all=load_reference(root,item)
  actual_group=hashlib.sha256(np.asarray(ref_all['position']).astype('<f8').tobytes()+np.asarray(ref_all['yaw']).astype('<f8').tobytes()).hexdigest()
  assert actual_group==item['trajectory_sha256']
  obs=load_observation(root,item);_,encoded=encode_image(obs.image,cfg['max_image_edge'],cfg['jpeg_quality'])
  assert encoded==raw['image_encoding'];assert obs.instruction==old['instruction']==item['instruction']
  folder=root/'samples'/item['split']/item['episode_id']
  for filename,field in [('0.jpg','image_sha256'),('traj_data.pkl','metadata_sha256')]:
   assert hashlib.sha256((folder/filename).read_bytes()).hexdigest()==item[field]
  score=None
  if old['prediction_valid']:
   content=[a for a in raw['attempts'] if a.get('raw_response')][-1]['raw_response']['choices'][0]['message']['content']
   from worldnav.trajectory_plan import compile_plan
   actions=(compile_plan(content) if cfg.get('policy_kind')=='structured_route' else parse_actions(content));saved=json.loads((run/'predictions'/(k+'.json')).read_text())['episodes'][0]['actions'];assert actions==saved
   xy,yaw=integrate(actions);traj=json.loads((run/'trajectories'/(k+'.json')).read_text());assert xy==traj['xy'] and yaw==traj['yaw']
   ref=load_reference(root,item);score=evaluate(actions,ref['position'],ref['yaw'],load_metrics())
   assert all(abs(score[k]-old['evaluation_metrics'][k])<1e-10 for k in score)
  else:
   assert old['evaluation_metrics'] is None and not (run/'predictions'/(k+'.json')).exists()
  rows.append({'episode_id':item['episode_id'],'split':item['split'],'style':item['instruction_style'],'metrics':score,'failure':old['failure_category']})
 def aggregate(rs):
  valid=[r['metrics'] for r in rs if r['metrics'] is not None]
  return {'planned':len(rs),'valid':len(valid),'sr_numerator':sum(m['SR'] for m in valid),'SR_failure_zero':sum(m['SR'] for m in valid)/len(rs),'Score_failure_zero':sum(m['Score'] for m in valid)/len(rs),'valid_subset':{k:sum(m[k] for m in valid)/len(valid) for k in valid[0]} if valid else {}}
 json_count=0;legal_count=0
 for a in attempts:
  try:
   content=a['raw_response']['choices'][0]['message']['content'];json.loads(content);json_count+=1
   parse_actions(content);legal_count+=1
  except (KeyError,IndexError,ValueError,TypeError):pass
 return {'run':run.name,'overall':aggregate(rows),'per_split':{s:aggregate([r for r in rows if r['split']==s]) for s in ['val_seen','val_unseen']},'by_instruction_style':{str(s):aggregate([r for r in rows if r['style']==s]) for s in [0,1,2]},'request_count':len(attempts),'api_success_count':sum(a['api_success'] for a in attempts),'json_valid_response_count':json_count,'legal_action_response_count':legal_count,'api_success_rate':sum(a['api_success'] for a in attempts)/len(attempts),'json_valid_per_request':json_count/len(attempts),'final_valid_rate':sum(r['metrics'] is not None for r in rows)/len(rows),'input_tokens':sum((a.get('raw_response',{}).get('usage') or {}).get('prompt_tokens',0) or 0 for a in attempts),'output_tokens':sum((a.get('raw_response',{}).get('usage') or {}).get('completion_tokens',0) or 0 for a in attempts),'latency_sum_seconds':sum(a.get('latency_seconds',0) for a in attempts),'failures':dict(collections.Counter(r['failure'] for r in rows if r['failure'])),'cases':rows}

if __name__=='__main__':
 out=ROOT/'outputs/stage2_recomputed';out.mkdir(exist_ok=False)
 root=Path('/data1/worldnav-data');names=['qwen_api_100case_baseline','qwen_api_100case_optimized']+['qwen_prompt_ablation/v'+str(v) for v in [1,2,3]]
 results={name:recompute(ROOT/'runs'/name,root) for name in names}
 formal=json.loads((ROOT/'configs/eval_100.json').read_text());dev=json.loads((ROOT/'configs/dev_12.json').read_text())
 overlap={x['trajectory_sha256'] for x in formal['episodes']}&{x['trajectory_sha256'] for x in dev['episodes']};assert not overlap
 paired=compare(ROOT/'runs'/names[0],ROOT/'runs'/names[1])
 (out/'all_results.json').write_text(json.dumps({'runs':results,'paired':paired,'trajectory_overlap':len(overlap),'GT_input_boundary':'Observation(image,instruction); execute_case persists raw response/prediction before load_reference; covered by CPU mock ordering test'},ensure_ascii=False,indent=2)+'\n')
 public={n:{k:v for k,v in r.items() if k!='cases'} for n,r in results.items()}
 (ROOT/'reports/stage2_recomputed_metrics.json').write_text(json.dumps({'runs':public,'paired':{k:v for k,v in paired.items() if k!='rows'},'trajectory_overlap':len(overlap)},ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({n:r['overall'] for n,r in results.items()},indent=2))
