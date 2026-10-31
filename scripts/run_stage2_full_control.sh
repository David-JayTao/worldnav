#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
py="${WORLDNAV_API_PYTHON:-$HOME/.venv/bin/python}"
count=0
while [ "$count" -lt 180 ]; do
    if [ -f configs/eval_100_full_stage2.json ] && "$py" -c 'import json; assert json.load(open("runs/stage2_candidate_100/summary.json"))["completed_records"]==100' 2>/dev/null; then break; fi
    if ! tmux has-session -t worldnav_stage2_research 2>/dev/null && [ ! -f configs/stage2_candidate_100.json ]; then echo 'Research selection unavailable; stopping.'; exit 1; fi
    count=$((count + 1)); sleep 20
done
if [ "$count" -ge 180 ]; then echo 'Reached bounded readiness wait.'; exit 1; fi
"$py" -c 'import json,sys,pathlib; rows=[a for p in pathlib.Path("runs/stage2_candidate_100/raw_responses").glob("*.json") for a in json.load(open(p)).get("attempts",[])]; sys.exit(1 if any(a.get("http_status") in (401,402,403) for a in rows) else 0)'
for variant in base candidate; do
    run="runs/stage2_full_${variant}_100"
    if [ "$variant" = base ]; then config=configs/stage2_full_base.json; else config=configs/stage2_candidate_100.json; fi
    if [ -d "$run" ]; then resume=--resume; else resume=; fi
    sh scripts/run_api_sprint.sh --manifest configs/eval_100_full_stage2.json --api-config "$config" --data-root /data1/worldnav-data --run-dir "$run" $resume
    "$py" -c 'import json,sys,pathlib; rows=[a for p in pathlib.Path(sys.argv[1],"raw_responses").glob("*.json") for a in json.load(open(p)).get("attempts",[])]; sys.exit(1 if any(a.get("http_status") in (401,402,403) for a in rows) else 0)' "$run"
done
"$py" scripts/compare_experiments.py --base runs/stage2_full_base_100 --optimized runs/stage2_full_candidate_100 --output outputs/stage2_full_comparison/paired.json
