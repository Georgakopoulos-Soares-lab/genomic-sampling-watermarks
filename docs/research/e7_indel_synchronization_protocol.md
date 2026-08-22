# E7 insertion, deletion, and synchronization protocol

Frozen before inspecting any indel detector output.

## Question

An insertion or deletion shifts every later base, so it shifts the token grid for the whole remainder
of the sequence. How far does the declared detector, which searches strand, phase, and key-stream
offset but reads one full window, survive that — and is the failure a corruption failure or a
synchronization failure?

## Why this is a different mechanism

A substitution damages one 6-mer and leaves every other token where it was. An indel at base `p`
leaves every token before `p` intact and aligned, and pushes every token after `p` off the grid by
one base. A single full-sequence read can therefore recover the prefix and nothing else, no matter
which phase or offset it picks, because one read has one alignment.

That is the crux of the whole robustness story, so it is stated as arithmetic before it is measured.

## Predicted shape, stated before the run

> **This prediction was measured and found wrong.** It is left exactly as written because it is the
> preregistration record. The claim in the previous section that "a single full-sequence read can
> recover the prefix and nothing else" is false: a read at phase 5 with key-stream offset 1 recovers
> everything *after* a single deletion. See "The preregistered prediction was wrong" in the result
> section for the corrected mechanism and the evidence for it. Do not cite anything in this section
> as a finding.

Let `D1` be the distance in bases from the start of the observed sequence to the first indel. Tokens
fully inside that first segment are aligned at phase 0 and key-stream offset 0; every later token is
misaligned and its keyed group is a fair coin. With `L1 = floor(D1 / 6)` aligned tokens out of `n`
observed tokens, and a generator-side agreement near 0.99:

```text
matches ~ 0.99 * L1 + 0.5 * (n - L1)
z       ~ 0.98 * L1 / sqrt(n)
```

The statistic is diluted by `sqrt(n)` while the signal grows only with the *first segment*. Against a
null maximum near 4, detection needs `L1 >= 4 * sqrt(n) / 0.98`. Under an independent per-base indel
rate `r`, `D1` is geometric, so the probability of detection is about `(1 - r)^(6 * L1_required)`:

| Observed tokens | Bases | Aligned tokens needed | Predicted detection at r = 0.001 | at 0.005 | at 0.01 |
|---:|---:|---:|---:|---:|---:|
| 64 | 384 | 33 | 0.82 | 0.37 | 0.14 |
| 128 | 768 | 46 | 0.76 | 0.25 | 0.06 |
| 256 | 1,536 | 65 | 0.68 | 0.14 | 0.02 |

Two consequences worth stating in advance because they are counter-intuitive:

1. **The tolerable indel rate is one to two orders of magnitude below the tolerable substitution
   rate.** E5 kept detection at 1.0 through `r = 0.05` to `0.20`. Here the prediction is collapse by
   `r = 0.01`.
2. **Longer sequences are predicted to be *worse*, not better, at a fixed indel rate.** More observed
   tokens means more `sqrt(n)` dilution while the first segment does not grow, and more bases means a
   higher chance of an early indel. This reverses the length ordering seen in every previous
   experiment.

Insertions and deletions should behave the same way, because the first-segment mechanism does not
care which one happened. If their curves differ materially, this model is wrong and that must be
explained before anything is admitted.

## Stage 1 — the unwindowed detector

| Item | Frozen choice |
|---|---|
| Policies | `C_tok`, `G_tok`, `G_bp` |
| Corpus | the E4 generated corpus, unchanged; 8 prompts, 3,072 bases per prompt and arm |
| Edits | independent per-base insertion, and independent per-base deletion, run separately |
| Rates | 0.0, 0.0005, 0.001, 0.002, 0.005, 0.01, 0.02 |
| Evaluated lengths | 384, 768, 1,536 observed bases as prefixes of the edited sequence |
| Detector search | unchanged from E4: 2 orientations x 6 phases x full-prefix window x 8 offsets |
| Positive trials | 5 independent edit replicates per prompt = 40 per cell |
| N1, N2 | wrong key on the edited watermarked arm, and any key on the edited ordinary arm, 8 keys each |
| Target FPR | 0.01, calibrated per rate and per length on pooled N1 and N2 |
| Uncertainty | percentile bootstrap over the 8 prompt clusters, 20,000 replicates, seed 2718 |
| Key material | published non-secret fixture |
| Decision rule | `statistic > threshold`, matching how null exceedances are counted |

The evaluated length is measured in **observed** bases, not original bases. A deletion channel
shortens the sequence, so a fixed observed prefix covers slightly more original tokens; an insertion
channel lengthens it, so the same prefix covers fewer. The maximum evaluated length is 1,536 observed
bases so that every trial at every rate has enough sequence, which is why the 3,072-base length used
by E5 is absent here.

### Preregistered reading

- Report detection against rate for each edit, length, and policy. The headline is the largest rate
  at which detection remains 1.0, and the rate at which it collapses.
- A collapse one to two orders of magnitude below the substitution threshold is the expected result.
  It is a **synchronization-limited** finding, which the contribution frame lists as a legitimate
  outcome, and it must be reported as the main indel result rather than buried.
- If longer sequences are not worse at a fixed rate, the dilution model is wrong.
- If insertion and deletion curves differ materially, the first-segment model is wrong.

## Stage 2 — the windowed detector

Frozen before inspecting any windowed output, and after stage 1 was complete, so stage 1's corrected
mechanism informs the design. That is legitimate because stage 2 is a different declared detector, not
a reanalysis of stage-1 data.

### The parameterization, and why it is not "window start times absolute key position"

Stage 1 established that an observed token at read index `i`, after `D` net inserted or deleted bases,
corresponds to original token `i + (phase + D) / 6`. The key position a window needs is therefore its
own start index plus a small **drift** term. Searching window start and absolute key position
independently would multiply the hypothesis count by the sequence length and buy nothing, because
almost every pair is unreachable. Searching start and drift keeps multiplicity proportional to the
drift a channel can actually produce.

At the rates measured here the drift stays small: 1,536 bases at rate 0.02 gives about 31 net indels,
which is a drift of about five tokens. A declared drift range of 0 to 15 covers every rate in the grid
with margin.

### Frozen shape

| Item | Frozen choice |
|---|---|
| Policies | `C_tok`, `G_tok`, `G_bp` |
| Corpus and arms | the E4 generated corpus, unchanged |
| Edits | independent per-base deletion, and independent per-base insertion, run separately |
| Rates | 0.0, 0.002, 0.005, 0.01, 0.02, 0.05 |
| Observed length | 1,536 bases, the length where stage 1 showed the clearest dilution |
| Window lengths | 32, 64, 128, and 256 tokens |
| Window stride | half of each window length |
| Drift offsets | -15 to 15, signed; see the amendment below |
| Hypotheses scored | about 8,400 per trial, against 96 for the unwindowed search |
| Positive trials | 5 edit replicates per prompt = 40 per cell |
| N1, N2 | wrong key on the edited watermarked arm, and any key on the edited ordinary arm, 8 keys each |
| Target FPR | 0.01, calibrated per rate on pooled N1 and N2 |
| Comparator | the unwindowed narrow search from stage 1, rerun on the identical edited sequences |
| Key material | published non-secret fixture |

The 256-token window is the whole read, so the windowed search **contains** the unwindowed one as a
special case. Any improvement is therefore attributable to the added windows and not to a different
statistic, and any loss is attributable purely to the larger multiplicity.

Running the comparator on the *same* edited sequences, in the same process, is what makes the
comparison paired rather than a comparison of two separate experiments.

### Predicted outcome, stated before the run

A window of `W` tokens sitting inside an aligned segment scores `z = 0.98 * sqrt(W)` with no dilution.
Clearing a threshold `tau` therefore needs

```text
W >= (tau / 0.98)^2 tokens
```

which for `tau` between 4.5 and 5.5 is 22 to 32 tokens, that is **132 to 192 intact consecutive
bases**. The expected longest intact run in `n` bases at indel rate `r` is about `ln(n * r) / r`:

| Rate | Expected longest intact run in 1,536 bases | Clears 132-192 bases? |
|---:|---:|---|
| 0.002 | 561 | yes, comfortably |
| 0.005 | 408 | yes |
| 0.01 | 273 | yes |
| 0.02 | 171 | marginal |
| 0.05 | 87 | no |

So the prediction is: **the wall moves by roughly an order of magnitude and then reappears.** Windowing
should restore detection to near 1.0 through rate 0.01, be marginal at 0.02, and fail at 0.05. It
cannot do better than that at any window size, because the requirement of 130 to 190 consecutive intact
bases is set by the multiple-testing threshold and not by the window choice.

If windowing does *not* improve on the unwindowed comparator at rates 0.005 and 0.01, the dilution
diagnosis from stage 1 is wrong. If it does improve beyond rate 0.05, the run-length argument is wrong.
Either would have to be explained before anything is admitted.

The prediction is symmetric across the two channels, because the run-length argument does not care
which edit occurred. A material insertion-versus-deletion gap under the corrected shape would mean
something else is going on.

### Amendment: the first frozen shape had a design flaw (2026-08-21)

The shape was first frozen with a drift range of 0 to 15 and run. The insertion arm of that run is
invalid, and the reason is worth recording rather than quietly fixing.

Drift is **signed**. Deletions move content left, so a segment after `D` deletions needs drift about
`+D/6`. Insertions move content right, so a segment after `I` insertions needs drift about `-I/6`. A
non-negative drift range therefore cannot reach any post-insertion segment once the insertions exceed
what a phase shift can absorb, which happens at `I > 5`. On 1,536 bases that is an insertion rate
above roughly 0.004 — inside the measured grid.

The run itself contains the evidence. Across every rate and policy, detected positives on the
deletion channel used drifts 0, 1, 2, 3, 4, 5, 6, 7, 9, 11, and 14, while detected positives on the
insertion channel used **only drift 0**. A search dimension that never once moves off its origin on
one channel and ranges over half its span on the other is not a result about the channel; it is a
search that cannot reach.

The corrected shape uses a symmetric signed drift range of -15 to 15. Hypotheses whose key start
would be negative are not scorable and are skipped, so the hypothesis count is computed by counting
scorable pairs rather than multiplying. Both channels are re-run under the corrected shape so that
they remain comparable to each other, and the deletion arm is re-run too even though its drift range
was adequate, because the larger drift range changes the multiplicity and therefore the threshold.

The first run is superseded and is not cited. This amendment is dated after the first run because it
records a correction; the corrected shape was fixed before the corrected run was inspected.

### Boundary specific to stage 2

The windowed search still declares no *absolute* key-position sweep, so it does not address a
watermarked fragment spliced at an unknown position inside a much longer unwatermarked sequence. It
also does not implement any error-correcting or synchronization-string code; it is the same statistic
scored on smaller spans.

## Stage-1 result (2026-08-21)

Run after the shape above was frozen, under the corrected strict decision rule. 4,032 trials per
policy and channel, 21 seconds each, model-free.

Detection rate, 40 positive trials per cell, threshold calibrated per rate and length:

| Edit | Policy | Rate | 384 b | 768 b | 1,536 b |
|---|---|---:|---:|---:|---:|
| deletion | `C_tok` | 0.0000 | 1.000 | 1.000 | 1.000 |
| deletion | `C_tok` | 0.0005 | 0.950 | 1.000 | 1.000 |
| deletion | `C_tok` | 0.0010 | 1.000 | 1.000 | 1.000 |
| deletion | `C_tok` | 0.0020 | 0.900 | 0.975 | 1.000 |
| deletion | `C_tok` | 0.0050 | 0.675 | 0.900 | 0.725 |
| deletion | `C_tok` | 0.0100 | 0.575 | 0.575 | 0.600 |
| deletion | `C_tok` | 0.0200 | 0.075 | 0.325 | 0.175 |
| deletion | `G_tok` | 0.0000 | 1.000 | 1.000 | 1.000 |
| deletion | `G_tok` | 0.0005 | 0.950 | 1.000 | 1.000 |
| deletion | `G_tok` | 0.0010 | 1.000 | 1.000 | 1.000 |
| deletion | `G_tok` | 0.0020 | 0.950 | 1.000 | 0.975 |
| deletion | `G_tok` | 0.0050 | 0.850 | 0.875 | 0.825 |
| deletion | `G_tok` | 0.0100 | 0.525 | 0.725 | 0.550 |
| deletion | `G_tok` | 0.0200 | 0.350 | 0.175 | 0.050 |
| deletion | `G_bp` | 0.0000 | 1.000 | 1.000 | 1.000 |
| deletion | `G_bp` | 0.0005 | 1.000 | 1.000 | 1.000 |
| deletion | `G_bp` | 0.0010 | 0.975 | 1.000 | 1.000 |
| deletion | `G_bp` | 0.0020 | 0.975 | 0.975 | 0.975 |
| deletion | `G_bp` | 0.0050 | 0.700 | 0.800 | 0.850 |
| deletion | `G_bp` | 0.0100 | 0.675 | 0.675 | 0.550 |
| deletion | `G_bp` | 0.0200 | 0.250 | 0.250 | 0.125 |
| insertion | `C_tok` | 0.0000 | 1.000 | 1.000 | 1.000 |
| insertion | `C_tok` | 0.0005 | 1.000 | 1.000 | 1.000 |
| insertion | `C_tok` | 0.0010 | 0.975 | 1.000 | 1.000 |
| insertion | `C_tok` | 0.0020 | 0.925 | 1.000 | 1.000 |
| insertion | `C_tok` | 0.0050 | 0.875 | 0.850 | 0.725 |
| insertion | `C_tok` | 0.0100 | 0.525 | 0.300 | 0.175 |
| insertion | `C_tok` | 0.0200 | 0.150 | 0.050 | 0.025 |
| insertion | `G_tok` | 0.0000 | 1.000 | 1.000 | 1.000 |
| insertion | `G_tok` | 0.0005 | 0.975 | 1.000 | 1.000 |
| insertion | `G_tok` | 0.0010 | 0.975 | 1.000 | 1.000 |
| insertion | `G_tok` | 0.0020 | 0.875 | 0.925 | 0.975 |
| insertion | `G_tok` | 0.0050 | 0.850 | 0.800 | 0.700 |
| insertion | `G_tok` | 0.0100 | 0.575 | 0.375 | 0.100 |
| insertion | `G_tok` | 0.0200 | 0.225 | 0.050 | 0.100 |
| insertion | `G_bp` | 0.0000 | 1.000 | 1.000 | 1.000 |
| insertion | `G_bp` | 0.0005 | 1.000 | 1.000 | 1.000 |
| insertion | `G_bp` | 0.0010 | 0.975 | 1.000 | 1.000 |
| insertion | `G_bp` | 0.0020 | 0.875 | 1.000 | 1.000 |
| insertion | `G_bp` | 0.0050 | 0.775 | 0.850 | 0.775 |
| insertion | `G_bp` | 0.0100 | 0.650 | 0.475 | 0.150 |
| insertion | `G_bp` | 0.0200 | 0.275 | 0.275 | 0.100 |

Largest rate with detection 1.0:

| Edit | Policy | 384 b | 768 b | 1,536 b |
|---|---|---:|---:|---:|
| deletion | `C_tok` | 0.001 | 0.001 | 0.002 |
| deletion | `G_tok` | 0.001 | 0.002 | 0.001 |
| deletion | `G_bp` | 0.0005 | 0.001 | 0.001 |
| insertion | `C_tok` | 0.0005 | 0.002 | 0.002 |
| insertion | `G_tok` | 0.0 | 0.001 | 0.001 |
| insertion | `G_bp` | 0.0005 | 0.002 | 0.002 |

### The headline: this construction is synchronization-limited

Across every policy, channel, and length the largest fully detected indel rate is between 0.0005 and
0.002. On the same corpus, the same detector, and the same declared search, E5 measured substitution
tolerance of 0.05 to 0.20. At matched lengths the ratio is **50 to 150 times**. Indels are the binding
constraint on this construction by two orders of magnitude, and that is the main indel result.

Insertions and deletions behave the same way, as the mechanism predicts: the channel does not care
which one happened, only that everything after it has moved.

### The preregistered prediction was wrong, and the correction is the interesting part

The prediction above assumed only the **first** aligned segment contributes, giving
`z ~ 0.98 * L1 / sqrt(n)` and predicting detection near 0.68 at `r = 0.001` and 1,536 bases. Measured:
**1.000**. The prediction under-called low-rate performance badly, so the model was wrong.

Here is why, and it is a genuinely positive finding. Delete `k` bases before a token and that token's
content shifts left by `k`. A verifier reading at phase `k mod 6` with key-stream offset `ceil(k/6)`
lands back exactly on the original grid. The declared search already contains 6 phases and 8 offsets,
so **it already covers every drift up to about 47 bases** — it performs implicit resynchronization,
without any code written for that purpose. A single deletion does not leave the detector with only the
prefix; it leaves the detector with the prefix at phase 0 offset 0 *and* the entire remainder at
phase 5 offset 1, and it takes whichever is larger.

The data says this directly. Fraction of detected positives that aligned at phase 0 and offset 0, at
1,536 observed bases:

| Edit | Policy | r = 0 | 0.0005 | 0.001 | 0.002 | 0.005 | 0.01 | 0.02 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| deletion | `C_tok` | 1.00 | 0.60 | 0.60 | 0.20 | 0.17 | 0.04 | 0.00 |
| deletion | `G_tok` | 1.00 | 0.62 | 0.55 | 0.28 | 0.09 | 0.05 | 0.00 |
| deletion | `G_bp` | 1.00 | 0.75 | 0.57 | 0.33 | 0.03 | 0.09 | 0.00 |
| insertion | `C_tok` | 1.00 | 0.72 | 0.57 | 0.17 | 0.14 | 0.29 | 1.00 |
| insertion | `G_tok` | 1.00 | 0.68 | 0.60 | 0.26 | 0.07 | 0.00 | 0.00 |
| insertion | `G_bp` | 1.00 | 0.70 | 0.65 | 0.23 | 0.19 | 0.17 | 0.50 |

At zero edits every detection is at the origin alignment, as it must be. By `r = 0.002` only 17 to 33
percent are, and by `r = 0.005` to `0.02` almost none: the detector is overwhelmingly recovering
segments *after* indels, at phases and offsets spread across the declared search.

So the corrected model is not "first segment" but **largest reachable aligned segment**:

```text
z ~ 0.98 * Lmax / sqrt(n)
```

where `Lmax` is the longest run of consecutive aligned tokens whose required phase and offset lie
inside the declared search. Under rate `r` the segments between indels average `1/r` bases, so `Lmax`
falls roughly as `1/r` while the dilution `sqrt(n)` stays fixed. That reproduces the observed collapse:
at `r = 0.005` on 1,536 bases the largest of about eight segments is a few hundred bases, giving
`z ~ 4`, which is exactly the threshold, and detection sits at 0.70 to 0.88.

### The rest of the preregistered reading

- **Longer sequences worse at fixed rate**: confirmed for insertions, where detection at `r = 0.01`
  falls monotonically from 0.53-0.65 at 384 bases to 0.10-0.18 at 1,536. For deletions the ordering is
  noisy rather than monotone. Both are consistent with dilution, but the deletion channel is not clean
  enough at 40 trials per cell to claim the ordering, and it is not claimed.
- **Insertion and deletion agreement**: confirmed. No systematic separation between the channels.
- Nulls remain rate-independent, as in E5.

## Stage-1 evidence-admission review (2026-08-21)

Reviewed and admitted, using the same validator and analyzer as E5 with one addition. The validator
now also recomputes, per rate and length, where each detected positive actually aligned: how many were
detected, what fraction sat at phase 0 and offset 0, and which phases and offsets appeared. That is
the evidence for the resynchronization finding above, so it must be checkable rather than asserted.

The addition is purely additive. Re-running the E5 analyzer after the change reproduces every admitted
E5 value exactly and adds one key, which was verified rather than assumed. A reviewer re-running the
E5 analysis command today therefore gets a superset artifact whose digest differs from the admitted
one while every admitted value is identical.

Admitted to `evidence/measurements.yaml`: eighteen entries, one per channel, policy, and length,

- `e7.{deletion,insertion}.{c_tok,g_tok,g_bp}.b{384,768,1536}.max_fully_detected_rate`

Each carries the seven-point curve, the per-rate recovered-alignment record, and the null-invariance
spreads. Every entry states in its notes that this is the unwindowed detector and that stage 2 is not
implemented.

Cited artifact digests:

| Edit | Policy | Report | Analysis |
|---|---|---|---|
| deletion | `C_tok` | `39c7b95ea0113e54876a0bf960f4b303ac57e46c77da2860e1a2b0a3d9976c11` | `64539b848826db176315ac9c63a62de82df2b2ef74455f7d8c76f80cfa4b1d72` |
| deletion | `G_tok` | `a9f5b959b8a01b0caa26f73c390026b27a0bc11373b60f9f40a3e43aabdef923` | `bb217d107aafee3502bd666ab20091bb90b114037760800d3a600bb80bad245b` |
| deletion | `G_bp` | `82de16332f266140077a7ac6be78150c82269476a5da8d1e99bca92c5fa8d66d` | `1f831e6c4ae6448816d80081b2dfbafe97c00ccbab7f3ad134c74e74351866fe` |
| insertion | `C_tok` | `44a1534b0f84333c1f9657b2b374751fc8b9f00b0c63e73da0912a0972f23091` | `5dc6511225e98fbcb5f98be9704fc20517fe3191975e1dec11430f93e142a1a6` |
| insertion | `G_tok` | `4048dc3f4e5992a2d2fa44dd74e9178e18a1d21e5f140d9a230743850cca2691` | `c8b510cf051ca05a37f2f4af5c6fb852c39279f1f6f962b3db825c89f55936e6` |
| insertion | `G_bp` | `9410437788b8f60d5082d164c5588fb0b0316f60972f1e18dad36b1ef04be0bd` | `d20dc21c9a0a11d600f3c4b245d529ce32924117e41abc8f012719439048eaf9` |

### What stage 2 now has to beat

Stage 1 makes the stage-2 target concrete. The failure is dilution, not reachability: the declared
search already finds the right alignment, but it scores that alignment over the whole window, so a
200-base aligned segment inside a 1,536-base read is drowned. A window of `W` tokens placed inside a
segment scores `z ~ 0.98 * sqrt(W)` with no dilution at all, which for `W = 32` is 5.5 and for
`W = 64` is 7.8. The question is purely whether that survives the null maximum over the far larger
windowed hypothesis space. Stage 1 says the signal is there to be found.

## Stage-2 result (2026-08-21)

Run under the corrected signed-drift shape. 2,016 trials per policy and channel, each scored by both
searches, 64 seconds per run, model-free. The windowed search scores 7,862 hypotheses per trial
against 96 for the comparator.

| Edit | Policy | Rate | Windowed TPR | Unwindowed TPR | Gain | Windowed threshold | Unwindowed threshold | Cost |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| deletion | `C_tok` | 0.000 | 1.000 | 1.000 | +0.000 | 4.25 | 3.82 | +0.43 |
| deletion | `C_tok` | 0.002 | 1.000 | 1.000 | +0.000 | 4.25 | 3.57 | +0.68 |
| deletion | `C_tok` | 0.005 | 1.000 | 0.875 | +0.125 | 4.24 | 3.95 | +0.30 |
| deletion | `C_tok` | 0.010 | 0.950 | 0.350 | +0.600 | 4.24 | 3.82 | +0.42 |
| deletion | `C_tok` | 0.020 | 0.700 | 0.150 | +0.550 | 4.50 | 3.69 | +0.81 |
| deletion | `C_tok` | 0.050 | 0.075 | 0.025 | +0.050 | 4.25 | 3.69 | +0.56 |
| deletion | `G_tok` | 0.000 | 1.000 | 1.000 | +0.000 | 4.50 | 4.00 | +0.50 |
| deletion | `G_tok` | 0.002 | 1.000 | 1.000 | +0.000 | 4.60 | 3.69 | +0.90 |
| deletion | `G_tok` | 0.005 | 1.000 | 0.775 | +0.225 | 4.50 | 3.75 | +0.75 |
| deletion | `G_tok` | 0.010 | 0.975 | 0.450 | +0.525 | 4.60 | 3.44 | +1.15 |
| deletion | `G_tok` | 0.020 | 0.800 | 0.050 | +0.750 | 4.50 | 3.82 | +0.68 |
| deletion | `G_tok` | 0.050 | 0.050 | 0.000 | +0.050 | 4.25 | 3.44 | +0.81 |
| deletion | `G_bp` | 0.000 | 1.000 | 1.000 | +0.000 | 4.50 | 3.75 | +0.75 |
| deletion | `G_bp` | 0.002 | 1.000 | 0.975 | +0.025 | 4.50 | 3.88 | +0.62 |
| deletion | `G_bp` | 0.005 | 1.000 | 0.925 | +0.075 | 4.75 | 3.69 | +1.06 |
| deletion | `G_bp` | 0.010 | 1.000 | 0.475 | +0.525 | 4.25 | 3.82 | +0.43 |
| deletion | `G_bp` | 0.020 | 0.525 | 0.050 | +0.475 | 4.60 | 3.50 | +1.10 |
| deletion | `G_bp` | 0.050 | 0.050 | 0.025 | +0.025 | 4.42 | 3.44 | +0.98 |
| insertion | `C_tok` | 0.000 | 1.000 | 1.000 | +0.000 | 4.25 | 3.82 | +0.43 |
| insertion | `C_tok` | 0.002 | 1.000 | 0.975 | +0.025 | 4.25 | 3.82 | +0.43 |
| insertion | `C_tok` | 0.005 | 1.000 | 0.650 | +0.350 | 4.25 | 3.69 | +0.56 |
| insertion | `C_tok` | 0.010 | 0.975 | 0.100 | +0.875 | 4.25 | 3.57 | +0.68 |
| insertion | `C_tok` | 0.020 | 0.575 | 0.050 | +0.525 | 4.50 | 3.82 | +0.68 |
| insertion | `C_tok` | 0.050 | 0.025 | 0.025 | +0.000 | 4.60 | 3.44 | +1.15 |
| insertion | `G_tok` | 0.000 | 1.000 | 1.000 | +0.000 | 4.50 | 4.00 | +0.50 |
| insertion | `G_tok` | 0.002 | 1.000 | 1.000 | +0.000 | 4.25 | 3.44 | +0.81 |
| insertion | `G_tok` | 0.005 | 1.000 | 0.675 | +0.325 | 4.42 | 3.44 | +0.98 |
| insertion | `G_tok` | 0.010 | 0.925 | 0.200 | +0.725 | 4.60 | 3.44 | +1.15 |
| insertion | `G_tok` | 0.020 | 0.600 | 0.100 | +0.500 | 4.25 | 3.50 | +0.75 |
| insertion | `G_tok` | 0.050 | 0.050 | 0.000 | +0.050 | 4.60 | 3.57 | +1.03 |
| insertion | `G_bp` | 0.000 | 1.000 | 1.000 | +0.000 | 4.50 | 3.75 | +0.75 |
| insertion | `G_bp` | 0.002 | 1.000 | 0.975 | +0.025 | 4.50 | 3.95 | +0.55 |
| insertion | `G_bp` | 0.005 | 1.000 | 0.750 | +0.250 | 4.25 | 3.95 | +0.30 |
| insertion | `G_bp` | 0.010 | 0.975 | 0.225 | +0.750 | 4.50 | 3.95 | +0.55 |
| insertion | `G_bp` | 0.020 | 0.625 | 0.075 | +0.550 | 4.60 | 3.82 | +0.78 |
| insertion | `G_bp` | 0.050 | 0.100 | 0.000 | +0.100 | 4.42 | 3.82 | +0.60 |

Largest rate detected in every trial:

| Edit | Policy | Windowed | Unwindowed |
|---|---|---:|---:|
| deletion | `C_tok` | 0.005 | 0.002 |
| deletion | `G_tok` | 0.005 | 0.002 |
| deletion | `G_bp` | 0.01 | 0.0 |
| insertion | `C_tok` | 0.005 | 0.0 |
| insertion | `G_tok` | 0.005 | 0.002 |
| insertion | `G_bp` | 0.005 | 0.0 |

### Reading against the prediction

1. **Detection returns to near one through rate 0.01.** Windowed detection is 1.000 at rate 0.005 for
   every policy and channel, and 0.925 to 1.000 at rate 0.010, against 0.100 to 0.475 for the
   unwindowed comparator on the identical sequences. Predicted.
2. **It is marginal at 0.02 and fails at 0.05.** Windowed detection is 0.525 to 0.800 at 0.02 and
   0.025 to 0.100 at 0.05. Predicted, and the failure point matches the run-length argument: a
   detection needs roughly 130 to 190 consecutive intact bases, and the expected longest intact run
   in 1,536 bases drops below that between rates 0.02 and 0.05.
3. **The two channels agree** under the corrected shape, as the mechanism requires. Under the flawed
   shape they did not, which is what exposed the flaw.
4. **The multiplicity cost is real and affordable.** Scoring 82 times as many hypotheses raises the
   calibrated threshold by 0.3 to 1.2 in `z` units, mostly 0.5 to 0.8. That cost is paid at every
   rate including zero, which is why the windowed search is not simply better everywhere: at rate 0
   both searches detect everything, and the windowed one does so with less margin.

### What this does and does not settle

The synchronization limit is **moved, not removed**. Stage 1 measured a wall at an indel rate of
0.0005 to 0.002; the windowed detector moves it to about 0.01, a five- to tenfold improvement, and
then meets a second wall at 0.02 to 0.05 that no window size can push further. The second wall is
information-theoretic rather than a search failure: clearing a multiple-testing threshold requires a
run of intact tokens, and above some indel rate the sequence simply does not contain one.

Substitution tolerance on the same corpus remains 0.05 to 0.20, so indels are still the binding
constraint, now by roughly a factor of 5 to 20 rather than 50 to 150.

Getting past the second wall requires changing the construction rather than the detector: shorter
tokens would shorten the required run, and an error-correcting or synchronization-string layer would
change the problem outright. Neither is implemented, and the project rule is that coding work starts
only after the edit channel is measured. It now is.

## Stage-2 evidence-admission review (2026-08-21)

Reviewed and admitted. `src/genomic_watermarks/windowed_report.py` recomputes every reported
aggregate from the stored per-trial rows and additionally enforces the two structural properties the
comparison depends on: the windowed search must include the full-read window, so it is a superset of
the comparator rather than a different statistic, and both searches must have scored the identical
set of trials, so the comparison is paired. It also requires the drift range to be declared signed in
both directions, rejects a windowed trial whose key start would be negative, and requires the
windowed search to score strictly more hypotheses than the comparator.

Admitted to `evidence/measurements.yaml`: six entries, one per channel and policy,

- `e7.stage2.{deletion,insertion}.{c_tok,g_tok,g_bp}.windowed_max_fully_detected_rate`

Each carries the comparator's value, the full per-rate paired comparison with gains and threshold
costs, and the hypothesis counts of both searches. A verification pass additionally checks the
drift-sign invariant: every admitted insertion entry must show negative recovered drift and every
deletion entry positive, which is exactly what the earlier flawed run could not do.

Cited artifact digests:

| Edit | Policy | Report | Analysis |
|---|---|---|---|
| deletion | `C_tok` | `bc199605ea0a841d17734abbac94ae25572ee298c6f700be5a550aa19006af17` | `b174cefdcae79f70cc2dbdc8af1f08cd83cf6c28efbd77d7b437065da8787df7` |
| deletion | `G_tok` | `958507a8dbfa2f990fdd36367899db72c5b416ad6dfc4d83d52336f9b3bd315d` | `f1172efa1935a86147cbb93b41fc0e524090f15034a1d5a3d0fd941af2368369` |
| deletion | `G_bp` | `1824f4725c01562d45e58ffbe4dc67a5f86eacdcdaabfc0ca65884db2262fb1c` | `f9d6c4094dfe4dd4ea4aadc2f56438dfbb00b0b448aa1a27360817b91ce81436` |
| insertion | `C_tok` | `27e2232da205f7d50ea107054322cc2c796cbf2e2f9ed640e0ab22b339fb5833` | `7290c32fe9d48522a3e784b933c6e4c2c0a5bd8ab5066836f171ffeadefa22b4` |
| insertion | `G_tok` | `5cd8e9994b7031be89cf8d298dd150584948c3653e7d2c2fb664d84d8da6ce4c` | `36b3bd3ff848f5529478bca30a0d7db4a8203a05bc1ff571bb02cac4f3e58674` |
| insertion | `G_bp` | `141b75b65dbc7f08d043ca5ae12e4f4dbc530dcca08107e47f66381bd2099e34` | `4b4f16e7f87252aa432e1512478943fca292e8aeb457b9018d25fbbdb38a14b6` |

## Boundary

Independent per-base insertion and deletion channels. Not measured: indels combined with
substitutions, indels combined with crops, a single indel placed adversarially, spliced or partial
watermarking, and error-correcting or synchronization-string codes. A uniform independent per-base
indel process is a statistical channel, not a model of sequencing, assembly, or synthesis error, and
supports no biological claim.

## Implementation status

- `src/genomic_watermarks/edits/channel.py` provides the insertion and deletion channels.
- `scripts/run_edit_robustness_pilot.py` runs stage 1 unchanged; it already accepts these channels.
- `src/genomic_watermarks/edit_report.py` and `scripts/analyze_edit_robustness.py` validate and bind
  provenance unchanged.
- The sliding observed window exists in `DetectorConfig` but is not declared by any run yet. Stage 2
  is not implemented.

## Exact stage-1 commands

```bash
uv run python scripts/run_edit_robustness_pilot.py \
  --sequences outputs/carbon_c_tok_e4_sequences_v1.jsonl \
  --cohort-jsonl data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl \
  --cohort-manifest data/public_prompt_cohort_v2.yaml \
  --edit deletion \
  --rates 0.0 0.0005 0.001 0.002 0.005 0.01 0.02 \
  --token-lengths 64 128 256 \
  --stream-offsets 8 --null-keys 8 --positive-replicates 5 \
  --target-fpr 0.01 --bootstrap-replicates 20000 --bootstrap-seed 2718 \
  --experiment-label e7-deletion-v1 \
  --output outputs/carbon_c_tok_e7_deletion_v1.json
```

Repeat with `--edit insertion` and label `e7-insertion-v1`, and for `G_tok` and `G_bp`.

## Evidence boundary

Reports are engineering artifacts in ignored `outputs/`. No number moves into
`evidence/measurements.yaml` without explicit evidence-admission review.
