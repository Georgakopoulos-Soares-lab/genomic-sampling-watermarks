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

## Result and admission, revision 2 (2026-08-22)

Four matched draws per policy, 8 prompts, 32 decisions per distinguisher, chance exactly 0.5,
calibrated against a two-sided permute-and-refit null with 1,999 replicates.

| Policy | Distinguisher | Correct | Accuracy | p | Null accuracy range |
|---|---|---:|---:|---:|---|
| `C_tok` | `compression` | 12/32 | 0.3750 | 0.3835 | [0.156, 0.781] |
| `C_tok` | `proxy_centroid` | 19/32 | 0.5938 | 0.5355 | [0.125, 0.812] |
| `C_tok` | `trimer_centroid` | 17/32 | 0.5312 | 0.8935 | [0.094, 0.812] |
| `G_tok` | `compression` | 14/32 | 0.4375 | 0.7265 | [0.156, 0.750] |
| `G_tok` | `proxy_centroid` | 17/32 | 0.5312 | 0.9005 | [0.125, 0.781] |
| `G_tok` | `trimer_centroid` | 15/32 | 0.4688 | 0.8980 | [0.125, 0.781] |
| `G_bp` | `compression` | 10/32 | 0.3125 | 0.1405 | [0.156, 0.812] |
| `G_bp` | `proxy_centroid` | 7/32 | 0.2188 | 0.0195 ** | [0.125, 0.812] |
| `G_bp` | `trimer_centroid` | 6/32 | 0.1875 | 0.0090 ** | [0.094, 0.812] |

Nine tests. The Bonferroni threshold is 0.0056 and **no test clears it**. Two tests are nominally
significant at 0.05, both on `G_bp`, against 0.45 expected under the null.

### `C_tok` and `G_tok`: no separation

Every p-value is between 0.38 and 0.90. The single-key compression smoke of 0.875 that motivated this
experiment is fully explained: with matched per-draw pairs it falls to 0.375, and the correct null
puts that comfortably inside chance.

### `G_bp`: unresolved, and not claimed either way

Two of three distinguishers on `G_bp` land at p = 0.0195 and p = 0.0090, both in the **below-chance**
direction — the held-out pair's difference runs opposite to the direction fitted on other prompts.
A distinguisher that is reliably wrong can be inverted into one that is reliably right, which is why
the test is two-sided and why this is not dismissed as "worse than chance, therefore fine".

What can be said: neither clears Bonferroni across the nine tests, so this is **not** a
distinguishability finding. What must not be said: that `G_bp` is indistinguishable. Two nominal
rejections in one policy, in a consistent direction, is exactly the pattern that either resolves as
noise or turns out to be real, and 32 decisions cannot tell which.

`G_bp` is the base-marginal policy, whose 4,096-way law is a product of six independent base
marginals rather than a general categorical. That is a structural difference from the other two
policies and the obvious place to look. It is a hypothesis, not a finding.

Owed next: more draws for `G_bp`, which is the only way to move the resolution. The design is already
in place; it needs generation time.

### The calibration that had to be replaced

Revision 1 used an exact sign-flip over prompt clusters. That test assumes prompts can be relabelled
independently. They cannot: every decision uses a direction fitted from the **other prompts' labels**,
so all decisions share a fitted quantity and the sign-flip null is too narrow.

The defect was caught by the `G_bp` numbers looking wrong rather than merely surprising — accuracies
*below* chance with small p-values. Replicating the entire procedure on true-null synthetic data
settled it: accuracy ranged from 0.156 to 0.750 across 40 replications with a mean at 0.49. The
procedure is unbiased; its null is simply very wide. A sign-flip null that ignores the shared fit
cannot see that width, so its p-values were anti-conservative.

Under the corrected null the observed null ranges above confirm the width directly: roughly 0.09 to
0.81 in every cell.

Cited artifact digests:

| Policy | Report |
|---|---|
| `C_tok` | `6e8d37a13848d15d890fb27087ccfd5dad1e5acc071ab53167e7bbde4a3e812d` |
| `G_tok` | `be3a934f539bf763dd266f353fd2050fb989591a1412e7916e5ab10e4e5db20e` |
| `G_bp` | `b0d787c0c958392708f6ad9293e51e6546579ef7ecde5775cc8533109ebc3338` |

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

## Note on the additional draws, 2026-08-23

The two unresolved nominal `G_bp` rejections need more matched draws to sharpen the permutation null
from 32 decisions to 80. Eighteen draws were queued — six new published fixture keys for each of the
three policies, both arms, 512 tokens, the same eight prompts — and the run was **stopped without
producing any artifact**, so nothing partial entered the repository.

The reason is worth recording, because it is a reproducibility constraint on this hardware rather than
an experiment problem. On battery power the MPS device is power-limited: the same generation job that
ran at essentially one full core when the machine was on mains advanced at about 11% of a core on
battery, roughly a tenfold slowdown, while a pure CPU benchmark on the same machine ran at full speed.
Eighteen draws would have taken tens of hours instead of about five, and the battery had under three
hours left.

**The additional draws require mains power.** The command is unchanged:

```bash
for i in 7 8 9 10 11 12; do
  .venv/bin/python scripts/generate_watermarked.py --policy G_bp \
    --case-id arabidopsis_q20 --case-id arabidopsis_q80 \
    --case-id celegans_q20 --case-id celegans_q80 \
    --case-id drosophila_q20 --case-id drosophila_q80 \
    --case-id yeast_q20 --case-id yeast_q80 \
    --steps 512 --arms both --experiment-label "e10-extra-draw-k${i}" \
    --public-fixture-key --fixture-key-index "$i" --local-files-only \
    --output "outputs/generator_g_bp_e10_extra_generation_k${i}_v1.json" \
    --sequences-output "outputs/generator_g_bp_e10_extra_sequences_k${i}_v1.jsonl"
done
```

This also means no runtime figure may be quoted without stating the power state it was measured in.
The admitted E14 wall times were all collected on mains power; that is now recorded rather than
assumed.
