# 07 — Running it on the MacBook

## Local contract

The required path targets one Apple M5 Pro MacBook Pro with 48 GB unified memory:

- Python 3.12;
- single-process execution;
- Apple MPS first;
- CPU fallback;
- batch size 1 for initial model probes;
- one model loaded at a time.

The repository does not require CUDA, Brev, SLURM, or a remote server.

## Set up the small development environment

From the repository root:

```bash
uv sync --extra dev
```

This installs the package, tests, YAML support, and Ruff. It does not install model libraries or
download checkpoint weights.

Run all local checks:

```bash
uv run ./scripts/run_smoke.sh
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Expected current result:

```text
all tests passed
evidence ledger OK (0 measurements)
```

Zero measurements is correct: we have not admitted any model-backed paper results.

## Audit tokenizers without checkpoint weights

Install the optional model libraries:

```bash
uv sync --extra dev --extra models
```

Then run:

```bash
uv run python scripts/audit_model_vocab.py \
  --policy G_tok --cache-dir .cache/huggingface

uv run python scripts/audit_model_vocab.py \
  --policy C_tok --cache-dir .cache/huggingface
```

These commands download tokenizer and configuration files. Carbon's tokenizer code imports
PyTorch, but the audit does not request checkpoint weights.

After the first successful audit, verify the cache is sufficient:

```bash
uv run python scripts/audit_model_vocab.py \
  --policy C_tok --cache-dir .cache/huggingface --local-files-only
```

## A one-state model-backed probe

The following command will download Carbon-500M weights if they are absent:

```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 uv run python scripts/probe_model_distribution.py \
  --policy C_tok --device auto --cache-dir .cache/huggingface
```

It performs one forward pass on a fixed public synthetic context. It does not generate or save a
DNA sequence. Its JSON output includes:

- exact model revision;
- selected device and dtype;
- canonical vocabulary boundaries;
- probability sum;
- entropy and effective support;
- top-1 probability;
- load and inference time;
- process peak memory.

Example shape, with deliberately invented numbers:

```json
{
  "policy_id": "C_tok",
  "device": "mps",
  "dtype": "bfloat16",
  "canonical_count": 4096,
  "probability_sum": 1.0,
  "entropy_bits": 7.2,
  "effective_support": 84.0,
  "top1_mass": 0.11
}
```

Those example measurements are illustrative. They are not current findings and must never be
copied into the evidence ledger.

Once the checkpoint is cached, compare the full 4,096-way distribution across MPS and CPU:

```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 uv run python scripts/compare_model_devices.py \
  --policy C_tok --cache-dir .cache/huggingface --local-files-only
```

The comparison reports total-variation distance, Jensen-Shannon divergence, top-token agreement,
and top-10/top-100 overlap. It loads one device at a time to stay within the laptop-first contract.

The small multi-context engineering pilot is:

```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 uv run python scripts/run_model_capacity_pilot.py \
  --cache-dir .cache/huggingface --partitions-per-state 8 \
  --cpu-parity-cases 4 --local-files-only
```

It uses eight public synthetic contexts and never saves generated DNA. Its main lesson so far is
that repetitive and pseudorandom contexts produce radically different probability support. These
fixtures validate the mechanism; they cannot replace a versioned public prompt cohort.

## Build and run the first public cohort

The manifest fixes 12 public, 384-base windows without committing the DNA payloads:

```bash
uv run python scripts/build_public_prompt_cohort.py --offline

PYTORCH_ENABLE_MPS_FALLBACK=1 uv run python scripts/run_model_capacity_pilot.py \
  --policy C_tok \
  --cohort-jsonl data/processed/ncbi_refseq_eukaryote_windows_v1/prompts.jsonl \
  --partitions-per-state 16 --cpu-parity-cases 12 --local-files-only \
  --output outputs/carbon_public_prompt_pilot_v1.json
```

The JSON output is ignored because this is an engineering pilot, not an admitted paper result. The
tracked manifest is enough to rebuild the same inputs and verify every sequence checksum.

## Exercise sequential state collection

After the one-state policy pilots pass, exercise the collector on one prompt:

```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 uv run python scripts/collect_sequential_capacity.py \
  --policy G_bp --case-id yeast_q20 --states-per-prompt 4 \
  --cache-dir .cache/huggingface --local-files-only \
  --output outputs/generator_g_bp_sequential_smoke_yeast_q20_v1.json
```

That command generates only 24 new bases and records summaries for four states. The completed final
E2 shape uses 128 states on all 24 prompts. The report contains no raw prompt, generated tokens,
logits, or dense probability vectors.

Build the expanded cohort and validate a full report with:

```bash
uv run python scripts/build_public_prompt_cohort.py \
  --manifest data/public_prompt_cohort_v2.yaml --offline

uv run python scripts/analyze_sequential_capacity.py \
  --input outputs/generator_g_tok_e2_sequential_v2.json \
  --cohort-jsonl data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl \
  --output outputs/generator_g_tok_e2_cluster_analysis_v2.json
```

## What happens next

The next gates are deliberately sequential:

1. Completed: validate Carbon across synthetic contexts on MPS and CPU.
2. Completed: define, checksum, and rebuild a public benign prompt cohort.
3. Completed: run Carbon over all 12 public contexts on MPS and CPU.
4. Completed: repeat model integration for GENERator `G_tok` and `G_bp` in MPS `float32`.
5. Completed: freeze and smoke-test the 12-prompt sequential capacity collector.
6. Completed: implement prompt-cluster uncertainty and run the three-policy E2 pilot.
7. Completed: apply the frozen trigger, expand output-blind to 24 prompts, and stop when stable.
8. Next: review the E2 result package, then test standalone detection within the 1–5 kbp budget.

This keeps the study laptop-sized and prevents a large experiment grid from growing before the
basic channel is known to work.

Return to the [explainer index](README.md), or continue into the formal
[combined research plan](../docs/research/combined_research_plan.md).
