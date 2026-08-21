# 16 — How much damage it survives

## The first edit

DNA gets copied, sequenced, assembled, and edited. A provenance mark that only works on a pristine
sequence is not much use. So the next question is how much corruption the watermark tolerates.

Substitutions come first, and not arbitrarily. They are the only edit class that leaves the token
grid alone: base 17 stays at position 17, so a changed base damages the one 6-mer it sits in and
nothing after it. Insertions and deletions shift *every* later position, which is a completely
different failure — a synchronization problem, not a corruption problem. Mixing them would measure
two mechanisms and explain neither.

## Predicting the answer before measuring it

This is worth doing before running anything, because a prediction you write down first is a test of
understanding, and one you write down afterwards is not.

A token survives a per-base substitution rate `r` intact with probability `(1 - r)^6` — six bases,
each independently untouched. If it survives, it keeps its keyed agreement, about 0.99 on these
policies. If it does not, the corrupted 6-mer is effectively a random different token, so its keyed
group is a fair coin and agrees half the time. So:

```text
agreement  q(r) = 0.5 + 0.49 * (1 - r)^6
statistic  z(r, n) = 0.98 * (1 - r)^6 * sqrt(n)
```

The detector's null maximum sits near `z ≈ 4`. Setting `z(r, n) = 4` predicts the breaking point:
around `r = 0.25` for 3,072 bases, around `r = 0.12` for 384 bases. Note the `(1 - r)^6`: because
tokens are six bases wide, the mark decays roughly six times faster than the per-base error rate
would suggest. The 6-mer tokenization is the vulnerability.

## The measurement

Seven rates, four lengths, three policies, 40 watermarked trials per cell, each threshold recalibrated
on nulls that went through the *same* edit process — 4,704 detector runs per policy, 46 seconds each,
no GPU and no model.

Largest rate at which every single sequence is still detected:

| Length | `C_tok` | `G_tok` | `G_bp` |
|---|---:|---:|---:|
| 384 bases | 0.05 | 0.05 | 0.05 |
| 768 bases | 0.10 | 0.10 | 0.10 |
| 1,536 bases | 0.15 | 0.15 | 0.15 |
| 3,072 bases | 0.15 | 0.20 | 0.20 |

At 3,072 bases the detector still finds every sequence after **one base in five** has been changed.
Then it falls off a cliff: at 30% substitution detection drops to 0.05–0.175. At 384 bases the same
cliff arrives between 10% and 15%.

The prediction held. Detection is essentially perfect at `r = 0.20` and collapsed at `r = 0.30` for
3,072 bases; at 384 bases it is partial at `r = 0.10` and gone at `r = 0.15`. No fitting, no
adjusted grid — the channel model just works.

The three policies agree almost exactly, which is what you would expect if the mechanism is the
tokenization and the coupling rather than anything specific to Carbon or GENERator.

## One check that had to be done

Every rate gets its own threshold, calibrated on nulls at that rate. But should the null even depend
on the rate? Argument: under a wrong key, a token's keyed group is a fair coin whether or not its
bases were edited — the key knows nothing about the DNA. So the null distribution should be identical
at every rate.

That is a prediction, so it was measured rather than assumed. Across all seven rates the pooled null
mean moves by 0.06 to 0.15 in `z` units against a mean near 2.5, with no trend. Confirmed. It matters
because it licenses comparing rates to each other at all.

## Reading the noise honestly

Two cells look non-monotone: `C_tok` at 384 bases reports the same 0.075 at 20% and 30%, and `G_tok`
reports 0.000 at 768 bases but 0.050 at 1,536 bases for 30%. Those are not findings. With 40 trials
per cell the resolution is 0.025, and the thresholds are order statistics of 128 null trials. In the
collapsed tail, cells are not distinguishable from each other. Reporting them as a trend would be
inventing structure.

## The accidental 15× speedup

The first version of the detector rebuilt its keyed partition table for every sequence it scored.
But a partition depends on the key, the domain, and the position — *never* on the DNA being examined.
One table per key therefore serves every sequence, every edit rate, and every length.

Fixing that took the clean detection pilot from 826 seconds to 53, and it reproduced every stored
trial byte for byte against the already-admitted result, which is how we know the optimization
changed only speed. It is why a seven-rate sweep costs 46 seconds instead of two hours.

## Still not established

- **Indels.** An insertion or deletion shifts every downstream token's phase. The offset search
  exists for exactly this, but nothing here measures whether it is enough.
- **Crops.** A cropped fragment needs sliding-window search, which this experiment deliberately does
  not declare, and windows need their own calibration.
- **An adversary.** This is a *random* channel. Someone who knows the construction and chooses where
  to edit is a different and harder problem.
- **Biology.** A uniform independent per-base substitution process is a statistical channel. It is
  not a model of mutation, of sequencing error, or of synthesis error, and nothing here says how a
  real sequence degrades.

Return to the [explainer index](README.md).
