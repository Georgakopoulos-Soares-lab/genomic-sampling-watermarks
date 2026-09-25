#!/bin/bash
#SBATCH -J gsw_tests
#SBATCH -o outputs/synthid_v2_fpr_logs/slurm_%x_%j.out
#SBATCH -e outputs/synthid_v2_fpr_logs/slurm_%x_%j.out
#SBATCH -p development
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -t 00:30:00
#SBATCH -A MCB25091
set -uo pipefail
cd "$SLURM_SUBMIT_DIR"
unset PYTHONPATH PYTHONHOME
export PYTHONNOUSERSITE=1
PY=/scratch/10899/kimopro/conda/envs/tacc_watermark/bin/python
echo "node=$(hostname) start=$(date -u +%FT%TZ)"
$PY -c "import numpy,scipy;print('numpy',numpy.__version__,'scipy',scipy.__version__)"
PYTHONPATH=src $PY -m unittest discover -s tests -v 2>&1 | tail -40
echo "UNITTEST_EXIT=${PIPESTATUS[0]}"
echo "--- detector CLI still accepts v1-style invocation (default generation id) ---"
$PY scripts/run_carbon_synthid_position_independent.py --help 2>&1 | grep -A2 'generation-experiment-id'
echo "end=$(date -u +%FT%TZ)"
