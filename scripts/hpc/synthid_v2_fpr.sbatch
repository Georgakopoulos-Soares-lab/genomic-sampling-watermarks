#!/bin/bash
# Submit from a Lonestar6 login node (compute nodes cannot submit):
#
#   sbatch --export=ALL,GSW_MODEL=carbon    scripts/hpc/synthid_v2_fpr.sbatch
#   sbatch --export=ALL,GSW_MODEL=generator scripts/hpc/synthid_v2_fpr.sbatch
#
# Resubmitting the identical job resumes: completed per-prompt shards are
# validated and skipped. c301-002 is excluded because one of its A100s has
# failed RmInitAdapter, which makes /dev/nvidia-uvm unopenable for every job
# on that node. Drop the exclusion once TACC repairs it.
#SBATCH -J gsw_synthid_v2_fpr
#SBATCH -o outputs/synthid_v2_fpr_logs/slurm_%x_%j.out
#SBATCH -e outputs/synthid_v2_fpr_logs/slurm_%x_%j.out
#SBATCH -p gpu-a100
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -t 48:00:00
#SBATCH -A MCB25091
#SBATCH --exclude=c301-002
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
mkdir -p outputs/synthid_v2_fpr_logs
echo "node=$(hostname) job=$SLURM_JOB_ID start=$(date -u +%FT%TZ)"
bash scripts/hpc/synthid_v2_fpr_direct.sh "${GSW_MODEL:?set GSW_MODEL=carbon or generator}" all
echo "end=$(date -u +%FT%TZ)"
