"""Stop an unresponsive optional route after three fully exhausted API cases."""
import json,time,os,signal,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];run=root/'runs/stage2_dev_vision'
for _ in range(120):
 cases=[json.loads(p.read_text()) for p in (run/'cases').glob('*.json')]
 if len(cases)>=3:
  if any(r['prediction_valid'] or r['failure_category']!='api_error' for r in cases):sys.exit(0)
  state=json.loads((run/'logs/process.json').read_text());pid=state['pid']
  cmd=Path(f'/proc/{pid}/cmdline').read_bytes().decode(errors='ignore')
  if 'run_api_sprint.py' not in cmd or 'stage2_dev_vision' not in cmd:raise RuntimeError('PID identity mismatch')
  os.kill(pid,signal.SIGTERM)
  for _ in range(20):
   if not Path(f'/proc/{pid}').exists():break
   time.sleep(.25)
  attempts=[a for p in (run/'raw_responses').glob('*.json') for a in json.loads(p.read_text()).get('attempts',[])]
  slots=len(list((run/'logs/request_budget').glob('*.json')))
  report={'reason':'Optional vision route: at least three terminal API failures after bounded retries; stop further paid requests','completed_cases':len(cases),'valid_cases':0,'reserved_requests':slots,'recorded_requests':len(attempts),'unresolved_reserved_requests':slots-len(attempts),'warning':'In-flight requests interrupted; charges/provider completion unknown. Do not label unresolved requests as model predictions.','stopped_at_unix':time.time()}
  with (run/'logs/controlled_stop.json').open('x') as f:json.dump(report,f,indent=2)
  state.update(state='stopped_unavailable_route',finished_unix=time.time());(run/'logs/process.json').write_text(json.dumps(state,indent=2))
  (root/'reports/stage2_vision_probe.json').write_text(json.dumps(report,indent=2)+'\n')
  if any(a.get('http_status') in (401,402,403) for a in attempts):
   print('Authorization/credit failure: stop optional route and do not launch further inference.');sys.exit(1)
  # The parent research shell exits with the terminated child, preventing duplicates.
  subprocess.run(['tmux','new-session','-d','-s','worldnav_stage2_candidate',f'cd {root} && sh scripts/run_api_sprint.sh --manifest configs/eval_100.json --api-config configs/stage2_candidate_100.json --data-root /data1/worldnav-data --run-dir runs/stage2_candidate_100 > logs/stage2_candidate.txt 2>&1'],check=True)
  print(json.dumps(report));sys.exit(0)
 time.sleep(5)
print('Optional route monitor expired without the terminal-failure criterion; existing bounded runner retained.')
