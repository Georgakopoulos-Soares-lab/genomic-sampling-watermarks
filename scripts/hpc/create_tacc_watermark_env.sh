#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
environment_name="${GSW_CONDA_ENV:-tacc_watermark}"
cuda_module="${GSW_CUDA_MODULE:-cuda/12.8}"

module load "${cuda_module}"
conda_base="$(conda info --base)"
# shellcheck disable=SC1091
source "${conda_base}/etc/profile.d/conda.sh"

if conda env list | awk 'NF && $1 !~ /^#/' | sed 's/[[:space:]]*\*$//' | grep -Fxq "${environment_name}"; then
    conda env update --name "${environment_name}" \
        --file "${repo_root}/environment/tacc_watermark.yml"
else
    conda env create --name "${environment_name}" \
        --file "${repo_root}/environment/tacc_watermark.yml"
fi

conda activate "${environment_name}"
unset PYTHONPATH
export PYTHONNOUSERSITE=1
python -m pip install --requirement "${repo_root}/environment/tacc-cu128-requirements.txt"
python -m pip install --editable "${repo_root}[models,analysis,dev]" --no-deps
python -m pip check
python "${repo_root}/scripts/hpc/check_tacc_cuda.py" --allow-no-gpu
