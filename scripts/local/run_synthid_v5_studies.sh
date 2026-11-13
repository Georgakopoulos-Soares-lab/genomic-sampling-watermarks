#!/usr/bin/env bash
# Unattended S0 to S4 of the v5 review studies on the locally generated cohort.
#
# Protocol: docs/research/synthid_v5_review_studies_protocol_2026_11_12.md.
#
# Usage:
#   scripts/local/run_synthid_v5_studies.sh detect <carbon|generator>   # collect, S0, S1, S2, S3
#   scripts/local/run_synthid_v5_studies.sh final                       # S3 natural DNA, S4, S2 timing
#
# Environment (defaults are the protocol values; override only for a smoke test):
#   N_EVAL=512  S2_PROMPTS=256  WORKERS=12  V5_ROOT=outputs/synthid_v5_local
#   V5_OUT=$V5_ROOT (where merged cohorts and study outputs go)
# Every step is write-once and resumable; rerunning the same command continues.
set -euo pipefail

STAGE="${1:?stage: detect or final}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="$ROOT/.venv/bin/python"
N_EVAL="${N_EVAL:-512}"
S2_PROMPTS="${S2_PROMPTS:-256}"
WORKERS="${WORKERS:-12}"
V5_ROOT="${V5_ROOT:-$ROOT/outputs/synthid_v5_local}"
V5_OUT="${V5_OUT:-$V5_ROOT}"
COHORT="$ROOT/data/processed/ncbi_refseq_eukaryote_windows_fpr_v2_1608/prompts.jsonl"
PROTOCOL="$ROOT/docs/research/synthid_v5_review_studies_protocol_2026_11_12.md"
IDS_ALL="$V5_ROOT/evaluated_case_ids.txt"

export HF_HOME="$ROOT/.cache/huggingface" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false PYTHONNOUSERSITE=1 PYTHONPATH="$ROOT/src"

policy() { [[ "$1" == carbon ]] && echo C_tok || echo G_tok; }
step() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

detect() {
  local model="$1" label="$1-synthid-local-v5" gen_id="$1_synthid_v5_local_generation"
  local det_id="$1_synthid_v5_local_position_independent"
  local merged="$V5_OUT/$model/merged" studies="$V5_OUT/$model/studies"
  local ids="$V5_OUT/$model/evaluated_case_ids.txt"
  mkdir -p "$merged/generation/sessions" "$merged/detection" "$studies"
  head -n "$N_EVAL" "$IDS_ALL" > "$ids.tmp" && mv "$ids.tmp" "$ids"
  [[ "$(wc -l < "$ids" | tr -d ' ')" == "$N_EVAL" ]] || { echo "bad id list" >&2; exit 1; }

  step "$model: collect shards"
  local draw case_id source target part count
  for draw in 00 01; do
    mkdir -p "$merged/generation/shards/draw_$draw"
    while IFS= read -r case_id; do
      target="$merged/generation/shards/draw_$draw/$case_id.json"
      count=0
      for part in "$V5_ROOT/$model/parts"/p*; do
        source="$part/generation/shards/draw_$draw/$case_id.json"
        if [[ -f "$source" ]]; then
          count=$((count + 1))
          if [[ -f "$target" ]]; then cmp -s "$source" "$target"; else cp "$source" "$target"; fi
        fi
      done
      [[ "$count" == 1 ]] || { echo "$case_id draw $draw: found in $count parts" >&2; exit 1; }
    done < "$ids"
  done
  for part in "$V5_ROOT/$model/parts"/p*; do
    for source in "$part"/generation/sessions/draw_*_session_*.json; do
      [[ -f "$source" ]] || continue
      # Carbon numbers its session files per directory, so prefix the part name.
      target="$merged/generation/sessions/$(basename "$source" | sed "s/_session_/_session_$(basename "$part")_/")"
      [[ -f "$target" ]] || cp "$source" "$target"
    done
  done

  local case_args=()
  while IFS= read -r case_id; do case_args+=(--case-id "$case_id"); done < "$ids"

  step "$model: finalize generation"
  for draw in 0 1; do
    "$PY" "$ROOT/scripts/run_${model}_large_generation.py" \
      --cohort-jsonl "$COHORT" --draw-index "$draw" --steps 512 \
      --experiment-label "$label" --experiment-id "$gen_id" \
      --tournament-depth 30 --context-tokens 4 --context-history-size 1024 \
      --device mps --dtype bfloat16 --cache-dir "$ROOT/.cache/huggingface" --local-files-only \
      --output-root "$merged" --finalize-only --expected-case-count "$N_EVAL" "${case_args[@]}"
  done
  "$PY" "$ROOT/scripts/summarize_${model}_large_generation.py" --output-root "$merged" \
    --cohort-jsonl "$COHORT" --draw-index 0 --draw-index 1 \
    --expected-case-count "$N_EVAL" --experiment-id "$gen_id"

  if [[ ! -f "$merged/detection/prompt_split.json" ]]; then
    "$PY" - "$COHORT" "$ids" "$merged/detection/prompt_split.json" <<'EOF'
import json, sys
from genomic_watermarks.large_validation import CALIBRATION_SPLIT_LABEL

all_ids = [str(json.loads(line)["prompt_id"]) for line in open(sys.argv[1]) if line.strip()]
evaluated = set(open(sys.argv[2]).read().split())
record = {
    "schema_version": 1,
    "label": CALIBRATION_SPLIT_LABEL,
    "assignment_rule": (
        "rank sha256(label, case_id); first 64 reserved; the next "
        f"{len(evaluated)} are evaluation; every other prompt is not_evaluated (v5 protocol, Section 3)"
    ),
    "calibration_prompts": 64,
    "assignments": {c: "evaluation" if c in evaluated else "not_evaluated" for c in all_ids},
}
open(sys.argv[3], "w").write(json.dumps(record, indent=2, sort_keys=True) + "\n")
EOF
  fi

  step "$model: S0 verifier on the reference layout"
  if [[ ! -f "$merged/position_independent/summary.json" ]]; then
    "$PY" "$ROOT/scripts/run_${model}_synthid_position_independent.py" \
      --validation-root "$merged" --cohort-jsonl "$COHORT" --protocol "$PROTOCOL" \
      --output-dir "$merged/position_independent" --workers "$WORKERS" \
      --experiment-id "$det_id" --generation-experiment-id "$gen_id" \
      --experiment-label "$label" --expected-evaluation-prompts "$N_EVAL"
  fi
  "$PY" "$ROOT/scripts/validate_${model}_synthid_position_independent.py" \
    --output-dir "$merged/position_independent" --experiment-id "$det_id" \
    --expected-evaluation-prompts "$N_EVAL" \
    || echo "WARNING: S0 bundle validator failed for $model (recorded; see log)"

  step "$model: S1 layout study"
  if [[ ! -f "$studies/s1_layout/summary.json" ]]; then
    "$PY" "$ROOT/scripts/run_synthid_v5_layout.py" --generation-root "$merged" \
      --experiment-label "$label" --policy-id "$(policy "$model")" \
      --generation-experiment-id "$gen_id" --evaluated-prompts "$N_EVAL" \
      --s0-trials "$merged/position_independent/trials.jsonl" \
      --output-dir "$studies/s1_layout" --workers "$WORKERS"
  fi

  step "$model: S2 detector comparison"
  if [[ ! -f "$studies/s2_detectors/summary.json" ]]; then
    "$PY" "$ROOT/scripts/run_synthid_v5_detector_comparison.py" --generation-root "$merged" \
      --experiment-label "$label" --policy-id "$(policy "$model")" \
      --generation-experiment-id "$gen_id" --evaluated-prompts "$N_EVAL" \
      --prompts "$S2_PROMPTS" --output-dir "$studies/s2_detectors" --workers "$WORKERS"
  fi

  local family
  for family in ordinary_model_output marked_independent_key; do
    step "$model: S3 null calibration, $family"
    if [[ ! -f "$studies/s3_null_$family/summary.json" ]]; then
      "$PY" "$ROOT/scripts/run_synthid_v5_null_calibration.py" --family "$family" \
        --model "$model" --generation-root "$merged" --experiment-label "$label" \
        --generation-experiment-id "$gen_id" --n-eval "$N_EVAL" \
        --output-dir "$studies/s3_null_$family" --workers "$WORKERS"
    fi
  done
  step "$model: detect stage done"
}

final() {
  local shared="$V5_OUT/shared" model
  mkdir -p "$shared"
  step "S3 null calibration, natural DNA"
  if [[ ! -f "$shared/s3_null_natural_dna/summary.json" ]]; then
    "$PY" "$ROOT/scripts/run_synthid_v5_null_calibration.py" --family natural_dna \
      --output-dir "$shared/s3_null_natural_dna" --workers "$WORKERS"
  fi
  for model in generator carbon; do
    step "$model: S4 entropy pass"
    "$PY" "$ROOT/scripts/run_synthid_v5_entropy.py" --model "$model" \
      --generation-root "$V5_OUT/$model/merged" --experiment-label "$model-synthid-local-v5" \
      --generation-experiment-id "${model}_synthid_v5_local_generation" --n-eval "$N_EVAL" \
      --output-dir "$V5_OUT/$model/studies/s4_entropy" --device mps --dtype bfloat16
  done
  step "S4 analysis"
  if [[ ! -f "$shared/s4_entropy_analysis/summary.json" ]]; then
    "$PY" "$ROOT/scripts/analyze_synthid_v5_entropy.py" \
      --carbon-entropy-dir "$V5_OUT/carbon/studies/s4_entropy" \
      --carbon-s0-trials "$V5_OUT/carbon/merged/position_independent/trials.jsonl" \
      --carbon-generation-root "$V5_OUT/carbon/merged" \
      --generator-entropy-dir "$V5_OUT/generator/studies/s4_entropy" \
      --generator-s0-trials "$V5_OUT/generator/merged/position_independent/trials.jsonl" \
      --generator-generation-root "$V5_OUT/generator/merged" \
      --output-dir "$shared/s4_entropy_analysis"
  fi
  # Runtime last, single process, nothing else running.
  local timing_prompts=$((S2_PROMPTS < 32 ? S2_PROMPTS : 32))
  for model in generator carbon; do
    step "$model: S2 single-process timing"
    if [[ ! -f "$V5_OUT/$model/studies/s2_timing/summary.json" ]]; then
      "$PY" "$ROOT/scripts/run_synthid_v5_detector_comparison.py" \
        --generation-root "$V5_OUT/$model/merged" --experiment-label "$model-synthid-local-v5" \
        --policy-id "$(policy "$model")" \
        --generation-experiment-id "${model}_synthid_v5_local_generation" \
        --evaluated-prompts "$N_EVAL" --prompts "$timing_prompts" --timing-only \
        --output-dir "$V5_OUT/$model/studies/s2_timing"
    fi
  done
  step "final stage done"
}

case "$STAGE" in
  detect) detect "${2:?model}" ;;
  final) final ;;
  *) echo "unknown stage: $STAGE" >&2; exit 2 ;;
esac
