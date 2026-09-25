# OpenReview rebuttal draft — PAT feedback, submission 32263

**Date:** 2026-09-21
**Status:** draft for author review. Nothing here has been posted.
**Companion:** `2026-09-21_pat_response_lane2.md` records what changed in the manuscript.

Each response below is written to be posted as-is. Where a response says "we have added", the text
is already in `paper/manuscript/source/main.tex`. Where it says "we would add", the change is
contingent on a decision or on Lane 1.

## Read this before posting

Two facts constrain what can honestly be said.

**The submitted PDF and the repository source are separate lineages.** Section numbering matches
through §7 and every reported number is identical, but the figures are numbered differently: what
the review calls Figure 3 (quality proxies) is Figure 2 in the repository source, and what it calls
Figure 2 (detection) is Figure 3. Any response that names a figure number should use the submitted
PDF's numbering, which is what the reviewer sees. Any revised PDF must be regenerated so the
numbering the response cites still holds.

**Part C is on its default branches.** The responses to W4, W7, and W8 below are written for the
case where no new measurement lands. If Lane 1 delivers `synthid.v2.*` numbers, those three
responses change and so does the manuscript; the branch tables in the lane plan supply both.

## W1, M4, R2, D1 — edit rate and the scope of the edit regime

We agree this is the most important open question, and we now state its answer as far as the design
determines it.

Detection requires a contiguous region whose 6-mer alignment survives across one of the evaluated
windows, the shortest of which spans 384 bases. Independent indels at rate *r* leave expected clean
stretches near 1/*r* bases, so the method should degrade near *r* = 0.1% and fail near an
illustrative *r* = 1%, where the expected clean stretch falls below our shortest window. We have added this reasoning and its boundary
condition to the Limitations section, together with the observation that substitutions are milder
than indels because a substitution corrupts the tokens overlapping it without shifting the frame.

We have not run the sweep. Multiple-edit robustness is outside this study's declared threat model,
and a credible sweep needs a shorter-window search with a correspondingly larger correction, which
is a different verifier and a different study. We identify the search geometry, not the watermark
strength, as the binding constraint at higher rates, and we name the sweep as the most useful
direction for the next study.

## W2, R5 — absence of comparative baselines

Our contribution is the verifier, not a new watermark construction. The study scope admits exactly
one construction, the SynthID tournament, with ordinary categorical sampling as its matched control.
Implementing a distortionary red/green-list scheme for 6-mers would compare two constructions rather
than two verifiers, and would confound the comparison we are making.

We have instead added a structured property comparison to the Background section, along four axes
the study can support: whether verification needs the generating model or its probabilities, whether
it needs an alignment or a known boundary or strand, what edit model is claimed, and whether the
sampling distribution is distorted. We have also added a Discussion sentence stating the absence of
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

We agree that 192 independent prompts cannot validate a 1% target, which is why we report the
interval rather than a point estimate: 2.87% for one positive prompt and 1.90% for none. We have
sharpened the Limitations text to say that we did not scale the cohort for this version and that
precise estimation near a 1% target requires roughly an order of magnitude more independent prompts,
which we identify as required future work rather than a resolved question.

We would add one point in the paper's favor that the current text now makes explicit. The windows
are strongly positively correlated: two windows of the same length whose starts differ by a multiple
of six bases share a token phase and all but a few tokens. Bonferroni correction is valid without
independence but conservative in such a family, so the realized false-positive rate is below the
declared target and our reported control counts should be read as an upper bound rather than an
estimate.

## W5a — the goodness-of-fit test statistic

The statistic is the likelihood-ratio (*G*) statistic against the fully specified law, referred to a
parametric Monte Carlo null of 999 replicates resampled from that law rather than to its asymptotic
chi-square distribution. The reviewer's diagnosis of why this matters is correct: at 4,096 categories
and 5,000 draws per state the expected count per category is about 1.2, so the asymptotic reference
is unreliable, whereas the Monte Carlo reference is exact under the declared law by construction. We
have added the statistic, the reference distribution, and the reason to the Sampler validation
subsection.

## W5b, R4 — multiple-testing correction for the 256 state tests

The 256 per-state tests form one family per arm. We report Benjamini–Hochberg correction at
α = 0.05 as the primary correction, and also record Bonferroni correction at α/256 = 1.95 × 10⁻⁴
while noting that 999 Monte Carlo replicates bound the attainable P-value below at 10⁻³, so no
state can reject at the Bonferroni level and that correction carries no information at this family
size. Neither arm produced a rejection under either correction in either model, against a chance
expectation of 12.8 nominal rejections per arm. We have added both corrections to the Results text
so that "after correction" now names which correction it means.

## W6, R1 — the two window-score summaries and the selection rule

The two candidates were the released SynthID mean score over scored tokens and the upstream default
weighted-mean score. They were compared on the 64 calibration prompts alone, at the shortest and
longest of the four window lengths, by the separation between the marked and ordinary arms in
units of the ordinary-arm standard deviation, on continuations scored under known token alignment. The mean score separated the arms
at least as well at both lengths and was selected. Evaluation prompts were never scored during this
selection and no signal-matched weights were fitted. We have added this to the Results section, and
a reader can now reproduce the selection from the paper alone.

## W7, R3 — the cross-model detection-strength gap

The weakest marked read differs substantially between models, 124.8 in Carbon against 19.6 in
GENERator, while both clear the 6.21 corrected threshold with wide margin — the weakest GENERator
read by 13.4 orders of magnitude in the window p-value, the weakest Carbon read by 118.6. We do not
attribute this difference in margin to a specific cause. Candidate explanations include the number
of tokens actually scored per read after repeated-context exclusion, since a model that revisits
four-token contexts more often yields fewer scored bits at identical watermark strength, and
differences in predictive entropy between the models. Distinguishing them requires per-token
analysis we leave to future work. We have added this to the Results text and note that the detection
decision is unaffected: every marked read in both models cleared the corrected threshold.

## W8, D2 — the Carbon provenance discrepancy

We have expanded this in Limitations to enumerate what the retained protocol document governs: the
cohort identity, the prompt split rule, the four window lengths, both orientations, the declared
false-positive target, and the tournament and context settings. All of these are independently
recorded in the result artifact's own configuration and command fields and agree with the reported
analysis. We were nonetheless unable to determine which revision of the document the recorded hash
corresponds to, so the document-level chain for this execution cannot be closed. We report it as an
unresolved provenance gap rather than a resolved one, and we do not rely on its resolution for any
claim.

## W9, A1 — AI Use Statement accuracy

The reviewer is right. The paper contains no formal theorems or proofs, and the statement should not
have said it did. We have corrected the statement to describe statistical derivations rather than
proofs and added an explicit sentence that the paper contains no formal theorems or proofs, that the
statistical development uses standard probability models and a Bonferroni correction, and that all
derivations, numbers, and claims were verified by the authors against the evidence ledger. We note
that this check is what surfaced the mark-bit correction under M3 below. We have
not narrowed the disclosure elsewhere.

## A2 — reproducibility and code availability

The Reproducibility Statement now names what is released: the verifier implementation, the sampler,
the prompt-cohort construction scripts, the analysis and figure scripts, the frozen protocol
documents, and the evidence ledger to which every number in the paper resolves. The two experimental
keys are published fixtures rather than deployment secrets. Generated sequences and the full result
files are available from the authors on request; the committed artifacts include the summaries and
digests needed to re-derive every reported value.

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
mark bits, of which at least 1,004 must be positive. The floor on scored tokens is correspondingly
much lower than the reviewer's estimate: 21 positive mark bits already reach the corrected
threshold, so a single fully positive scored token would suffice. The binding constraint is
therefore the shortest window the verifier evaluates, 384 bases, not the supply of mark bits. We
are grateful for the prompt to check this: the conclusion the reviewer draws is right, and the
mechanism is the window-length set rather than the bit count.

## M5 — algorithmic complexity

We have added a complexity paragraph describing the implemented algorithm. For a read of *N* bases
there are twelve reading frames, two orientations by six phases, and the mark bits of every token
position in a frame are computed once in a single pass. Window statistics then follow from prefix
sums over the per-token bit counts, so each window of a given length is evaluated in constant time;
where a frame contains repeated four-token contexts, the first-occurrence rule is enforced with
Fenwick trees and each window costs O(log *N*). The work is O(*N*) keyed hash evaluations and
O(*N* log *N*) additional time with O(*N*) space per read.

## T1–T5 — typography and hyphenation

Accepted, and corrected in the source. We note for the record that the repository source already
carried the hyphenated forms and the correctly bound accent; the unhyphenated compounds the reviewer
lists are artifacts of the submitted build, and the revised PDF will not carry them.

## T6 — naming the measures with the largest standardized effects

Added. The largest absolute standardized effects were 0.084 standard deviations in Carbon, on the
longest single-base run, and 0.111 in GENERator, on the mean single-base run. Every interval included
zero and no measure survived correction in either model.

## T7 — "drift" versus "shift"

Accepted. The body text already used "Jensen–Shannon drift"; the appendix figure axis labels read
"shift from prompt". The figures are regenerated from the analysis artifacts by script, and the axis
labels will read "Jensen–Shannon drift" in the revision so that text and figures agree.
