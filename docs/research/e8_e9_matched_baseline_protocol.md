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
- The generation runner and the comparison runner are not yet written.

## Evidence boundary

No number moves into `evidence/measurements.yaml` without explicit evidence-admission review.
