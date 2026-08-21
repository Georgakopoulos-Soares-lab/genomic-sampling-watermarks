# 06 — Detection and DNA edits

## Detection starts with alignment uncertainty

The detector receives a DNA string, not the original token sequence. It may not know:

- whether the string is in its original orientation or reverse-complemented;
- which of the six possible 6-mer phases is correct;
- where a crop begins relative to the secret-key stream;
- whether insertions or deletions changed alignment inside the string.

Even before handling indels, the detector must inspect 12 basic hypotheses:

```text
2 strand orientations × 6 phases = 12 hypotheses
```

The repository already enumerates those 12 cases explicitly.

## A crop changes phase

Start with:

```text
ATCGGC | AAAAAA | TTTTTT
```

Crop the first base:

```text
TCGGCA | AAAAAT | TTTTT...
```

The biological string is nearly the same, but the observed 6-mers are completely different. The
detector therefore searches phases rather than assuming the sequence starts on the original block
boundary.

## Insertions and deletions are harder

Insert `G` after the first block:

```text
before: ATCGGC | AAAAAA | TTTTTT | CCCCCC
after:  ATCGGC | GAAAAA | ATTTTT | TCCCCC | C...
```

One inserted base shifts every later token until the detector resynchronizes. A substitution is
more local: it changes the 6-mer containing that position but does not move all later boundaries.

This is why the plan treats substitutions, crops, and indels as different edit channels.

## A detector score is not yet a p-value

For one aligned hypothesis, the simple reference score counts how often the observed token's keyed
group matches the expected target bit.

```text
expected targets:  0 1 1 0 1 0 0 1
observed groups:   0 1 0 0 1 0 1 1
score:             6 matches out of 8
```

But the final detector will search many hypotheses, windows, and offsets and retain a strong score.
Chance alone can produce a high maximum when many alternatives are tested.

Therefore null calibration must repeat the **entire search**:

```text
ordinary DNA
    ↓
same strand + phase + window + offset + synchronization search
    ↓
distribution of maximum null scores
    ↓
global threshold for the declared false-positive rate
```

Taking the smallest uncorrected p-value from the search would overstate confidence.

## Planned robustness comparisons

The paper will measure detection power against:

- clean sequences at several lengths;
- independent and clustered substitutions;
- insertions, deletions, and mixed indels;
- crops with unknown starting position;
- reverse complementation;
- wrong keys and ordinary model output;
- public benign DNA;
- adaptive watermark-removal attempts.

Every robustness result must name the model policy, sequence length, edit rate, detector search, and
globally calibrated false-positive rate.

Next: [Running it on the MacBook](07_running_and_next_steps.md).
