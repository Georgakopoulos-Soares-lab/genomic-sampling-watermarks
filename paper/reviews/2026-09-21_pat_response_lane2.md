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

## Assumption register

The lane plan carried six assumptions. Their status after implementation and audit:

| ID | Assumption | Status |
|---|---|---|
| `ASM-01` | the clean-stretch length ≈ 1/r is an order-of-magnitude heuristic, not a measurement | **holds, and is now stated in the manuscript itself** — the Limitations paragraph says so in its own words, so the assumption is disclosed to the reader rather than only logged here |
| `ASM-02` | any new false-positive-rate run keeps the 1% target and the four window lengths | **untested.** Lane 1 has not reported. The L2-17 text is on its inconclusive branch, which does not depend on this assumption; it becomes load-bearing only if a `synthid.v2.*` number lands |
| `ASM-03` | the 124.8 and 19.6 strength values and the 6.21 threshold are stable | **holds.** All three traced to the ledger during audit: `synthid.detector.strength_separation` 124.78, `synthid.generator.detector.strength_separation` 19.614794, `threshold_strength_clean` 6.207795885205 |
| `ASM-04` | `M = 16,136` and α = 0.01 hold for the reads discussed | **holds**, and `M` was confirmed independently from `hypotheses_searched: 16136` in every retained trial. But see `ASM-07`: this register named the wrong variables |
| `ASM-05` | the submitted source will be supplied and its section titles match the repository's | **superseded.** The submitted source was never committed; the PDF comparison established that section titles and numbering match anyway, so every target location resolved. See the AD-5 section above |
| `ASM-06` | the figure axes will read "Jensen–Shannon drift" | **outstanding.** Lane 1 work. The manuscript text is correct; the submitted PDF's appendix figure still reads "shift from prompt" |

One assumption was missing, and it is the one that failed:

| ID | Assumption | Status |
|---|---|---|
| `ASM-07` | the window-level binomial statistic is taken over one mark bit per scored token | **false.** The statistic is taken over `depth = 30` mark bits per scored token (`src/genomic_watermarks/synthid_boundary.py:126`). Every figure in L2-06 and every claim resting on it changed. See the audit section above |

`ASM-04` tracked the two parameters the lane plan happened to name, `M` and α, and treated the
window geometry as self-evident. Tournament depth enters the same arithmetic and was never listed,
so the register gave false assurance: all four of its named inputs were correct while the result was
wrong by a factor of 30 in the floor. A register is only as good as its coverage of the inputs, and
coverage was assumed rather than derived from the code.

## Deep-research pass, 2026-09-22

The lane plan's Part B carried four research prompts. They were run after the prose landed, which
means the prose was written from references already in the bibliography and the research then tested
it. Two of the four findings changed what the manuscript claims rather than merely supporting it.

### L2-16 contradicted the text that cited it

The Limitations paragraph called a standardized benchmark study "the natural next step before any
claim about biological consequence". The sweep found that **no standardized public benchmark, as of
September 2026, scores de novo generated sequence**. BEND, GenBench, GENEB, Genomic Benchmarks and
the Nucleotide Transformer task set are probe-or-finetune protocols: a metric exists only because a
held-out label tied to a genome coordinate exists, and a generation carries neither. DART-Eval's
motif-footprinting task needs no coordinates, but motif presence is itself the ground truth.

The paragraph now states that the suites do not transfer, and that closing the gap requires either a
paired design — a generated sequence scored against a deliberately altered copy of itself — or an
assay. The W3 rebuttal response was rewritten to match. This is a better answer to the reviewer than
the one the lane plan drafted: it engages with the specific benchmarks named instead of promising to
use them.

### L2-12 replaced an appeal to novelty with a falsifiable claim

The §2.2 argument originally asserted that frameshift is structurally different from text-domain
desynchronization. It now rests on a specific case: context-free green lists \cite{zhao2024provable}
remove key desynchronization entirely — the strongest case available — and would still fail here,
because the failure under frameshift is destruction of token identity rather than desynchronization
of the key. A shifted six-mer is a different vocabulary item carrying an independent mark bit.

The converse is also now stated: `hou2024semstamp` is tokenization-independent by construction, and
fails for a different reason — it needs an encoder at verification and a natural segmentation into
units, and we have neither.

The Discussion gained `davey2001reliable`, the canonical treatment of offset as a latent drift
variable integrated out by an HMM rather than enumerated as hypotheses. It presumes control of the
encoding, which a sampling watermark lacks, which is precisely why our verifier searches and
corrects instead.

### L2-14 found a property of one of our own models

GENERator's tokenizer "introduces a randomized starting position between 0 and 5 for each sample" —
explicit phase augmentation at training time. §2.4 now records it, and records that it is a training
augmentation rather than a verification mechanism: it does not reduce the verifier's search.

The same pass tightened the scope of the phase claim. DNABERT's k-mers are overlapping, so every
frame is present at once and there is no phase to choose. For BPE models the ambiguity is unbounded
re-segmentation, not a mod-k phase, and cannot be resolved by trying k offsets. The manuscript's
claim is now explicitly about fixed non-overlapping k-mer tokenization.

### Bibliographic verification

Eight entries were added. Two of the author lists supplied by the research agents were wrong:

- `hou2024semstamp` listed an author who is not on the ACL Anthology page and omitted three who are.
  Corrected against `https://aclanthology.org/2024.naacl-long.226/`.
- `dathathri2024scalable`, found in the earlier citation audit, carried two people who are not
  authors of that paper at all. Pre-existing, not introduced by this lane.

The remaining six were checked against their arXiv listings and all matched exactly:
`nguyen2023hyenadna`, `schiff2024caduceus`, `zhao2024provable`, `marin2024bend`, `liu2024genbench`,
`patel2024darteval`. `davey2001reliable` is a 2001 IEEE Transactions paper and was not re-fetched;
its metadata is stable and widely reproduced, but it is the one new entry not checked against a
primary record in this pass.

Two entries were deliberately **not** cited despite being useful:

- Schwartzman, Gavrilov and Adler on peak detection as multiple testing would support the
  Bonferroni-conservatism argument in §3.3, but the journal version could not be confirmed.
- `GenBench` is cited as an arXiv preprint. Its NeurIPS 2024 record is a workshop poster under a
  different title with a different author list, and citing it as a NeurIPS paper would be wrong.

Both are recorded in `docs/research/literature_map.md` under "Do not cite without further checking",
along with the finding that no primary source supports the common secondary claim that BPE is more
indel-robust than k-mer tokenization.

### Lane 2 coverage after this pass

| Part | Status |
|---|---|
| Part A, L2-01 … L2-11 | complete, audited, corrected |
| Part B prose, L2-12 … L2-16 | complete |
| Part B research, four prompts | complete; two findings changed the text |
| Part C, L2-17 … L2-19 | complete on default branches |
| `docs/research/literature_map.md` | background section added |
| Assumption register | logged, with `ASM-07` added |

The lane plan is fully executed. What remains is not Lane 2 work: the Carbon evidence-ledger gap,
the figure axis relabelling for `TERM-1`, and whatever Lane 1's runs return.
