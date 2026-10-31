#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
py="${WORLDNAV_API_PYTHON:-$HOME/.venv/bin/python}"
# Independent finite readiness wait; no network calls and no restart of old jobs.
count=0
while [ "$count" -lt 90 ]; do
    if [ -f /data1/worldnav-data/archives/val_unseen.tar ]; then break; fi
    if ! tmux has-session -t worldnav_stage2_data 2>/dev/null; then echo 'Download stopped; full manifest not generated.'; exit 1; fi
    sleep 20
    count=$((count + 1))
done
if [ "$count" -ge 90 ]; then echo 'Full archive wait reached 30-minute bound.'; exit 1; fi
if [ ! -f configs/eval_100_full_stage2.json ]; then
    "$py" scripts/build_eval_manifest.py --data-root /data1/worldnav-data --output configs/eval_100_full_stage2.json --seed 20261101 --exclude-manifest configs/dev_12.json --exclude-manifest configs/eval_100.json
fi
