# 18 — Measuring our construction against the alternatives

## The comparison we owed

Our watermark is not the only exact-marginal sampling watermark. Two others are already published, and
they were always the ones we would be measured against:

- **Inverse transform** (`its`). Shuffle the 4,096 possible 6-mers into a secret key-dependent order,
  then use one secret number to pick a point on the cumulative distribution and emit whichever token
  the point lands in.
- **Exponential**, sometimes called the Gumbel trick (`exp`). Give *every* candidate 6-mer its own
  secret number, and emit the one that wins a weighted contest between them.

All three preserve the model's distribution exactly. All three can be checked by a verifier holding
only DNA, a key, and public settings. Neither of the other two is our invention; we implemented them
so the comparison could happen on one corpus with one detector, instead of across three papers with
three different setups.

## Three ways this comparison could have been rigged, and what we did about each

This is the part worth reading carefully, because a comparison between watermark constructions is very
easy to bias without meaning to.

**One method could search fewer alignments.** The detector does not know which strand it is reading,
which of six cutting positions is right, or where in the key stream the sequence starts. It tries all
of them and reports the best score. Trying *more* possibilities means more chances for a random high
score, which raises the bar the real signal has to clear. A method that quietly searched fewer
possibilities would get a lower bar and look better for free.

So all three methods reuse the *same* search code, not merely the same settings, and the check that
they searched the identical number of alignments is recomputed from the stored trials rather than read
from a flag. It came out at 96 alignments for every method at every length — except at the very
shortest length, where five of the six cutting positions leave the sequence too short to score at all
and the honest count is 16.

**One method could get an easier bar.** The three scores are on completely different scales, so a
shared threshold would be meaningless. Each method gets its own threshold, calibrated on its own
random-key trials, aimed at the same 1-in-100 false-alarm rate. What we then compare is what each
achieves at that common rate.

**One method could get easier material.** Same eight prompts, same lengths, same model, same
non-watermarked control sequences. Only the sampler differs.

## The headline we predicted, and the answer we got

We wrote down in advance that the headline would be *the shortest length at which each method finds
every sequence*. That was the wrong question, and the result says so cleanly.

Every method, on every model policy, at every length from 96 bases up to 3,072: **every single
sequence detected**. The shortest length is 96 bases for all nine combinations, and 96 bases is
simply the floor of the detector's own search — it will not score anything shorter. There is no
separation to find because all three constructions cleared the bar before the shortest measurable
length.

That is a null result, and it is reported as one. Presenting "all three detect everything" as the
comparison would dress up a question that could not be answered as an answer.

## What actually separates them

The measure that does distinguish the three is **how much signal each one puts into a single 6-mer**,
each measured against its own random-key noise level. Higher means the mark is louder per token:

| Model policy | Ours (`partition_mc`) | Inverse transform | Exponential |
|---|---|---|---|
| `C_tok` | 0.96 – 0.97 | 1.38 – 1.39 | 7.2 – 7.9 |
| `G_tok` | 0.98 – 1.00 | 1.38 – 1.39 | 7.4 – 8.0 |
| `G_bp` | 0.99 – 1.00 | 1.39 | 7.3 – 7.6 |

The exponential construction is roughly **7.5 times louder per token** than ours. Inverse transform is
about **1.4 times** louder.

We predicted this before running it, and the predicted figure for the exponential method was about
7.9. It measured between 7.2 and 8.0.

## Why we lose, and why that is not a bug

The natural worry is that we implemented our own method badly. We did not, and there is a clean way to
see it.

Our construction hides **exactly one bit** in each 6-mer. It flips a secret coin, splits the 4,096
possible tokens into two equal halves, and steers the draw towards the half the coin chose — without
changing the distribution. One bit per token, perfectly recovered, gives a per-token loudness of
exactly 1.0. That is not a tuning parameter; it is the ceiling of the design.

Our measured 0.96 to 1.00 is that ceiling, minus the small unavoidable loss when the two halves do not
carry equal probability. You can see the arithmetic close: the generator recorded that the steering
worked on 98.4%, 99.2%, and 99.7% of tokens for the three policies, and `2 × 0.984 − 1 = 0.968`,
which is what the detector reports for the first policy to three decimals.

The exponential method is not limited to one bit. It reads a fine-grained secret number attached to
the token that was actually emitted, and on a genomic model where thousands of 6-mers are plausible at
every step, there is far more than one bit of secret information available to read. That is the whole
of the difference.

So the honest conclusion is: **on these models, our construction is not the strongest of the three**,
and the reason is structural rather than a defect. What this project contributes is the measurement —
on real released genomic models, with one shared and properly calibrated detector, and with the
fairness conditions checked instead of asserted.

## Two things this result does *not* say

**It does not say the exponential method is more robust.** Everything above is on clean, unedited
sequences. How each method behaves under substitutions, insertions, and deletions is a different
experiment that has not been run for the two baselines. A louder clean signal is not a promise of
better survival, and reading it that way would be exactly the kind of unearned inference this project
tries to avoid.

**It does not say a 1-in-100 false-alarm rate transfers to real genomes.** Which brings us to
something we were not looking for.

## The finding nobody asked for

Thresholds are calibrated on *model-generated* sequences under wrong keys. But the verifier in the
real world will be handed natural DNA. So we also scored real genomic windows under random keys —
never using them to set any threshold, only to see what happens.

Natural DNA sets off the detector more often than the 1-in-100 target, and unevenly by method. At 192
bases: inverse transform fired on 6.9% of natural windows and exponential on 5.0%, while ours fired on
0.0%. Our worst cell anywhere across the three models was 2.5%, and on `G_bp` it was 0.0% everywhere.

Each of those percentages comes from 160 trials, so the resolution is 0.6% — 6.9% is 11 windows out of
160. Small numbers, but not noise at the 1% level.

The reading: **a threshold calibrated on generated sequences is not valid on natural genomic DNA**, and
the two published baselines are more exposed to this than ours is at short lengths. Natural DNA is
repetitive and low-complexity in ways model output is not, and the two baselines' scores appear more
sensitive to that.

This was not a preregistered hypothesis, so it is recorded as an observation rather than a tested
claim. It is also the first result in this project where our construction comes out ahead — and it
would have been invisible if the public-DNA trials had been quietly pooled into the calibration
instead of kept separate on purpose.
