# E2 capacity pilot protocol

## Decision

The preregistered 12-prompt `ncbi_refseq_eukaryote_windows_v1` pilot triggered expansion for
`G_tok`: its prompt-cluster interval width was 0.03323 bit/base and its maximum leave-one-prompt-out
change was 0.01088 bit/base. `C_tok` and `G_bp` did not trigger expansion.

Before inspecting any new model output, v2 retained all original windows and added the same three
relative positions from one different chromosome per organism. The resulting
`ncbi_refseq_eukaryote_windows_v2` cohort contains 24 prompts across eight accession-versioned
chromosome records. All three policies pass the frozen stability thresholds on v2, so E2 stops at
24 prompts. This remains a model-organism capacity cohort, not support for general biological or
cross-organism claims.

## Frozen pilot shape

| Item | Pilot choice |
|---|---|
| Prompt clusters | 24 public 384-base windows |
| Model policies | `C_tok`, `G_tok`, `G_bp` |
| Continuation states | 128 per prompt and policy |
| Total states | 3,072 per policy; 9,216 overall |
| Generated length | 768 bases per continuation |
| Temperature | 1.0 |
| Truncation | none: no top-k or top-p |
| Partition evaluations | 32 domain-separated evaluation partitions per state |
| Carbon runtime | MPS `bfloat16`, declared CPU parity subset |
| GENERATOR runtime | MPS `float32`, declared CPU parity subset |

Each policy follows its own declared unwatermarked categorical law to obtain its continuation path.
The 32 partition evaluations reuse a model state and therefore do not require 32 forward passes.
Within one policy run, the same 32 public partitions are reused across prompts and states. This
treats each partition like one fixed test key, enables paired comparisons across states, and avoids
repeating HMAC construction. The policy ID is part of the public domain label, so policy runs have
separate partition fixtures. The partitions estimate keyed-partition variation; they are not 32
independent genomic observations.

## Summaries and uncertainty

Report per-policy entropy, top-1 mass, effective support, partition mass, and maximal-coupling
information per token/base. Preserve prompt identity in every state row. The primary interval is
an equal-weight prompt-cluster percentile bootstrap with 20,000 replicates, deterministic public
seed 2718, and 95% coverage. States and partitions are not resampled as independent clusters.
Show every per-prompt summary and every leave-one-prompt-out mean.

The public evaluation-key derivation is for reproducible measurement of the random-partition
distribution. It is not a deployment key or evidence that public watermarks are secure. Raw secret
keys remain forbidden in repository artifacts.

## Expansion trigger

Do not expand automatically. Add prompt clusters only if either condition occurs:

1. the prompt-cluster 95% interval for mean information/base is wider than 0.02 bit/base; or
2. removing one prompt changes the overall mean by more than 0.01 bit/base.

If expansion is triggered, freeze new accession.version records and selection rules before
inspecting their model outputs. Otherwise retain the small cohort and proceed to distribution
preservation and clean detection.

## Evidence boundary

The single-state reports, `G_bp` equivalence audits, v1 expansion decision, and v2 capacity reports
remain engineering artifacts in ignored `outputs/`. The v2 aggregates were evidence-eligible only
after their result package and exact command trail passed explicit evidence-admission review. No
number moves into `evidence/measurements.yaml` automatically.

## Evidence-admission review (2026-08-21)

Reviewed: the three v2 sequential reports, their cluster analyses, the frozen v2 cohort, and the
commands below.

Confirmed:

1. all six v2 artifact digests match their recorded values, and the three sequential reports pass
   the strict validator with 24 cases, 3,072 states, 32 partitions per state, and no forbidden raw
   fields;
2. each report pins model ID, revision, MPS device, policy dtype, temperature 1.0, no truncation,
   the unwatermarked path scheme and seed, and the public partition scheme and material digest;
3. the validator checks each per-prompt `prompt_sequence_sha256` against the cohort file, so prompt
   content is bound, not merely the cohort name.

One provenance gap was found and closed. The v2 analysis artifacts bound only their input report
digest, `cohort_id`, and `policy_id`; they did not record model revision, device, dtype, or any
cohort digest. `scripts/analyze_sequential_capacity.py` now emits a `provenance` block with cohort
content and manifest digests, model policy/revision/device/dtype, protocol shape, the metric
definition and its `1/6` bit/base upper bound, and explicit uncertainty and comparison scope. The
cohort content digest is now one shared function used by both the cohort builder and the analyzer.

The v2 artifacts were not modified and no model inference was repeated. Analysis was recomputed
from the same immutable sequential reports into new `*_e2_cluster_analysis_v3.json` files whose
cluster means, bootstrap interval, leave-one-out means, and expansion decision are identical to v2.

Admitted to `evidence/measurements.yaml`: one mean information bit/base value per primary policy,
with its 95% prompt-cluster interval, sample shape, model scope, cohort digests, source artifacts,
digests, and exact command.

- `e2.capacity.c_tok.mean_information_bits_per_base`
- `e2.capacity.g_tok.mean_information_bits_per_base`
- `e2.capacity.g_bp.mean_information_bits_per_base`

Uncertainty is prompt-cluster uncertainty over 24 frozen prompts, conditional on the 32 fixed
public evaluation partitions and the unwatermarked continuation path. Sequential states and
partitions are not independent samples. Nothing else from these runs is admitted, and no
cross-policy difference is admitted: the three policies use policy-domain-separated partition
fixtures, so a difference between them is not attributable to watermarking.

Analysis artifact digests:

| Policy | Analysis artifact | SHA-256 |
|---|---|---|
| `C_tok` | `outputs/carbon_c_tok_e2_cluster_analysis_v3.json` | `47e276baccf4e3735f258d988ba10d43dbdafc36550615b336fb8b2f06baf26b` |
| `G_tok` | `outputs/generator_g_tok_e2_cluster_analysis_v3.json` | `e140fb389a693f52b96a04e15f4e61c0af5c2874c1cebabcb674d60244798307` |
| `G_bp` | `outputs/generator_g_bp_e2_cluster_analysis_v3.json` | `03d18eecfbb1986a3507475393c6ee4e7392a8c5e9ff2dc96cf2477f9e1b925a` |

## Implementation status

`scripts/collect_sequential_capacity.py` implements the unwatermarked path, context growth, public
partition derivation and reuse, per-state summaries, prompt identity, runtime/memory fields, and a
single ignored JSON report. `scripts/analyze_sequential_capacity.py` rejects wrong revisions,
runtime settings, cohort membership, state counts, derived capacity values, summaries, and raw
sequence/logit fields before applying the cluster analysis.

| Policy | Mean bit/base | Prompt-cluster 95% interval | Width | Max leave-one-out change | Expand? |
|---|---:|---:|---:|---:|---:|
| `C_tok` | 0.15395 | 0.15149–0.15579 | 0.00431 | 0.00098 | no |
| `G_tok` | 0.15142 | 0.13979–0.15777 | 0.01798 | 0.00538 | no |
| `G_bp` | 0.15744 | 0.15478–0.15926 | 0.00448 | 0.00107 | no |

Each v2 report contains 3,072 states and passed the strict validator with raw prompt, generated
token, logits, dense probability, and secret fields absent. The three mean values and their
intervals are now ledger-admitted; the remaining per-prompt and per-state fields are not.

## Exact v2 commands

```bash
uv run python scripts/build_public_prompt_cohort.py \
  --manifest data/public_prompt_cohort_v2.yaml --offline

PYTORCH_ENABLE_MPS_FALLBACK=1 uv run python scripts/collect_sequential_capacity.py \
  --policy G_tok \
  --cohort-jsonl data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl \
  --cache-dir .cache/huggingface --local-files-only \
  --output outputs/generator_g_tok_e2_sequential_v2.json

uv run python scripts/analyze_sequential_capacity.py \
  --input outputs/generator_g_tok_e2_sequential_v2.json \
  --cohort-jsonl data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl \
  --output outputs/generator_g_tok_e2_cluster_analysis_v2.json

uv run python scripts/analyze_sequential_capacity.py \
  --input outputs/generator_g_tok_e2_sequential_v2.json \
  --cohort-jsonl data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl \
  --cohort-manifest data/public_prompt_cohort_v2.yaml \
  --output outputs/generator_g_tok_e2_cluster_analysis_v3.json
```

The `v3` command is the admitted one: it binds cohort and manifest digests alongside the model
scope. The `v2` command is retained because its artifact is immutable and cited by the review.

Use the same collector/analyzer pair for `C_tok` and `G_bp` with policy-specific output names.
