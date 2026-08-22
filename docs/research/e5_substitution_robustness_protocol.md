# E5 substitution robustness protocol

Frozen before inspecting any edited-sequence detector output.

## Question

How far does substitution corruption degrade detection, at each generated length, when the threshold
is calibrated over the complete declared search under the same edit condition?

## Why substitutions first

Substitutions are the only edit class that leaves the token grid intact: base `i` stays at position
`i`, so a corrupted 6-mer damages exactly one key-stream position and nothing downstream. Insertions
and deletions shift every later position and are a synchronization problem, not a corruption
problem. Measuring the corruption channel alone first isolates one mechanism and gives the indel
experiment a baseline to be compared against.

## Predicted shape, stated before the run

With per-base substitution rate `r`, a token survives intact with probability `(1 - r)^6`. An intact
token keeps its generator-side agreement, about 0.99 on these policies; a corrupted token becomes a
different token whose keyed group is a fair coin. So the expected agreement is

```text
q(r) = 0.5 + 0.49 * (1 - r)^6
z(r, n) = (2 q(r) - 1) * sqrt(n) = 0.98 * (1 - r)^6 * sqrt(n)
```

Against the E4 null maxima of roughly 3.7 to 4.6, that predicts the transition sits near `r = 0.25`
at 3,072 bases and near `r = 0.12` at 384 bases. The rate grid below is chosen to bracket both. If
the measurement disagrees with this prediction, the prediction is what was wrong; do not adjust the
grid after seeing results.

## Frozen shape

| Item | Frozen choice |
|---|---|
| Policies | `C_tok`, `G_tok`, `G_bp` |
| Corpus | the E4 generated corpus, unchanged; 8 prompts, 3,072 bases per prompt and arm |
| Edit | independent per-base substitution to a different base |
| Rates | 0.00, 0.01, 0.05, 0.10, 0.15, 0.20, 0.30 |
| Evaluated lengths | 384, 768, 1,536, 3,072 bases as prefixes of the edited sequence |
| Detector search | unchanged from E4: 2 orientations x 6 phases x full-prefix window x 8 offsets = 96 hypotheses |
| Positive trials | 5 independent edit replicates per prompt = 40 per policy, rate, and length |
| N1 | wrong key on the edited watermarked arm, replicate 0, 8 keys = 64 |
| N2 | any key on the edited ordinary arm, replicate 0, 8 keys = 64 |
| Target FPR | 0.01, calibrated per rate and per length on pooled N1 and N2 |
| Uncertainty | percentile bootstrap over the 8 prompt clusters, 20,000 replicates, seed 2718 |
| Key material | published non-secret fixture, as in E4 |

The sequence is edited once per prompt, rate, and replicate, and the prefixes are taken from the
edited sequence, so every evaluated length sees the same edit process at the same rate.

Edit replicates are nested inside prompts. The bootstrap therefore resamples prompts and averages
replicates within a prompt; replicates are not independent clusters and are never resampled as such.

Rate 0.00 is retained as an internal consistency check: it must reproduce the E4 clean result up to
the smaller null-key count.

## Null calibration

The threshold is calibrated **per rate**, from that rate's own 128 pooled null trials, so no
invariance assumption is needed. Attainable false-positive granularity is therefore 1/128 = 0.0078.

The report also computes a threshold from nulls pooled across all rates within a policy and length,
and the per-rate null summaries needed to see whether pooling is justified. Under a wrong key each
observed token's group is a fair coin whether or not the base was substituted, so the null
distribution should not depend on the rate. That is a prediction, not an assumption: the per-rate
null maxima and means are reported so it can be checked. The pooled threshold is reported as a
sensitivity check with finer resolution, never as the headline.

## Preregistered reading

- Report detection rate against rate for each policy and length. The headline number is the largest
  rate at which detection remains 1.0 at the calibrated 0.01 threshold, per length.
- A monotone decline with length-dependent breakdown is the expected result and is a positive
  finding, not a failure.
- If detection collapses at rates below 0.01, the construction is not substitution-robust at these
  lengths and that is the result. Do not widen the search, lengthen the sequence, or drop a rate to
  rescue it.
- If the per-rate null maxima drift systematically with rate, the fair-coin argument above is wrong
  and the discrepancy must be explained before any robustness number is admitted.

## Boundary

Substitutions only. Insertions, deletions, crops, reverse complementation, adaptive removal, and key
reuse are separate experiments with their own frozen shapes. Substitution robustness is not evidence
of indel robustness; the mechanisms differ, which is the whole reason they are separated.

Biological note: a uniform independent per-base substitution process is a statistical channel, not a
model of mutation, sequencing error, or synthesis error. It supports no claim about real-world
sequence degradation.

## Implementation status

- `src/genomic_watermarks/edits/channel.py` implements the substitution channel.
- `src/genomic_watermarks/detector/search.py` provides the unchanged declared search and calibration.
- `scripts/run_edit_robustness_pilot.py` runs this experiment. It loads no model.

## Exact command

```bash
uv run python scripts/run_edit_robustness_pilot.py \
  --sequences outputs/carbon_c_tok_e4_sequences_v1.jsonl \
  --cohort-jsonl data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl \
  --cohort-manifest data/public_prompt_cohort_v2.yaml \
  --edit substitution \
  --rates 0.0 0.01 0.05 0.10 0.15 0.20 0.30 \
  --token-lengths 64 128 256 512 \
  --stream-offsets 8 --null-keys 8 --positive-replicates 5 \
  --target-fpr 0.01 --bootstrap-replicates 20000 --bootstrap-seed 2718 \
  --experiment-label e5-substitution-v1 \
  --output outputs/carbon_c_tok_e5_substitution_v1.json
```

Repeat for `G_tok` and `G_bp` with policy-specific names.

## Result (2026-08-21)

Run after the shape above was frozen. 4,704 trials per policy in 47-48 seconds each, model-free.
The values below are the corrected revision described under "Decision-rule correction" at the end
of this document.

Detection rate, 40 positive trials per cell, threshold calibrated per rate and length at target
FPR 0.01 (attainable granularity 1/128 = 0.0078):

| Policy | Rate | 384 b | 768 b | 1,536 b | 3,072 b |
|---|---:|---:|---:|---:|---:|
| `C_tok` | 0.00 | 1.000 | 1.000 | 1.000 | 1.000 |
| `C_tok` | 0.01 | 1.000 | 1.000 | 1.000 | 1.000 |
| `C_tok` | 0.05 | 1.000 | 1.000 | 1.000 | 1.000 |
| `C_tok` | 0.10 | 0.775 | 1.000 | 1.000 | 1.000 |
| `C_tok` | 0.15 | 0.150 | 0.700 | 1.000 | 1.000 |
| `C_tok` | 0.20 | 0.075 | 0.100 | 0.550 | 0.975 |
| `C_tok` | 0.30 | 0.000 | 0.050 | 0.000 | 0.175 |
| `G_tok` | 0.00 | 1.000 | 1.000 | 1.000 | 1.000 |
| `G_tok` | 0.01 | 1.000 | 1.000 | 1.000 | 1.000 |
| `G_tok` | 0.05 | 1.000 | 1.000 | 1.000 | 1.000 |
| `G_tok` | 0.10 | 0.950 | 1.000 | 1.000 | 1.000 |
| `G_tok` | 0.15 | 0.150 | 0.825 | 1.000 | 1.000 |
| `G_tok` | 0.20 | 0.050 | 0.250 | 0.750 | 1.000 |
| `G_tok` | 0.30 | 0.000 | 0.000 | 0.050 | 0.150 |
| `G_bp` | 0.00 | 1.000 | 1.000 | 1.000 | 1.000 |
| `G_bp` | 0.01 | 1.000 | 1.000 | 1.000 | 1.000 |
| `G_bp` | 0.05 | 1.000 | 1.000 | 1.000 | 1.000 |
| `G_bp` | 0.10 | 0.750 | 1.000 | 1.000 | 1.000 |
| `G_bp` | 0.15 | 0.150 | 0.525 | 1.000 | 1.000 |
| `G_bp` | 0.20 | 0.025 | 0.400 | 0.800 | 1.000 |
| `G_bp` | 0.30 | 0.000 | 0.000 | 0.025 | 0.050 |

Largest rate with detection 1.0:

| Length | `C_tok` | `G_tok` | `G_bp` |
|---|---:|---:|---:|
| 384 b | 0.05 | 0.05 | 0.05 |
| 768 b | 0.10 | 0.10 | 0.10 |
| 1,536 b | 0.15 | 0.15 | 0.15 |
| 3,072 b | 0.15 | 0.20 | 0.20 |

Reading against the preregistered rule:

1. **Every policy tolerates 5% substitution at every evaluated length, and 20% at 3,072 bases for
   two of three policies.** Breakdown is length-dependent and monotone, which is the expected
   result. The three policies agree closely, which is what a policy-independent mechanism predicts.
2. **The null distribution does not depend on the edit rate.** Across rates, the pooled null mean
   moves by 0.06 to 0.15 in z units against a null mean near 2.5, and the null maximum by a similar
   amount with no trend. The fair-coin argument holds, so rates are comparable and pooling nulls
   across rates is defensible; the per-rate calibration used for the headline needs no such
   assumption.
3. **The stated prediction is confirmed.** With `z(r, n) = 0.98 (1 - r)^6 sqrt(n)` and the E4 null
   maxima near 3.7-4.6, the predicted transitions were near `r = 0.25` at 3,072 bases and near
   `r = 0.12` at 384 bases. Measured: detection is still 0.975-1.0 at `r = 0.20` and collapses to
   0.05-0.175 at `r = 0.30` at 3,072 bases; at 384 bases it is 0.75-0.95 at `r = 0.10` and
   0.15-0.20 at `r = 0.15`. The analytic channel model therefore predicts the empirical curve
   without fitting.

One non-monotonicity is visible and is sampling noise, not a finding: `G_tok` at `r = 0.30` reports
0.000 at 768 bases but 0.050 at 1,536 bases, and `G_bp` reports 0.000 at 768 bases and 0.025 at
1,536 bases. At 40 trials per cell the resolution is 0.025 and the thresholds are 128-trial order
statistics, so cells in the collapsed tail are not distinguishable from each other.

## Evidence-admission review (2026-08-21)

Reviewed and admitted. `src/genomic_watermarks/edit_report.py` recomputes every reported aggregate
from the stored per-trial rows: each statistic from its match count, the token total from its length
and phase, the per-rate threshold, achieved and attainable false-positive rates, detection rate, the
prompt-cluster bootstrap that averages replicates within a prompt, the empirical global p-values,
both null-family exceedance rates, and the separation summary. It enforces the declared search
unchanged from E4, the edit grid, the replicate and null-key counts per cell, that null trials use
only the first edit replicate, and the absence of raw DNA, key, logit, and probability fields. It
also returns the per-rate null summaries used for the invariance check above.

`scripts/analyze_edit_robustness.py` binds provenance: the report digest, the generation report
digest with model revision, device, and dtype, the sequences digest, recomputed cohort digests, the
edit channel with its explicit non-biological boundary, and calibration, null-invariance,
uncertainty, and security scope.

Admitted to `evidence/measurements.yaml`: twelve entries, one per policy and length,

- `e5.substitution.{c_tok,g_tok,g_bp}.b{384,768,1536,3072}.max_fully_detected_rate`

Each value is the largest evaluated rate with detection 1.0. The complete seven-point curve is
admitted inside each entry under `admitted_curve`, with per-point detection rate, interval,
threshold, achieved FPR, both null exceedances, and separation statistics, plus the null-invariance
spreads under `admitted_null_invariance`. Per-trial statistics are not admitted.

Cited artifact digests, corrected revision:

| Policy | Report | Analysis |
|---|---|---|
| `C_tok` | `7547ad2ec49fdb58fa0e8f6797fd68c36de18b74e31ae165b2592ed7ebe49264` | `4f1255ec7d9943a6bd1ea7ee56f3f57d0dd86d1b6e9197fd342bc360de93621d` |
| `G_tok` | `95a27d9270e8f34bd647084eaeb0762b534924eb7b5ee928cec5a0ab73162b6f` | `13509c0ab6a82fcea69e126732a657f2f25d1850935b02d79a62842aca2de3cd` |
| `G_bp` | `f40b7df954d50783410f16aae5769a2f5b5cb36344c4b8d65093917f8268a18a` | `23104f323138211552bdfc69759853d2105c52563d6817054aaab1fea3c6fcfd` |

## Decision-rule correction (2026-08-21)

A first revision of this experiment was admitted and then superseded. The calibration chose its
threshold by counting null statistics **strictly above** a candidate, but the decision applied to a
trial was **greater than or equal to** the threshold. The statistic is discrete and the threshold is
itself a null order statistic, so ties at the threshold were common and were counted as detections.
The realized false-positive rate therefore exceeded the reported one: at 3,072 bases in the clean
pilot the reported rate was 0.009375 against a target of 0.01, while the rule as applied achieved
0.0125.

The rule is now strictly greater than the threshold everywhere, including the bootstrap indicators
inside every runner and validator, and `src/genomic_watermarks/detector/search.py` states the rule
and documents why the two must agree. A regression test constructs tied statistics and asserts that
the calibration and the decision rule count identically.

The experiment was re-run with the same edit seeds, so the only difference is the rule. Thresholds
are identical. Every headline value, the largest fully detected rate, is unchanged. Of 28 curve cells
per policy, one to three moved, all downward, all inside the collapsed tail: `C_tok` 0.775 to 0.700
at rate 0.15 and 768 bases and 0.075 to 0.000 at rate 0.30 and 384 bases; `G_tok` three cells;
`G_bp` one cell. The superseded artifacts remain on disk unmodified and are no longer cited.

## Runtime note

The first version of the detector pilots rebuilt the keyed partition cache for every scored
sequence. A keyed partition depends on the key, the domain, and the stream position and never on the
observed DNA, so one cache per key serves every sequence, rate, and length. Sharing the cache made
the clean pilot 15.6 times faster, from 826 to 53 seconds, and reproduced every stored trial and
aggregate byte for byte against the admitted E4 artifact. That check is why this experiment could
sweep seven rates in 46 seconds instead of two hours.

## Evidence boundary

Reports are engineering artifacts in ignored `outputs/`. Only the twelve admitted entries and the
curves inside them are paper-printable. Substitution results say nothing about indels, crops,
reverse complementation, adaptive removal, or key reuse.
