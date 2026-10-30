#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
for variant in 1 2 3; do
    run_dir="runs/qwen_prompt_ablation/v$variant"
    if [ -d "$run_dir" ]; then
        sh scripts/run_api_sprint.sh --manifest configs/dev_12.json --api-config "configs/qwen_dev_v$variant.json" --data-root /data1/worldnav-data --run-dir "$run_dir" --resume
    else
        sh scripts/run_api_sprint.sh --manifest configs/dev_12.json --api-config "configs/qwen_dev_v$variant.json" --data-root /data1/worldnav-data --run-dir "$run_dir"
    fi
done
"${WORLDNAV_API_PYTHON:-$HOME/.venv/bin/python}" scripts/select_optimized_prompt.py
# Avoid exceeding four simultaneous requests across independent jobs.
count=0
while [ "$count" -lt 720 ]; do
    if "${WORLDNAV_API_PYTHON:-$HOME/.venv/bin/python}" -c 'import json,sys; p="runs/qwen_api_100case_baseline/logs/process.json"; sys.exit(0 if json.load(open(p))["state"]=="complete" else 1)'; then
        break
    fi
    count=$((count + 1))
    sleep 10
done
if [ "$count" -ge 720 ]; then
    printf '%s\n' 'Baseline did not finish within two hours; optimized run not started.' >&2
    exit 1
fi
if [ -d runs/qwen_api_100case_optimized ]; then
    sh scripts/run_api_sprint.sh --manifest configs/eval_100.json --api-config configs/qwen_optimized_100.json --data-root /data1/worldnav-data --run-dir runs/qwen_api_100case_optimized --resume
else
    sh scripts/run_api_sprint.sh --manifest configs/eval_100.json --api-config configs/qwen_optimized_100.json --data-root /data1/worldnav-data --run-dir runs/qwen_api_100case_optimized
fi
