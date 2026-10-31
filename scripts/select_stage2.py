"""Select one novel Qwen strategy from development evidence only."""
import hashlib,json,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
rows=[]
for name in ('scale','stop','turn','structured','json'):
 p=ROOT/f'runs/stage2_dev_{name}/summary.json'
 if not p.exists():continue
 s=json.loads(p.read_text())
 if s['completed_records']!=12:raise ValueError('Development experiment incomplete')
 g=s['overall'];m=g['metrics_on_evaluated'];rows.append({'strategy':name,'Score':g['score_all_planned_failure_zero'],'SR':g['sr_all_planned_failure_zero'],'valid':s['valid_predictions'],'ATE':m['ATE'] if m['ATE'] is not None else float('inf')})
if not rows:raise ValueError('No completed development candidates')
best=max(rows,key=lambda r:(r['Score'],r['SR'],r['valid'],-r['ATE']))
cfg=json.loads((ROOT/f'configs/stage2_{best["strategy"]}_dev.json').read_text());cfg['max_requests']=240
path=ROOT/'configs/stage2_candidate_100.json'
if path.exists():raise FileExistsError('Candidate already frozen; do not reselect')
path.write_text(json.dumps(cfg,indent=2)+'\n')
old=json.loads((ROOT/'runs/qwen_prompt_ablation/v3/summary.json').read_text())['overall']['score_all_planned_failure_zero']
record={'selected':best['strategy'],'candidates':rows,'V3_development_Score':old,'selected_beats_V3_on_development':best['Score']>old,'formal_metrics_used_for_selection':False,'formal_set_reused_exploratory':True,'config_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'frozen_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
p=ROOT/'runs/stage2_selection.json'
with p.open('x') as f:json.dump(record,f,indent=2)
(ROOT/'reports/stage2_selection.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
