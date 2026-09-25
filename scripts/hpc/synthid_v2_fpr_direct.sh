#!/bin/bash
# Resumable driver for the SynthID v2 false-positive-rate run (Lane 1, L1-01).
#
#   bash scripts/hpc/synthid_v2_fpr_direct.sh <carbon|generator> [smoke|full|all]
#
# Runs inside a GPU allocation that exposes two healthy A100s. Every stage is an
# immutable per-prompt checkpoint: rerunning the identical command validates and
# skips finished shards, so an interrupted allocation is resumed by repeating it.
set -euo pipefail

MODEL="${1:?usage: synthid_v2_fpr_direct.sh <carbon|generator> [smoke|full|all|detection] [draw]}"
WHAT="${2:-all}"
# Third argument selects one draw (0 or 1) so a single-GPU partition can run one draw per
# job. Omit it on a two-GPU node to run both draws concurrently.
DRAW="${3:-}"
DRAW_ARG=()
if [ -n "$DRAW" ]; then
  case "$DRAW" in 0|1) DRAW_ARG=(--draw "$DRAW") ;; *) echo "draw must be 0 or 1" >&2; exit 2 ;; esac
fi
NEED_GPUS=1
[ -z "$DRAW" ] && NEED_GPUS=2
case "$MODEL" in carbon|generator) ;; *) echo "unknown model: $MODEL" >&2; exit 2 ;; esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PYTHON="${GSW_PYTHON:-/scratch/10899/kimopro/conda/envs/tacc_watermark/bin/python}"
COHORT="$ROOT/data/processed/ncbi_refseq_eukaryote_windows_fpr_v2_1608/prompts.jsonl"
PROTOCOL="$ROOT/docs/research/synthid_v2_fpr_scaling_protocol_2026_09_21.md"
CONFIG="$ROOT/configs/${MODEL}_synthid_v2_fpr_hpc.toml"
SMOKE_ROOT="${GSW_SMOKE_ROOT:-/scratch/10899/kimopro/synthid_v2_fpr_smoke/$MODEL}"
FULL_ROOT="${GSW_FULL_ROOT:-/scratch/10899/kimopro/synthid_v2_fpr/$MODEL}"
LOG_DIR="$ROOT/outputs/synthid_v2_fpr_logs"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$LOG_DIR"

# Frozen identity gates. These digests are recorded in the protocol document.
EXPECT_PROTOCOL_SHA256="ad950bfdda3d664d7691574d4d88e3403d84cd438a7961f6ebfb25a787523d32"
EXPECT_PROMPTS_SHA256="cb19e90662fcb25f774b0840e2e696132e2dc9c54439d97597bd186d4948f775"

module load cuda/12.8 2>/dev/null || true

# Slurm --export=ALL carries the submitting login shell's environment into the job,
# including a PYTHONPATH pointing at the system Python 3.9 site-packages. Keep this
# Python 3.12 environment hermetic so only the conda environment supplies packages.
unset PYTHONPATH PYTHONHOME
export PYTHONNOUSERSITE=1

export GSW_HF_CACHE="$ROOT/.cache/huggingface"
export HF_HOME="$GSW_HF_CACHE"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false

check_sha() {  # path expected label
  local got; got="$(sha256sum "$1" | cut -d' ' -f1)"
  if [ "$got" != "$2" ]; then
    echo "FATAL: $3 digest changed: $got != $2" >&2; exit 3
  fi
}
check_sha "$PROTOCOL" "$EXPECT_PROTOCOL_SHA256" "protocol"
check_sha "$COHORT"   "$EXPECT_PROMPTS_SHA256"  "cohort prompts"

# Hard preflight: fail on a node that cannot run this job before doing any work.
# The position-independent detector is CPU bound and never touches CUDA, so a
# detection-only job can run on an ordinary compute partition.
if [ "$WHAT" != "detection" ]; then
  "$PYTHON" scripts/hpc/check_v2_fpr_node.py --gpus "$NEED_GPUS"
else
  echo "detection stage: CPU only, skipping the GPU preflight"
fi

run_stage() {  # profile output_root extra...
  local profile="$1"; shift
  local out="$1"; shift
  echo "=== $MODEL/$profile -> $out ($(date -u +%FT%TZ)) ==="
  "$PYTHON" scripts/hpc/run_direct_synthid_fpr.py \
    --model "$MODEL" --profile "$profile" \
    --cohort-jsonl "$COHORT" --output-root "$out" \
    --config "$CONFIG" --protocol "$PROTOCOL" "${DRAW_ARG[@]}" "$@" \
    2>&1 | tee -a "$LOG_DIR/${MODEL}_${profile}_${STAMP}.log"
}

if [ "$WHAT" = "smoke" ] || [ "$WHAT" = "all" ]; then
  run_stage smoke "$SMOKE_ROOT"
fi
if [ "$WHAT" = "full" ] || [ "$WHAT" = "all" ]; then
  run_stage full "$FULL_ROOT" --stage generation
fi
# Detection needs both draws finalized, so it is a separate step that the last
# finishing job (or a later job) runs. It is CPU bound and re-entrant.
if [ "$WHAT" = "detection" ]; then
  # The detector parallelises over evaluation prompts, so give it the node's cores.
  run_stage full "$FULL_ROOT" --stage detection --workers "${GSW_WORKERS:-${SLURM_CPUS_ON_NODE:-$(nproc)}}"
fi

echo "=== status ==="
"$PYTHON" scripts/hpc/run_direct_synthid_fpr.py --model "$MODEL" --profile full \
  --cohort-jsonl "$COHORT" --output-root "$FULL_ROOT" --status
