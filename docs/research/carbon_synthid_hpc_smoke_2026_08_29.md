# Carbon SynthID TACC smoke result, 2026-08-29

Status: complete validation artifact; not admitted to `evidence/measurements.yaml` and not a
256-prompt scientific result.

## Runtime

The smoke ran in the isolated `tacc_watermark` environment inside Lonestar6 Slurm job `3399876`.
The preflight observed three NVIDIA A100-PCIE-40GB devices, PyTorch `2.11.0+cu128`, runtime CUDA
12.8, the `cuda/12.8` module, Python 3.12.14, Transformers 5.15.1, and an unset `PYTHONPATH`. A real
CUDA tensor probe passed.

Two four-prompt, 64-token draws ran concurrently on separate GPUs. Draw 0 used 25.765 seconds of
model-generation time and draw 1 used 26.076 seconds. Their per-process wall times, including model
load and artifact work, were 74.988 and 75.204 seconds. Per-GPU throughput was 119.23 and 117.81
generated bases/second, and each process reported 1.006 GiB peak CUDA allocation. The four-state
distribution stage took 45.510 seconds; teacher-forced analysis of all 16 sequences took 37.072
seconds.

Linear scaling of generation alone gives approximately 3.7 hours for each full draw; the two draws
run concurrently. This is a planning projection, not a full-run measurement. The full GPU job keeps
a 24-hour limit because fixed-state simulation, longer-context likelihood, filesystem variance, and
resume overhead do not scale from this smoke with enough confidence to tighten the limit.

## Correctness and statistical smoke

The selected four prompts intentionally include calibration and evaluation cases plus one frozen
negative-control state. The run produced eight tournament and eight ordinary sequences, totaling
1,024 generated 6-mer positions and 6,144 bases.

- All four tournament samples failed to reject their exact fixed-key tournament laws after
  Bonferroni correction; all four ordinary samples failed to reject `C_tok`.
- The deliberately broken sampler rejected on its one selected negative-control state at the
  99-replicate Monte Carlo floor (`p = 0.01`).
- The 8-key finite average remained far from `C_tok` (mean TV 0.7155). This is expected to be noisy
  for a 4,096-way, depth-30 tournament and is not evidence against or for the analytic expectation
  identity.
- Mean NLL/token was 7.7635 for tournament output and 7.6970 for ordinary output. The paired mean
  difference was 0.06643 with a prompt-cluster interval of [-0.04497, 0.15559] and unadjusted
  `p = 0.3693`.
- At 384 generated bases, held-out TPR was 1.0 and the corresponding-key ordinary FPR was 0.0. The
  mean paired detector-score difference was 20.40, but the prompt-level sign-flip `p = 0.4970`
  because the smoke has too few prompt clusters for a power claim.

The strict validator passed every declared structural check: two explicit draws, distinct replay
streams, canonical lengths, correct-key positives, lower wrong-key scores, prompt-level clustering,
disjoint calibration/evaluation prompts, and exact threshold recomputation. Ten diagnostic figures
and the generated report were also completed.

These results establish that the CUDA/SynthID pipeline is executable and internally aligned. They
do not establish distribution preservation for a fixed key, calibrated 1% FPR, sequence-level
quality equivalence, biological validity, robustness to edits, or statistical significance. Those
questions require the frozen 256-prompt run and subsequent evidence audit.

