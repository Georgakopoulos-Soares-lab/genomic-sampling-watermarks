# Model source audit

Audit date: 2026-08-20. Revisions below are frozen inputs for implementation review, not claims that upstream repositories will remain unchanged.

## Frozen revisions

| Component | Revision |
|---|---|
| `huggingface/carbon` | `10bbc4b35f6e26d2a8767342576ff65108028bf5` |
| `HuggingFaceBio/Carbon-500M` main | `9796b752108258c1d365089f842e62e6c0547704` |
| `HuggingFaceBio/Carbon-500M` fns | `974bc8a54e95d72af5c909416f1b0473e11b7bf4` |
| Carbon transitive `Qwen/Qwen3-4B-Base` tokenizer snapshot | `906bfd4b4dc7f14ee4320094d8b41684abff8539` |
| `GenerTeam/GENERator` | `5132e2c35da5d5e9a7dcec7484901be4de864bf6` |
| `GenerTeam/GENERator-v2-eukaryote-1.2b-base` | `c41b0018da9ee13b9e96ee54647de8da381ccd72` |
| `jthickstun/watermark` | `80d4ec8f4280da2a2cada03adfc8940593d1964c` |
| `yihwu/DiPmark` | `34abbeb527243c79bda8043313bb797a731f4ae7` |
| `poseidonchan/ProteinWatermark` | `af959ea4b7d08f796f9cdb104c9521542b660331` |

Machine-readable copies live in `sources.yaml`.

## Carbon findings

### Tokenizer

- Hybrid vocabulary: Qwen-style BPE outside DNA tags and fixed, non-overlapping 6-mers inside DNA tags.
- Canonical DNA alphabet contains all `4^6 = 4096` A/T/C/G 6-mers.
- Executable audit of both pinned Carbon revisions found canonical IDs 151,672-155,767 in A/T/C/G product order. These IDs come from `dna_token_to_id`; `get_vocab()` is not authoritative because a DNA string can also exist in the BPE vocabulary.
- DNA sequences require `<dna>` framing for the intended mode.
- Invalid or ambiguous material and trailing partial chunks require explicit tests; they must not be silently normalized differently in generation and detection.
- The remote tokenizer hard-codes `Qwen/Qwen3-4B-Base` without a revision and does not expose the resolved commit. The adapter therefore injects the audited `906bfd4...` revision in a scoped loader guard during Carbon tokenizer construction and immediately restores the Transformers loader afterward.

### Generation

- The audited main Carbon-500M revision loads as standard `LlamaForCausalLM`.
- Factorised Nucleotide Supervision is a training objective; it does not by itself imply a special deployed sampler.
- The audited `fns` revision contains `CarbonForCausalLM` with a `_BPLogitsProcessor` that marginalizes token probabilities by base position and reconstructs a 6-mer.

### Paper consequence

Define `C_tok` as direct categorical sampling from the current main checkpoint. Define `C_bp` as the optional, revision-pinned base-marginal branch. Never describe `C_bp` as the current default Carbon sampler.

## GENERator-v2 findings

### Tokenizer

- Vocabulary size is 4,128: 32 special tokens followed by all 4,096 canonical 6-mers in the tokenizer's recorded order.
- Executable audit of the pinned checkpoint confirmed canonical IDs 32-4,127, contiguous in A/T/C/G product order.
- Fixed-block tokenization creates six possible phases for a cropped DNA string.
- The adapter requires a context length divisible by six instead of silently trimming the left edge and changing phase.

### Generation

- The audited custom model defines `_BPLogitsProcessor`.
- It applies softmax to the 4,096 DNA-token scores, marginalizes probability independently at each of six base positions, chooses each base independently, and reconstructs the resulting 6-mer.
- For stochastic sampling, the resulting next-token law is the product of the six base marginals. The greedy path is deterministic and is not that categorical law.

### Paper consequence

Define `G_tok` as the research baseline that samples directly from the processed 4,096-way distribution. Define `G_bp` as the audited released generation path. Their output distributions are not assumed equivalent and must be measured separately.

## Executable audit

The tokenizer audit downloads tokenizer/configuration files only. Carbon's tokenizer module also imports PyTorch, but the command does not request checkpoint weights.

```bash
uv run python scripts/audit_model_vocab.py --policy G_tok --cache-dir .cache/huggingface
uv run python scripts/audit_model_vocab.py --policy C_tok --cache-dir .cache/huggingface
uv run python scripts/audit_model_vocab.py --policy C_bp --cache-dir .cache/huggingface
```

Verified on 2026-08-20: all three audits returned 4,096 unique, contiguous canonical IDs and a successful ID-to-token round trip. They also passed with `--local-files-only`; Carbon reported the required Qwen revision as enforced. `G_bp` shares the audited `G_tok` tokenizer revision.

## Remaining integration tests

1. Test real-tokenizer uppercase/lowercase, invalid symbols, DNA tags, empty input, and 1-5 base tails.
2. Verify the model-backed adapter output against each pinned model's generation path.
3. Verify that generation never admits non-DNA tokens during DNA-only baselines.
4. Record temperature, top-k/top-p, repetition penalties, and every logits processor before defining `P_t`.

## Weight-backed Carbon smoke

On 2026-08-20, the pinned Carbon-500M main revision completed a real `C_tok` forward pass on the
48 GiB M5 Pro using MPS with `bfloat16`. The adapter returned one normalized 4,096-way canonical
distribution for the fixed 96-base synthetic context used by `probe_model_distribution.py`.

A paired offline-cache run compared that same state with CPU `float32`:

| Diagnostic | Observed value |
|---|---:|
| Top-1 token agreement | yes |
| Top-10 overlap | 1.00 |
| Top-100 overlap | 1.00 |
| Total-variation distance | 0.0033585 |
| Jensen-Shannon divergence | 0.00003108 bits |
| Maximum absolute probability difference | 0.0033584 |

This is an engineering smoke, not paper evidence or a general parity claim. It covers one synthetic
context and two different dtypes; the follow-up below broadens that engineering check.

## Small synthetic Carbon capacity pilot

The follow-up engineering pilot evaluated eight public synthetic contexts on MPS at temperature
1.0. It used eight public, non-secret partition fixtures per state and repeated four contexts on CPU
for parity. It did not generate or retain DNA outputs and is not admitted paper evidence.

The contexts deliberately exposed two regimes:

| Context class | Entropy | Effective support | Top-1 mass | Mean estimated information/base |
|---|---:|---:|---:|---:|
| Six repetitive 96-base fixtures | 0.75–2.61 bits | 1.17–1.74 | 0.756–0.924 | 0.0057–0.0203 bits |
| Two deterministic pseudorandom fixtures | 11.832–11.834 bits | 3,031–3,070 | 0.0034–0.0040 | 0.1623–0.1627 bits |

The aggregate median estimated information was 0.01355 bit/base, but that number hides a sharp
context split and must not be used as a paper capacity estimate. The next capacity gate requires a
versioned public prompt cohort and state sampling across positions, not more synthetic averaging.

The four spanning CPU parity cases retained the same top token. Mean total-variation distance was
0.00384, mean top-10 overlap was 0.975, and mean top-100 overlap was 0.9775 between MPS `bfloat16`
and CPU `float32`. This remains an engineering tolerance observation, not a proof of numerical
equivalence.

MPS held about 0.95 GiB of allocated model memory and 1.08 GiB of driver memory. After model load,
the eight MPS distributions took 0.21 seconds in total; four spanning CPU states took 0.35 seconds.
These small, mixed-length timings establish feasibility but are not a throughput benchmark.

## Public-context Carbon engineering pilot

On 2026-08-21, the follow-up ran `C_tok` over the 12 frozen 384-base RefSeq windows documented in
[`public_prompt_cohort.md`](public_prompt_cohort.md). Sixteen public, non-secret partition fixtures
were evaluated per state. All 12 states were also repeated on CPU.

| Diagnostic | Observed value |
|---|---:|
| Median estimated information/base | 0.15565 bits |
| Range across contexts | 0.08653–0.15978 bits |
| MPS top-token agreement with CPU | 12/12 |
| Mean MPS/CPU total-variation distance | 0.00745 |
| MPS states/second after load | 35.9 |
| MPS driver memory | 1.08 GiB |

The broad range matters more than its mean: one Arabidopsis window had top-1 mass 0.286 and the
lowest estimated information rate, while most windows were near 0.15–0.16 bit/base. This is a small
engineering diagnostic using public partition material, not paper evidence, an uncertainty
estimate, or a claim about an organism. It justifies testing real contexts instead of extrapolating
from synthetic DNA. The evidence ledger remains empty.

## Weight-backed GENERator-v2 validation

On 2026-08-21, the pinned 1.2B checkpoint revision completed real `G_tok` and `G_bp` forward passes
on the M5 Pro. The snapshot publishes one 4,648,274,384-byte `model.safetensors` file whose verified
SHA-256 is `c007687ff52ae8dadaa894539eed3fb24f21be09a46a6ad394ea9eb3a778cb1a`.

The upstream `from_pretrained()` implementation automatically calls `AutoTokenizer.from_pretrained()`
without forwarding revision, cache, or offline settings. The local adapter now scopes that internal
reload to the pinned tokenizer revision and restores the Transformers loader immediately afterward.
A regression test covers the injection and restoration.

### Precision gate

MPS `bfloat16` was rejected on the 12 public prompts. Against CPU `float32`, `G_tok` had only 4/12
top-token agreement, mean total-variation distance 0.23754, and mean top-100 overlap 0.516. This is
large enough to change both sampling and capacity conclusions.

With MPS and CPU both using `float32`:

| Diagnostic | `G_tok` | `G_bp` |
|---|---:|---:|
| Top-token agreement | 12/12 | 12/12 |
| Mean total-variation distance | 0.0000206 | 0.00000266 |
| Top-10 / top-100 overlap | 1.00 / 1.00 | 1.00 / 1.00 |
| Median estimated information/base | 0.15842 bits | 0.15979 bits |
| Context range | 0.08810–0.16109 bits | 0.10228–0.16291 bits |
| MPS states/second after load | 14.2 | 16.2 |
| MPS driver memory | 5.03 GiB | 5.03 GiB |

The base-product policy increased the median and the lowest per-context estimate in this small
cohort. This is an engineering observation using public partition fixtures, not an admitted
capacity measurement or a general superiority claim. Current GENERator work must use `float32`.

### Direct released-policy equivalence

`audit_generator_bp_policy.py` compares the local product-of-marginals law with the pinned model's
own `compute_bp_probs` helper on identical logits. The gate was frozen before execution: maximum
base-marginal delta at most `1e-6`, maximum token-probability delta at most `1e-7`, and total-
variation distance at most `1e-5`.

All 12 public prompts passed on both MPS and CPU in `float32`:

| Backend | Worst base delta | Worst token delta | Worst TV |
|---|---:|---:|---:|
| MPS | `1.10e-7` | `9.43e-9` | `3.71e-8` |
| CPU | `3.39e-7` | `3.22e-9` | `6.45e-8` |

The remaining differences are floating-point summation effects far below the audit tolerances. This
closes the equivalence question for the audited revision and temperature-1, untruncated logits. It
does not validate future upstream revisions or other logits-processor configurations.

## Open audit items

- Resolve `C_deployed` from the exact main-revision processor stack before enabling it in the local profile.
