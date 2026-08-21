# E3 distribution-preservation protocol

Frozen before inspecting any model output for this experiment.

## Question

Does `partition_mc` sampling reproduce the declared policy law at real model states?

The construction has an analytic exact-marginal argument: the coupled group is drawn with the
declared group mass, and the token is then drawn from the declared conditional law inside that
group. This experiment is the empirical check that the implementation matches the argument at real
model states, not a separate distributional claim.

## Stage 1 — fixed-state goodness of fit

| Item | Frozen choice |
|---|---|
| Model policies | `C_tok`, `G_tok`, `G_bp` |
| Prompt states | the four `q50` windows of the v1 records: `yeast_q50`, `arabidopsis_q50`, `celegans_q50`, `drosophila_q50` |
| Cohort | `ncbi_refseq_eukaryote_windows_v2` |
| State handling | one forward pass per prompt; every draw reuses that frozen state |
| Draws per state and arm | 8,000 |
| Arms | `partition-mc-v1` and `ordinary-categorical-v1` |
| Statistic | likelihood-ratio `G` against the declared policy law |
| Reference null | parametric Monte Carlo, 999 replicates, public seed 2718 |
| Nominal level | 0.05, with a Bonferroni level of 0.0125 across the four states |
| Key material | published non-secret fixture; this stage measures implementation correctness, not deployment security |
| Runtime | MPS, `bfloat16` for `C_tok` and `float32` for GENERATOR |

Each watermarked draw uses a fresh stream position, so it gets a fresh keyed partition and a fresh
latent bit. Draws within a state are therefore independent given the state.

The asymptotic chi-square reference is not used. With 4,096 categories and an effective support near
10^3, the expected counts are too small for it. The Monte Carlo reference has correct size under
sparsity.

`arabidopsis_q50` is retained deliberately: E2 measured it as a near-degenerate, low-capacity state,
which is the case most likely to expose a coupling bug.

### Preregistered reading

The watermarked arm passes if, across the four states:

1. no state is rejected at the Bonferroni level 0.0125; and
2. the count of rejections at the nominal 0.05 level is consistent with the expected 0.2.

The ordinary arm is a size control. Ordinary sampling *is* the declared law, so a rejection there
indicates a defect in the test or in the declared-law extraction, not in the watermark.

Failure of the watermarked arm alone is a real negative result about the construction or its
implementation and must be reported as such.

### Boundary

A passing stage-1 result supports one-step marginal preservation at the tested states. It is not
evidence of sequence-level indistinguishability. Do not describe it as such.

## Stage 2 — matched sequence-level proxies

Stage 2 compares matched ordinary and watermarked continuations on sequence-level proxy metrics.

| Item | Frozen choice |
|---|---|
| Policies | `C_tok`, `G_tok`, `G_bp` |
| Prompts | the eight `q20` and `q80` windows of the v1 records |
| Corpus | the E4 generation corpus, 3,072 bases per prompt and arm |
| Metrics | GC fraction, purine fraction, CpG fraction, base/dinucleotide/trinucleotide entropy, distinct-hexamer fraction, longest and mean homopolymer run |
| Comparison | paired per prompt: watermarked minus ordinary from the same prompt |
| Test | exact two-sided sign-flip permutation on the paired differences, statistic = absolute mean difference, all 256 sign assignments enumerated |
| Level | 0.05 nominal, Bonferroni 0.05/9 = 0.00556 across the nine metrics |
| Also reported | Jensen-Shannon divergence between arms at k = 1, 2, 3, and each arm against its prompt |

The metric list, the test, and the level were fixed in `src/genomic_watermarks/sequence_proxies.py`
before the first comparison was run, and the corpus was generated for E4 before stage 2 existed, so
neither the metrics nor the corpus were chosen after seeing a stage-2 result. The exact permutation
null is used because eight pairs is far too few for an asymptotic approximation.

### Preregistered reading

Stage 2 passes if no metric is rejected at the Bonferroni level for any policy. Nominal rejections
are reported with their direction and effect size; with nine metrics per policy, 0.45 nominal
rejections are expected under the null.

Stage 2 is a limited test and must be reported as one. Its power at eight prompts is low, and it is
*not* the reason to believe the construction preserves the distribution — the analytic argument and
stage 1 are. Stage 2 can only catch a gross sequence-level artifact.

### Stage-2 result (2026-08-21)

| Policy | Nominal rejections of 9 | Bonferroni rejections | Minimum p | Mean 3-mer divergence between arms (bit) |
|---|---:|---:|---:|---:|
| `C_tok` | 2 | 0 | 0.0078 | 0.0224 |
| `G_tok` | 0 | 0 | 0.3750 | 0.0171 |
| `G_bp` | 0 | 0 | 0.1562 | 0.0228 |

No metric is rejected at the Bonferroni level for any policy, so the preregistered rule passes.

`C_tok` is worth stating plainly rather than rounding off. Its two nominal rejections are CpG
fraction (0.0333 watermarked against 0.0256 ordinary, p = 0.0078) and distinct-hexamer fraction
(0.606 against 0.577, p = 0.039), and the remaining seven metrics lean the same way: slightly higher
entropies, slightly shorter homopolymer runs. That is a coherent direction, not obviously noise, and
it should not be reported as "no difference".

Two things bound the interpretation:

1. **This cannot be a marginal-preservation failure.** Conditioned on the emitted prefix, the
   construction samples exactly the declared conditional law, which makes the joint law of the whole
   sequence exactly the model's joint law *when the key is unknown or random*. Stage 1 confirms the
   one-step law empirically at real states.
2. **This experiment holds the key fixed.** One key was used for every watermarked sequence. A
   fixed-key realization can show a systematic sequence-level shift even when the construction is
   exact in expectation over keys, and eight prompts do not average that away.

The follow-up is therefore a key-averaged stage-2 design: regenerate the watermarked arm under
several independent keys per prompt and test the difference averaged over keys. That requires
another generation pass per key per policy, roughly 22 minutes each on the M5 Pro, so it is deferred
with this justification recorded rather than run opportunistically. Until it is run, the honest
statement is that stage 2 finds no Bonferroni-level sequence-level artifact and that a fixed-key
directional pattern in `C_tok` remains unresolved.

Stage-2 artifact digests:

| Policy | Artifact | SHA-256 |
|---|---|---|
| `C_tok` | `outputs/carbon_c_tok_e3_stage2_proxies_v1.json` | `d626b3aa3fa4122f6092908cc57f72622d15ac833d71247fdaa0fc20bc0d2708` |
| `G_tok` | `outputs/generator_g_tok_e3_stage2_proxies_v1.json` | `aa32d216ec3d4763e43a1633c3e14a0b43dd09f40c659d11f5bb6b19b8d67633` |
| `G_bp` | `outputs/generator_g_bp_e3_stage2_proxies_v1.json` | `ff87a0110b8c24a3c4668444065569e0306cbec6d82e36eeb77d50e19b7050ad` |

Nothing from stage 2 is admitted. Admission waits for the key-averaged design, because admitting a
fixed-key proxy comparison would invite exactly the over-reading the result cannot support.

## Implementation status

- `src/genomic_watermarks/watermark.py` implements the `partition_mc` generation loop, the matched
  ordinary control, the keyed position-indexed stream, and model-free keyed recomputation.
- `src/genomic_watermarks/gof.py` implements the `G` statistic, the parametric Monte Carlo p-value,
  and a p-value family summary that is explicitly not a global test.
- `scripts/generate_watermarked.py` runs matched generation against a pinned policy and writes a
  compact report plus a separate sequences file.
- `scripts/audit_distribution_preservation.py` runs stage 1.

Stage 1 has been run for all three primary policies; see the result section below. Stage 2 has not
been run.

## Exact stage-1 command

```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 uv run python scripts/audit_distribution_preservation.py \
  --policy C_tok \
  --cohort-jsonl data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl \
  --case-id yeast_q50 --case-id arabidopsis_q50 \
  --case-id celegans_q50 --case-id drosophila_q50 \
  --draws 8000 --replicates 999 --gof-seed 2718 \
  --experiment-label e3-preservation-v1 \
  --cache-dir .cache/huggingface --local-files-only \
  --output outputs/carbon_c_tok_e3_preservation_v1.json
```

Repeat with `--policy G_tok` and `--policy G_bp` and policy-specific output names.

## Stage-1 result (2026-08-21)

Run after the shape above was frozen. Four states per policy, 8,000 draws per state and arm, 999
Monte Carlo replicates, seed 2718, MPS. Wall time was about 201-203 seconds per policy.

| Policy | State | Entropy (bit) | Effective support | Watermarked p | Ordinary p | Agreement rate |
|---|---|---:|---:|---:|---:|---:|
| `C_tok` | `yeast_q50` | 11.257 | 1271.6 | 0.987 | 0.317 | 0.991 |
| `C_tok` | `arabidopsis_q50` | 7.219 | 11.4 | 0.238 | 0.823 | 0.859 |
| `C_tok` | `celegans_q50` | 10.767 | 415.3 | 0.458 | 0.029 | 0.978 |
| `C_tok` | `drosophila_q50` | 11.382 | 975.6 | 0.577 | 0.584 | 0.988 |
| `G_tok` | `yeast_q50` | 11.670 | 2565.3 | 0.989 | 0.296 | 0.994 |
| `G_tok` | `arabidopsis_q50` | 7.100 | 13.2 | 0.999 | 0.838 | 0.872 |
| `G_tok` | `celegans_q50` | 10.899 | 1000.0 | 0.204 | 0.135 | 0.991 |
| `G_tok` | `drosophila_q50` | 11.491 | 1772.7 | 0.037 | 0.069 | 0.993 |
| `G_bp` | `yeast_q50` | 11.837 | 3299.9 | 0.245 | 0.712 | 0.997 |
| `G_bp` | `arabidopsis_q50` | 7.340 | 29.3 | 0.471 | 0.830 | 0.919 |
| `G_bp` | `celegans_q50` | 10.987 | 1137.3 | 0.849 | 0.144 | 0.992 |
| `G_bp` | `drosophila_q50` | 11.702 | 2758.5 | 0.220 | 0.551 | 0.996 |

Reading against the preregistered rule:

1. No state in either arm is rejected at the Bonferroni level 0.0125, for any policy.
2. Across the 12 watermarked tests there is one rejection at the nominal 0.05 level (`G_tok`
   `drosophila_q50`, p = 0.037). Across the 12 ordinary size-control tests there is also exactly one
   (`C_tok` `celegans_q50`, p = 0.029). The expectation under the null is 0.6 in each arm, so both
   arms are consistent with correct size and with each other.

Stage 1 therefore passes for all three policies. The watermarked arm is statistically
indistinguishable from the ordinary arm on this test, which is what an exact-marginal construction
predicts.

Two secondary observations, both consistent with E2:

- the `arabidopsis_q50` state is near-degenerate at every policy (effective support 11-29) and shows
  the lowest agreement rates, 0.859-0.919, because a concentrated law puts the partition mass far
  from one half;
- agreement rates on high-entropy states are 0.978-0.997, close to the ceiling of one.

Agreement rates here are generator-side diagnostics computed with a published fixture key. They are
not detector results and carry no calibrated false-positive rate.

Artifact digests:

| Policy | Artifact | SHA-256 |
|---|---|---|
| `C_tok` | `outputs/carbon_c_tok_e3_preservation_v1.json` | `b87e1c2553c4c2fd947fd800b11089c8f6fa8d9053cf0d62a8af2e7bca935bf5` |
| `G_tok` | `outputs/generator_g_tok_e3_preservation_v1.json` | `63674eb2fbaeb19ca9771b5e044e46db3795a54326c5091e38bfb9be86e3f889` |
| `G_bp` | `outputs/generator_g_bp_e3_preservation_v1.json` | `e0eab907198464d7d5b80ed1142183c034e1cdd1ba2a447539de4303aae538ae` |

## Stage-1 evidence-admission review (2026-08-21)

Reviewed and admitted. The stage-1 reports were validated by
`src/genomic_watermarks/preservation_report.py`, which checks schema, classification, pinned
policy/revision/device/dtype, temperature and truncation, the declared fixture-key source, cohort
membership and per-state prompt checksums, the frozen draws/replicates/seed, p-value bounds and
Monte Carlo lattice values, and recomputes both family summaries from the per-state p-values. Raw
key, logit, probability, token, and sequence fields are absent.

Provenance was bound the same way as E2: `scripts/analyze_preservation.py` reads the immutable
report, validates it, and writes a new analysis artifact carrying the cohort content and manifest
digests, the model scope, the protocol block, and explicit test, control, and multiplicity scope.
No model inference was repeated and no completed file was edited.

Admitted to `evidence/measurements.yaml`, six entries — one per policy and arm:

- `e3.preservation.{c_tok,g_tok,g_bp}.watermarked_minimum_p_value`
- `e3.preservation.{c_tok,g_tok,g_bp}.ordinary_minimum_p_value`

Each entry's value is the smallest p-value over the four tested states for that arm. Rejection
counts at the nominal 0.05 and Bonferroni 0.0125 levels are admitted alongside it under
`admitted_counts`.

**Deliberate granularity decision.** The per-state p-value table is *not* admitted. The paper
reports the family summary for each policy and arm, not the 12-row state table. If a later draft
needs the state table, those values require their own admission.

Analysis artifact digests:

| Policy | Analysis artifact | SHA-256 |
|---|---|---|
| `C_tok` | `outputs/carbon_c_tok_e3_preservation_analysis_v1.json` | `2de589db9f31753973d52b8b52f115e97224b87416591ee259996768ce02de13` |
| `G_tok` | `outputs/generator_g_tok_e3_preservation_analysis_v1.json` | `154784eea96ddfa23ad737abbe1c16ce81433d332ceb553549f5494d6bd43165` |
| `G_bp` | `outputs/generator_g_bp_e3_preservation_analysis_v1.json` | `bcbfb20a47d306aaea2a5b4985e46f8ccd9a8db8e47ddc793292cb90347af857` |

## Evidence boundary

Stage-1 reports are engineering artifacts in ignored `outputs/`. Only the six admitted family
summaries above are paper-printable; nothing else from these runs is. Stage-2 has not been run and
has no admitted numbers.
