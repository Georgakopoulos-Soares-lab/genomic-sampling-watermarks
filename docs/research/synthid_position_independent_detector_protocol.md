# Position-independent SynthID detector protocol

This document defines `synthid-position-independent-detector-v1`. It applies only to the existing
`synthid-tournament-v1` generator.

## What changed and what did not

The generation algorithm did not change. SynthID already computes its keyed values from the four
most recent generated 6-mer tokens and a candidate token, rather than from an absolute sequence
position. Therefore, moving the generated continuation to a different position does not alter the
watermark embedded in it and does not alter the model's sampling distribution.

The new component is a standalone detector that does not receive the prompt, generation boundary,
6-mer phase, strand orientation, or an offset. Its complete private input is the secret key. Its
public inputs are the observed DNA, the domain used during generation, and the detector
configuration.

The domain, depth, context length, and repetition-history length must match generation. A wrong
value for any of these fields intentionally behaves like a wrong key.

## Complete search

For a read of `N` bases and each configured window length `L` that fits the read, the detector:

1. examines the read in its supplied orientation and as its reverse complement;
2. tries every nucleotide start from `0` through `N - L`, inclusive;
3. splits each candidate substring into 6-mers beginning at that start;
4. treats the first four 6-mers as local context and recomputes the SynthID keyed bits for every
   later 6-mer; and
5. applies the same repeated-context mask used during generation.

A one-nucleotide stride searches the unknown generation boundary and all six possible 6-mer phases
at the same time. No prompt bases are required. If a prompt is present in the observed read, it is
simply background surrounding the candidate generated region.

With both orientations enabled, the total number of tested regions is

```text
M = 2 * sum over fitting L of (N - L + 1).
```

Reverse-complement winning coordinates are converted back into coordinates on the supplied read.
Both the converted interval and the start in the searched orientation are returned.

## One sequence-level decision

For one candidate region, let `g_ones` be the number of recomputed SynthID bits equal to one and
`g_total` the number of unmasked bits. Under the absent-watermark or independent-key idealization,
the local one-sided probability is the exact fair-binomial tail

```text
p_local = P[Binomial(g_total, 1/2) >= g_ones].
```

The detector reports the strongest local region but makes only one decision for the entire read:

```text
p_sequence = min(1, M * minimum p_local).
detected    = p_sequence <= target false-positive rate.
```

This Bonferroni correction includes every searched orientation, start, and length. It remains valid
when neighboring windows overlap and are highly dependent. The implementation also retains natural
log probabilities so very strong signals are not lost when an ordinary floating-point probability
becomes too small to represent.

No calibration prompts are used to fit this rule. The target false-positive rate is analytic.
The completed Carbon and GENERator validations check matched ordinary outputs and watermarked
outputs scored with the other draw's key as separate false-positive families.

## Fixed public configuration

The default configuration searches 384, 768, 1,536, and 3,072-base windows, both orientations, a
target sequence-level false-positive rate of 0.01, 30 tournament layers, four context tokens, and a
1,024-context repetition history. Window lengths are protocol choices, not settings that may be
selected after inspecting one read. Adding orientations, lengths, offsets, or other regions requires
including those additional tests in `M`.

Only lengths that physically fit an observed read are searched. The detector rejects a read shorter
than every declared length rather than silently changing the protocol.

## Interpretation and limitations

- This change affects detection only, so it cannot lower model sequence quality. The
  generated bases are exactly those produced by the existing SynthID tournament sampler.
- Arbitrary prompt length and whole-read cropping are handled because every possible start is
  searched. Reverse-complement reads are handled by the two-orientation search.
- A substitution affects only nearby keyed contexts. An insertion or deletion changes the local
  6-mer grouping, but later candidate starts can restore alignment. Robustness to any particular
  edit rate remains an empirical claim, not a consequence of this interface.
- Searching more bases makes `M` larger and therefore makes the corrected decision more
  conservative. “Position independent” does not mean that an unlimited, undisclosed search is free.
- The fair-binomial calculation relies on the stated keyed-function idealization. It is not a proof
  of biological provenance, authenticity, viability, or secret-key recovery resistance.
- This implementation identifies the strongest declared region. It is not a multi-region caller and
  does not estimate the true generation boundary with a separate confidence interval.

## Implementation

The library entry point is `detect_synthid_position_independent` in
`src/genomic_watermarks/synthid_position_independent.py`. The model-free command-line wrapper is
`scripts/detect_synthid_position_independent.py`. It reads a hexadecimal key from
`GENOMIC_SYNTHID_KEY` by default and never prints the key or input DNA.
