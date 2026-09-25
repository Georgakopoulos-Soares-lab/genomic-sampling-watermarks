#!/bin/bash
# Full-cohort edit-rate run (L1-07), governed by
# docs/research/synthid_v3_edit_rate_protocol_2026_09_24.md.
# CPU only: it re-scores the frozen v2 reads and never regenerates.
#
#   sbatch --export=ALL,GSW_MODEL=carbon    scripts/hpc/synthid_v3_edit_rate.sbatch
#   sbatch --export=ALL,GSW_MODEL=generator scripts/hpc/synthid_v3_edit_rate.sbatch
#SBATCH -J gsw_v3edit
#SBATCH -o outputs/synthid_v2_fpr_logs/slurm_%x_%j.out
#SBATCH -e outputs/synthid_v2_fpr_logs/slurm_%x_%j.out
#SBATCH -p development
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -t 02:00:00
#SBATCH -A MCB25091
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
# Slurm --export=ALL carries the login shell's PYTHONPATH; keep the interpreter hermetic.
unset PYTHONPATH PYTHONHOME
export PYTHONNOUSERSITE=1
MODEL="${GSW_MODEL:?set GSW_MODEL=carbon or generator}"
PY=/scratch/10899/kimopro/conda/envs/tacc_watermark/bin/python
WORKERS="${GSW_WORKERS:-${SLURM_CPUS_ON_NODE:-16}}"
echo "node=$(hostname) model=$MODEL workers=$WORKERS start=$(date -u +%FT%TZ)"
$PY -c "import numpy,scipy;print('numpy',numpy.__version__,'scipy',scipy.__version__)"
PYTHONPATH=src $PY scripts/run_synthid_edit_rate_pilot.py \
  --validation-root "/scratch/10899/kimopro/synthid_v2_fpr/$MODEL" \
  --cohort-jsonl data/processed/ncbi_refseq_eukaryote_windows_fpr_v2_1608/prompts.jsonl \
  --output "evidence/derived/edit_rate_v3_${MODEL}_2026_09_24.json" \
  --prompts 1544 --workers "$WORKERS" \
  --edit-label synthid-edit-rate-v3 \
  --classification validation_result_pending_evidence_admission \
  --protocol docs/research/synthid_v3_edit_rate_protocol_2026_09_24.md
echo "end=$(date -u +%FT%TZ)"
