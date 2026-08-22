# 15 — The detector, and what an honest threshold costs

## The verifier is deliberately poor

The generator had everything: the model, the prompt, the probability vector at every step, and the
key. The verifier gets three things:

- the DNA string;
- the key, supplied at run time;
- the public configuration.

No model. No prompt. No logits. No generation seed. No reference copy of the "original" sequence.
This is not modesty for its own sake — it is the only setting in which provenance checking is
practical. Whoever receives a DNA sequence generally cannot re-run the model that produced it.

The detector in this repository loads no model weights at all. It is pure arithmetic over the DNA,
the key, and the public list of 4,096 canonical 6-mers.

## What the verifier does not know

A watermarked sequence arrives stripped of its bookkeeping. The verifier does not know:

- **which strand it is looking at.** DNA is double-stranded; the sequence may have been stored as
  its reverse complement.
- **where the token grid starts.** The generator emitted 6-mers, but if the first few bases were
  trimmed, the verifier's blocks of six are offset. There are six possible phases.
- **where in the key stream the sequence begins.** If the sequence is a fragment, position 0 of the
  DNA is not position 0 of the key stream.

So the verifier must try combinations. For this pilot: 2 strands × 6 phases × 8 key-stream offsets =
**96 alignments**, each scored separately.

## The statistic

For one alignment with `n` tokens and `m` keyed-group agreements:

```text
z = (2m - n) / sqrt(n)
```

If the key did not write this sequence, each token's group is an independent fair coin, so `z` is
about standard normal: centred at 0, and roughly ±1 or ±2 by chance. If the key did write it, most
positions agree and `z` grows like `sqrt(n)` — which is why longer sequences are easier.

The detector reports the **largest** `z` over all 96 alignments.

## Why the maximum is the whole problem

Here is the mistake this project is built to avoid. Take the largest of 96 statistics and read off
its normal tail as if it were a single test. A `z` of 3.0 looks like a p-value near 0.001. It is not.
You searched 96 times; you were *fishing* for a large value, and you found one.

The honest procedure is to calibrate the maximum itself: run the identical 96-alignment search on
sequences the key did *not* write, and see how large the maximum gets purely by chance.

There is a second, subtler trap hiding inside that. The threshold you pick from the null trials is
itself one of those null values, and the statistic `(2m − n)/√n` is *discrete* — it can only land on
`n + 1` possible values. So ties at the threshold are not rare, they are common. If you choose the
threshold by counting nulls *strictly above* a candidate but then call a sequence watermarked when
its statistic is *at or above* the threshold, the ties get counted as detections and the real
false-positive rate quietly exceeds the one you reported. That is not hypothetical: an earlier
revision of this work did exactly that, reporting 0.0094 while the rule as applied achieved 0.0125
against a 0.01 target. The rule is now strictly greater than the threshold everywhere, and a test
constructs deliberate ties to keep it that way.

The measured answer in this pilot: the null maximum reaches `z ≈ 3.7` to `4.6`. So a
threshold of about 2.33 — the textbook one-sided 1% cutoff for a *single* test — would be badly
wrong here. Calibration is not a formality; it moves the threshold by well over a full standard
deviation.

## Three ways to be wrong

A single null family is not enough, because there are different ways for a sequence to be
unwatermarked. All three families below run the identical 96-alignment search:

| Family | What it asks |
|---|---|
| wrong key on watermarked DNA | does a *different* key claim someone else's watermark? |
| any key on the matched ordinary arm | does the key claim same-model output that was never watermarked? |
| any key on real public genome DNA | does the key claim actual *Saccharomyces*, *Arabidopsis*, *C. elegans*, or *Drosophila* DNA? |

The third matters most for a biology paper. If real genomic DNA scored higher than model output,
calibration on model output alone would understate the false-positive rate on exactly the inputs a
verifier meets in practice. It does not: real DNA behaves like the other nulls.

The first two families are pooled to set the threshold — both are "this key did not write this
sequence" at the same length and search. The public-DNA family is reported separately rather than
folded in, so it cannot quietly move the threshold it is supposed to be testing.

## The result

Eight prompts per policy, 3,072 generated bases per prompt per arm, evaluated as prefixes at 384,
768, 1,536, and 3,072 bases. Threshold calibrated to a target false-positive rate of 0.01 from 320
pooled null trials at each length.

At every length, for all three policies, every watermarked sequence scored above the calibrated
threshold, and above *every* null trial. There is no overlap to speak of: at 384 bases the smallest
positive statistic is `z = 7.5` to `8.0` depending on the policy, while the largest of the 320 null
statistics is `z = 3.9` to `4.4`. By 3,072 bases the positives are at `z ≈ 21` to `22`.

Every positive trial's global p-value sits at the floor the null count allows, 1/321.

That is a clean separation with room to spare, and the room matters, because the edits come next.

## What this does and does not establish

It establishes that the construction is detectable by a model-free verifier that searches strand,
phase, and key offset, at a false-positive rate calibrated over that entire search, and that real
genomic DNA is not spuriously attributed.

It does not establish anything about:

- **edits.** These sequences are untouched. Substitutions, insertions, deletions, crops, and
  reverse complementation each get their own experiment. Insertions and deletions are the ones to
  worry about: they shift every downstream token's phase, which is why the offset search exists at
  all.
- **security.** The pilot uses a published fixture key, and the measurement is statistical power,
  not resistance to an adversary. Key reuse, many-output attacks, and detector-query removal are
  separate.
- **longer or shorter extremes.** 384 bases already separates; below that has not been measured, and
  the roughly 5,000-base length was deferred until the pilot had shown separation and a measured
  runtime.
- **other samplers.** Inverse-transform and exponential/Gumbel watermarks get their own matched
  detectors before any comparison is drawn.

## The cost, honestly

The detector is cheap in concept and not free in practice. Each key-stream position requires ranking
all 4,096 tokens by an HMAC, about 4.4 ms. The saving grace is that a partition depends only on the
key and the position, never on the observed token, so one cache serves all 96 alignments and all
four evaluated lengths. One trial on a 3,072-base sequence costs a few seconds; the full pilot for
one policy is about 1,500 trials and runs in under fifteen minutes on the laptop, using no GPU and
no model.

Return to the [explainer index](README.md).
