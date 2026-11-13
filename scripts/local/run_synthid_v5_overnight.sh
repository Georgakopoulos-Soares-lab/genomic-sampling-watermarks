#!/usr/bin/env bash
# Wait for local v5 generation, then run every study unattended. Logs under outputs/synthid_v5_local/logs.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
V5="$ROOT/outputs/synthid_v5_local"
mkdir -p "$V5/logs"
shards() { find "$V5/$1/parts" -path '*/shards/draw_0[01]/*.json' 2>/dev/null | wc -l | tr -d ' '; }
wait_generation() {
  until [[ "$(shards "$1")" -ge 1024 ]] && ! pgrep -f "run_${1}_large_generation.py" > /dev/null; do
    sleep 120
  done
}
status=0
for model in generator carbon; do
  wait_generation "$model"
  "$ROOT/scripts/local/run_synthid_v5_studies.sh" detect "$model" > "$V5/logs/detect_$model.log" 2>&1 \
    || { echo "detect $model FAILED; see $V5/logs/detect_$model.log"; status=1; }
done
"$ROOT/scripts/local/run_synthid_v5_studies.sh" final > "$V5/logs/final.log" 2>&1 \
  || { echo "final FAILED; see $V5/logs/final.log"; status=1; }
echo "v5 studies finished with status $status"
exit "$status"
