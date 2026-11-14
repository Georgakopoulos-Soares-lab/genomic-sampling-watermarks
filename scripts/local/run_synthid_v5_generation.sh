#!/usr/bin/env bash
# Generate the local v5 review cohort for one model on Apple MPS.
#
# Protocol: docs/research/synthid_v5_review_studies_protocol_2026_11_12.md, Section 3.
# Three processes over disjoint prompts, each with its own output root; each process
# generates draw 0 and then draw 1. Completed per-prompt shards are skipped on rerun.
#
# Usage: scripts/local/run_synthid_v5_generation.sh <carbon|generator>
set -euo pipefail

MODEL="${1:?model: carbon or generator}"
N_EVAL=512
PROCESSES=3
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"
COHORT="$ROOT/data/processed/ncbi_refseq_eukaryote_windows_fpr_v2_1608/prompts.jsonl"
OUT="$ROOT/outputs/synthid_v5_local/$MODEL"
IDS="$ROOT/outputs/synthid_v5_local/evaluated_case_ids.txt"

case "$MODEL" in
  carbon | generator) ;;
  *) echo "unknown model: $MODEL" >&2; exit 2 ;;
esac

export HF_HOME="$ROOT/.cache/huggingface" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false PYTHONNOUSERSITE=1

mkdir -p "$OUT/logs"
if [[ ! -f "$IDS" ]]; then
  PYTHONPATH="$ROOT/src" "$PYTHON" - "$COHORT" "$N_EVAL" > "$IDS.tmp" <<'EOF'
import hashlib, json, sys
from genomic_watermarks.large_validation import CALIBRATION_SPLIT_LABEL, deterministic_prompt_split

rows = [json.loads(line) for line in open(sys.argv[1]) if line.strip()]
ids = [str(row["prompt_id"]) for row in rows]
ranked = sorted(
    ids,
    key=lambda c: (hashlib.sha256(f"{CALIBRATION_SPLIT_LABEL}\x00{c}".encode()).digest(), c),
)
held_out = ranked[64:]
split = deterministic_prompt_split(ids, calibration_prompts=64, label=CALIBRATION_SPLIT_LABEL)
assert set(held_out) == {c for c, v in split.items() if v == "evaluation"}
assert len(held_out) == 1544
print("\n".join(held_out[: int(sys.argv[2])]))
EOF
  mv "$IDS.tmp" "$IDS"
fi
[[ "$(wc -l < "$IDS" | tr -d ' ')" == "$N_EVAL" ]] || { echo "bad id list" >&2; exit 1; }

pids=()
for ((k = 0; k < PROCESSES; k++)); do
  case_args=()
  while IFS= read -r case_id; do
    case_args+=(--case-id "$case_id")
  done < <(awk -v k="$k" -v n="$PROCESSES" '(NR - 1) % n == k' "$IDS")
  (
    for draw in 0 1; do
      "$PYTHON" "$ROOT/scripts/run_${MODEL}_large_generation.py" \
        --cohort-jsonl "$COHORT" --draw-index "$draw" --steps 512 \
        --experiment-label "${MODEL}-synthid-local-v5" \
        --experiment-id "${MODEL}_synthid_v5_local_generation" \
        --tournament-depth 30 --context-tokens 4 --context-history-size 1024 \
        --device mps --dtype bfloat16 \
        --cache-dir "$ROOT/.cache/huggingface" --local-files-only \
        --output-root "$OUT/parts/p$k" "${case_args[@]}"
    done
  ) > "$OUT/logs/p$k.$(date -u +%Y%m%dT%H%M%SZ).log" 2>&1 &
  pids+=($!)
done

status=0
for pid in "${pids[@]}"; do
  wait "$pid" || status=1
done
echo "generation $MODEL finished with status $status"
exit "$status"
