# Secret-Key Sampling Watermarks for Genomic Language Models

This repository is the code, evidence, and manuscript workspace for **one combined paper** studying secret-key sampling watermarks in Carbon and GENERator-v2. The paper asks whether fixed 6-mer genomic language models expose a useful, distribution-preserving provenance channel, and whether a verifier with only the DNA sequence, a key, and public configuration can recover that signal after realistic edits.

The repository is a research scaffold, not a results release. No empirical claim is valid until it
appears in the evidence ledger and points to a reproducible result.

## Scope

- Primary models: Carbon-500M and GENERator-v2 eukaryote 1.2B.
- Optional confirmation: Carbon-3B on a deliberately reduced cohort.
- Hardware contract: one Apple M5 Pro MacBook Pro with 48 GB unified memory; MPS first, CPU fallback; no CUDA, SLURM, Brev, or distributed runtime required.
- Initial samplers: exact partition coupling, inverse-transform sampling, and exponential/Gumbel sampling.
- Detector: model-free verification over both strand orientations, six 6-mer phases, configured windows, and key offsets, with calibration over the full search.
- Claims excluded by default: biological function, viability, cryptographic security, or robustness at an unmeasured false-positive rate.

## Start here

1. New to the topic: begin with the numbered [explainers](explainers/README.md).
2. Read [PROJECT.md](PROJECT.md) for the formal paper thesis and boundaries.
3. Read [docs/research/combined_research_plan.md](docs/research/combined_research_plan.md) for the staged study.
4. Read [docs/experiments.md](docs/experiments.md) and [evidence/README.md](evidence/README.md) before adding experiments.
5. Read [AGENTS.md](AGENTS.md) before making agent-assisted changes.
6. Claude Code also reads [CLAUDE.md](CLAUDE.md); specialized roles are documented in [.claude/README.md](.claude/README.md).
7. For a fresh Claude session, use the copy/paste [continuation prompt](CLAUDE_CONTINUATION_PROMPT.md).

## Local smoke test

The foundational sampler and detector utilities use only the Python standard library.

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/doctor.py
python3 scripts/check_evidence.py
```

For model-backed work:

```bash
uv sync --extra dev --extra models --extra analysis
```

Model downloads are intentionally not part of setup or CI. Pin every model revision in
`sources.yaml` before collecting results.

Tokenizer structure can be checked without downloading model weights:

```bash
uv run python scripts/audit_model_vocab.py --policy G_tok --cache-dir .cache/huggingface
uv run python scripts/audit_model_vocab.py --policy C_tok --cache-dir .cache/huggingface
```

After explicitly choosing to download a checkpoint, the first M5 Pro smoke command is:

```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 uv run python scripts/probe_model_distribution.py \
  --policy C_tok --device auto --cache-dir .cache/huggingface
```

The probe performs one forward pass on a public synthetic context and prints only structural,
distribution, timing, and memory summaries. It does not generate or save DNA.

After the checkpoint is cached, compare its complete canonical distribution across MPS and CPU:

```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 uv run python scripts/compare_model_devices.py \
  --policy C_tok --cache-dir .cache/huggingface --local-files-only
```

Run the compact eight-context Carbon engineering pilot:

```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 uv run python scripts/run_model_capacity_pilot.py \
  --cache-dir .cache/huggingface --partitions-per-state 8 \
  --cpu-parity-cases 4 --local-files-only
```

The contexts and partition fixtures are public and synthetic. The command prints streamed summary
statistics and is explicitly not a paper-evidence run.

Build the frozen public prompt cohort and run the corresponding Carbon engineering pilot:

```bash
uv run python scripts/build_public_prompt_cohort.py --offline
PYTORCH_ENABLE_MPS_FALLBACK=1 uv run python scripts/run_model_capacity_pilot.py \
  --policy C_tok \
  --cohort-jsonl data/processed/ncbi_refseq_eukaryote_windows_v1/prompts.jsonl \
  --partitions-per-state 16 --cpu-parity-cases 12 --local-files-only \
  --output outputs/carbon_public_prompt_pilot_v1.json
```

The tracked cohort manifest contains only public source coordinates and checksums. FASTA, derived
prompts, and the detailed engineering report remain in ignored directories.

GENERATOR-v2 uses `float32` on this Mac because its MPS `bfloat16` path failed the public-cohort
parity gate:

```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 uv run python scripts/run_model_capacity_pilot.py \
  --policy G_tok --mps-dtype float32 \
  --cohort-jsonl data/processed/ncbi_refseq_eukaryote_windows_v1/prompts.jsonl \
  --partitions-per-state 16 --cpu-parity-cases 12 --local-files-only \
  --output outputs/generator_g_tok_public_prompt_pilot_float32_v1.json
```

Use the same command with `--policy G_bp` for the released base-product policy. The two policies
share one cached 4.6 GB checkpoint.

The frozen sequential E2 collector advances an ordinary, unwatermarked continuation while
measuring 32 public test partitions at every state. Start with one prompt before launching the full
run:

```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 uv run python scripts/collect_sequential_capacity.py \
  --policy G_bp --case-id yeast_q20 --states-per-prompt 4 \
  --cache-dir .cache/huggingface --local-files-only \
  --output outputs/generator_g_bp_sequential_smoke_yeast_q20_v1.json
```

The smoke graduated into a final 24-prompt cohort after the frozen stability trigger fired for
`G_tok`. Full runs now use `data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl`; detailed
results remain ignored engineering artifacts until evidence review.

## Repository map

```text
src/genomic_watermarks/  Model-independent algorithms and model adapters
tests/                   Deterministic unit and statistical smoke tests
configs/                 Smoke and M5 Pro configurations
sources.yaml             Pinned upstream model and reference-code revisions
evidence/                Minimal ledger of numbers allowed into the paper
docs/                    Threat model, baselines, research audit, and roadmap
explainers/              Numbered beginner-friendly walkthroughs with examples
paper/                   Manuscript source, source map, figures, and reviews
.claude/                 Claude Code routing and specialized subagents
```

## Status

The source audit, E0 partition-coupling reference, model policy transforms, local runtime selection,
real tokenizer audits, versioned public prompt cohort, and weight-backed Carbon `C_tok` and
GENERATOR-v2 `G_tok`/`G_bp` MPS/CPU capacity pilots are implemented. Local `G_bp` matches the
pinned upstream base-marginal helper on MPS and CPU. The sequential E2 collector has passed a real
three-policy run on 24 prompts: 3,072 states per policy and 9,216 states overall. The
preregistered cluster rule stops expansion at 24 prompts. Evidence-admission review is complete:
`evidence/measurements.yaml` now holds one admitted mean information bit/base value per primary
policy with its prompt-cluster interval and full provenance. Watermarked generation, ITS/EXP,
calibrated detector statistics, and later paper experiments remain open.
