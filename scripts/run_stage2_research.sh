#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
py="${WORLDNAV_API_PYTHON:-$HOME/.venv/bin/python}"
for strategy in scale stop turn structured json vision; do
    if [ "$strategy" = json ]; then
        "$py" -c 'import json; s=json.load(open("runs/stage2_json_smoke/summary.json")); assert s["evaluated_cases"]==1' || continue
    fi
    run="runs/stage2_dev_$strategy"
    if [ -d "$run" ]; then resume=--resume; else resume=; fi
    sh scripts/run_api_sprint.sh --manifest configs/dev_12.json --api-config "configs/stage2_${strategy}_dev.json" --data-root /data1/worldnav-data --run-dir "$run" $resume
    "$py" -c 'import json,sys,pathlib; attempts=[a for p in pathlib.Path(sys.argv[1],"raw_responses").glob("*.json") for a in json.load(open(p)).get("attempts",[])]; sys.exit(1 if any(a.get("http_status") in (401,402,403) for a in attempts) else 0)' "$run"
done
"$py" scripts/select_stage2.py
if [ -d runs/stage2_candidate_100 ]; then resume=--resume; else resume=; fi
sh scripts/run_api_sprint.sh --manifest configs/eval_100.json --api-config configs/stage2_candidate_100.json --data-root /data1/worldnav-data --run-dir runs/stage2_candidate_100 $resume
