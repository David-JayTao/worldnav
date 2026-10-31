#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
data_root="${WORLDNAV_DATA_ROOT:?Set WORLDNAV_DATA_ROOT}"
python_bin="${WORLDNAV_API_PYTHON:-$HOME/.venv/bin/python}"
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
attempt=0
while [ "$attempt" -lt 3 ]; do
    attempt=$((attempt + 1))
    if "$python_bin" -u scripts/download_validation.py --data-root "$data_root"; then
        "$python_bin" -u scripts/audit_validation.py --data-root "$data_root" --output "outputs/full_validation_audit_$(date +%Y%m%dT%H%M%S).json"
        exit 0
    fi
    printf 'Validation resume cycle %s failed; partial files preserved.\n' "$attempt"
    if [ "$attempt" -lt 3 ]; then sleep "$((15 * (1 << (attempt - 1))))"; fi
done
printf '%s\n' 'Validation downloader stopped after three bounded resume cycles; inspect logs.' >&2
exit 1
