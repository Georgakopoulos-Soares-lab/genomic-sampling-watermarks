# E8 and E9 matched baseline protocol

Frozen before generating or scoring any inverse-transform or exponential sequence.

## Question

On the same model policies, the same prompts, and the same detector discipline, how does the
partition-coupling construction compare with the two published alternatives it was always meant to be
measured against?

## The three methods

| Method | Sampling rule | Detector statistic | Auxiliary randomness |
|---|---|---|---|
| `partition_mc` | fair keyed latent bit coupled to a keyed equal-cardinality partition by maximal coupling | keyed group agreement | yes, the residual draw |
| `its` | keyed permutation of the support, keyed uniform selects a point on the cumulative distribution | closeness of the token's normalized rank to the uniform | none |
| `exp` | one keyed uniform per candidate, emit `argmax u^(1/p)` | `-log(1 - u)` at the observed token | none |

All three preserve the declared one-step marginal exactly. All three are scored by a verifier holding
only DNA, a runtime key, and public configuration. Neither `its` nor `exp` is claimed as novel; they
are implemented here so the comparison is on identical footing rather than across papers.

## Prediction, stated before the run, and it does not favour our construction

The three methods do not carry the same amount of signal per token, and the arithmetic says so in
advance.

`partition_mc` couples **one bit** per token. At the best possible partition mass the sampled group
equals the latent bit every time, giving a standardized statistic of `sqrt(n)` after `n` tokens.
That is the ceiling, and E2 measured the realized channel at about 0.15 of the 0.167 bit per base it
allows.

`exp` is not capped at one bit. For a near-uniform law over `K = 4096` tokens, the winning token's
keyed uniform is close to one, and

```text
E[-log(1 - u_winner)] = H_K  =  8.895   for K = 4096
```

against a null mean of 1 and null standard deviation of 1. The per-token standardized signal is
therefore about **7.9**, and the statistic grows like `7.9 * sqrt(n)`.

`its` sits in the same family: the emitted token's normalized rank tracks the keyed uniform, and the
signal grows with how finely the permutation resolves the support.

**So the prediction is that `exp`, and probably `its`, detect at substantially shorter sequences than
`partition_mc` on these high-entropy genomic states.** If that holds, the honest framing of this
project's contribution is not that partition coupling is the best construction, but that the
comparison was measured on real genomic policies with a calibrated detector — which is outcome three
in `paper/context/01_contribution.md`, listed there as legitimate from the start.

If instead `partition_mc` matches or beats them, that is the surprising result and needs an
explanation before it is believed.

## Frozen shape

| Item | Frozen choice |
|---|---|
| Policies | `C_tok`, `G_tok`, `G_bp` |
| Prompts | the eight `q20` and `q80` windows |
| Generated length | 512 tokens, 3,072 bases, per prompt and method |
| Methods | `partition_mc` reusing the existing E4 corpus, plus newly generated `its` and `exp` arms |
| Control | the existing ordinary arm from the same generation runs |
| Evaluated lengths | 384, 768, 1,536, and 3,072 bases as prefixes |
| Detector search | identical for all three: 2 orientations x 6 phases x full prefix x 8 key-stream offsets |
| Target FPR | 0.01, calibrated **separately for each method** on its own nulls |
| Nulls | wrong key on that method's watermarked arm, and any key on the shared ordinary arm |
| Uncertainty | percentile bootstrap over the 8 prompt clusters, 20,000 replicates, seed 2718 |
| Key material | published non-secret fixture |

### What makes the comparison fair

Three things, and each is a way the comparison could be rigged if left unstated.

1. **Identical search, identical multiplicity.** All three detectors search the same 96 hypotheses,
   so no method gets a threshold advantage from a smaller search.
2. **Per-method calibration.** The three statistics live on different scales, so a shared threshold
   would be meaningless. Each is calibrated to the same target false-positive rate on its own nulls,
   and the comparison is between detection rates at that common rate.
3. **Shared prompts, lengths, policy, and control.** Only the sampler differs.

### Preregistered reading

- Report detection rate against length for each method and policy at the common calibrated FPR.
- The headline is the shortest evaluated length at which each method detects every sequence.
- A method that detects at 384 bases while another needs 3,072 is a real and reportable difference,
  in whichever direction it falls.
- Do not compare raw statistic values across methods; they are on different scales and only the
  calibrated detection rate is comparable.

## Boundary

Clean sequences only. Edit robustness for `its` and `exp` is a separate experiment: the three methods
may degrade very differently under substitution and indels, and nothing about that may be inferred
from a clean comparison. Also out of scope: `dipmark`, green-list biasing, and any method that is not
exact-marginal.

## Amendment, 2026-08-23: a declared short-length extension

Declared before the extension was run, and recorded here rather than by editing the frozen shape
above.

A reduced smoke run of the comparison runner on `C_tok` (one length, three null keys) showed all
three methods detecting **every** sequence at 384 bases, the shortest length the frozen grid
evaluates. E4 already established that `partition_mc` reaches a detection rate of 1.0 at 96 bases,
which is the detector's own floor: `minimum_window_tokens` is 16, so 96 bases is the shortest
sequence the declared search will score at all.

So the frozen grid cannot separate the three methods, and neither can any grid, because the floor of
the declared search is already above every method's detection length. That is a property of the
question, not a defect in the run, and the frozen grid is still executed and admitted exactly as
declared.

Two things follow, both declared now:

1. **A short extension**, at 16, 24, 32, 48, and 64 tokens — the same lengths E4's short-length
   companion run used, the same declared search, and calibrated on its own nulls. Its purpose is to
   confirm that saturation persists all the way to the detector's floor rather than to find a
   separating length.
2. **The preregistered reading is amended.** "The shortest evaluated length at which each method
   detects every sequence" is expected to be identical for all three, so it is reported as a null
   finding rather than as the headline. The quantity that does separate the methods is the
   standardized signal **per token**, in units of each method's *own* null standard deviation. That
   is a derived quantity, it is not a detection rate, and the boundary on it is stated with it: it
   compares each method against its own null, never one method's statistic against another's.

This does not relax the fairness conditions. All three methods still search the same 96 hypotheses,
each is still calibrated on its own nulls at the same target rate, and the prompts, lengths, policy,
and control are still shared.

## Implementation status

- `src/genomic_watermarks/baselines.py` implements both samplers, both detector statistics, the keyed
  stream, and model-free recomputation.
- `tests/test_baselines.py` holds the invariants, written before the samplers were trusted: exact
  marginal under a skewed law for both, detector recomputation from DNA and key alone, null mean and
  variance matching what each statistic assumes, determinism under a fixed key, and two deliberately
  broken variants.
- One of those invariants is worth repeating here: walking the cumulative distribution in the
  declared order instead of the keyed order leaves the marginal **exactly correct** while removing
  the watermark entirely. A distribution-preservation test cannot catch it; only the detector can.
  That is the sharpest available argument for why E3 alone was never sufficient evidence.
- `src/genomic_watermarks/detector/baseline_search.py` implements both standalone detectors. They
  reuse `DetectorConfig` and `enumerate_search` from the partition detector unchanged, so the
  identical-search condition is structural rather than a claim; `tests/test_baseline_detector.py`
  asserts that all three methods report the same hypothesis count on the same sequence.
- `scripts/generate_baseline_arms.py` generates the `its` and `exp` arms and deliberately does not
  regenerate the control.
- `scripts/run_baseline_comparison.py` scores all three methods, calibrates each on its own nulls,
  and stores every per-trial statistic so intervals can be recomputed without rerunning inference.
- Detection-rate intervals use the joint resample established by the 2026-08-23 audit: each
  replicate resamples the pooled nulls, recalibrates the threshold, and independently resamples the
  prompt clusters.

## Result, 2026-08-23

Three policies, eight prompts, 512 tokens per prompt per method, the same 96-hypothesis search for
all three methods, each calibrated on its own nulls at a target false-positive rate of 0.01.
Validated by `validate_baseline_comparison_report`, which recomputes every aggregate from the stored
per-trial rows and re-derives each statistic from the primitive it was built from.

An independent check that the comparison is scoring the shared arm correctly: the partition arm's
calibrated thresholds in this run reproduce the E4 short-length run exactly — 3.000, 3.545, 3.772,
3.355, 3.654 for `C_tok` at 96 to 384 bases.

### The preregistered headline is a null result

Every method, every policy, every evaluated length from 96 to 3,072 bases: **detection rate 1.000**,
joint interval [1.000, 1.000]. The shortest length at which each method detects every sequence is 96
bases for all nine method-policy pairs, and 96 bases is the detector's own floor rather than a
measured limit. So the quantity the protocol nominated as the headline cannot distinguish the three
constructions on clean sequences, and the amendment above anticipated this.

### The per-token signal does separate them, exactly as predicted

Mean standardized signal per 6-mer token, in units of each method's own null standard deviation:

| Policy | `partition_mc` | `its` | `exp` |
|---|---|---|---|
| `C_tok` | 0.963 – 0.969 | 1.377 – 1.393 | 7.19 – 7.86 |
| `G_tok` | 0.977 – 1.000 | 1.380 – 1.389 | 7.43 – 8.02 |
| `G_bp` | 0.993 – 1.000 | 1.388 – 1.391 | 7.29 – 7.62 |

`exp` carries about **7.5 times** the per-token signal of partition coupling and `its` about **1.4
times**. The prediction stated before the run was about 7.9 for `exp`; the measurement is 7.2 to 8.0.

### Why partition coupling loses, and why that is not an implementation defect

Partition coupling is at its ceiling, not below it. It couples one bit per token, so its per-token
standardized signal cannot exceed 1.0, and the measured values are the coupling loss away from that
cap: agreement rates of 0.984, 0.992, and 0.997 give `2p - 1` of 0.968, 0.983, and 0.994, which is
what the detector reports to three decimals. `exp` is not capped at one bit, and that is the whole
of the difference.

So the honest reading is the third outcome listed in `../../paper/context/01_contribution.md`:
partition coupling is **not** the strongest of the three constructions on high-entropy genomic
states. What this project contributes is the measurement — on real released policies, with one
shared calibrated detector, and with the fairness conditions checked rather than asserted.

### An unplanned finding: calibration does not transfer to natural DNA equally

Thresholds are calibrated on model-generated nulls. The public-DNA family, which is never pooled into
any threshold, exceeds those thresholds at rates above the 0.01 target, and unequally by method. At
192 bases: `C_tok` `its` 0.069 and `exp` 0.050 against `partition_mc` 0.000; `G_tok` `its` 0.044.
Partition coupling's worst cell across all three policies is 0.025, and for `G_bp` it is 0.000
everywhere.

Each cell has 160 trials, so the granularity is 0.00625 and 0.069 is 11 of 160 — small but not noise
at the 0.01 level. The reading is that a threshold calibrated on generated sequences is not valid on
natural genomic DNA at a 1% target, and that the two baselines are more exposed to this than
partition coupling at short lengths. This is a limitation of calibration transfer, it was not
preregistered, and it is reported as an observation rather than as a tested hypothesis.

### Boundary on this result

Clean sequences only. Nothing here bears on how the three methods degrade under substitution,
indels, cropping, or adaptive removal, and the per-token signal ordering must not be read as a
robustness ordering. Measured under a published non-secret fixture key, so it is a power measurement
and not a security claim.

## Evidence boundary

No number moves into `evidence/measurements.yaml` without explicit evidence-admission review.
