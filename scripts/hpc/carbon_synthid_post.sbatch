#!/usr/bin/env bash
#SBATCH --job-name=gsw-synthid-post
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --time=06:00:00

set -euo pipefail

repo_root="${GSW_REPO_ROOT:?GSW_REPO_ROOT is required}"
output_root="${GSW_OUTPUT_ROOT:?GSW_OUTPUT_ROOT is required}"
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
    --allow-no-gpu \
    --output "${output_root}/environment/post_job_${SLURM_JOB_ID}.json"

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
    token_lengths=(64)
    bootstrap_replicates=200
    permutation_replicates=500
else
    if [[ "${profile}" != "full" ]]; then
        echo "unsupported profile: ${profile}" >&2
        exit 2
    fi
    case_count=256
    steps=512
    token_lengths=(64 128 256 512)
    bootstrap_replicates=20000
    permutation_replicates=100000
fi

expected_pairs=$((case_count * 2))
python scripts/run_carbon_large_detection.py \
    --output-root "${output_root}" \
    --cohort-jsonl "${cohort}" \
    --draw-index 0 \
    --draw-index 1 \
    --token-lengths "${token_lengths[@]}" \
    --target-fpr 0.01 \
    --threshold-source analytic \
    --calibration-prompts 64 \
    --experiment-label carbon-synthid-validation-v1 \
    --tournament-depth 30 \
    --context-tokens 4 \
    --context-history-size 1024 \
    --bootstrap-replicates "${bootstrap_replicates}" \
    --permutation-replicates "${permutation_replicates}" \
    --analysis-seed 2718 \
    --finalize \
    --expected-pair-count "${expected_pairs}" \
    "${case_args[@]}" \
    >"${output_root}/orchestration/logs/detection.log" 2>&1

if [[ "${profile}" == "full" ]]; then
    python scripts/compare_synthid_detectors.py \
        --output-root "${output_root}" \
        --draw-index 0 \
        --draw-index 1 \
        --token-lengths 64 512 \
        --tournament-depth 30 \
        --context-tokens 4 \
        --context-history-size 1024 \
        >"${output_root}/orchestration/logs/detector_comparison.log" 2>&1
fi

python scripts/plot_carbon_large_validation.py --output-root "${output_root}"
declare -a report_args=()
if [[ "${profile}" == "smoke" ]]; then
    report_args+=(--smoke)
fi
python scripts/render_carbon_large_report.py \
    --output-root "${output_root}" \
    "${report_args[@]}"
python scripts/validate_carbon_large_validation.py \
    --output-root "${output_root}" \
    --expected-prompts "${case_count}" \
    --expected-draws 2 \
    --expected-generated-tokens "${steps}" \
    --expected-states "${case_count}" \
    --calibration-prompts 64 \
    --require-figures \
    --require-report

echo "Post-processing stage completed for ${profile} profile at ${output_root}"
