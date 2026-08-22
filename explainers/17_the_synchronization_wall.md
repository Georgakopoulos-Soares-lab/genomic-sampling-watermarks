# 17 — The synchronization wall

## The edit that breaks everything

Substitutions were survivable: one base in five could change and the mark still came through. Crops
were survivable too, as long as the verifier's declared search reached far enough.

Insertions and deletions are different, and the difference is structural rather than a matter of
degree. Change a base and one 6-mer is damaged. *Delete* a base and every base after it slides one
position left, so every token after the deletion is cut at the wrong place. One edit, and the entire
remainder of the sequence is off the grid.

This is the failure mode that decides whether the whole construction is practical, so it got a
prediction written down in advance — and the prediction turned out to be wrong in an interesting way.

## The prediction, and why it was wrong

The reasoning was: a single read has a single alignment, so a read can recover the tokens *before* the
first indel and nothing else. With `L1` aligned tokens out of `n` read, and the statistic diluted by
`√n`:

```text
z ≈ 0.98 × L1 / √n
```

That predicted detection of about 0.68 at a per-base indel rate of 0.001 on 1,536 bases. Measured:
**1.000**. Not a small miss.

The error is worth understanding because it reveals something the construction gets for free. Delete
`k` bases before a token and that token's content has moved left by `k`. A verifier reading at phase
`k mod 6`, starting at key-stream position `⌈k/6⌉`, lands *exactly* back on the original grid. The
declared search already tries 6 phases and 8 offsets. So it already covers every drift up to about 47
bases.

Concretely: one deletion does not leave the detector holding only the prefix. It leaves the prefix
recoverable at phase 0 / offset 0, **and the entire remainder recoverable at phase 5 / offset 1**, and
the detector takes whichever is bigger. The phase-and-offset search performs resynchronization without
a single line of code written for that purpose.

The data says so directly. Fraction of successful detections that used the original phase-0,
offset-0 alignment, at 1,536 bases:

| Indel rate | 0 | 0.0005 | 0.002 | 0.005 |
|---|---:|---:|---:|---:|
| Fraction at the original alignment | 1.00 | 0.60–0.75 | 0.17–0.33 | 0.03–0.19 |

With no edits, every detection is at the origin, as it must be. By a rate of 0.005 almost none are:
the detector is overwhelmingly recovering segments *after* indels, at phases and offsets spread across
its declared search. The table stops at 0.005 on purpose — by 0.02 only a handful of the 40 trials in
a cell are detected at all, so the fraction is computed over too few trials to read.

So the corrected model is not "first segment" but **largest reachable aligned segment**, and the
binding constraint is not *finding* the alignment — it is that the statistic is computed over the whole
read, so a 200-base aligned run inside a 1,536-base window is drowned by the surrounding noise.

## The wall

Largest per-base indel rate at which every sequence is still detected:

| | 384 bases | 768 bases | 1,536 bases |
|---|---:|---:|---:|
| deletions | 0.0005–0.001 | 0.001–0.002 | 0.001–0.002 |
| insertions | 0–0.0005 | 0.001–0.002 | 0.001–0.002 |

Compare with substitutions on the identical corpus, detector, and search: 0.05 to 0.20. The indel
tolerance is **50 to 150 times lower**.

That is the headline, and it is a negative result stated as such. This construction, with this
detector, is synchronization-limited. Insertions and deletions are the binding constraint by two
orders of magnitude, and nothing about the substitution result softens that.

Insertions and deletions behave the same as each other, which is the mechanism's own prediction
holding: the channel does not care which one happened, only that everything afterwards moved.

## Why this is a wall and not a cliff edge

The distinction matters for what comes next. If the detector could not *find* the right alignment,
the problem would be search, and searching harder costs multiplicity — which E6 already showed is
expensive but affordable.

But the detector *does* find the right alignment; it just scores it against too much noise. That is a
dilution problem, and dilution has an obvious fix: score a **window** instead of the whole read. A
window of `W` tokens sitting inside an aligned segment gets `z ≈ 0.98 √W` with no dilution at all —
about 5.5 for a 32-token window, 7.8 for 64. The signal is demonstrably there.

The catch is the null. Sliding a window over every start position, at every drift, on both strands, at
all six phases, means thousands of hypotheses instead of 96, and the maximum of thousands of
near-noise statistics is bigger than the maximum of 96.

## The window works, and then it stops working

It was run. The windowed search scores 7,862 hypotheses per trial against 96, and on the identical
edited sequences:

| Indel rate | Windowed | Unwindowed |
|---:|---:|---:|
| 0.005 | 1.000 | 0.65–0.93 |
| 0.010 | 0.925–1.000 | 0.10–0.48 |
| 0.020 | 0.525–0.800 | 0.05–0.15 |
| 0.050 | 0.025–0.100 | 0.00–0.03 |

The wall moves from about 0.002 to about 0.01 — five- to tenfold — and the price is a threshold higher
by 0.3 to 1.2 in `z`, mostly around 0.6. Paid at every rate, including zero, which is why the windowed
search is not free: with no edits both find everything, but the windowed one has less margin.

Then it stops. At 0.02 it is marginal, at 0.05 it fails, and no window size fixes that. The reason is
the run-length arithmetic: clearing a multiple-testing threshold needs `W ≥ (τ/0.98)²` tokens, about
130 to 190 consecutive intact bases, and the expected longest intact run in 1,536 bases falls below
that between rates 0.02 and 0.05. The second wall is information-theoretic, not a search failure.

Getting past it means changing the *construction* — shorter tokens, or a synchronization code — not
the detector. That is a different project, and the rule here has always been that coding work starts
only after the edit channel is measured. It now is.

## A second flaw, found the same way

The first windowed run declared drift from 0 to 15, and its insertion arm was invalid. Deletions move
content left and need positive drift; insertions move it right and need *negative* drift. A
non-negative range cannot reach a post-insertion segment at all once the insertions exceed what a
phase shift absorbs.

What gave it away was in the run's own output: across every rate and policy, deletion detections used
drifts 0 through 14, while insertion detections used only drift 0. A search dimension that never once
leaves its origin on one channel and ranges over half its span on the other is not measuring the
channel — it cannot reach. The shape was corrected to a signed range, both channels re-run, and the
insertion and deletion curves now agree, which is what the mechanism demands.

## Two things not to take from this

- **Not a claim about real DNA.** A uniform independent per-base indel process is a statistical
  channel. It is not a model of sequencing error, assembly error, or synthesis error, and it says
  nothing about how a real sequence degrades in a real pipeline.
- **Not a claim about an adversary.** These indels fall at random. Someone who understands the
  construction would place a small number of them deliberately, and that is a different and harder
  problem than a random channel at a given rate.

Return to the [explainer index](README.md).
