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

Not yet run. Stage 2 compares matched ordinary and watermarked continuations on declared
sequence-level proxy metrics from `docs/baseline_definition.md`. It requires the generation pilot at
paper lengths and is reported separately, with its own frozen shape.

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

## Evidence boundary

Stage-1 reports are engineering artifacts in ignored `outputs/`. No number moves into
`evidence/measurements.yaml` without explicit evidence-admission review.
