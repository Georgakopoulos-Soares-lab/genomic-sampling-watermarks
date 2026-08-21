# Local feasibility: M5 Pro

## Hardware contract

The required paper pipeline targets one Apple M5 Pro MacBook Pro with 18 CPU cores and 48 GB unified memory. The execution path is single-process MPS with CPU fallback. No remote GPU, Brev instance, CUDA extension, distributed training, or SLURM scheduler is required.

## Model tiers

| Tier | Models | Purpose | Requirement |
|---|---|---|---|
| Smoke | Synthetic logits, no weights | Sampler proofs, detector indexing, edit channel, schemas | Required in CI |
| Primary | Carbon-500M, GENERator-v2 1.2B | Main cross-model empirical claims | Required locally |
| Confirmation | Carbon-3B | Reduced replication of selected primary results | Optional after gates pass |
| Excluded | Carbon-8B | None | Not required |

Carbon-500M is approximately 1 GB in BF16 weights. The GENERator-v2 snapshot is 4.6 GB on disk;
its accepted MPS `float32` pilot used 5.03 GiB of driver memory and about 4.82 GiB peak process RSS.
Both are comfortably within 48 GB unified memory. Carbon-3B BF16 weights are roughly 7 GB, but
long contexts and retained logits can dominate memory. Every runner must therefore stream summaries
and avoid retaining dense logits for a full sequence.

## Runtime controls

- batch size defaults to 1;
- generation context defaults to 512 tokens for the pilot;
- sample counts are promoted only after measured throughput and memory are logged;
- full 4,096-way probability vectors are stored only for a stratified audit subset;
- all other states emit sufficient statistics online;
- bootstraps and null simulations run on CPU and cache deterministic summaries;
- long experiments are resumable by config-defined shards, never by mutating completed shards.

## Evidence budgets

These are planning ceilings, not promised sample sizes.

| Stage | Initial local budget | Promotion rule |
|---|---|---|
| Fixed-distribution Monte Carlo | up to 1,000,000 draws for selected distributions | Run only after analytic unit tests pass |
| Real-logit channel pilot | 1,000-5,000 states per model/policy | Estimate throughput, variance, and information |
| Real-logit main cohort | 10,000-50,000 streamed states per model/policy | Choose by precision target from pilot |
| Sequence detection pilot | 25-50 sequences per cell | Prune weak methods and redundant edit rates |
| Main detection cells | 100-500 sequences per retained cell | Determine by binomial CI width and runtime |
| Empirical null floor | Begin at `10^-3` | Lower only with enough calibrated null scans or justified analytic/permutation evidence |

Avoid a full Cartesian product. Use paired outputs, common prompts, common edit seeds, and sequential elimination.

## MPS policy

- Prefer `torch.bfloat16` when the adapter and operations pass parity tests; otherwise use `float16` or `float32` and record the change.
- Carbon-500M currently passes its engineering gate with MPS `bfloat16`; GENERator-v2 does not and
  must use MPS `float32` unless a new revision passes the full public-cohort parity check.
- Do not use `device_map="auto"` as if it were CUDA CPU offload. On MPS, the model must fit in unified memory.
- CPU fallback for unsupported operations is acceptable for correctness, but its use and runtime must be recorded.
- Quantized GGUF checkpoints may be used for throughput exploration. They are not the primary exact-sampler backend unless the integration exposes and validates the complete pre-sampling distribution and custom keyed sampler.

## Acceptance criteria

A paper-scale configuration is local-feasible when it:

1. completes a primary-model sequence without swapping or process termination;
2. records peak memory, tokens per second, and wall time;
3. can resume between immutable shards;
4. projects the retained experiment matrix to a reasonable laptop schedule;
5. produces the same discrete detector result on MPS- and CPU-generated fixtures where parity is expected.
