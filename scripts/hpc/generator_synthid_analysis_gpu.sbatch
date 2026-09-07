#!/usr/bin/env bash
#SBATCH --job-name=gsw-generator-analysis
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --time=02:00:00

# Resume only the two GPU analyses after generation has completed.  This is
# deliberately separate from generator_synthid_gpu.sbatch: the full-generation
# job can reach a development-queue time limit after writing the immutable
# sequence corpus, and rerunning generation would waste the completed work.

set -euo pipefail

repo_root="${GSW_REPO_ROOT:?GSW_REPO_ROOT is required}"
output_root="${GSW_OUTPUT_ROOT:?GSW_OUTPUT_ROOT is required}"
cache_dir="${GSW_HF_CACHE:?GSW_HF_CACHE is required}"
cohort="${GSW_COHORT:-${repo_root}/data/processed/ncbi_refseq_eukaryote_windows_large_v1/prompts.jsonl}"

# shellcheck disable=SC1091
source "${repo_root}/scripts/hpc/lib_tacc.sh"
activate_tacc_watermark
cd "${repo_root}"

mkdir -p "${output_root}/orchestration/logs" "${output_root}/environment"
python scripts/hpc/freeze_source_manifest.py \
    --output "${output_root}/orchestration/source_manifest.json" \
    --verify
python scripts/hpc/check_tacc_cuda.py \
    --require-slurm \
    --minimum-gpus 2 \
    --output "${output_root}/environment/analysis_job_${SLURM_JOB_ID}.json"

distribution_summary="${output_root}/distribution/distribution_summary.json"
distribution_trials="${output_root}/distribution/fixed_state_trials.parquet"
if [[ -f "${distribution_summary}" && -f "${distribution_trials}" ]]; then
    echo "Complete distribution outputs already exist; skipping distribution resume." \
        >"${output_root}/orchestration/logs/distribution_resume.log"
    distribution_pid=""
else
    CUDA_VISIBLE_DEVICES=0 python scripts/run_generator_large_distribution.py \
    --output-root "${output_root}" \
    --cohort-jsonl "${cohort}" \
    --draw-zero-sequences "${output_root}/generation/draw_00_sequences.jsonl" \
    --state-token-index 64 \
    --draws 5000 \
    --replicates 999 \
    --gof-seed 2718 \
    --negative-control-states 8 \
    --experiment-label generator-synthid-validation-v1/distribution \
    --tournament-depth 30 \
    --context-tokens 4 \
    --context-history-size 1024 \
    --key-average-replicates 64 \
    --device cuda \
    --dtype bfloat16 \
    --cache-dir "${cache_dir}" \
    --local-files-only \
    --bootstrap-replicates 20000 \
    --permutation-replicates 100000 \
    --analysis-seed 2718 \
    --finalize \
    --expected-state-count 256 \
        >"${output_root}/orchestration/logs/distribution_resume.log" 2>&1 &
    distribution_pid=$!
fi

sequence_summary="${output_root}/sequence_comparison/sequence_comparison_summary.json"
sequence_metrics="${output_root}/sequence_comparison/sequence_metrics.parquet"
if [[ -f "${sequence_summary}" && -f "${sequence_metrics}" ]]; then
    echo "Complete sequence-comparison outputs already exist; skipping sequence resume." \
        >"${output_root}/orchestration/logs/sequence_comparison_resume.log"
    sequence_pid=""
else
    CUDA_VISIBLE_DEVICES=1 python scripts/analyze_generator_large_sequences.py \
    --output-root "${output_root}" \
    --cohort-jsonl "${cohort}" \
    --draw-index 0 \
    --draw-index 1 \
    --device cuda \
    --dtype bfloat16 \
    --cache-dir "${cache_dir}" \
    --local-files-only \
    --bootstrap-replicates 20000 \
    --permutation-replicates 100000 \
    --analysis-seed 2718 \
    --finalize \
    --expected-sequence-count 1024 \
        >"${output_root}/orchestration/logs/sequence_comparison_resume.log" 2>&1 &
    sequence_pid=$!
fi

distribution_status=0
sequence_status=0
set +e
if [[ -n "${distribution_pid}" ]]; then
    wait "${distribution_pid}"
    distribution_status=$?
fi
if [[ -n "${sequence_pid}" ]]; then
    wait "${sequence_pid}"
    sequence_status=$?
fi
set -e
if (( distribution_status != 0 || sequence_status != 0 )); then
    echo "GPU analyses failed: distribution=${distribution_status}, sequence=${sequence_status}" >&2
    exit 1
fi

echo "GPU analyses completed at ${output_root}"
