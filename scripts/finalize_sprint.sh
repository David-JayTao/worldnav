#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
python_bin="${WORLDNAV_API_PYTHON:-$HOME/.venv/bin/python}"
data_root="${WORLDNAV_DATA_ROOT:?Set WORLDNAV_DATA_ROOT}"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR="$PWD/.cache/matplotlib"
count=0
while [ "$count" -lt 720 ]; do
    if "$python_bin" -c 'import json,sys,pathlib; roots=[pathlib.Path("runs/qwen_api_100case_baseline"),pathlib.Path("runs/qwen_api_100case_optimized")]; sys.exit(0 if all((p/"logs/process.json").exists() and json.load(open(p/"logs/process.json"))["state"]=="complete" for p in roots) else 1)'; then
        break
    fi
    count=$((count + 1))
    sleep 20
done
if [ "$count" -ge 720 ]; then
    printf '%s\n' 'Finalization timed out after four hours; inspect incomplete experiments.' >&2
    exit 1
fi
for experiment in qwen_api_100case_baseline qwen_api_100case_optimized; do
    "$python_bin" scripts/analyze_sprint.py --run-dir "runs/$experiment" --data-root "$data_root"
done
"$python_bin" scripts/compare_experiments.py --base runs/qwen_api_100case_baseline --optimized runs/qwen_api_100case_optimized --output runs/model_comparison/paired.json
"$python_bin" -m unittest discover -s tests -v > logs/tests_sprint_20261031_final.log 2>&1
"$python_bin" scripts/build_meeting_ppt.py --test-log logs/tests_sprint_20261031_final.log
mkdir -p outputs/ppt_final
soffice -env:UserInstallation="file://$PWD/.cache/libreoffice-worldnav-final" --headless --convert-to pdf --outdir outputs/ppt_final reports/WorldNav_阶段进展汇报_20261031.pptx
printf '%s\n' 'All final offline analyses, reports, slides, and CPU tests completed.'
