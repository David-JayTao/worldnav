#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
. "$HOME/.config/worldnav/api.env"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
python_bin="${WORLDNAV_API_PYTHON:-$HOME/.venv/bin/python}"
exec "$python_bin" -u scripts/run_api_sprint.py "$@"
