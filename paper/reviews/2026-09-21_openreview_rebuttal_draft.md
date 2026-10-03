# OpenReview rebuttal draft — PAT feedback, submission 32263

**Date:** 2026-09-21
**Status:** draft for author review. Nothing here has been posted.
**Companion:** `2026-09-21_pat_response_lane2.md` records what changed in the manuscript.

Each response below is written to be posted as-is. Where a response says "we have added", the text
is already in `paper/manuscript/source/main.tex`. Where it says "we would add", the change is
contingent on a decision or on Lane 1.

## Read this before posting

Two facts constrain what can honestly be said.

**Figure numbers follow the revised PDF.** The response is posted together with the revised PDF
built from the repository source, so every response cites that PDF's numbering. The submitted PDF
numbered figures differently, so the reviewer's references map as follows, and the opening of the
response should state this mapping once:

| Content | Submitted PDF | Revised PDF |
|---|---|---|
| Method overview | Figure 1 | Figure 1 |
| Detection, development cohort | Figure 2 | Supplementary Figure S1 |
| Quality proxies | Figure 3 (appendix) | Figure 2 |
| Single-base edits, development cohort | Figure 4 (appendix) | Supplementary Figure S2 |
| Detection, detection cohort | — | Figure 3 (new) |
| Single-base edits, detection cohort | — | Figure 4 (new) |
| Detection as edits accumulate | — | Figure 5 (new) |
| Detection counts, detection cohort | — | Table 1 (new) |
| Detection counts, development cohort | Table 1 | Supplementary Table S1 |
| Strength and window length by edit | — | Supplementary Table S2 (new) |

Check this table against the submitted PDF before posting; the submitted file is not in the
repository. Section headings also changed in the revision: the detection cohort and the edit-rate
experiment have their own Methods and Results subsections.

**Part C landed 2026-09-29 and was revised 2026-09-30.** Lane 1's second-cohort and edit-rate
measurements arrived after this draft was first written. The 2026-09-29 reconciliation
(`paper/reviews/2026-09-29_lane3_reconciliation.md`) updated the manuscript, and the 2026-09-30
revision (`paper/reviews/2026-09-30_post_lane_revision_plan.md`) corrected the W1, W4, W7, W8, A2,
and M3 responses to match the revised paper. W7 no longer uses the inconclusive branch: the strength
analysis shows that the gap is one weak sequence rather than a difference between models. The revision
adds Table 2 and Figure 5, shows the detection cohort in Figures 3 and 4, and moves the primary-cohort
detection and edit figures to Supplementary Figures S1 and S2. A language and flow pass on
2026-09-30 moved some text between sections; the section pointers below follow the revised PDF.

## W1, M4, R2, D1 — edit rate and the scope of the edit regime

We agree this is the most important open question, and we have now answered it with a
measurement rather than only an argument. The revised paper describes it in a new Methods
subsection and reports it in a new Results subsection with its own figure (Figure 5 of the revised
PDF).

The single-edit conditions remain the fully controlled evaluation: exactly one substitution,
insertion, or deletion per sequence, with matched ordinary and wrong-key controls. We additionally
re-scored the 3,088 sequences per model of a second, larger cohort after random edits at per-base
rates from 0.03% to 10% (1 to 307 edits per 3,072-base continuation), as substitutions, insertions
only, deletions only, and a mixture of the two. Each substitution changes one base, and each
insertion or deletion adds or removes one to five bases. Edit positions came from a public hash stream and
never depended on the detector. Detection stayed complete or nearly complete through a 2% rate in
both models: every cell detected all 3,088 marked sequences except GENERator's mixed series at 2%,
which detected 3,087. At 5%, substitutions were still detected in 3,088 Carbon sequences and 3,087
GENERator sequences, and insertions and deletions in 92.9–93.9%. At 10%, detection fell to 18.7–19.7%
for substitutions and 4.6–5.9% otherwise. The two models agreed within one percentage point in
every cell. Ordinary outputs stayed at or below 0.29% in every cell.

A simple clean-stretch argument predicts failure near 1%, where indel-free stretches average about
100 bases against a 384-base minimum window. Detection outlasts it because a window need not be
intact: tokens that keep their reading frame and context add excess 1s, the others only dilute
the count, and an unedited sequence starts near strength 800 against a threshold of 6.21. A single
edit shows the relative cost: one substitution removes about 2% of the median strength and one
insertion or deletion about 45%.

The edits were placed without reference to the detector, so this is not an adversarial-robustness
result, and the series scored correct-key and ordinary sequences only, not the wrong-key family. An
editor who inspects the detector, the key, or any score remains outside the study, and we name
that as the most useful direction for further work.

## W2, R5 — absence of comparative baselines

Our contribution is the verifier, not a new watermark construction. The study scope admits exactly
one construction, the SynthID tournament, with ordinary categorical sampling as its matched control.
Implementing a distortionary red/green-list scheme for 6-mers would compare two constructions rather
than two verifiers, and would confound the comparison we are making.

We have instead added a structured property comparison to the Background section, along four axes
the study can support: whether verification needs the generating model or its probabilities, whether
it needs an alignment or a known boundary or strand, what edit model is claimed, and whether the
sampling distribution is distorted. We have also added a Limitations paragraph stating the absence of
a same-cohort empirical baseline as a limitation, rather than leaving it unremarked.

## W3, R6, D3 — biological validation benchmarks

We agree that the gap between sequence statistics and function matters, and we have added it to
Limitations. In checking the suites the reviewer names, we found that they do not transfer to this
setting as directly as the request implies. BEND, GenBench, GENEB, Genomic Benchmarks and the
Nucleotide Transformer task set are probe-or-finetune protocols: a metric exists only because a
held-out label tied to a genome coordinate exists, and a de novo generation carries neither a label
nor a coordinate. DART-Eval's motif-footprinting task needs no coordinates, but motif presence is
itself the ground truth. As of September 2026 we could find no standardized public benchmark that
scores unlabelled generated sequence.

We have therefore written the limitation as what it is: evaluating watermarked generations against
these suites would require either a paired design, in which a generated sequence is scored against a
deliberately altered copy of itself, or experimental assay. Our quality claim remains confined to the
14 declared model-likelihood and sequence summaries, and we make no claim about function, viability,
or safety anywhere in the paper.

## W4 — false-positive-rate sample size

We agree that 192 independent prompts cannot validate a 1% target, which is why the paper reports
the interval rather than a point estimate: 2.87% for one positive prompt and 1.90% for none in the
development cohort. We have since run a detection cohort of 1,608 prompts (1,544 held out for evaluation),
fixed before any output was generated and drawn separately from the same chromosome records. It
reproduces complete detection (3,088 of 3,088 marked sequences per model and condition), and every
one-sided 95% upper confidence bound on the prompt-level rate of positive ordinary outputs lies
below 1%; the largest is 0.850% (GENERator, deletion). The analysis plan designated ordinary
outputs as the primary false-positive measure before the run. In the secondary wrong-key family,
one cell (Carbon, deletion) has an upper bound of 1.015%, which the paper reports as observed. A
new table (Table 1 of the revised PDF) gives every cell.

We would add one point in the paper's favor that the current text now makes explicit and has also
measured. The windows are strongly positively correlated: two windows of the same length whose
starts differ by a multiple of six bases share a token phase and all but a few tokens. Bonferroni
correction is valid without independence but conservative in such a family. On ordinary sequences the
corrected decision fired on 0.105% of Carbon sequences and 0.186% of GENERator sequences, 9.5 and 5.4 times
below the 1% target, and the observed minimum window P-values behave like about 828–852
independent tests rather than the 16,136 searched. The decision rule itself is unchanged.

## W5a — the goodness-of-fit test statistic

The statistic is the likelihood-ratio (*G*) statistic against the fully specified law, referred to a
parametric Monte Carlo null of 999 replicates resampled from that law rather than to its asymptotic
chi-square distribution. The reviewer's diagnosis of why this matters is correct: at 4,096 categories
and 5,000 draws per state the expected count per category is about 1.2, so the asymptotic reference
is unreliable, whereas the Monte Carlo reference is exact under the declared law by construction. We
have added the statistic, the reference distribution, and the reason to the Sampler validation
subsection.

In checking this test we also made its scope explicit. The draws at each state come from the
computed distributions, so the G-test confirms the sampling step and the test itself at realistic
model distributions, but it does not by itself verify how the fixed-key distribution is computed.
That rests on implementation tests, which the revised Methods now describe:
- the tournament update matches the public SynthID-Text reference implementation;
- the vectorized computation used during generation agrees with an independent implementation to
  floating-point precision;
- the generation sampler's draws are reproduced exactly by the sampling step used in the checks.

The negative control, draws from the model's own distribution tested against the fixed-key
distribution, is rejected at every control state, which shows the test can tell the two apart.

## W5b, R4 — multiple-testing correction for the 256 state tests

The 256 per-state tests form one family per arm. We report Benjamini–Hochberg correction at
α = 0.05 as the primary correction, and also record Bonferroni correction at α/256 = 1.95 × 10⁻⁴
while noting that 999 Monte Carlo replicates bound the attainable P-value below at 10⁻³, so no
state can reject at the Bonferroni level and that correction carries no information at this family
size. In GENERator, neither arm produced a rejection after Benjamini–Hochberg correction. For
Carbon, the corrected count was not retained with the evidence; its 13 and 12 nominal rejections
are close to the 12.8 expected by chance. We have added both corrections to the Results text
so that "after correction" now names which correction it means.

## W6, R1 — the two window-score summaries and the selection rule

The two candidates were the released SynthID mean score over scored tokens and the upstream default
weighted-mean score. For GENERator, they were compared on the 64 calibration prompts alone, at the
shortest and longest of the four window lengths, by the separation between the marked and ordinary
arms in units of the ordinary-arm standard deviation, on continuations scored under known token
alignment; the mean score separated the arms at least as well at both lengths and was selected.
Evaluation prompts were never scored during this selection and no signal-matched weights were
fitted. We apply the same selected summary to Carbon, but note in the text that the equivalent
Carbon comparison was not retained as a committed artifact, so the selection is independently
verified for GENERator only. We have added this to the Methods section (Prompts and generation), and a reader can now
reproduce the selection from the paper alone.

## W7, R3 — the cross-model detection-strength gap

We examined this directly and found that the gap is a property of one sequence, not of the models.
The median unedited marked sequence had strength 790.6 in Carbon and 798.8 in GENERator. The weakest
sequences, 124.8 and 19.6, differ because GENERator's weakest sequence came from a repetitive continuation:
174 of its four-token contexts repeated and were excluded, leaving 334 of 508 scored tokens, and
only 54.6% of its mark bits were 1, against a median of 74% in both models. Restoring all 508
scored tokens at that fraction would close only 9% of the gap, so most of the shortfall is weak
signal rather than fewer scored tokens. In the larger detection cohort, the medians were again close
(792.9 and 799.7) and the weakest sequences were 237.6 in Carbon and 123.8 in GENERator. We have
rewritten the Results paragraph accordingly. Low per-token entropy in repetitive stretches is a
plausible reason for weak signal, but we did not measure it and the paper says so.

## W8, D2 — the Carbon provenance discrepancy

We have audited the discrepancy and expanded Limitations accordingly. The retained protocol
document governs nine settings: the cohort, the prompt split, the four window lengths, both
orientations, the false-positive target, the tournament depth, the context width, the
repetition-history size, and the edit rule. Eight are recorded in the result's own fields and agree
with the reported analysis. The ninth, the 1,024-context repetition history, is fixed only by the
default of the detector code identified by its recorded hash. The mismatch therefore gives no
indication that the generated sequences or the detection statistic differ from what we report. We
could not recover the original document bytes, so the paper still states that the execution
cannot be checked against the document itself.

## W9, A1 — AI Use Statement accuracy

The reviewer is right. The paper contains no formal theorems or proofs, and the statement should not
have said it did. We have corrected the statement to describe statistical derivations rather than
proofs and added an explicit sentence that the paper contains no formal theorems or proofs, that the
statistical development uses standard probability models and a Bonferroni correction, and that all
derivations, numbers, and claims were verified by the authors against the evidence ledger. We note
that this check is what surfaced the mark-bit correction under M3 below. We have
not narrowed the disclosure elsewhere.

## A2 — reproducibility and code availability

The Reproducibility Statement now names what is released: the verifier implementation, the
sampler, the prompt-cohort construction scripts, the analysis and figure scripts, the protocol
documents, and the evidence ledger to which every number in the paper resolves. The two
experimental keys are published fixtures rather than deployment secrets. The repository includes
the detection results for both models in the detection cohort and the GENERator results for the
development cohort; the Carbon primary-cohort result files and the generated sequences are available
from the authors on request.

## B1 — contrast with text-domain synchronization robustness

We agree this strengthens the motivation, and we have added it to the Background section. Text-domain
watermarks that target edit robustness treat synchronization as a local problem, because an insertion
or deletion in text perturbs tokenization near the edit and leaves distant tokens largely intact.
Non-overlapping *k*-mer genomic tokenization removes that locality: a single inserted or deleted base
shifts the reading frame, so every downstream token changes identity and the keyed context
determining each mark bit changes with it. An edit-distance alignment against a key sequence does not
recover this, because there is no surviving token sequence to align; what survives is a contiguous
region in one of six phases. This is why verification is posed here as a search over strands, phases,
start positions, and window lengths, and why the correction over that search is part of the method.

## B2 — scope of the token-phase problem

We have added this to the tokenization subsection. The phase problem is specific to multi-mer
tokenization: single-nucleotide models place one token per base, so an indel shifts token positions
without changing token identities and a verifier faces an offset rather than a frame. Multi-mer
tokenization is nevertheless widely used because it shortens sequences by the token width and lets a
model cover more bases within a fixed context, which is why both evaluated models use non-overlapping
6-mers. The cost is the six phases and the identity change downstream of an indel.

## B3 — local context in LLM watermarks

We agree that hashing local token context is a standard structural feature of autoregressive text
watermarks and not unique to SynthID, and we have corrected the text. We adopt SynthID because it
combines that property with tournament sampling, whose distribution-preservation identity holds in
expectation over fresh keyed functions. Local context is what makes verification possible at an
unknown location; distribution preservation is what keeps the generated sequence usable as a sample
from the model's own law.

## M2 — conservatism of Bonferroni on correlated windows

We have added the operational consequence to the detection subsection, as described under W4 above.
We keep Bonferroni because it bounds the family-wise error rate without assuming independence, and we
now state that in a correlated family it is conservative, so our recall is attained under a threshold
stricter than necessary.

## M3 — detectability constraints on short windows

We have added the boundary to the paper as a property of the design, and in recomputing it with an
exact binomial tail we found that the reviewer's figures rest on one bit per scored token. The
sampler applies 30 tournament layers, each contributing its own mark bit, and the detector's
binomial statistic is taken over all of them: at the shortest evaluated length, 384 bases is 64
tokens, of which the first four supply unwatermarked context, leaving 60 scored tokens and 1,800
mark bits, of which at least 1,004 must be positive. The binding constraint is therefore the
dilution imposed by the shortest window, not the supply of mark bits. A window need not be intact:
tokens that lose their reading frame or context only dilute the count, so detection needs enough
tokens within one window to keep both, about 56% ones for the shortest window and less for longer
ones. The new edit-rate results (see W1) show how densely random edits must fall before this fails.

## M5 — algorithmic complexity

We have added a complexity paragraph describing the implemented algorithm. For a sequence of *N* bases
there are twelve reading frames, two orientations by six phases, and the mark bits of every token
position in a frame are computed once in a single pass. Window statistics then follow from prefix
sums over the per-token bit counts, so each window of a given length is evaluated in constant time;
where a frame contains repeated four-token contexts, the first-occurrence rule is enforced with
Fenwick trees and each window costs O(log *N*). The work is O(*N*) keyed hash evaluations and
O(*N* log *N*) additional time with O(*N*) space per sequence. Measured: verifying one 3,456-base sequence
took a median 0.0956 s single-threaded (0.245 s at 6,912 bases; 0.902 s at 13,824) on an AMD EPYC
7763, with peak memory per process of 27.9 MiB at 3,456 bases and 69.1 MiB at 13,824; running 16
workers in parallel across sequences raised throughput to one sequence per 0.0167 s of wall-clock time,
5.7 times the single-threaded rate.

## T1–T5 — typography and hyphenation

Accepted, and corrected in the source. We note for the record that the repository source already
carried the hyphenated forms and the correctly bound accent; the unhyphenated compounds the reviewer
lists are artifacts of the submitted build, and the revised PDF will not carry them.

## T6 — naming the measures with the largest standardized effects

Added. The largest absolute standardized effects were 0.084 standard deviations in Carbon, on the
longest single-base run, and 0.111 in GENERator, on the mean single-base run. Every interval included
zero and no measure survived correction in either model.

## T7 — "drift" versus "shift"

Accepted. The body text already used "Jensen–Shannon drift"; the appendix figure axis labels sequence
"shift from prompt". The figures are regenerated from the analysis artifacts by script, and the axis
labels will sequence "Jensen–Shannon drift" in the revision so that text and figures agree.
