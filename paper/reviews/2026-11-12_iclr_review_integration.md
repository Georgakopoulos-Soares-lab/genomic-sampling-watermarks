# ICLR 2027 review integration — submission 32263

**Date:** 2026-11-12
**Branch:** `iclr-2027-revision`
**Forum:** https://openreview.net/forum?id=vo1qxcMxxx&noteId=LyX9i394f8 (could not be fetched
automatically on 2026-11-12: OpenReview returned a browser-verification page; the review text below
is the copy supplied by the authors)
**Status:** manuscript edited; nothing posted to OpenReview. No experiment was run and no ledger
entry was added.

## Facts

- The three official reviews (GmoA, ot4K, zdRG; ratings 2, 1, 2) were written against the PDF
  submitted on 2026-09-17: one cohort, 192 held-out prompts, 384 marked sequences per model,
  single edits only.
- The latest manuscript is `paper/manuscript/source/main.tex`, identical in text to
  `paper/submission/arxiv_2026-10-03/main.tex`. It already contains the detection cohort
  (1,544 held-out prompts), the edit-rate series, the window-score selection, the strength analysis,
  the search cost, and the Carbon protocol audit. Several review comments were therefore already
  answered by existing text.
- This pass edits `main.tex` only where a review comment was not yet answered in the text. Every
  added sentence is either a statement of scope, a description of what was not measured, or a
  restatement of a number already in the manuscript.
- The reviews are reproduced verbatim at the end of this note. Mathematical symbols were lost when
  the review text was copied; those gaps are marked `[symbol lost in copy]`.

## Checks

| Check | Result |
|---|---|
| Numerals, before and after | removed: none. Added occurrences: `384` ×1, `3,072` ×3, `3,456` ×1, `45` ×1, `19` ×1. No numeric value appears that was not already in the manuscript. |
| `\label` and `\cite` keys | unchanged. New `\ref` uses point to existing labels only. |
| Build (`paper/scripts/build.sh`, tectonic) | 17 pages, no undefined references; three pre-existing underfull boxes. `paper/manuscript/main.pdf` updated from the build. |
| `python3 scripts/check_evidence.py` | fails only on the five known missing Carbon development-cohort files, as before this pass. |
| Unit tests | 138 run, 8 skipped, all pass. `tests.test_synthid_position_independent` (11 tests) passes. |
| `paper/submission/arxiv_2026-10-03/` | untouched; it is the record of the arXiv submission. |

## Section and figure mapping

Reviewers cite the submitted PDF. The mapping to the latest manuscript is the table in
`2026-09-21_openreview_rebuttal_draft.md`. In short: submitted Table 1, Figure 2, and Figure 4 are
now Supplementary Table S1 and Supplementary Figures S1 and S2; submitted Section 4.3 is split
between Results (Detection and false-positive rate) and Supplementary Sections S1, S5, S6, and S7;
submitted Section 6 is Limitations.

## Comment-by-comment status

Status values: **answered** (existing or new text addresses the comment with measured evidence),
**scoped** (the manuscript now states the gap as a limitation; no measurement exists),
**open** (needs new evidence or an author decision).

### Reviewer GmoA

| Comment | Status | Where in the manuscript | Basis |
|---|---|---|---|
| W1, Q1: no comparison of the full search with aligned, phase-only, or adapted window-search detectors at a common false-positive target; cost not justified | scoped | Limitations, second paragraph (new sentences); Discussion, first paragraph (new: the verifier is assembled from existing parts) | No such comparison exists. Runtime of the full search is in Supplementary Section S4 (`synthid.v2.detector.search_seconds_per_read`, `peak_memory_mib`). |
| W2, Q2: one continuation length, fixed prompt, phase and strand not varied; shorter fragments, longer flanks, more edits | scoped for layout; answered for edit burden | Abstract (new sentence); Methods, Prompts and cohorts (new sentence); Limitations, new third paragraph; Discussion, margin paragraph; Results, Detection as edits accumulate (existing) | Layout facts follow from the cohort design: 384-base prompt = 64 tokens, forward strand, 3,072-base continuation. Edit burden: `synthid.v3.*` entries. |
| Q3: cause of the Carbon protocol-hash discrepancy; which configuration produced the results; reproducibility with a consistent record | answered as far as known | Limitations, fourth paragraph (three new sentences) | `docs/research/carbon_provenance_discrepancy_audit_2026_09_21.md` (cause unrecoverable; run used detector-code defaults; runner only hashed the document); `docs/research/synthid_v2_fpr_direct_a100_execution_2026_09_21.md` (protocol digest matches for both models in the detection cohort). |

### Reviewer ot4K

| Comment | Status | Where in the manuscript | Basis |
|---|---|---|---|
| W1: instantiation, not method; one scheme only | scoped | Discussion, first paragraph (new); Background (existing: "propose no new construction"); Limitations, second paragraph | Statement of contribution, no measurement. |
| W2, Q4: weakest sequence 124.8 versus 19.6; relate strength to per-token entropy; does portability survive | answered for the gap; scoped for entropy | Results, Detection and false-positive rate (existing); Supplementary Section S6 (existing); Discussion, margin paragraph (new sentence) | `synthid.v2.strength_gap.*`. Per-token entropy was not measured; the manuscript says so in two places. |
| Q1: broad baselines, biased and distribution-preserving | scoped | Limitations, second paragraph (added "or another distribution-preserving scheme") | Outside repository scope (`CLAUDE.md`: no other watermark constructions). |
| Q2: region length between grid points | scoped | Discussion, margin paragraph (new sentence); Limitations, third paragraph | Design consequence of fixed window lengths; not measured. |
| Q3: detection across continuation lengths | scoped | Limitations, third paragraph; Discussion, margin paragraph | Not measured for the position-independent verifier. See open item 1. |
| Q5: what method would suit the task | answered as a direction, not a result | Discussion, synchronization paragraph (new sentences) | Uses two existing numbers: about 19 times (`synthid.v2.detector.effective_independent_windows`) and about 45% (`synthid.v2.detector.correct_key_strength_by_condition`). Marked "We evaluated neither." |

### Reviewer zdRG

| Comment | Status | Where in the manuscript | Basis |
|---|---|---|---|
| W1: generated region always a suffix; no internal region, two flanks, or cropping; no curve over region length, flank length, placement | scoped | Abstract; Methods, Prompts and cohorts; Limitations, third paragraph | As GmoA W2. The implementation tests named below cover flanks and reverse complement on a synthetic region only. |
| W2: number of edits, edit location, clustered indels, longer indels, recombination, cropping, score-aware edits | answered for edit count and for indels of one to five bases; scoped for the rest | Results, Detection as edits accumulate (existing); Limitations, edit paragraph (new sentences) | `synthid.v3.*`. Score-aware editing is outside the threat model (`docs/threat_model.md`). |
| W3: validity of the binomial null under the full search; calibration across keys, ordinary corpora, wrong-key controls | partly answered; rest scoped | Limitations, new paragraph after the false-positive paragraph; Supplementary Section S7 (one clause added); Results and Supplementary Section S3 (existing realized rates) | `synthid.v2.detector.empirical_familywise_rate`, `synthid.v3.*.edit_rate_null_rate`, Table 1 wrong-key cells. No calibration across many keys or on non-generated genomic DNA exists. |
| W4: 192 prompts give limited precision near 1% | answered | Results, Detection and false-positive rate; Table 1 (existing) | `synthid.v2.detector.fpr_upper_bound`. |
| W5: the 64 reserved prompts, the two candidates, the criterion, the choice, and whether other settings changed | answered, with one author confirmation outstanding | Supplementary Section S1 (existing, one new sentence) | `docs/research/synthid_position_independent_detector_protocol.md`: no calibration prompts fit the decision rule; window lengths are protocol settings. See open item 4. |

## Source of each added sentence

| Added text (location) | Source |
|---|---|
| "Every test sequence had the same layout ... remain untested." (Abstract) | Cohort design in Methods; no new number. |
| "Every test sequence therefore has the same layout ..." (Methods) | 384-base prompt is 64 six-base tokens; continuations are generated on the forward strand after the prompt. |
| "The verifier is assembled from existing parts ..." (Discussion) | Background already cites Kirchenbauer et al. 2024 for span search with calibrated false-positive rate. |
| "A region whose length falls between two window lengths ..." (Discussion) | Follows from the fixed window lengths and the dilution property stated in Methods. Not a measurement. |
| "The margin also varies between sequences ..." (Discussion) | Supplementary Section S6; `docs/research/cross_model_strength_analysis_2026_09_21.md` (entropy explanation remains a hypothesis). |
| "Two measurements indicate where a different verifier could gain ... We evaluated neither." (Discussion) | 19 times: Supplementary Section S3. 45%: Results, single-base edits. The two suggested directions are proposals, not results. |
| Narrower-detector comparison not made (Limitations) | No such run exists in the ledger. |
| "All test sequences share one layout ..." (Limitations) | Cohort design. Implementation-test sentence: `tests/test_synthid_position_independent.py`, `test_finds_one_watermark_after_two_different_unknown_prefix_lengths` (prefixes of 7 and 71 bases, with suffixes) and `test_reverse_complement_has_the_same_complete_search_result`. Both use a synthetic region sampled from a uniform toy distribution and one window length. |
| Cause unknown; run used code defaults; detection cohort hash matches (Limitations) | Audit and execution documents named above. |
| Null-validity paragraph (Limitations) | Two published keys with one domain label per model and cohort: `docs/research/synthid_v2_fpr_scaling_protocol_2026_09_21.md`. |
| Edit types not tested (Limitations) | `docs/research/synthid_v3_edit_rate_protocol_2026_09_24.md`: positions drawn without replacement from a hash stream; indel lengths one to five bases. |
| "No other verifier setting was fitted to the reserved prompts ..." (Supplementary Section S1) | Detector protocol, sections "One sequence-level decision" and "Fixed public configuration". |
| "... and it is not a calibration of the full search" (Supplementary Section S7) | The aligned diagnostic searched one hypothesis per sequence. |

## Open items

These cannot be closed by wording. Each needs a decision, and items 1 to 3 need a new evidence
identity under a documented protocol.

1. **Region length, flank length, placement, strand, and phase (all three reviewers).** No
   measurement exists. A rescoring study on the stored detection-cohort sequences could truncate
   continuations, add unmarked flanks, and reverse-complement, without new generation. It is not a
   multiple-edit or detector-guided experiment, but it is a new experiment and needs its own
   protocol and namespace.
2. **Narrower-detector comparison (GmoA W1, Q1).** Aligned, phase-only, and full search on the same
   stored sequences at the same sequence-level target, with runtime. Rescoring only.
3. **Null calibration across keys and on non-generated DNA (zdRG W3).** The full search scored with
   many independent keys on ordinary sequences and on RefSeq windows.
4. **Author confirmation for zdRG W5.** The manuscript now says no other verifier setting was fitted
   to the reserved prompts. The reviewer also asks whether any part of the detector design was
   modified after outcomes were observed. The repository documents cannot answer that about the
   authors' process; an author should confirm before the rebuttal states it.
5. **Existing GENERator aligned-prefix artifact.** `outputs/generator_synthid_e16_v1/detection_summary.json`
   records aligned, forward, phase-zero detection of 384 held-out marked continuations at 384, 768,
   1,536, and 3,072 bases, and null rates for an independent key on ordinary output and on RefSeq
   windows. It bears on items 1 to 3, but only for GENERator, only with phase and boundary known,
   and at a per-test threshold without the search correction. The file classifies itself as
   `validation_artifact_not_admitted_evidence`, and only its ordinary null fit is in the ledger. It
   was **not** used in this pass. Admitting more of it is an evidence decision.
6. **Other watermark constructions (ot4K W1, Q1).** Excluded by repository scope. The manuscript
   states the absence as a limitation.
7. **Per-token entropy versus strength (ot4K W2).** Needs model inference on stored sequences.
8. **Venue format.** The edited source is the two-column arXiv layout with author names. An ICLR
   revision needs the ICLR style and anonymization; neither was done here.
9. **Presentation scores (2 from all three reviewers).** No reviewer names a specific passage. The
   2026-09-30 language pass postdates the submitted PDF. No further prose changes were made.

## Assumptions

- "Latest paper version" means `paper/manuscript/source/main.tex`.
- "Integrate the review comments" means revising the manuscript text within admitted evidence, not
  running experiments and not drafting the OpenReview responses.

## Reviews as received

Copied from the OpenReview page on 2026-11-12.

### Reviewer GmoA

Official Review by Reviewer GmoA, 22 Oct 2026, 03:20 (modified: 06 Nov 2026, 14:28)

**Paper Summary:**
This paper presents a position-independent verifier for watermarked DNA generated by genomic language models. It uses the existing SynthID tournament watermark and searches both strand orientations, every nucleotide starting position, and four window lengths to accommodate unknown token alignment and generation boundaries. A Bonferroni correction converts the strongest window-level evidence into a read-level significance decision. Experiments on Carbon-500M and GENERator-v2 1.2B detect all 384 held-out marked reads per model, both unedited and after each tested single-base substitution, insertion, or deletion. Ordinary-output and wrong-key controls produce at most one positive per 384 reads in each condition. No statistically significant differences are observed across 14 prespecified sequence-quality proxies after correction.

Presentation: 2: Generally understandable, but requires substantial effort in places.
Informativeness: 2: I learned something interesting or useful.
Soundness: 2: I have minor or fixable concerns about the paper’s soundness.

**Critical Strengths:**
Explicit treatment of synchronization uncertainty and statistical significance. The verifier incorporates strand orientation, token phase, starting position, and window length into a single corrected read-level decision. This prevents reporting the strongest searched window without accounting for the selection process.

Consistent empirical detection with appropriate controls and qualified conclusions. The evaluation includes two genomic models, ordinary-output and wrong-key controls, sampler-validation checks, and prompt-level uncertainty estimates. Complete detection under the tested single-edit conditions supports feasibility within the specified regime. The authors appropriately avoid interpreting nonsignificant quality differences as biological equivalence.

**Critical Weaknesses:**
The incremental benefit of the proposed verifier is insufficiently established. SynthID already supports detection without access to the generating model, while window-based watermark detection and Bonferroni correction are established techniques. The paper does not compare the combined search against aligned detection, phase-only search, or an adapted window-search baseline at a common false-positive target. Consequently, the results do not establish which components provide consequential improvements or whether their computational cost is justified.

The evaluation insufficiently characterizes the synchronization problem and operating limits. All continuations contain 3,072 bases and follow a 384-base prompt, which preserves the original six-mer phase relative to the read start. Boundary position, initial phase, and strand orientation are not independently varied. Robustness is restricted to one nonadaptive edit per continuation. Performance on shorter marked fragments, longer surrounding sequences, and greater edit burdens remains unresolved, limiting the demonstrated generality of position-independent verification.

**Questions For Authors:**
At the same read-level false-positive target, how does the proposed verifier compare with aligned, phase-only, and adapted window-search detectors in detection power and runtime?

How does detection change when marked-fragment length, surrounding-sequence length, boundary position, token phase, and strand orientation are varied independently? These measurements would clarify when the complete search is necessary and effective.

What caused the Carbon protocol-hash discrepancy acknowledged in Section 6? Which configuration produced the reported results, and can that execution be reproduced with a consistent protocol record?

Flag For Ethics Review: No
Rating: 2: Weak rejection
Confidence: 2: I have broad familiarity with this field but little or no direct research experience on this topic.

### Reviewer ot4K

Official Review by Reviewer ot4K, 21 Oct 2026, 07:32 (modified: 06 Nov 2026, 14:28)

**Paper Summary:**
This paper asks whether a generation time watermark can be recovered from DNA produced by a genomic language model when the verifier does not know how the sequence lines up. Both models studied, Carbon-500M and GENERator-v2 1.2B, emit nonoverlapping six base tokens, so token boundaries leave no trace in the sequence and six phases are possible. Reverse complementation changes token identity and order, and the generated region sits somewhere inside a longer read with no marked boundary. The authors take the SynthID-Text tournament watermark and build a verifier around this uncertainty. It scores four prespecified window lengths at every starting base on both strands, 16,136 windows for a 3,456 base read, and Bonferroni corrects over the whole search so that one read level decision can be reported at a declared 1% threshold. The experiments cover sampler fidelity, fourteen likelihood and sequence quality measures, detection on 192 held out prompts per model, and the effect of a single substitution, insertion or deletion on both detection and on which window length carries the strongest signal.

Presentation: 2: Generally understandable, but requires substantial effort in places.
Informativeness: 2: I learned something interesting or useful.
Soundness: 2: I have minor or fixable concerns about the paper’s soundness.

**Critical Strengths:**
Treating genomic provenance as a synchronisation problem. Hidden token boundaries and strand ambiguity have no counterpart in text watermarking, and the paper is the first I know of to state the problem in this form and attach a calibrated decision procedure to it.

**Critical Weaknesses:**
W1. Contribution is instantiation rather than method. The watermark is SynthID-Text used unchanged, and the verifier applies a standard Bonferroni correction over an exhaustive alignment search. No new estimator, null model, or search strategy is introduced from its analysis insights. Evaluation is also confined to one scheme. Section 2.2 separates biased schemes such as KGW from distribution-preserving ones, but only the latter is instantiated and the two families are not compared.

W2. Cross-model claim rests on two points without accounting for their spread The weakest marked read scores 124.8 in Carbon and 19.6 in GENERator against a common threshold of 6.21, and the paper concludes portability without addressing the gap. A six fold difference in log units suggests the available watermark signal is model dependent, which matters because it predicts divergent behavior precisely in the short continuation and long read regimes that were not evaluated. Relating per read strength to per token entropy would test this.

**Questions For Authors:**
Can the authors report a broad range of baselines, such as biased schemes and additional distribution-preserving methods?
The continuation length of 3,072 bases coincides exactly with the longest window in the grid. How does detection behave when the generated region length falls between grid points?
All experiments use a single continuation length. Since shorter regions give fewer scored bits while the threshold stays nearly the same, can the authors report detection across a range of continuation lengths?
What accounts for the gap between 124.8 in Carbon and 19.6 in GENERator, and does the portability claim survive it?
Given the observed insights, what kind of method would be good for this task?

Flag For Ethics Review: No
Rating: 1: Clear rejection
Confidence: 3: I am familiar with this topic and its relevant literature.

### Reviewer zdRG

Official Review by Reviewer zdRG, 21 Oct 2026, 02:18 (modified: 06 Nov 2026, 14:28)

**Paper Summary:**
This paper studies watermark verification for DNA generated by genomic language models when the verifier does not know the strand orientation, 6-mer token phase, or location of the generated region. It instantiates the existing SynthID tournament watermark and proposes a verifier that scans both strands, every nucleotide start, and four window lengths. It computes a binomial-tail statistic for each candidate window and applies a Bonferroni correction to obtain one read-level decision.

Presentation: 2: Generally understandable, but requires substantial effort in places.
Informativeness: 2: I learned something interesting or useful.
Soundness: 2: I have minor or fixable concerns about the paper’s soundness.

**Critical Strengths:**
The paper identifies a concrete and practically relevant issue for genomic watermarking: unlike tokenized model outputs, a nucleotide read does not expose the original token phase, strand orientation, or generation boundary.

The detector is clearly specified. In particular, the paper correctly treats the final decision as a multiple-testing problem over the entire search space, and Eq. 3 uses a conservative correction that does not require overlapping windows to be independent.

**Critical Weaknesses:**
In Sections 3.4 and 4.3, every evaluated read has the same structure: a 384 bp prompt followed by a 3,072 bp generated suffix. The generated region is therefore always at the end of the read, rather than at an unknown internal position with unrelated DNA on both sides. Table 1 and Figure 4 establish detection for this fixed suffix geometry with one edit, but not for a generated segment embedded within arbitrary surrounding DNA. How does the detector behave when the generated segment occurs in the middle of a read, when both flanks are non-generated, or when the observed read is randomly cropped? This distinction matters because additional flanking sequence increases the number of searched windows [symbol lost in copy] and hence the Bonferroni penalty, while shorter generated segments contain less cumulative watermark evidence. Section 5 acknowledges this tradeoff qualitatively, but the paper does not characterize detection strength as a function of generated-region length, flank length, or segment placement.

Table 1 evaluates exactly one randomly selected, nonadaptive substitution, insertion, or deletion per read. Figure 4 provides a plausible qualitative explanation for why the detector can retain evidence after one indel, but it does not characterize the synchronization behavior beyond that setting. How does recall or window strength change with the number of edits, edit location, clustered indels, longer insertions/deletions, recombination, cropping, or score-aware modification? The current results leave unclear whether the proposed search resolves a general synchronization problem or only recovers sufficient aligned evidence after one mild perturbation.

Equation 2 treats reconstructed null mark bits as independent fair binary variables. Bonferroni controls the family-wise error rate without requiring different windows to be independent, but it still requires each window-level [symbol lost in copy] to be valid under the stated null. The only empirical diagnostic is the aligned GENERator ordinary-output analysis in Section 4.3, which observes [symbol lost in copy] positives across four lengths, versus roughly five expected at each length. This is not a calibration test for the deployed procedure, which searches both strands, every start position, and multiple window lengths. Does the assumed binomial null remain valid after HMAC construction, context reconstruction, repeated-context handling, and the full scan over candidate alignments? The paper does not provide full-search read-level [symbol lost in copy]-value calibration across independent keys, ordinary corpora, and wrong-key controls.

At the prompt level, the 95% upper bound on the false-positive rate is 1.90% when no control prompt is positive and 2.87% when one is positive. Thus, Figure 2 and Table 1 establish only that the observed controls are compatible with the nominal 1% target, not that the operational false-positive rate is below 1%. Given that the claimed verifier is defined around a declared 1% read-level threshold, the current control sample has limited precision in the relevant tail regime.

Section 4.3 states that 64 prompts were reserved for selecting between two window-score summaries, but it does not define the candidate summaries, the selection criterion, the selected option, or whether this process affected any other detector settings. What exactly was chosen using these prompts, and was any part of the detector design modified after observing their outcomes?

**Questions For Authors:**
See questions in weaknesses.

Flag For Ethics Review: No
Rating: 2: Weak rejection
Confidence: 3: I am familiar with this topic and its relevant literature.
