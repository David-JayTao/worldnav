#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
py="${WORLDNAV_API_PYTHON:-$HOME/.venv/bin/python}"
count=0
while [ "$count" -lt 180 ] && tmux has-session -t worldnav_stage2_full_control 2>/dev/null; do count=$((count + 1)); sleep 20; done
if [ "$count" -ge 180 ]; then echo 'Full control wait exceeded one hour.'; exit 1; fi
"$py" -c 'import json,pathlib; assert json.load(open("runs/stage2_full_candidate_100/summary.json"))["completed_records"]==100; attempts=[a for name in ("stage2_full_base_100","stage2_full_candidate_100") for p in pathlib.Path("runs",name,"raw_responses").glob("*.json") for a in json.load(open(p)).get("attempts",[])]; assert not any(a.get("http_status") in (401,402,403) for a in attempts)'
if [ -d runs/stage2_full_v3_100 ]; then resume=--resume; else resume=; fi
sh scripts/run_api_sprint.sh --manifest configs/eval_100_full_stage2.json --api-config configs/stage2_full_v3.json --data-root /data1/worldnav-data --run-dir runs/stage2_full_v3_100 $resume
