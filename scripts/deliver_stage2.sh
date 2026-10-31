#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
py="${WORLDNAV_API_PYTHON:-$HOME/.venv/bin/python}"
count=0
while [ "$count" -lt 360 ]; do
    if "$py" -c 'import json; assert json.load(open("runs/stage2_full_candidate_100/summary.json"))["completed_records"]==100' 2>/dev/null && ! tmux has-session -t worldnav_stage2_data 2>/dev/null; then break; fi
    count=$((count + 1)); sleep 20
done
if [ "$count" -ge 360 ]; then echo 'Delivery readiness exceeded bounded two-hour wait.'; exit 1; fi
export CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
"$py" scripts/analyze_stage2.py
"$py" scripts/finalize_stage2.py
"$py" scripts/build_stage2_ppt.py
libreoffice "-env:UserInstallation=file://$PWD/.cache/lo_stage2" --headless --convert-to pdf --outdir reports reports/WorldNav_科研冲刺汇报_20261031_v2.pptx
