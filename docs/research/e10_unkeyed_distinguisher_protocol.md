# E10 held-out unkeyed distinguisher protocol

Frozen before running the multi-key experiment. One disclosure below: a single-key smoke was run
first, and it is what motivated the design. That is stated rather than hidden.

## Question

The threat model's third goal is that a one-output classifier **without** the key should not reliably
tell an exact-marginal watermarked sequence from an ordinary one under matched conditions. Can cheap,
model-free distinguishers do it?

## Why cheap distinguishers are the right test

If a construction is separable by a 3-mer centroid or by a general-purpose compressor, it is
separable, and no elaborate classifier is needed to establish that. The converse does not hold:
failing with these rules out the crude attacks and does not establish undetectability. That
asymmetry is the scope of this experiment and must be stated wherever its result is reported.

## Disclosure: what was seen before freezing

A single-key smoke on `C_tok`, using the existing E4 corpus, scored:

| Distinguisher | Accuracy, 8 decisions | Interval covers chance |
|---|---:|---|
| `compression` | 0.875 | no |
| `proxy_centroid` | 0.750 | yes |
| `trimer_centroid` | 0.750 | yes |

Seven of eight for the compressor is not nothing. It also points the same way as the fixed-key
stage-2 proxy result, where `C_tok`'s watermarked arm looked slightly more diverse — higher entropy,
higher distinct-hexamer fraction — and a less compressible sequence is exactly what that would
produce.

Both observations share one candidate explanation: a **single key** is a single realization, and the
construction is exact only in expectation over keys. So the frozen design below averages over keys,
and the prediction is stated before running it.

## Frozen shape

| Item | Frozen choice |
|---|---|
| Policies | `C_tok`, `G_tok`, `G_bp` |
| Prompts | the eight `q20` and `q80` windows |
| Keys | four independent published fixture keys |
| Sequences | 3,072 bases per prompt, per key, watermarked; the single ordinary arm as control |
| Task | paired two-alternative forced choice: given one watermarked and one ordinary sequence from the *same* prompt, say which is watermarked |
| Chance | exactly 0.5, because the pair shares a prompt |
| Fitting | leave-one-prompt-out; a distinguisher never scores a prompt it was fit to |
| Ties | count as a miss, never as a coin flip |
| Distinguishers | `proxy_centroid` over the nine sequence proxies, `trimer_centroid` over 64 3-mer frequencies, `compression` over zlib bytes per base |
| Decisions | 8 prompts x 4 keys = 32 per distinguisher and policy |
| Uncertainty | percentile bootstrap over the 8 prompt clusters, 20,000 replicates, seed 2718 |

The observer never receives the key, the model, the prompt, or the pairing rule used to fit — only
the sequences.

## Predicted outcome, stated before the run

Accuracy near 0.5 with a prompt-cluster interval covering 0.5, for every distinguisher and policy.
Specifically, the `C_tok` compression accuracy is predicted to fall from 0.875 toward chance once the
watermarked arm spans four keys, because a per-key realization effect cannot survive averaging over
keys.

If it does **not** fall, the effect is not a realization artifact. That would be a genuine one-output
distinguishability finding against threat-model goal three, and it would have to be reported as such
rather than explained away. It would also require re-examining the fixed-key stage-2 pattern as a
real effect.

Note the resolution limit honestly: with 8 prompt clusters the bootstrap is coarse, and 32 decisions
cannot separate 0.5 from, say, 0.6. This experiment can catch a gross distinguisher and cannot
certify a subtle one.

## Amendment forced by the E3 finding (2026-08-21)

The shape above pairs each watermarked sequence against **one** ordinary control. The E3 stage-2
investigation then showed that exactly this asymmetry invalidates a comparison: averaging or
comparing against a single control cannot separate a watermark effect from that control's own
realization noise, and a single-key smoke pointing the same way as a single-control proxy comparison
is the signature of shared noise, not of a real effect.

The same objection applies here. A distinguisher trained to separate four watermarked draws from one
fixed control can learn the control's realization as easily as the watermark.

The corrected shape pairs each watermarked draw with the ordinary draw from **its own generation
run**, so every forced choice is between two sequences produced under the same conditions and
differing only in whether the watermark was applied.

This is a shape change made after seeing the single-key smoke and after the E3 result, and it is
recorded as such. It is not yet run: it needs matched per-draw pairs, which exist for `C_tok` from
the symmetric draws but not for `G_tok` or `G_bp`.

Status: distinguishers implemented and unit-tested, protocol frozen, single-key smoke recorded above
as motivation. The experiment itself is **not run** and nothing from it is admitted.

## Result and admission for `C_tok` (2026-08-21)

Four matched draws, 8 prompts, 32 decisions per distinguisher, chance exactly 0.5.

| Distinguisher | Correct | Accuracy | Exact cluster p | Descriptive bootstrap |
|---|---:|---:|---:|---|
| `compression` | 12/32 | 0.3750 | 0.3125 | [0.219, 0.531] |
| `proxy_centroid` | 19/32 | 0.5938 | 0.2500 | [0.531, 0.688] |
| `trimer_centroid` | 17/32 | 0.5312 | 1.0000 | [0.375, 0.688] |

**No distinguisher separates the arms.** The exact cluster sign-flip p-values are 0.31, 0.25, and
1.00, and the strongest accuracy is 0.594 on 32 decisions.

The prediction holds. Compression fell from **0.875** under a single key against a shared control to
**0.375** with matched per-draw pairs — below chance. The single-key smoke was the shared-control
artifact the amendment anticipated, and it is now resolved rather than left as an open worry.

### A statistical defect found while reading this result

The first version of this run reported a prompt-cluster bootstrap and a flag for whether its interval
covered chance. For `proxy_centroid` that interval was [0.531, 0.688] and therefore *excluded* chance,
which reads as a finding. It is not one. The pooled count is 19 of 32, whose two-sided binomial
p-value is 0.38.

The bootstrap resamples eight per-prompt accuracies **as if each were known**, when each is estimated
from only four decisions. Every prompt happened to land at 0.5 or 0.75 — exactly what chance produces
with four draws — so the resampled mean almost never fell below 0.53. The scheme ignored
within-prompt noise entirely.

The admitted test is now an **exact two-sided sign-flip over prompt clusters**: under the null the
two members of a pair are exchangeable, so relabelling a whole prompt maps `k` correct to `draws - k`,
and enumerating all `2^8` relabellings gives an exact p-value that keeps decisions inside a prompt
together. The bootstrap is retained in the artifact as a descriptive interval, carrying its own
caveat, and is not admitted.

This is the third resampling scheme in this project that had to be replaced because it did not match
the actual noise structure. The pattern is worth naming: an interval is only as valid as the
exchangeability it assumes, and every one of these was caught by a number that looked too good rather
than by inspection.

Admitted: one entry, `e10.unkeyed_distinguisher.c_tok.minimum_exact_p_value`, carrying all three
distinguishers with accuracies, counts, and exact p-values, plus an explicit record of the resolution
against the single-key smoke. Report digest `839b3745e0f6dc1a31a0f1313b9d7f61cced39f9ad936fb29d01b55b0be673e8`.

`G_tok` and `G_bp` are not admitted: their matched per-draw generation is not complete.

## Boundary

Three cheap distinguishers, one output per key per prompt, a fixed corpus, and no adaptivity. Out of
scope: stronger learned classifiers, many outputs under one key, an observer who chooses the prompts,
and any claim of cryptographic indistinguishability. Nothing here is a security proof.

## Implementation status

- `src/genomic_watermarks/distinguishers.py` implements the three distinguishers and the
  leave-one-prompt-out forced choice.
- `scripts/run_unkeyed_distinguisher_pilot.py` runs the experiment. It loads no model.

## Exact command

```bash
uv run python scripts/run_unkeyed_distinguisher_pilot.py \
  --base-sequences outputs/carbon_c_tok_e4_sequences_v1.jsonl \
  --additional-sequences outputs/carbon_c_tok_e3_keyavg_sequences_k1_v1.jsonl \
                         outputs/carbon_c_tok_e3_keyavg_sequences_k2_v1.jsonl \
                         outputs/carbon_c_tok_e3_keyavg_sequences_k3_v1.jsonl \
  --cohort-jsonl data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl \
  --cohort-manifest data/public_prompt_cohort_v2.yaml \
  --bootstrap-replicates 20000 --bootstrap-seed 2718 \
  --output outputs/carbon_c_tok_e10_unkeyed_distinguisher_v1.json
```

Repeat for `G_tok` and `G_bp`.

## Evidence boundary

Reports are engineering artifacts in ignored `outputs/`. No number moves into
`evidence/measurements.yaml` without explicit evidence-admission review.
