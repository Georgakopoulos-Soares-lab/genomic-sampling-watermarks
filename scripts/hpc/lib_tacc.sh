#!/usr/bin/env bash

# Shared Lonestar6 activation. This file is sourced by batch jobs and therefore
# deliberately does not enable shell options or execute work on import.

activate_tacc_watermark() {
    local environment_name="${GSW_CONDA_ENV:-tacc_watermark}"
    local cuda_module="${GSW_CUDA_MODULE:-cuda/12.8}"

    if ! type module >/dev/null 2>&1; then
        echo "TACC module function is unavailable" >&2
        return 1
    fi
    module load "${cuda_module}"

    local conda_base
    conda_base="$(conda info --base)"
    # shellcheck disable=SC1091
    source "${conda_base}/etc/profile.d/conda.sh"
    conda activate "${environment_name}"

    # TACC injects an Intel MPI Python 3.9 directory. It is ABI-incompatible
    # with this Python 3.12 environment and must not enter model jobs.
    unset PYTHONPATH
    export PYTHONNOUSERSITE=1
    export HF_HUB_DISABLE_TELEMETRY=1
    export TOKENIZERS_PARALLELISM=false
    export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
}

