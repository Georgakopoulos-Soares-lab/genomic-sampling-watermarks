#!/usr/bin/env bash
#SBATCH --job-name=gsw-generator-gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --time=24:00:00

set -euo pipefail

repo_root="${GSW_REPO_ROOT:?GSW_REPO_ROOT is required}"
output_root="${GSW_OUTPUT_ROOT:?GSW_OUTPUT_ROOT is required}"
cache_dir="${GSW_HF_CACHE:?GSW_HF_CACHE is required}"
profile="${GSW_PROFILE:-full}"
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
    --output "${output_root}/environment/gpu_job_${SLURM_JOB_ID}.json"

declare -a case_args=()
if [[ "${profile}" == "smoke" ]]; then
    mapfile -t smoke_cases < <(
        python scripts/hpc/select_smoke_cases.py \
            --cohort-jsonl "${cohort}" \
            --calibration-prompts 64
    )
    for case_id in "${smoke_cases[@]}"; do
        case_args+=(--case-id "${case_id}")
    done
    case_count=4
    steps=64
    distribution_draws=500
    distribution_replicates=99
    key_average_replicates=8
    bootstrap_replicates=200
    permutation_replicates=500
else
    if [[ "${profile}" != "full" ]]; then
        echo "unsupported profile: ${profile}" >&2
        exit 2
    fi
    case_count=256
    steps=512
    distribution_draws=5000
    distribution_replicates=999
    key_average_replicates=64
    bootstrap_replicates=20000
    permutation_replicates=100000
fi

run_generation() {
    local physical_gpu="$1"
    local draw_id="$2"
    CUDA_VISIBLE_DEVICES="${physical_gpu}" python scripts/run_generator_large_generation.py \
        --output-root "${output_root}" \
        --cohort-jsonl "${cohort}" \
        --draw-index "${draw_id}" \
        --steps "${steps}" \
        --experiment-label generator-synthid-validation-v1 \
        --tournament-depth 30 \
        --context-tokens 4 \
        --context-history-size 1024 \
        --device cuda \
        --dtype bfloat16 \
        --cache-dir "${cache_dir}" \
        --local-files-only \
        --finalize \
        --expected-case-count "${case_count}" \
        "${case_args[@]}"
}

run_generation 0 0 >"${output_root}/orchestration/logs/generation_draw_00.log" 2>&1 &
generation_zero_pid=$!
run_generation 1 1 >"${output_root}/orchestration/logs/generation_draw_01.log" 2>&1 &
generation_one_pid=$!

set +e
wait "${generation_zero_pid}"
generation_zero_status=$?
wait "${generation_one_pid}"
generation_one_status=$?
set -e
if (( generation_zero_status != 0 || generation_one_status != 0 )); then
    echo "generation failed: draw0=${generation_zero_status}, draw1=${generation_one_status}" >&2
    exit 1
fi

python scripts/summarize_generator_large_generation.py \
    --output-root "${output_root}" \
    --cohort-jsonl "${cohort}" \
    --draw-index 0 \
    --draw-index 1 \
    --expected-case-count "${case_count}"

CUDA_VISIBLE_DEVICES=0 python scripts/run_generator_large_distribution.py \
    --output-root "${output_root}" \
    --cohort-jsonl "${cohort}" \
    --draw-zero-sequences "${output_root}/generation/draw_00_sequences.jsonl" \
    --state-token-index 64 \
    --draws "${distribution_draws}" \
    --replicates "${distribution_replicates}" \
    --gof-seed 2718 \
    --negative-control-states 8 \
    --experiment-label generator-synthid-validation-v1/distribution \
    --tournament-depth 30 \
    --context-tokens 4 \
    --context-history-size 1024 \
    --key-average-replicates "${key_average_replicates}" \
    --device cuda \
    --dtype bfloat16 \
    --cache-dir "${cache_dir}" \
    --local-files-only \
    --bootstrap-replicates "${bootstrap_replicates}" \
    --permutation-replicates "${permutation_replicates}" \
    --analysis-seed 2718 \
    --finalize \
    --expected-state-count "${case_count}" \
    "${case_args[@]}" \
    >"${output_root}/orchestration/logs/distribution.log" 2>&1 &
distribution_pid=$!

expected_sequences=$((case_count * 2 * 2))
CUDA_VISIBLE_DEVICES=1 python scripts/analyze_generator_large_sequences.py \
    --output-root "${output_root}" \
    --cohort-jsonl "${cohort}" \
    --draw-index 0 \
    --draw-index 1 \
    --device cuda \
    --dtype bfloat16 \
    --cache-dir "${cache_dir}" \
    --local-files-only \
    --bootstrap-replicates "${bootstrap_replicates}" \
    --permutation-replicates "${permutation_replicates}" \
    --analysis-seed 2718 \
    --finalize \
    --expected-sequence-count "${expected_sequences}" \
    "${case_args[@]}" \
    >"${output_root}/orchestration/logs/sequence_comparison.log" 2>&1 &
sequence_pid=$!

set +e
wait "${distribution_pid}"
distribution_status=$?
wait "${sequence_pid}"
sequence_status=$?
set -e
if (( distribution_status != 0 || sequence_status != 0 )); then
    echo "GPU analyses failed: distribution=${distribution_status}, sequence=${sequence_status}" >&2
    exit 1
fi

echo "GPU stage completed for ${profile} profile at ${output_root}"
