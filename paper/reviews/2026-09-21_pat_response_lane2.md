# Lane 2 — PAT response implementation

**Date:** 2026-09-21
**Scope:** claims, LaTeX, and background work from the Paper Assistant Tool feedback on ICLR 2027
submission 32263 (posted 2026-09-17).
**Files written:** `paper/manuscript/source/main.tex`, `paper/manuscript/source/refs.bib`,
`docs/threat_model.md` (prose only), and this directory. No evidence, output, script, config,
figure, or protocol file was touched.

## AD-5 resolved: the submitted PDF is a separate lineage, not a newer source

The lane plan assumed the repository source was behind the submitted PDF. Comparison of
`32263_Tracing_model_generated_.pdf` (14 pages) against `git show HEAD:paper/manuscript/source/main.tex`
(12 pages after this pass, 10 before) shows something different: the two documents are parallel
renderings of the same study, and the ICLR source was never committed.

Facts established by the comparison:

- Methods (§3.1–§3.7), Limitations, and Conclusion are word-for-word identical apart from
  hyphenation and citation rendering.
- Section numbering is identical through §7. Every "Target location" in the lane plan resolved
  without change.
- Every reported number is identical in both documents: 13/5 nominal rejections against 12.8
  expected, ordinary-arm 12 and 14, adjusted `P` 0.85 and 0.73, +0.00852 and −0.00564 nats,
  `M = 16,136`, threshold 6.21, 383/381, 203/200, 232/227, 384/384.
- The abstracts differ wholly. The PDF frames the contribution as a verification framework; the
  repository abstract frames it as integrating SynthID and adds a portability claim and an
  explicit non-claims sentence.
- Four Discussion sentences and one Introduction sentence differ. The repository Results section
  carries an opening paragraph the PDF lacks.
- The PDF is anonymized ICLR single-column with line numbers; the repository is the non-anonymous
  two-column lab layout with a different title.

### Figure and section mapping

| Item | Submitted PDF | Repository source |
|---|---|---|
| Method schematic | Figure 1, body, p. 4 | Figure 1, body |
| Detection results | Figure 2, body, p. 7 | Figure 3, body |
| Quality proxies | Figure 3, **Appendix A**, p. 13 | Figure 2, body |
| Single-base edits | Figure 4, **Appendix A**, p. 14 | Figure 4, body |
| Detection table | Table 1, p. 7 | Table 1 |
| AI Use / Ethics / Reproducibility | pp. 10, unnumbered | added by this pass |
| Data and code / Competing interests / Acknowledgments | absent (anonymized) | present |

PAT's section numbers therefore apply to the repository source unchanged. PAT's figure numbers do
not: read PAT's "Figure 3" as the quality figure and its "Figure 2" as the detection figure.

### Consequence for the three statements

The AI Use, Ethics, and Reproducibility statements exist only in the submitted PDF. They were
transcribed into the repository source rather than reconstructed from the OpenReview form. The
Ethics and Reproducibility statements are the submitted text with section numbers replaced by
`\ref` and compound modifiers hyphenated to match repository style. The AI Use statement is the
submitted text with one correction, described under L2-09 below.

## What landed

| Task | PAT point | Location | Note |
|---|---|---|---|
| L2-01 | W5a | §3.5 | names the likelihood-ratio (G) statistic and the parametric Monte Carlo null; gives ~1.2 expected count per category as the reason |
| L2-02 | W5b, R4 | §4.1 | Benjamini–Hochberg primary, Bonferroni at α/256 = 1.95 × 10⁻⁴ recorded; neither arm rejects under either |
| L2-03 | W6, R1 | §4.3 | both candidate summaries named, selection statistic named, calibration-only data named, outcome stated |
| L2-04 | T6 | §4.2 | longest single-base run (Carbon), mean single-base run (GENERator) |
| L2-05 | M2 | §3.3 | Bonferroni conservatism on correlated windows; control counts framed as an upper bound |
| L2-06 | M3 | §3.3 | 60 scored tokens and 1,800 mark bits at 384 bases, 1,004 bits required; binding constraint is the 384-base minimum window |
| L2-07 | M5 | §3.3 | complexity of the implemented search |
| L2-08 | W1, M4, R2, D1 | Limitations | edit-rate boundary as declared scope, derived from L2-06 |
| L2-09 | W9, A1 | AI use statement | added, with the proofs claim corrected |
| L2-10 | A2 | Reproducibility statement, Data and code | verifier, sampler, cohort scripts, protocols, ledger named |
| L2-11 | T1–T5, T7 | — | no change needed; see below |
| L2-12 | B1 | §2.2 | text-domain locality versus permanent frameshift |
| L2-13 | W2, R5 | §2.2, Discussion | four-axis property comparison; empirical baseline declined and its absence stated |
| L2-14 | B2 | §2.4 | phase problem scoped to multi-mer tokenization |
| L2-15 | B3 | §2.3 | local context is standard, not unique to SynthID; hedge preserved |
| L2-16 | W3, R6, D3 | Limitations | standardized in-silico benchmarks as future work |
| L2-17 | W4 | Limitations | inconclusive branch: cohort not scaled, order-of-magnitude requirement stated |
| L2-18 | W8, D2 | Limitations | unresolved branch, with the governed parameters enumerated |
| L2-19 | W7, R3 | §4.3 | inconclusive branch: margin difference not attributed |

No new empirical number was introduced. Every figure quoted in the added text is either already in
the manuscript or exact arithmetic on values already in it.

## Deviations from the lane plan, and why

**L2-07 — the O(1) per-window claim was wrong for the implemented code.** The lane plan drafted
"each of the M windows is evaluated in constant time". `src/genomic_watermarks/synthid_boundary.py`
computes mark bits in a single pass per phase (`_prepare_phase`, one `g_mask` call per token
yielding all 30 layer bits), then takes the prefix-sum path only when a phase trace contains no
repeated four-token context. When repeats exist, the first-occurrence rule is enforced with two
Fenwick trees and each window costs O(log N). The manuscript now states both paths and reports
O(N) keyed hash evaluations with O(N log N) additional time and O(N) space. The plan's acceptance
gate required exactly this check.

**L2-03 — the selection used two lengths, not four, and did not use the window search.**
`outputs/generator_synthid_e16_v1/detector_comparison.json` records `token_lengths` 64 and 512,
that is continuations of 384 and 3,072 bases, scored on the 64 calibration prompts. The plan's
"at each window length" is wrong twice over: there were two lengths, and they were scored under
known token alignment rather than by the position-independent search. No value from that artifact
is quoted, since it is classified `validation_artifact_not_admitted_evidence`; the audit below
removed the trial count for the same reason.

**L2-09 — the correction is narrower than the plan assumed.** The submitted statement claims
assistance with "mathematical reasoning and proofs". PAT is right that the paper contains no
proofs. The replacement says "statistical derivations", keeps every other declared category, and
adds an explicit sentence that the paper contains no formal theorems or proofs. The disclosure was
not narrowed elsewhere; PAT's complaint was inaccuracy, not breadth.

**L2-11 — nothing to fix in the repository source.** A grep for ` mer`, `generation time`,
`base by base`, `decoder only`, `position independent`, `wrong key `, and `shift from prompt`
returns nothing in `main.tex`. Every unhyphenated form PAT flagged is present in the submitted PDF
only, in all eight cases. The Jovanović accent also renders correctly in the submitted PDF, checked
at 600 dpi; `refs.bib` already carries `Jovanovi{\'c}`. PAT's T1–T5 apply to the ICLR source, which
is not in this repository.

## Open items

- **T7 is not closed.** The submitted PDF's appendix figure (quality proxies) labels its axes
  "1-mer shift from prompt", "2-mer shift from prompt", "3-mer shift from prompt", while §3.6 reads
  "Jensen–Shannon drift". The text side is already correct in the repository. Relabelling the figure
  axes is Lane 1 work under `scripts/make_paper_figures.py`; the manuscript must not be edited to
  match a figure that still says "shift".
- **The ICLR source is not in the repository.** Whatever is submitted for the revision has to be
  reconciled against this source. Either the ICLR version is regenerated from `main.tex` under the
  conference template, or the two lineages continue to diverge. This pass changed only `main.tex`.
- **Carbon has no committed detector-comparison artifact.** Only
  `outputs/generator_synthid_e16_v1/detector_comparison.json` exists. The §4.3 selection sentence is
  written from that artifact and from `scripts/compare_synthid_detectors.py`. If the Carbon
  comparison produced a different outcome, the sentence is wrong for Carbon.
- **Part C is on its default branches.** L2-17, L2-18, and L2-19 use the inconclusive and unresolved
  branches, with no `\evtag` placeholders in the body, so the document is submission-clean as it
  stands. The `\evtag` macro is defined in the preamble for Lane 3. If Lane 1 lands
  `synthid.v2.*` numbers, the branch tables in the lane plan supply the replacements.

## Declines recorded in the paper

| PAT request | Where the paper declines it |
|---|---|
| Multiple-edit or higher-rate sweep | Limitations, edit-rate paragraph: outside the declared threat model, binding constraint identified |
| Red/green-list or other watermark baseline | §2.2 property comparison and Discussion: absence of a same-cohort comparison stated as a limitation |
| Downstream biological task evaluation | Limitations: named as the natural next step, no result implied |

## Build

`cd paper && ./scripts/build.sh` succeeds. No undefined references or citations. 12 pages, up from
10. Only underfull-hbox warnings remain.


## Post-implementation audit, 2026-09-21

Two read-only audits ran against commit `5ca5aed`: an evidence audit of every number in the diff and
a citation audit of the four new cited passages. Both found real defects. The corrections below are
applied.

### The mark-bit error, and how it survived three checks

The lane plan's L2-06 arithmetic treated the window's binomial statistic as one draw per scored
token. It is not. The sampler applies 30 tournament layers, each contributing its own mark bit, and
the detector sets `total = scored_per_window * tournament.depth`
(`src/genomic_watermarks/synthid_boundary.py:126,165`). Retained GENERator trials confirm it:
`g_total: 15240` for `scored_tokens: 508`.

Corrected figures, recomputed with an exact binomial tail at `alpha/M = 6.1973e-7`:

| Quantity | Published in the plan | Correct |
|---|---|---|
| Binomial n at a 384-base window | 60 | 1,800 |
| Minimum positive bits | 49 of 60 | 1,004 of 1,800, about 56% |
| All-positive floor | 21 scored tokens | 21 mark bits, i.e. one scored token |

The consequence is not cosmetic. The "21 scored tokens" figure was the quantitative premise of the
L2-08 edit-rate argument, of the threat-model addition, and of the M3 and W1 rebuttal responses. The
argument survives, but its binding constraint is the shortest evaluated window, 384 bases, not a
mark-bit floor. All four locations now say so.

This error passed three checks before the audit caught it. The lane plan asserted the arithmetic had
been "independently verified". The acceptance gate said to recompute before publishing, and the
recomputation was done — but against the n the plan supplied, not against the n the detector uses.
The detector source was read during the same session, for L2-07, and the `* tournament.depth` line
was read without its significance registering. Checking an author's arithmetic is not the same as
checking their model of the system.

Note also that PAT's own M3 figures carry the same error: the review computed 49 of 60 independently
and arrived there by assuming one mark bit per token. The rebuttal now corrects the reviewer rather
than agreeing with them.

### Other corrections applied

| Severity | Issue | Fix |
|---|---|---|
| High | "the committed artifacts include the summaries and digests needed to re-derive every reported value" was false: `.gitignore` excludes `outputs/*`, and no Carbon artifact is committed | restricted to the GENERator summaries; Carbon result files stated as available on request |
| High | "128 trials per arm" resolved to no ledger entry, and its artifact self-labels `validation_artifact_not_admitted_evidence` | number removed; the selection is now described qualitatively |
| Medium | Bonferroni at `alpha/256 = 1.95e-4` is unattainable: 999 Monte Carlo replicates bound the p-value below at 1e-3, so the non-rejection was structurally guaranteed rather than empirical | §4.1 now states the bound and that the Bonferroni result carries no information at this family size |
| Medium | §2.3 dropped the mandatory hedge on the consequence clause of distribution preservation | reworded to expectation over fresh keyed functions, with fixed-key sampling following the reweighted law |
| Medium | "exceed the threshold by orders of magnitude" misreads a quantity that is already a logarithm; 19.6 against 6.21 is a factor of 3.2 | restated as 13.4 and 118.6 orders of magnitude in the window p-value |
| Medium | the detector-selection comparison scored continuations under known token alignment, not the position-independent window search | §4.3 now says so, and drops "window lengths" for "continuation lengths" |
| Low | "model likelihood and the 14 declared sequence summaries" implies 15 measures; likelihood is one of the 14 | corrected |
| Low | `r = 1%` attributed to long-read sequencing without a citation | restated as illustrative |
| Low | "twelve reading frames" collides with §2.4's own disclaimer that phase is not a coding frame | "twelve token frames" |

### Citation corrections

| Severity | Issue | Fix |
|---|---|---|
| Critical, pre-existing | `dathathri2024scalable` listed `Kushman, Nenad` and `Tarassov, Eugene`, who are not authors of that paper, and `Chen, Rob` for `McAdam, Rob`. This is the paper's central citation and predates this lane | author list replaced with the 24 authors of Nature 634(8035):818--823 |
| High | `wu2024dipmark` was grouped under "recover synchronization by alignment to a key sequence". DiPmark targets edit robustness but detects by a context-hashed green-list statistic, not alignment | the two mechanisms are now distinguished, one citation each |
| High | "related constructions use sliding windows" was uncited, and `haeupler2017synchronization` was made to carry a watermarking claim it cannot support | added `kirchenbauer2024reliability` (WinMax: searches all contiguous spans, calibrates under that search) and `golowich2024edit` (indexed pseudorandom codes); Haeupler now supports only the coding-theory clause |
| Low | missing page ranges on `wu2024dipmark` and `haeupler2017synchronization` | added |

The WinMax citation matters beyond correctness. Searching all spans and correcting for that search
is the text-domain analogue of this paper's verifier, and not citing it left an attribution gap. The
genuine novelty — the six-phase by two-strand dimension, which has no text analogue because text
tokenization has no frame — is unaffected and now stands against a named baseline.

### Still open

- `synthid.carbon.sampler.nominal_rejections` carries no Benjamini--Hochberg or Bonferroni field,
  and the Carbon artifact is not committed, so §4.1's "under either correction in either model" is
  not independently checkable for Carbon. This needs an evidence-side fix, which is outside Lane 2's
  write boundary.
- `check_evidence.py` fails on five missing Carbon artifacts. Pre-existing and documented in
  `paper/context/evidence_map.md`, but it makes every Carbon claim indirectly verified only.
- The GENERator trials show `repeated_contexts: 0` for 4,534 of 4,608 best hypotheses, which largely
  excludes repeated-context exclusion as the explanation for the strength gap in that model. The
  §4.3 candidate list could be narrowed once Lane 1 reports.
- `christ2024undetectable` is grouped as distribution-preserving; it targets the strictly stronger
  property of computational undetectability. Defensible as written, worth a qualifier.
- The `\evtag` macro is defined and unused. It is scaffolding for Lane 3 and must be removed before
  submission.
