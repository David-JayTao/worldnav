#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
py="${WORLDNAV_API_PYTHON:-$HOME/.venv/bin/python}"
count=0
while [ "$count" -lt 270 ]; do
    if "$py" -c 'import json; assert json.load(open("runs/stage2_full_v3_100/summary.json"))["completed_records"]==100' 2>/dev/null; then break; fi
    count=$((count + 1)); sleep 20
done
if [ "$count" -ge 270 ]; then echo 'Core experiment wait exceeded bounded 90 minutes.'; exit 1; fi
"$py" -c 'import pathlib,json; attempts=[a for p in pathlib.Path("runs/stage2_full_v3_100/raw_responses").glob("*.json") for a in json.load(open(p)).get("attempts",[])]; assert not any(a.get("http_status") in (401,402,403) for a in attempts)'
if [ -d runs/stage2_vision8_smoke ]; then resume=--resume; else resume=; fi
sh scripts/run_api_sprint.sh --manifest configs/stage2_json_smoke.json --api-config configs/stage2_vision8_smoke.json --data-root /data1/worldnav-data --run-dir runs/stage2_vision8_smoke $resume
if "$py" -c 'import json; assert json.load(open("runs/stage2_vision8_smoke/summary.json"))["valid_predictions"]==1'; then
    if [ -d runs/stage2_dev_vision8 ]; then resume=--resume; else resume=; fi
    sh scripts/run_api_sprint.sh --manifest configs/dev_12.json --api-config configs/stage2_vision8_dev.json --data-root /data1/worldnav-data --run-dir runs/stage2_dev_vision8 $resume
fi
"$py" -c 'import json,pathlib; p=pathlib.Path("runs/stage2_vision8_smoke/summary.json"); s=json.loads(p.read_text()); p=pathlib.Path("runs/stage2_dev_vision8/summary.json"); d=json.loads(p.read_text()) if p.exists() else None; pathlib.Path("reports/stage2_vision8_probe.json").write_text(json.dumps({"model":"qwen/qwen3-vl-8b-instruct","smoke_valid":s["valid_predictions"],"development_completed":d["completed_records"] if d else 0,"development_valid":d["valid_predictions"] if d else 0,"timeouts_seconds":45,"network_retries":0,"formal_100case_run":False},indent=2)+"\n")'
