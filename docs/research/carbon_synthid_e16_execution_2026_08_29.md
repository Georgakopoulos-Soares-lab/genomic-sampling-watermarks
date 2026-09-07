# Carbon SynthID execution record — 2026-08-29

## Outcome

The Carbon SynthID validation completed successfully. The evidence-selected root is
`/scratch/10899/kimopro/carbon_synthid_validation_hpc_v4`; its generation corpus is a byte-identical
copy of the completed CUDA generation under `..._hpc_v3`. The strict validator passed after all
256 fixed states, 1,024 generated sequences, ten figure pairs, and the report were present.

The frozen model is `HuggingFaceBio/Carbon-500M` revision
`9796b752108258c1d365089f842e62e6c0547704`, using the normalized `C_tok` policy, bfloat16,
temperature 1, and no truncation. The cohort is
`ncbi_refseq_eukaryote_windows_large_v1`, content SHA-256
`8f7f7bba52f26837cdef5f17b542e01ab61eb1ddf7735d43dcd6f7b8d0986308`. Two public fixture-key
draws generated 512 canonical 6-mer tokens per arm and prompt. The SynthID adaptation used depth
30, four output-context tokens, and a 1,024-context repetition history.

## Execution split

| Stage | Root | Device | Outcome |
|---|---|---|---|
| generation | `..._hpc_v3` | two A100s, CUDA bfloat16 | 1,024 sequences; complete before Slurm time limit |
| fixed-state distribution | `..._hpc_v4` | Lonestar6 VM CPU bfloat16 | 256/256 states |
| teacher-forced likelihood and proxies | `..._hpc_v4` | Lonestar6 VM CPU bfloat16 | 1,024/1,024 sequences |
| detection, figures, report, validation | `..._hpc_v4` | CPU, model-free | complete; strict validation passed |

GPU job `3400067` was submitted at 2026-08-29 12:11:42Z and wrote the complete generation summary
before reaching the two-hour `gpu-a100-dev` limit. Its `afterok` post job `3400068` did not run.
Interactive MFA prevented another non-interactive login-node submission during this continuation,
so the two remaining model-backed stages used the declared CPU fallback. The exact environment is
`configs/carbon_synthid_validation_cpu_analysis_resume_v1.toml`: Python 3.13.5, PyTorch
2.8.0+cu128, Transformers 5.15.1, NumPy 2.2.6, SciPy 1.18.1, pandas 2.3.3, and PyArrow 24.0.0.
Model and tokenizer access was local-only.

## Commands

The generation submission was:

```bash
/home1/10899/kimopro/WORK/miniconda3/bin/python3 scripts/hpc/submit_carbon_synthid_validation.py --profile full --account MCB25091 --output-root /scratch/10899/kimopro/carbon_synthid_validation_hpc_v3 --gpu-partition gpu-a100-dev --gpu-time 02:00:00
```

Each fixed-state worker used the following command, with `CASE_ID` replaced by one of the 256 frozen
prompt IDs. Four disjoint workers ran concurrently:

```bash
env HF_HUB_DISABLE_TELEMETRY=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=2 /scratch/10899/kimopro/gsw-analysis-venv/bin/python scripts/run_carbon_large_distribution.py --output-root /scratch/10899/kimopro/carbon_synthid_validation_hpc_v4 --cohort-jsonl data/processed/ncbi_refseq_eukaryote_windows_large_v1/prompts.jsonl --draw-zero-sequences /scratch/10899/kimopro/carbon_synthid_validation_hpc_v4/generation/draw_00_sequences.jsonl --case-id CASE_ID --state-token-index 64 --draws 5000 --replicates 999 --gof-seed 2718 --negative-control-states 8 --experiment-label carbon-synthid-validation-v1/distribution --tournament-depth 30 --context-tokens 4 --context-history-size 1024 --key-average-replicates 64 --device cpu --dtype bfloat16 --cache-dir .cache/huggingface --local-files-only --bootstrap-replicates 20000 --permutation-replicates 100000 --analysis-seed 2718
```

The distribution finalizer used the same arguments without `--case-id`, plus
`--finalize --expected-state-count 256`. Each sequence worker likewise replaced `CASE_ID` below by
one frozen prompt ID; the primary forward pass and disjoint tail/gap resumes never intentionally
targeted the same missing shard:

```bash
env HF_HUB_DISABLE_TELEMETRY=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=2 /scratch/10899/kimopro/gsw-analysis-venv/bin/python scripts/analyze_carbon_large_sequences.py --output-root /scratch/10899/kimopro/carbon_synthid_validation_hpc_v4 --cohort-jsonl data/processed/ncbi_refseq_eukaryote_windows_large_v1/prompts.jsonl --draw-index 0 --draw-index 1 --case-id CASE_ID --device cpu --dtype bfloat16 --cache-dir .cache/huggingface --local-files-only --bootstrap-replicates 20000 --permutation-replicates 100000 --analysis-seed 2718
```

The model-free sequence finalizer, detector comparison, detection analysis, presentation, and strict
validation commands were:

```bash
env HF_HUB_DISABLE_TELEMETRY=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=2 /scratch/10899/kimopro/gsw-analysis-venv/bin/python scripts/analyze_carbon_large_sequences.py --output-root /scratch/10899/kimopro/carbon_synthid_validation_hpc_v4 --cohort-jsonl data/processed/ncbi_refseq_eukaryote_windows_large_v1/prompts.jsonl --draw-index 0 --draw-index 1 --device cpu --dtype bfloat16 --cache-dir .cache/huggingface --local-files-only --bootstrap-replicates 20000 --permutation-replicates 100000 --analysis-seed 2718 --finalize --expected-sequence-count 1024

PYTHONPATH=src python3 scripts/compare_synthid_detectors.py --output-root /scratch/10899/kimopro/carbon_synthid_validation_hpc_v4 --draw-index 0 --draw-index 1 --token-lengths 64 512 --tournament-depth 30 --context-tokens 4 --context-history-size 1024

PYTHONPATH=src /scratch/10899/kimopro/gsw-analysis-venv/bin/python scripts/run_carbon_large_detection.py --output-root /scratch/10899/kimopro/carbon_synthid_validation_hpc_v4 --cohort-jsonl data/processed/ncbi_refseq_eukaryote_windows_large_v1/prompts.jsonl --draw-index 0 --draw-index 1 --token-lengths 64 128 256 512 --target-fpr 0.01 --threshold-source analytic --calibration-prompts 64 --experiment-label carbon-synthid-validation-v1 --tournament-depth 30 --context-tokens 4 --context-history-size 1024 --bootstrap-replicates 20000 --permutation-replicates 100000 --analysis-seed 2718 --finalize --expected-pair-count 512

/scratch/10899/kimopro/gsw-analysis-venv/bin/python scripts/plot_carbon_large_validation.py --output-root /scratch/10899/kimopro/carbon_synthid_validation_hpc_v4

/scratch/10899/kimopro/gsw-analysis-venv/bin/python scripts/render_carbon_large_report.py --output-root /scratch/10899/kimopro/carbon_synthid_validation_hpc_v4

PYTHONPATH=src /scratch/10899/kimopro/gsw-analysis-venv/bin/python scripts/validate_carbon_large_validation.py --output-root /scratch/10899/kimopro/carbon_synthid_validation_hpc_v4 --expected-prompts 256 --expected-draws 2 --expected-generated-tokens 512 --expected-states 256 --calibration-prompts 64 --require-figures --require-report
```

## Result summary

- Fixed-state goodness-of-fit: 13/256 tournament arms rejected their exact fixed-key tournament
  law at nominal alpha 0.05, versus 12.8 expected; the ordinary control had 12/256. The Monte Carlo
  p-value floor, 0.001, is above the 256-test Bonferroni cutoff, 0.0001953125, so zero Bonferroni
  rejections is not evidence of fit. All 8 deliberately broken negative controls rejected after
  Bonferroni correction.
- Teacher-forced Carbon NLL: watermarked minus ordinary was 0.0085207727 nat/token, 95% prompt-
  cluster interval [-0.0442604834, 0.0597329415], p=0.7506224938. No declared sequence proxy was
  significant after Benjamini-Hochberg correction.
- Clean detection TPR at 384, 768, 1,536, and 3,072 bases was 0.9973958333, 0.9973958333,
  0.9973958333, and 1.0. Corresponding held-out ordinary FPR was 0.0078125, 0.0052083333,
  0.015625, and 0.015625.
- The analytic-threshold fit checks used all 512 corresponding-key ordinary trials and observed
  0.009765625, 0.005859375, 0.017578125, and 0.013671875. Every prompt-cluster interval contained
  its exact binomial-lattice expectation near 0.01.
- Calibration-only detector separation favored the unweighted mean at both declared lengths:
  20.6949 versus 19.0223 ordinary-arm SD at 384 bases and 64.8415 versus 56.8352 at 3,072 bases.

These are clean aligned statistical and model-proxy results. They support no robustness, alignment
search, spoofing, removal, many-output, sequence-authentication, biological function, viability, or
safety claim.

## Artifact and source hashes

The small evidence bundle is `outputs/carbon_synthid_e16_v1/`. Its selected summary hashes are:

| File | SHA-256 |
|---|---|
| `generation_summary.json` | `6ab5c5948b921dbed721384cf360c7f91c2f36889f8c4a9ba52f698f0249ac07` |
| `distribution_summary.json` | `3e0016c25d7c45d32c8d3aef0066b73e3366772eae485f3e7de6518f6de77237` |
| `sequence_comparison_summary.json` | `6c9a73ea92592465b3a7c5121ab6a7e296839bc22a02edaa8050c36ebad7b0da` |
| `detection_summary.json` | `ad3eb9e43e734ae146693e4f68aafc2b2000ac9aaa6b825d08965657eb709dc5` |
| `detector_comparison.json` | `41b878598be7e3f977a119edb3d1d1010a7e4f07a76fff25767a05f039e629ed` |
| `artifact_digests.json` | `214049231e11aa1df9333ea7315f7bc3e68c5b621a91275076da328c7fbf3ccd` |

The `v3` generation source manifest SHA-256 is
`8b9c4d4791350131863b7757455044167a7d07675a4eef1076341c98f91cbba2`; it records commit
`3f202d2e84a03c3e9937d520778faef2e39ec9b7` plus a dirty-worktree digest. Phase 0's requested
commit/provenance lock was deliberately skipped, so no later analysis file is represented as
belonging to that commit. Instead, this execution records exact file hashes:

| Source | SHA-256 |
|---|---|
| `src/genomic_watermarks/synthid.py` | `a50fa22c451548e901c75d59b0e6583d9e9015fd6e414cf379d57c7258933082` |
| `src/genomic_watermarks/detector/search.py` | `cdaef0b46f17f24978807638b0caa8cd0236a42827135a12525d01912652f423` |
| `scripts/run_carbon_large_distribution.py` | `5bceecce1c8247df259927265c0c55f6b111e55c6f3d0a0c15d51e430c8beaf3` |
| `scripts/analyze_carbon_large_sequences.py` | `1b81e5923c1824f3d8280798384121107f310a2e3dc489f1c3eeb8f16eed1034` |
| `scripts/run_carbon_large_detection.py` | `9fc8a5837d8ae7251f938c6d6e778be9b97f7b8853e7cd0d8b2cc2d63c87b926` |
| `scripts/compare_synthid_detectors.py` | `bb7c2deb2b84d0d9f5cd5b11137b8e8d24f57f669bf646e814cc4b24d278b0bd` |
| `scripts/validate_carbon_large_validation.py` | `ffc293267f18591238fe3e84ded93e9a4da2852e07c747eb6d74690607715e4f` |

During the CPU resume, session filenames were changed from second-resolution timestamps to
nanosecond timestamps plus process IDs after concurrent workers exposed a session-record collision.
That change affects only diagnostic session filenames; scientific shard schemas and values were not
changed. Result-file hashes and the final validator bind the selected artifacts.
