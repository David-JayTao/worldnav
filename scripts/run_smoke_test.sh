#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
export CUDA_VISIBLE_DEVICES=""
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 WANDB_MODE=disabled
export PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR="$PWD/.cache/matplotlib"
PYTHON="${WORLDNAV_PYTHON:-.venv-cpu/bin/python}"
if [ ! -x "$PYTHON" ]; then
    printf '%s\n' 'Create the project environment first; see docs/REPRODUCTION.md.' >&2
    exit 1
fi
mkdir -p logs
log="logs/smoke_$(date +%Y%m%dT%H%M%S)_$$.log"
if "$PYTHON" -u scripts/smoke_test.py > "$log" 2>&1; then
    cat "$log"
else
    cat "$log" >&2
    exit 1
fi
