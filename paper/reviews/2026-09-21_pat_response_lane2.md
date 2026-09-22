# Lane 2 — PAT response implementation

**Date:** 2026-09-21
**Scope:** claims, LaTeX, and background work from the Paper Assistant Tool feedback on ICLR 2027
submission 32263 (posted 2026-09-17).
**Files written:** `paper/manuscript/source/main.tex` only. No evidence, output, script, config,
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
| L2-06 | M3 | §3.3 | 60 scorable tokens at 384 bases, 49 of 60 required, 21-token floor |
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

**L2-03 — the selection used two window lengths, not four.**
`outputs/generator_synthid_e16_v1/detector_comparison.json` records `token_lengths` 64 and 512,
that is 384 and 3,072 bases, at 128 trials per arm on the 64 calibration prompts. The manuscript
says "at the shortest and longest of the four window lengths". No separation value is quoted: that
artifact is classified `validation_artifact_not_admitted_evidence`, so only the procedure is
described.

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
