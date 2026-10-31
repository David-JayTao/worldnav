"""Paired geometric diagnostics and deterministic case gallery, never policy input."""
import sys,json,math,statistics,csv,re,textwrap
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from worldnav.data import load_reference,load_observation
from worldnav.geometry import integrate,canonical_reference,reference_actions,wrap_angle
from worldnav.evaluation import load_metrics,evaluate
from worldnav.qwen_api import parse_actions
from worldnav.trajectory_plan import compile_plan
from run_qwen_api import key
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def length(xy):return sum(math.dist(a,b) for a,b in zip(xy,xy[1:]))
def turns(actions):
 distances=np.array([math.hypot(a[0],a[1]) for a in actions]);total=distances.sum();progress=np.cumsum(distances)/(total if total else 1)
 return [(float(progress[i]),float(a[2])) for i,a in enumerate(actions) if abs(wrap_angle(a[2]))>=.2]
def turn_distance(a,b):
 if not a and not b:return 0.
 if not a or not b:return 1.
 # Symmetric nearest-turn distance in normalized path progress + sign mismatch.
 def directed(x,y):return sum(min(abs(px-py)+(0.5 if ax*ay<0 else 0) for py,ay in y) for px,ax in x)/len(x)
 return (directed(a,b)+directed(b,a))/2

def inspect(run,root):
 manifest=json.loads((run/'manifest.json').read_text());cfg=json.loads((run/'api_config.json').read_text());rows=[];details={}
 for item in manifest['episodes']:
  name=key(item);p=run/'cases'/(name+'.json')
  if not p.exists():continue
  row=json.loads(p.read_text());ref=load_reference(root,item);rxy,ryaw=canonical_reference(ref['position'],ref['yaw']);ra=reference_actions(ref['position'],ref['yaw']);rl=length(rxy)
  eid=item['episode_id'];scene=re.sub(r'^[A-Z][a-z]{2}-\d{2}-\d{4}-','',eid).split('_')[0]
  out={'episode_id':eid,'split':item['split'],'style':item['instruction_style'],'scene_filename_proxy':scene,'valid':row['prediction_valid'],'reference_steps':len(ra),'reference_length':rl,'step_bin':'<=10' if len(ra)<=10 else ('11-20' if len(ra)<=20 else '>20'),'length_bin':'<=3' if rl<=3 else ('3-7' if rl<=7 else '>7'),'Score':0,'SR':0,'failure':row['failure_category']}
  raw=json.loads((run/'raw_responses'/(name+'.json')).read_text());content=raw.get('attempts',[])
  details[name]={'item':item,'reference_xy':rxy,'reference_yaw':ryaw,'instruction':load_observation(root,item).instruction,'raw_responses':content,'predicted_xy':None,'actions':None}
  if row['prediction_valid']:
   saved=json.loads((run/'predictions'/(name+'.json')).read_text())['episodes'][0]['actions']
   decoder=compile_plan if cfg.get('policy_kind')=='structured_route' else parse_actions
   parsed=decoder([a for a in content if a.get('raw_response')][-1]['raw_response']['choices'][0]['message']['content']);assert parsed==saved
   xy,yaw=integrate(saved);m=evaluate(saved,ref['position'],ref['yaw'],load_metrics());assert all(abs(m[k]-row['evaluation_metrics'][k])<1e-10 for k in m)
   pl=length(xy);last=np.array(rxy[-1])-np.array(rxy[-2]);last=last/(np.linalg.norm(last) or 1)
   out.update(m,predicted_steps=len(saved),predicted_length=pl,path_length_ratio=pl/rl if rl>1e-12 else None,endpoint_error=math.dist(xy[-1],rxy[-1]),heading_error=abs(wrap_angle(yaw[-1]-ryaw[-1])),turn_count=len(turns(saved)),reference_turn_count=len(turns(ra)),turn_progress_proxy=turn_distance(turns(saved),turns(ra)),terminal_projection_proxy=float(np.dot(np.array(xy[-1])-np.array(rxy[-1]),last)),amplitudes=[math.hypot(a[0],a[1]) for a in saved],turn_positions=turns(saved),reference_turn_positions=turns(ra))
   details[name].update(predicted_xy=xy,actions=saved)
  rows.append(out)
 return rows,details

def aggregate(rows):
 valid=[r for r in rows if r['valid']];fields=['ATE','RPE','full_route_fidelity','heading_turn_fidelity','predicted_steps','reference_steps','predicted_length','reference_length','path_length_ratio','endpoint_error','heading_error','turn_count','reference_turn_count','turn_progress_proxy','terminal_projection_proxy']
 return {'planned':len(rows),'valid':len(valid),'SR_numerator':sum(r['SR'] for r in rows),'SR_denominator':len(rows),'SR':sum(r['SR'] for r in rows)/len(rows),'Score':sum(r['Score'] for r in rows)/len(rows),'valid_subset_means':{f:statistics.mean(r[f] for r in valid if r.get(f) is not None) for f in fields} if valid else {}}

def analyze():
 out=ROOT/'outputs/stage2_analysis';out.mkdir(exist_ok=True);root=Path('/data1/worldnav-data')
 runs={'Base':ROOT/'runs/qwen_api_100case_baseline','V3':ROOT/'runs/qwen_api_100case_optimized'}
 candidate=ROOT/'runs/stage2_candidate_100'
 if (candidate/'summary.json').exists() and json.loads((candidate/'summary.json').read_text())['completed_records']==100:runs['New']=candidate
 allrows={};alldetails={};summaries={}
 for label,run in runs.items():
  rows,details=inspect(run,root);allrows[label]=rows;alldetails[label]=details
  groups={f:{str(k):aggregate([r for r in rows if r[f]==k]) for k in sorted(set(r[f] for r in rows),key=str)} for f in ['split','style','scene_filename_proxy','step_bin','length_bin']}
  summaries[label]={'overall':aggregate(rows),'groups':groups}
  (out/(label+'_cases.json')).write_text(json.dumps(rows,indent=2,ensure_ascii=False))
  fields=sorted(set().union(*(r.keys() for r in rows))-{'amplitudes','turn_positions','reference_turn_positions'})
  with (out/(label+'_cases.csv')).open('w') as f:
   writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
  (out/(label+'_details.json')).write_text(json.dumps(details,ensure_ascii=False,indent=2))
 fig,axes=plt.subplots(2,3,figsize=(13,7))
 for ax,field,title,unit in zip(axes.flat,['predicted_steps','path_length_ratio','endpoint_error','heading_error','turn_progress_proxy','predicted_length'],['Predicted actions','Per-case path length ratio','Endpoint error','Final heading error','Turn progress mismatch proxy','Predicted path length'],['count','ratio','dataset units','rad','normalized progress + sign penalty','dataset units']):
  values=[[r[field] for r in allrows[label] if r['valid'] and r.get(field) is not None] for label in runs]
  ax.boxplot(values,labels=list(runs),showfliers=True);ax.set_title(title,fontsize=10);ax.set_ylabel(unit);ax.grid(axis='y',alpha=.2)
 fig.suptitle('Paired local 100-case diagnostics; valid subsets shown');fig.tight_layout();fig.savefig(out/'error_distributions.png',dpi=170);plt.close(fig)
 fig,ax=plt.subplots(figsize=(9,4))
 for label,rows in allrows.items():
  vals=[v for r in rows if r['valid'] for v in r['amplitudes']];ax.hist(vals,bins=np.linspace(0,2.46,25),histtype='step',density=True,label=label)
 ax.set(xlabel='Translation magnitude / dataset units',ylabel='Density',title='Action amplitude distribution; rotation-only steps included');ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(out/'action_amplitudes.png',dpi=170);plt.close(fig)
 a={r['split']+'__'+r['episode_id']:r for r in allrows['Base']};b={r['split']+'__'+r['episode_id']:r for r in allrows['V3']};valid=[k for k in b if b[k]['valid']]
 roles={'largest_score_gain':max(valid,key=lambda k:b[k]['Score']-a[k]['Score']),'worst_endpoint':max(valid,key=lambda k:b[k]['endpoint_error']),'worst_scale_ratio':max(valid,key=lambda k:abs(math.log(max(b[k]['path_length_ratio'] or 0,1e-12)))),'turn_mismatch_proxy':max(valid,key=lambda k:b[k]['turn_progress_proxy']),'stop_overshoot_proxy':max(valid,key=lambda k:b[k]['terminal_projection_proxy'])}
 failures=[k for k in b if not b[k]['valid']]
 if failures:roles['format_failure']=failures[0]
 success=[k for k in valid if b[k]['SR']==1]
 if success:roles['success_low_fidelity']=min(success,key=lambda k:b[k]['full_route_fidelity'])
 selections=[]
 for role,k in roles.items():
  d=alldetails['V3'][k];obs=load_observation(root,d['item']);fig,axes=plt.subplots(1,2,figsize=(12,5));axes[0].imshow(obs.image);axes[0].axis('off');axes[0].set_title('Initial RGB (only image input)')
  rxy=np.asarray(d['reference_xy']);axes[1].plot(rxy[:,0],rxy[:,1],'-o',ms=3,color='black',label='GT: evaluation only')
  for label in runs:
   xy=alldetails[label][k]['predicted_xy']
   if xy:
    xy=np.asarray(xy);axes[1].plot(xy[:,0],xy[:,1],'-x',ms=3,label=label)
  axes[1].axis('equal');axes[1].grid(alpha=.2);axes[1].legend(fontsize=8);axes[1].set(xlabel='X / dataset units',ylabel='Y / dataset units',title='Current-body action integration')
  metrics=' | '.join(f"{label}: SR={next(r for r in allrows[label] if r['episode_id']==d['item']['episode_id'] and r['split']==d['item']['split'])['SR']} Score={next(r for r in allrows[label] if r['episode_id']==d['item']['episode_id'] and r['split']==d['item']['split'])['Score']:.2f}" for label in runs)
  fig.suptitle(role+': '+d['item']['episode_id']+'\n'+metrics,fontsize=10)
  fig.text(.02,.02,textwrap.fill(d['instruction'],110),fontsize=8);fig.tight_layout(rect=(0,.14,1,.9));path=out/(role+'.png');fig.savefig(path,dpi=150);plt.close(fig)
  selections.append({'role':role,'case_key':k,'file':str(path.relative_to(ROOT)),'instruction':d['instruction'],'Base_Score':a[k]['Score'],'V3_Score':b[k]['Score'],'interpretation':'deterministic diagnostic selection; geometric proxy is not a semantic failure label'})
 (out/'gallery.json').write_text(json.dumps(selections,ensure_ascii=False,indent=2))
 public={'source':'raw response parsed, saved actions compared, public metrics independently recomputed','GT_used_only_for_post_prediction_analysis':True,'turn_proxy':'symmetric nearest normalized-progress turn difference, +0.5 penalty for opposite yaw sign; threshold |dyaw|>=0.2rad; not semantic turn correctness','stop_proxy':'endpoint residual projected on final reference displacement; not semantic stop correctness','scene_proxy':'filename prefix, not verified physical scene labels','runs':summaries,'gallery':selections}
 (ROOT/'reports/stage2_deep_analysis.json').write_text(json.dumps(public,ensure_ascii=False,indent=2)+'\n')
 print('Wrote diagnostics and',len(selections),'real paired case figures. No API calls.')
if __name__=='__main__':analyze()
