# E15 protocol — order-sensitive proxies, and pricing the removal attack

## Why this experiment exists

E12 showed that a full 6-mer positional shuffle removes the watermark completely and changes almost
nothing in the nine admitted sequence proxies: the largest relative shift across all three policies was
0.167, on a single extreme-value statistic. That reads as "removal is free", and it is not a safe
reading, because the nine proxies are composition and complexity statistics and the attack preserves
the 6-mer multiset *exactly*. A suite of counting statistics is blind to a permutation of the units it
counts, by construction and by test.

`docs/baseline_definition.md` declared two further measures for exactly this situation and neither was
implemented: open reading frame summaries and an independent-model likelihood. This experiment
implements both and asks whether they price the attack.

## Disclosure: an exploratory measurement was run before this shape was frozen

This is stated up front because it changes how the result should be read.

While implementing the two measures, an exploratory run on `C_tok`'s existing watermarked corpus was
used to check that the code worked at all. It showed two things that were not predicted:

1. Uniform random DNA contains long open reading frames **by chance** — a 1.8 kb random sequence
   routinely carries one over 200 bases — so the ORF statistics on high-entropy generated DNA are
   substantially chance statistics.
2. The independent-model Markov score barely moved under the attack (relative shift about 0.003 to
   0.005), while the longest-ORF measure moved a great deal (about 0.42).

So the confirmatory run below is **not** blind, and its predictions are informed by that exploratory
look on one policy. Recording that is the point: the alternative is a protocol that pretends to a
blindness it does not have.

## Question

Do either of the two declared order-sensitive measures price the E12 removal attack, and by how much
relative to the composition proxies that are blind to it?

## The two measures

| Measure | Definition | Why it could see a permutation |
|---|---|---|
| Open reading frames | standard start codon to in-frame stop, at least 25 codons, all three frames on both strands; longest ORF, ORF count, and the fraction of bases inside some ORF | a reading frame spans 6-mer junctions, so a permutation cuts it |
| Independent-model score | mean base-2 log probability under an order-`k` Markov model fitted with Laplace smoothing on held-out public prompts | the model conditions on preceding bases, so it sees the junctions a permutation creates |

Neither is a biological claim. The ORF measures are structural sequence statistics and say nothing
about translation, expression, function, viability, or safety. "Independent" in the second means fitted
without the generator, the key, or the scored sequence — not an independent *biological* model — and a
low score means "unlike the reference cohort's local statistics" and nothing more.

## Frozen shape

| Item | Frozen choice |
|---|---|
| Policies | `C_tok`, `G_tok`, `G_bp` |
| Sequences | the E4 watermarked corpus, 8 prompts, 3,072 bases |
| Attacks | the E12 attacks unchanged: full positional shuffle, block shuffle at widths 2, 3, 4, 6, 8, 16, 32, and the splice forgery at 2, 4, and 8 donors |
| Reference model | order 3 and order 5 Markov, fitted on the 16 cohort prompts **not** used by any detection experiment, so the reference is held out by construction |
| ORF minimum | 25 codons, declared before the confirmatory run and unchanged from the exploratory one |
| Comparison | relative shift against the same sequence before the attack, matching how the composition proxies are compared |
| Uncertainty | the exact paired sign-flip test over the 8 prompts, as used for the other proxy comparisons |

### Held-out reference

The reference model must not be fitted on anything the attack touches. The detection experiments use 8
of the 24 cohort prompts, so the other 16 are available and are used. This is checked in the runner
rather than asserted.

## Predictions, informed by the exploratory run and stated before the confirmatory one

1. **The longest-ORF measure prices the attack** at a relative shift well above the largest composition
   shift of 0.167, on all three policies. Expected magnitude around 0.3 to 0.5.
2. **The independent-model score does not**, with a relative shift below 0.02 on all three policies.
   The reason is structural rather than a tuning problem: a Markov model of order 3 to 5 assigns
   high-entropy DNA a score close to the uniform rate, and a permutation preserves most short contexts.
3. **Block shuffling shows a monotone trend in width** for the ORF measure, since a wider block
   displaces more of any frame.
4. **The splice forgery disturbs the ORF measure less than the shuffle does**, because splicing
   preserves each position's local content and only mixes across donors.

If prediction 2 holds, the honest conclusion is that *one* of the two declared instruments prices this
attack and the other does not, and the paper must say which — rather than claiming that implementing
both closed the gap.

## Preregistered reading

- A relative shift is reported per measure, per attack, per policy, with the paired sign-flip p-value.
- The ORF result is reported as a **structural** change and never as functional damage. On
  high-entropy DNA a long ORF is largely a chance event, so destroying it is evidence that order
  changed, not that anything biological was lost.
- If the independent-model score is blind, that is admitted as a negative result about the instrument,
  not omitted.
- Nothing here changes the E12 detection numbers. This experiment prices an attack whose success was
  already measured.

## Boundary

Public benign DNA and proxy metrics only. No functional, viability, or safety claim. The measures are
computed on generated sequences and their attacked versions, never on private or patient sequence.

## Result, 2026-08-24

Three policies, the E4 watermarked corpus, the E12 attacks rebuilt from the same public replay seeds,
and a reference Markov model fitted on the 16 cohort prompts no detection experiment uses. The runner
checks that separation rather than asserting it.

### Prediction 2 holds: the independent-model score is blind

Relative shift under a full positional shuffle: **0.0027 to 0.0086** across policies and Markov orders
3 and 5. The reason is structural. A Markov model of order 3 to 5 assigns high-entropy generated DNA a
mean log-probability close to the uniform rate (about −1.96 bits per base at order 3), and a 6-mer
permutation leaves most short contexts intact. This instrument does not price a rearrangement, and no
choice of order within the range we can fit will change that.

### Prediction 1 does not hold, and the way it failed matters

The relative shift of the longest open reading frame looked like a result: **0.07 to 0.43**, larger than
the largest composition shift on most cells. The paired sign-flip test over the eight prompts dissolves
it.

| Attack | `C_tok` | `G_tok` | `G_bp` |
|---|---|---|---|
| full positional shuffle | **8/8 decreased, mean −160 b, p = 0.0078** | 5/8, mean −64 b, p = 0.39 | 7/8, mean −60 b, p = 0.0625 |
| block shuffle, width 2 | 6/8, mean −9 b, p = 0.89 | 4/8, mean −15 b, p = 0.84 | 4/8, mean +4 b, p = 0.88 |
| block shuffle, width 8 | 5/8, mean +4 b, p = 0.96 | 4/8, mean −49 b, p = 0.48 | 3/8, mean +2 b, p = 0.80 |
| block shuffle, width 32 | 6/8, mean −57 b, p = 0.26 | 5/8, mean +14 b, p = 0.84 | 4/8, mean +0.4 b, p = 1.00 |

So the ORF measure prices only the **complete** shuffle, clearly on one policy of three and marginally
on a second. For the bounded block shuffles --- the attacker's realistic option, and the ones that
remove the mark at width 8 to 32 --- there is **no directional effect at all**: the longest ORF rises
about as often as it falls.

The explanation is the same one the exploratory run surfaced. On high-entropy DNA the longest open
reading frame is a chance extreme-value statistic: uniform random sequence routinely contains frames
over 200 bases. Permuting the sequence re-rolls that statistic rather than destroying a structure, so
its magnitude moves while its direction does not. A relative shift computed from absolute differences
records the re-roll and hides the absence of direction.

This is the seventh time in this project that a magnitude looked like a result and a properly paired
test dissolved it. The lesson is the same each time and worth writing on the wall: **an unsigned
magnitude is not evidence of an effect.**

### What this means for E12

**Neither declared instrument prices the removal attack in the regime that matters.** The nine
composition proxies are blind by construction, the independent-model score is blind in practice, and
the ORF measures respond only to a complete permutation and not to the bounded rearrangements that
suffice to strip the watermark.

So the E12 limitation is not closed by this work --- it is sharpened. The honest statement is now
stronger than "our proxies cannot see this attack": we implemented both instruments our own design
declared for the purpose, and they still cannot see it. Pricing a bounded 6-mer rearrangement needs a
measure sensitive to long-range order that none of these three families provides, and identifying one
is open work rather than a gap we neglected.

### One thing that did show up

The splice forgery disturbs the composition proxies substantially more than any shuffle does --- up to
0.53 on CpG fraction at eight donors against 0.13 to 0.23 for the shuffles --- because splicing mixes
DNA across organisms while a shuffle stays within one sequence. That is the reverse of what a defender
would hope for: the attack that manufactures provenance is easier to spot by composition than the
attack that destroys it. Prediction 4 anticipated the direction and understated the size.

## Implementation status

- `src/genomic_watermarks/structure_proxies.py` implements both measures.
- `tests/test_structure_proxies.py` asserts the mechanism without magic numbers: proxies that are
  functions of base or k-mer counts alone are checked to be *exactly* unchanged under a permutation,
  while the longest-ORF measure is checked to move. It also records the independent-model score's
  blindness as a test, so a later change cannot quietly assume otherwise.
- `scripts/run_structure_proxies.py` runs the experiment, storing every per-sequence measurement.
- Admission pending review.

## Evidence boundary

No number moves into `evidence/measurements.yaml` without explicit evidence-admission review.
