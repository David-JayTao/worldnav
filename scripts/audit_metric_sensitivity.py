"""CPU-only evaluator sensitivity to action subdivision; not model inference."""
from pathlib import Path
import sys,json,math,statistics
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from worldnav.geometry import integrate
from worldnav.data import load_reference
from worldnav.evaluation import evaluate,load_metrics
from run_qwen_api import key

def subdivide(actions):
 out=[]
 for dx,dy,dyaw in actions:
  if dx or dy:out.extend([[dx/2,dy/2,0],[dx/2,dy/2,dyaw]])
  else:out.append([dx,dy,dyaw])
 return out

def main():
 run=ROOT/'runs/qwen_api_100case_optimized';manifest=json.loads((run/'manifest.json').read_text());rows=[];skipped=0
 for item in manifest['episodes']:
  p=run/'predictions'/(key(item)+'.json')
  if not p.exists():continue
  old=json.loads(p.read_text())['episodes'][0]['actions'];new=subdivide(old)
  if len(new)>64:skipped+=1;continue
  a,ya=integrate(old);b,yb=integrate(new)
  endpoint=math.dist(a[-1],b[-1]);assert endpoint<1e-10 and abs(ya[-1]-yb[-1])<1e-10
  def length(x):return sum(math.dist(p,q) for p,q in zip(x,x[1:]))
  assert abs(length(a)-length(b))<1e-10
  ref=load_reference(Path('/data1/worldnav-data'),item);ma=evaluate(old,ref['position'],ref['yaw'],load_metrics());mb=evaluate(new,ref['position'],ref['yaw'],load_metrics())
  rows.append({'episode_id':item['episode_id'],'split':item['split'],'old_actions':len(old),'new_actions':len(new),'same_endpoint_error':endpoint,'old_metrics':ma,'subdivided_metrics':mb,'Score_delta':mb['Score']-ma['Score']})
 out={'experiment_type':'CPU metric sensitivity diagnostic, NOT a model/baseline experiment','rule':'halve translations, keep each original yaw on its final half-step; same polyline and endpoint','eligible':len(rows),'skipped_over_64':skipped,'mean_Score_delta':statistics.mean(r['Score_delta'] for r in rows),'max_abs_Score_delta':max(abs(r['Score_delta']) for r in rows),'rows':rows}
 (ROOT/'outputs/stage2_metric_sensitivity.json').write_text(json.dumps(out,indent=2))
 (ROOT/'reports/stage2_metric_sensitivity.json').write_text(json.dumps({k:v for k,v in out.items() if k!='rows'},indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='rows'}))
if __name__=='__main__':main()
