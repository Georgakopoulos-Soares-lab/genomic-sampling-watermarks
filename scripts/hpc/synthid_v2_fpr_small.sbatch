#!/bin/bash
# One draw of one model on a single-GPU gpu-a100-small node.
# Submit from a Lonestar6 login node (compute nodes cannot submit):
#
#   sbatch --export=ALL,GSW_MODEL=carbon,GSW_DRAW=0 scripts/hpc/synthid_v2_fpr_small.sbatch
#   sbatch --export=ALL,GSW_MODEL=carbon,GSW_DRAW=1 scripts/hpc/synthid_v2_fpr_small.sbatch
#   ... likewise for GSW_MODEL=generator
#
# Then, once all four draws are finalized, one detection job per model:
#
#   sbatch --export=ALL,GSW_MODEL=carbon,GSW_STAGE=detection scripts/hpc/synthid_v2_fpr_small.sbatch
#
# Resubmitting an identical job resumes: finished per-prompt shards are validated
# and skipped. qa100small allows 12 concurrent jobs and a 2-day walltime, but a job
# is only started if it fits before the next maintenance reservation, so keep -t
# under the remaining window (check: scontrol show reservation). Override per
# submission with sbatch -t, and -p gpu-a100-dev for a two-GPU node (2h cap).
#SBATCH -J gsw_v2fpr
#SBATCH -o outputs/synthid_v2_fpr_logs/slurm_%x_%j.out
#SBATCH -e outputs/synthid_v2_fpr_logs/slurm_%x_%j.out
#SBATCH -p gpu-a100-small
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -t 12:00:00
#SBATCH -A MCB25091
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
mkdir -p outputs/synthid_v2_fpr_logs
MODEL="${GSW_MODEL:?set GSW_MODEL=carbon or generator}"
STAGE="${GSW_STAGE:-all}"
echo "node=$(hostname) job=$SLURM_JOB_ID model=$MODEL stage=$STAGE draw=${GSW_DRAW:-both} start=$(date -u +%FT%TZ)"
nvidia-smi -L || true
# GSW_DRAW selects one draw for a single-GPU node. Leave it unset on a two-GPU node
# (gpu-a100-dev) to run both draws concurrently, which is the runner's default.
if [ "$STAGE" = "detection" ]; then
  bash scripts/hpc/synthid_v2_fpr_direct.sh "$MODEL" detection
else
  bash scripts/hpc/synthid_v2_fpr_direct.sh "$MODEL" "$STAGE" "${GSW_DRAW:-}"
fi
echo "end=$(date -u +%FT%TZ)"
