# Lane 2 — Claims, LaTeX and background work (WRITER)

**Date:** 2026-09-21
**Source of tasks:** Google Paper Assistant Tool (PAT) feedback on ICLR 2027 submission 32263,
posted 2026-09-17 11:49 as *LLM Feedback by Program Chairs* (note `LyX9i394f8`) on forum
`vo1qxcMxxx`.
**Owner:** the person with the manuscript, the bibliography, and agentic research tools.
**This document is self-contained. Do not read the Lane 1 document, and do not wait for it.**

## The one rule that makes this lane independent

> **Never type a number that is not already in `evidence/measurements.yaml`.**
> A number that does not exist yet is written as `\evtag{<evidence id>}`, and the sentence around
> it is drafted in **every** outcome branch below. Lane 3 substitutes the real value and deletes
> the unused branches.

Add this to the preamble of `main.tex` so the document always builds:

```latex
\newcommand{\evtag}[1]{\textbf{[EV:#1]}}
```

## Write ownership (hard boundary)

Lane 2 **writes** only: `paper/manuscript/source/main.tex`, `paper/manuscript/source/refs.bib`,
`docs/research/literature_map.md`, `docs/threat_model.md` (prose only, no scope change),
`paper/reviews/**`.

Lane 2 **never writes**: `evidence/**`, `outputs/**`, `scripts/**`, `configs/**`,
`paper/figures/**`, `docs/research/*protocol*`, `docs/research/*execution*`, `tests/**`.

Reading anything is allowed. Only writes are partitioned. In particular, Lane 2 **may** read
`src/genomic_watermarks/*.py` and `outputs/**` to document what the code already does — several
tasks below are exactly that, and they need no run.

## Shared constants, fixed now so neither lane waits

| ID | Constant | Value |
|---|---|---|
| `TERM-1` | canonical name of the k-mer distribution-shift metric, in text **and** figure axes | **Jensen–Shannon drift** (never "shift") |
| `NS-1` | evidence namespace for any new run in this cycle | `synthid.v2.*` |
| `TAG-1` | placeholder macro | `\evtag{<evidence id>}` |

Lane 1 is relabelling the figure axes to `TERM-1`. Lane 2 keeps "drift" in prose and captions and
does not touch the figures.

## AUTHOR DECISIONS required before some tasks can land

1. **AD-5 — The repository source is behind the submitted PDF. Settle this first.**
   `paper/manuscript/main.pdf` in the repository is **10 pages** and `main.tex` contains **no** AI
   Use Statement, Ethics Statement, Reproducibility Statement, or Appendix A. PAT reviewed a
   document whose pages 10–14 contain all four, and whose quality/edit figures are numbered 3 and 4
   in an appendix rather than 2 and 4 in the body. The submitted source is therefore a **later
   version that is not in this repository.**
   Before editing anything, the author must supply that source. Options:
   - (a) commit the submitted `main.tex` (and any appendix files) to
     `paper/manuscript/source/`, then edit it — **recommended**;
   - (b) edit the repository version and accept that PAT's section and figure numbers will not
     match, recording a mapping table;
   - (c) reconstruct the missing statements from the OpenReview submission form fields.
   **Every "Target location" below cites the repository numbering.** If (a) is chosen, re-resolve
   each location in the submitted source before drafting. Section titles, not numbers, are the
   reliable anchor.
2. **AD-2 (mirrors Lane 1) — edit-rate sweep.** `AGENTS.md` forbids multiple-edit experiments.
   This lane's answer (L2-08) is analytic and honest, and needs no run. If authors overrule and
   commission the sweep, L2-08's text becomes a forward reference instead of a boundary claim.
3. **AD-3 — competing-watermark baseline.** Forbidden by `AGENTS.md` / `PROJECT.md`. L2-12 declines
   it in prose. If authors want the experiment, the scope documents change first.
4. **AD-4 — downstream biological benchmarks.** Outside the declared claim boundary. L2-13 adds
   them as future work, which is what PAT's own Discussion segment proposes.

---

# Part A — Tasks answerable now, with no run and no research

These are documentation gaps. The answers are already in the repository; each is quoted with its
source so the writer does not have to hunt. **None of them depends on Lane 1.**

## L2-01 — Name the goodness-of-fit test statistic (PAT-W5a, PAT Methods "Ambiguity in Sampler Validation Test Statistic")

- **Why:** PAT: *"the exact test statistic … is not specified. Given the distribution's
  dimensionality (4,096 canonical 6-mer tokens) and the sample size (5,000 draws per state), the
  expected frequencies for many bins are very low (approximately 1.22)."* PAT's own diagnosis of
  *why* it matters is correct, and the code already handles it.
- **Type:** claim/method clarification. **No Lane 1 dependency.**
- **Target location:** `main.tex` §3.5 *Sampler validation* (repo line ~328).
- **Source of truth:** `src/genomic_watermarks/gof.py` — `g_statistic()` returns the
  likelihood-ratio (G) statistic against a fully specified law; the module docstring states the
  asymptotic chi-square reference is unreliable at this sparsity, so a **parametric Monte Carlo**
  reference is used instead.
- **Draft text** (replaces the sentence beginning "We compared the counts"):

  ```latex
  We compared the counts with the exact intended distribution using the likelihood-ratio
  ($G$) statistic, referred to a parametric Monte Carlo null of 999 replicates resampled from
  the declared law rather than to its asymptotic $\chi^2$ distribution. At 4{,}096 categories and
  5{,}000 draws per state the expected count per category is about 1.2, so the asymptotic
  reference is unreliable; the Monte Carlo reference is exact under the declared law by
  construction.
  ```

- **Acceptance gate:** the sentence names the statistic, names the reference distribution, and
  gives the reason. No number is introduced that is not already in the ledger.

## L2-02 — Name the multiple-testing correction for the 256 state tests (PAT-W5b, PAT Results "Unspecified Statistical Correction for Sampler Fidelity")

- **Why:** PAT: *"the specific multiple testing correction applied to the 256 state tests for
  sampler validation is omitted."*
- **Type:** claim clarification. **No Lane 1 dependency.**
- **Target location:** `main.tex` §4.1 *Sampler fidelity* (repo line ~369).
- **Source of truth:** `scripts/run_carbon_large_distribution.py` lines ~201–207 compute **both**
  Benjamini–Hochberg and Bonferroni; `outputs/*/distribution_summary.json` records
  `benjamini_hochberg_rejections`, `rejections_at_bonferroni`, and
  `bonferroni_alpha = 0.0001953125` (= 0.05/256), with
  `expected_rejections_under_null = 12.8`. Both corrections yield **0** rejections in both arms
  for both models. The nominal counts are already in the ledger
  (`synthid.carbon.sampler.nominal_rejections` = 13; `synthid.generator.sampler.nominal_rejections`
  = 5, ordinary arm 14).
- **Draft text:**

  ```latex
  The 256 per-state tests form one family per arm. We report Benjamini--Hochberg correction at
  $\alpha = 0.05$ as primary and also record Bonferroni correction at $\alpha/256 =
  1.95 \times 10^{-4}$. Neither the marked nor the ordinary arm produced a rejection under either
  correction in either model, against a chance expectation of 12.8 nominal rejections per arm.
  ```

- **Acceptance gate:** both corrections named; the "after correction" claim in §4.1 states which
  correction it means.

## L2-03 — Define the two window-score summaries and the selection rule (PAT-W6, PAT Results "Undefined Two Window Score Summaries")

- **Why:** PAT: *"the second summary metric and the selection criteria are not defined … Clarifying
  this is necessary to ensure the experimental protocol is fully reproducible."* This is the single
  most damaging reproducibility gap PAT found, and it costs one paragraph to close.
- **Type:** protocol clarification. **No Lane 1 dependency.**
- **Target location:** `main.tex` §4.3 *Recall and false-positive rate*, first paragraph (repo
  line ~410), with a cross-reference added in §3.3.
- **Source of truth:** `scripts/compare_synthid_detectors.py` (docstring: *"Compare released mean
  and weighted-mean SynthID scores on calibration prompts"*) and
  `outputs/*/detector_comparison.json`, which records for each window length a `mean` block and an
  `upstream_default_weighted_mean` block, the statistic
  `separation_in_ordinary_standard_deviations`, and `selected_detector: "mean"`. The comparison
  used the 64 calibration prompts only, 128 trials per arm, and the artifact states that
  evaluation prompts were never scored and no signal-matched weights were fitted.
- **Draft text:**

  ```latex
  The two candidate summaries were the released SynthID mean score over scored tokens and the
  upstream default weighted-mean score. They were compared on the 64 calibration prompts alone,
  at each window length, by the separation between the marked and ordinary arms in units of the
  ordinary-arm standard deviation. The mean score separated the arms at least as well at every
  length and was selected. Evaluation prompts were never scored during this selection and no
  signal-matched weights were fitted.
  ```

- **Acceptance gate:** a reader can reproduce the selection from the paper alone: both candidates
  named, the selection statistic named, the data used named, the outcome stated.

## L2-04 — Name the measures with the largest standardized effects (PAT Results minor correction)

- **Why:** PAT: *"does not explicitly name which of the 14 prespecified measures exhibited these
  maximum deviations."*
- **Type:** claim completion. **No Lane 1 dependency — the ledger already carries the names.**
- **Target location:** `main.tex` §4.2 *Sequence-quality proxies*, paragraph 2 (repo line ~379).
- **Source of truth:** `evidence/measurements.yaml`,
  `synthid.carbon.quality.metric_family_effects` → `largest_absolute_effect_metric:
  longest_homopolymer_run`, value 0.0837 s.d.; `synthid.generator.quality.metric_family_effects` →
  `largest_absolute_effect_metric: mean_homopolymer_run`, value 0.1114 s.d.
- **Draft text:**

  ```latex
  The largest absolute standardized effects were 0.084 standard deviations in Carbon, on the
  longest single-base run, and 0.111 in GENERator, on the mean single-base run. Every interval
  included zero and no measure survived correction in either model.
  ```

- **Acceptance gate:** both metric names match the ledger fields exactly (allowing for the prose
  rendering of `longest_homopolymer_run` / `mean_homopolymer_run`, which §3.6 already calls
  "longest and mean single-base run").

## L2-05 — Bonferroni conservatism on correlated windows (PAT Methods "Conservatism of the Bonferroni Correction on Correlated Windows")

- **Why:** PAT: *"windows shifted by exactly six bases (one token length) share the identical token
  phase and the vast majority of their token sequences … it is highly conservative in correlated
  spaces. This conservatism heavily penalizes the required threshold, reducing statistical power."*
  PAT is not disputing validity, only asking for the operational consequence to be stated. This
  costs nothing and strengthens the paper: it explains why 100% recall with a conservative
  correction is a strong result, not a lucky one.
- **Type:** statistical exposition. **No Lane 1 dependency** (Lane 1 may optionally quantify it;
  this text does not need that number).
- **Target location:** `main.tex` §3.3 *Position-independent detection*, after the equation that
  applies the correction (repo line ~290), or the Discussion.
- **Draft text:**

  ```latex
  The $M$ searched windows are far from independent: two windows of the same length whose starts
  differ by a multiple of six bases share a token phase and all but a few of their tokens, so
  their binomial statistics are strongly positively correlated. Bonferroni correction bounds the
  family-wise error rate without assuming independence, which is why it is used here, but in a
  correlated family it is conservative: the effective number of independent hypotheses is smaller
  than $M$, so the realized false-positive rate is below the declared target and the required
  per-window evidence is higher than a correlation-aware correction would demand. Our recall is
  therefore attained under a threshold stricter than necessary, and the reported control counts
  should be read as an upper bound on the operational false-positive rate rather than an estimate
  of it.
  ```

- **Optional placeholder:** if authors want the number, add
  `\evtag{synthid.v2.detector.effective_independent_windows}` in the final sentence. The paragraph
  is complete and publishable without it.

## L2-06 — State the short-window detectability boundary (PAT Methods "Detectability Constraints on Short Windows")

- **Why:** PAT computed the boundary and asks for it to be acknowledged. **The arithmetic has been
  independently verified and PAT is exactly right**, so state it as a property of the design rather
  than concede it as an oversight. It also does most of the work of answering PAT's edit-rate
  criticism (L2-08).
- **Type:** analytic exposition. **No Lane 1 dependency, no model, no run.**
- **Verified arithmetic** (recompute before publishing; `math.comb`, exact binomial tail):
  - threshold: $\alpha/M = 0.01/16{,}136 = 6.1973\times10^{-7}$, i.e. $-\log_{10} = 6.2078$ —
    matches the 6.21 already printed in §4.3 and the 6.207796 in the ledger;
  - at the shortest window, 384 bases = 64 tokens, minus the 4 unwatermarked context tokens = **60
    scorable tokens**; the minimum significant count is **49 of 60** (tail $3.78\times10^{-7}$);
  - an all-positive window needs **at least 21 scored tokens** ($2^{-21} = 4.77\times10^{-7} \le
    6.20\times10^{-7}$); at 20 tokens ($9.54\times10^{-7}$) detection is impossible even if every
    mark bit is positive.
- **Target location:** `main.tex` §3.3, and one sentence in Limitations.
- **Draft text:**

  ```latex
  The search geometry imposes a floor on what any single window can prove. At the shortest
  evaluated length, 384 bases is 64 tokens, of which the first four supply unwatermarked context,
  leaving 60 scorable tokens; the corrected threshold then requires at least 49 of those 60 mark
  bits to be positive. More generally, because repeated contexts are excluded from scoring, a
  window retaining fewer than 21 scored tokens cannot reach the corrected threshold even if every
  one of its mark bits is positive. Detection therefore requires a contiguous region whose token
  alignment is preserved over at least that many scorable tokens, which is the precise sense in
  which the method depends on recoverable synchronization rather than on the absence of edits.
  ```

- **Acceptance gate:** recompute all three numbers with an exact binomial tail before publishing;
  they depend only on $M$, $\alpha$ and the window geometry, all of which are already in the paper.

## L2-07 — Complexity analysis of the search (PAT Methods "Algorithmic Complexity and Implementation Details")

- **Why:** PAT asks for time and space complexity and notes the available optimizations (one
  hashing pass per reading frame, prefix sums for O(1) window evaluation).
- **Type:** exposition, with one measured number deferred.
- **Target location:** `main.tex` §3.3, end.
- **Draft text:**

  ```latex
  The search cost is dominated by keyed hashing rather than by the window enumeration. For a read
  of $N$ bases there are twelve reading frames, two orientations by six phases, and the mark bit
  of every token position in a frame can be computed once in a single pass; window statistics then
  follow from prefix sums of those bits, so each of the $M$ windows is evaluated in constant time.
  The work is therefore $O(N)$ keyed hash evaluations and $O(N)$ additional time and space per
  read, with $M$ growing linearly in $N$ for a fixed window set. Verification of one 3{,}456-base
  read took \evtag{synthid.v2.detector.search_seconds_per_read} on the hardware described in the
  reproducibility statement.
  ```

- **Depends on a Lane 1 number?** Yes, one: `\evtag{synthid.v2.detector.search_seconds_per_read}`.
- **Branch table:**

  | Outcome | Sentence to use |
  |---|---|
  | confirms (a timing exists) | "…took *X* seconds on *hardware*, single-threaded." |
  | weakens (timing much larger than expected) | "…took *X* seconds per read single-threaded; the search parallelizes trivially across reads, and we report wall clock at 16 workers as *Y*." |
  | refutes (complexity claim wrong — cost superlinear) | Delete the $O(N)$ claim; state the measured scaling in $N$ and describe the implementation as unoptimized, noting the single-pass and prefix-sum optimizations as available future work. |
  | inconclusive / not run | Drop the final sentence entirely and end at "…for a fixed window set." The complexity paragraph is analytic and complete without a measurement. |

- **Acceptance gate:** the asymptotic claim must describe the *implemented* algorithm. Read
  `src/genomic_watermarks/detector/search.py` and `synthid_position_independent.py` and confirm the
  single-pass/prefix-sum structure before claiming it; if the implementation is naive, say so and
  present the optimization as future work (PAT will accept that — it proposed it).

## L2-08 — The edit-rate boundary, answered honestly in Limitations (PAT-W1, PAT Methods "Scope of the Edit Regime", PAT Results "Limited Scope of Edit Robustness", PAT Discussion "Biological Realism and Minimum Window Constraints")

- **Why:** PAT raises this four times; it is the review's central criticism. The repository forbids
  multiple-edit experiments (`AGENTS.md`), so the answer must be analytic and candid. PAT itself
  supplies the frame: *"surviving multiple indels requires much shorter contiguous sub-windows, but
  overcoming the Bonferroni statistical penalty of the search requires longer windows."* That
  tension is real, derivable, and **already quantified by L2-06** — which makes it a strength of
  the paper's self-understanding rather than a gap.
- **Type:** limitations, scope statement. **No Lane 1 dependency.**
- **Target location:** `main.tex` Limitations (repo line ~588), expanding the existing single-edit
  sentence into its own paragraph.
- **Draft text:**

  ```latex
  The robustness evaluation covers exactly one non-adaptive substitution, insertion, or deletion
  per read, an edit rate near 0.03\%, and this is a declared scope boundary rather than an
  incidental limit. The design makes the consequence of raising that rate explicit. Detection
  requires a contiguous region whose 6-mer alignment survives, carrying at least 21 scored tokens,
  and the shortest window we evaluate spans 384 bases. Independent indels arriving at rate $r$
  leave expected clean stretches of about $1/r$ bases, so at $r = 0.1\%$ the expected clean stretch
  is near 1{,}000 bases and detection should often remain possible, whereas at $r = 1\%$, a rate
  reported for some long-read sequencing technologies, the expected clean stretch falls near 100
  bases, below our shortest window, and the verifier should fail. Substitutions are milder than
  indels in this respect: a substitution corrupts the tokens overlapping it without shifting the
  frame, whereas a single indel shifts every downstream token. We therefore claim provenance
  detection only in the single-edit regime, and we identify the search geometry, not the watermark
  strength, as the binding constraint at higher rates. Establishing the empirical breakdown point
  requires a shorter-window search with a correspondingly larger correction, which is outside this
  study's declared threat model and is the most useful direction for the next one.
  ```

- **Acceptance gate:** the paragraph must (1) name the rate tested, (2) derive the breakdown
  mechanism from numbers already in the paper, (3) name the binding constraint, (4) not promise an
  experiment that has not been commissioned. Do **not** state a detection rate at any edit rate
  other than the one tested.
- **Assumptions logged:** `ASM-01` — the clean-stretch heuristic $1/r$ is presented as an
  order-of-magnitude argument, not a measurement. If Lane 1 ever runs L1-07, this paragraph becomes
  a prediction that must be checked against it.

## L2-09 — The AI Use Statement (PAT-W9, PAT Appendix "AI Use Statement Accuracy")

- **Why:** PAT: the statement claims AI assisted with *"mathematical reasoning and proofs,"* but
  the paper contains no formal proofs. PAT calls it *"unedited boilerplate."* This is an integrity
  point and the cheapest fix in the review.
- **Type:** declaration correction. **No Lane 1 dependency.**
- **Target location:** the AI Use Statement — **not present in the repository source (see AD-5).**
  It exists in the submitted PDF, pages 10–14, and in the OpenReview submission form fields
  (`AI Assistance`, which lists five categories including research ideation/execution and drafting
  sections).
- **Draft text:**

  ```latex
  Generative AI tools assisted with writing and editing, literature retrieval and discovery,
  drafting sections that the authors then revised, research ideation and execution support, and
  generation of the synthetic sequence datasets analyzed here. The paper contains no formal
  theorems or proofs; the statistical development uses standard probability models and a
  Bonferroni correction, and all derivations, numbers, and claims were verified by the authors
  against the evidence ledger.
  ```

- **Acceptance gate:** the statement must match both the paper's contents and the five categories
  declared on the OpenReview form. Do not narrow the disclosure to make it look better — PAT's
  complaint is inaccuracy, not breadth.

## L2-10 — The Reproducibility / code-availability statement (PAT Appendix "Reproducibility and Code Availability")

- **Why:** PAT: *"it does not mention whether the custom code for the position-independent verifier
  or the exact prompt generation scripts will be made available."* The repository's *Data and code
  availability* section already names a public GitHub repository, so the submitted version's
  Reproducibility Statement is simply missing that pointer.
- **Type:** declaration completion. **No Lane 1 dependency.**
- **Target location:** the Reproducibility Statement (see AD-5) plus the existing *Data and code
  availability* section (repo line ~627).
- **Draft text (addition):**

  ```latex
  The verifier implementation, the sampler, the prompt-cohort construction scripts, the analysis
  and figure scripts, the frozen protocol documents, and the evidence ledger that every number in
  this paper resolves to are all in the public project repository. The two experimental keys are
  published fixtures for reproducibility and are not deployment secrets. Generated sequences and
  the full result files are available from the authors on request; the committed artifacts include
  the summaries and digests needed to re-derive every reported value.
  ```

- **Acceptance gate:** do not claim anything is released that is not; check what the repository
  actually contains before committing the sentence. Do not include host names, `$SCRATCH` paths, or
  allocation names (`paper/AGENTS.md`).

## L2-11 — Terminology and typography pass (PAT minor corrections across four segments)

- **Type:** copy-edit. **No Lane 1 dependency.**
- **Items, each with PAT's exact complaint:**
  1. Line ~97 of the submitted source: detached accent in the Jovanović citation — fix the bib
     entry `jovanovic2024stealing` to use `Jovanovi\'{c}` inside braces so the accent binds.
  2. Compound modifiers missing hyphens throughout: "generation time watermarks" →
     "generation-time watermarks"; "six mer sampling" → "six-mer sampling"; "base by base" →
     "base-by-base"; "decoder only" → "decoder-only" (§3.1); "distinct 6 mer fraction" → "distinct
     6-mer fraction" (§3.6). **Note:** the repository's §3.6 already reads "distinct 6-mer
     fraction" and "Jensen--Shannon drift", so several of these are artifacts of the submitted
     version only — another reason to settle AD-5 first.
  3. `TERM-1`: use "Jensen–Shannon drift" in prose **and** captions everywhere. Lane 1 is
     relabelling the figure axes to match; do not edit the figures.
  4. The abstract and TL;DR also carry unhyphenated forms ("six mer", "position independent",
     "wrong key"). Fix them in the paper; the OpenReview abstract field is a separate edit the
     author makes on the submission form.
- **Acceptance gate:** `cd paper && ./scripts/build.sh` runs clean; the accent renders; a grep for
  ` mer`, `generation time`, `base by base`, `decoder only`, and ` shift from prompt` returns
  nothing in the source.

---

# Part B — Tasks needing research (Deep Research prompts included)

Each DR prompt is self-contained. Run them in the order listed; L2-12 is the one that materially
changes how reviewers read the paper's novelty.

## L2-12 — Contrast genomic frameshift with text-domain synchronization robustness (PAT Background "Contextualizing Robust Text Watermarking")

- **Why:** PAT's sharpest constructive point: *"In natural language models, indels typically disrupt
  tokenization only locally … In contrast, for non-overlapping 6-mer genomic models, a single-
  nucleotide indel causes a permanent frameshift, fundamentally altering the entire downstream
  token sequence identity. Explicitly contrasting [these] would significantly strengthen the
  theoretical motivation and justify why the proposed position-independent exhaustive search … is
  necessary."* This converts the paper's core design choice from an engineering decision into a
  motivated necessity.
- **Type:** background / related work, with a motivation paragraph.
- **Target location:** `main.tex` §2.2 *Watermarking language-model output* (repo line ~162), plus
  two sentences in the Introduction's contribution list.
- **Already in `refs.bib`:** `kuditipudi2024robust` (robust distortion-free watermarks — the paper
  PAT names), `kirchenbauer2023watermark`, `haeupler2017synchronization` (synchronization strings),
  `christ2024undetectable`, `hu2024unbiased`, `wu2024dipmark`, `zhang2025securing`. **PAT's two
  named "Reference Papers" are both already cited** — the gap is engagement, not citation.
- **Draft text:**

  ```latex
  Text-domain watermarks that target robustness to editing treat synchronization as a local
  problem. Kuditipudi et al.\ align a candidate text to a key sequence under an edit distance, and
  related constructions use sliding windows or synchronization codes, because an insertion or
  deletion in text perturbs tokenization near the edit and leaves distant tokens largely intact.
  Non-overlapping $k$-mer genomic tokenization removes that locality. A single inserted or deleted
  base shifts the reading frame, so every downstream token changes identity, and the keyed context
  that determines each mark bit changes with it: the damage is not local but total from the edit
  onward. An edit-distance alignment against a key sequence does not recover this, because there is
  no surviving token sequence to align; what survives is a contiguous region in one of six phases.
  This is why verification here is posed as a search over strands, phases, start positions and
  window lengths rather than as an alignment problem, and why the correction over that search is
  part of the method rather than an afterthought.
  ```

- **Deep Research prompt:**

  ```
  Research how language-model watermarking schemes handle desynchronization from insertions,
  deletions and cropping, and how that machinery would or would not transfer to non-overlapping
  k-mer tokenization.

  Scope: peer-reviewed and arXiv work from 2022 to September 2026. Prioritize ICLR, NeurIPS, ICML,
  ACL, USENIX Security, IEEE S&P, and Nature/Science-family venues for the biological side.

  Answer five questions specifically:
  1. Which text watermarking schemes explicitly claim robustness to insertions and deletions
     (not just substitutions or paraphrase), and what mechanism provides it — edit-distance
     alignment to a key sequence, sliding windows, synchronization strings/codes, resampling, or
     something else? For each, state the assumed edit model and the reported detection degradation.
  2. For each such mechanism, state whether it relies on tokenization damage being LOCAL, and what
     specifically breaks if a single edit permanently shifts the token boundaries for the entire
     remainder of the sequence.
  3. What prior work exists on watermark or signal detection under unknown frame/phase, unknown
     start offset, or unknown strand — in genomics, in steganography, in synchronization coding, or
     in signal processing — and how is the multiple-hypothesis search corrected in each?
  4. What is the state of the art in watermarking DNA or protein sequences produced by generative
     models (as opposed to classical synthetic-DNA tagging via codon choice or inserted barcodes)?
     For each, state whether verification needs model access, whether it needs alignment, what edit
     robustness is claimed, and what it assumes about coding versus non-coding regions.
  5. Which of the above report computational cost of verification, and in what units?

  Evidence standard: a claim counts only if the source states it; distinguish claims proven,
  claims measured empirically, and claims asserted. Flag any paper whose robustness claim is
  asymptotic or assumes a bounded number of edits.

  Output: for each finding, one line of claim, the citation, one line on relevance to a
  6-mer-tokenized genomic watermark verified without model access, and a BibTeX entry. Group by the
  five questions. Then give a 200-word synthesis on whether existing alignment-resilient text
  machinery is sufficient, insufficient, or inapplicable for permanent frameshift, and say which.

  Exclusions: do not include classical non-generative DNA watermarking by codon substitution or
  inserted barcode text unless it bears directly on alignment recovery. Do not include
  detector-guided or adaptive attack literature; that is outside this paper's threat model. Do not
  recommend experiments.
  ```

- **Acceptance gate:** every added claim carries a citation; the paragraph makes a falsifiable
  structural claim (locality vs. frameshift), not a vague novelty assertion.

## L2-13 — Baseline comparison: answer it in prose, decline the experiment (PAT-W2, PAT Results "Absence of Comparative Baselines")

- **Why:** PAT asks for benchmarking against alignment-resilient frameworks, recent biological
  watermarking baselines, and a red/green-list scheme adapted to 6-mers. `AGENTS.md` and
  `PROJECT.md` forbid reintroducing other watermark constructions, so the honest answer is a
  structured qualitative comparison plus an explicit statement of the exclusion and its cost.
- **Type:** related work + rebuttal. **No Lane 1 dependency.**
- **Target location:** a short comparison paragraph or table in §2.2/§2.3, and a Discussion
  sentence naming the missing comparison as a limitation.
- **Draft framing:** compare along four axes the paper can support without running anything:
  (1) does verification need model access or probabilities; (2) does it need alignment or a known
  boundary/strand; (3) what edit model is claimed; (4) does it distort the sampling distribution.
  State that a same-cohort empirical comparison against a distortionary red/green-list scheme was
  not run, that it would require implementing a second watermark construction outside this study's
  declared scope, and that the resulting comparison would confound construction with verifier.
- **Deep Research prompt:** use L2-12's prompt, questions 4 and 5, then:

  ```
  Additionally: for red/green-list (biased-logit) watermarking as introduced by Kirchenbauer et
  al. 2023 and its successors, collect what is reported about (a) detectability margin as a
  function of sequence length, (b) distortion of the output distribution, and (c) robustness to
  insertions and deletions specifically. Then collect the same three items for distribution-
  preserving schemes (SynthID-Text/tournament sampling, Christ et al., Hu et al., DiPmark). Present
  as one comparison table with a column stating whether verification requires model access.
  Note explicitly where no source reports a number, rather than estimating it.
  ```

- **Acceptance gate:** the paragraph must not claim superiority over an unimplemented baseline. It
  compares properties, names what was not measured, and says why.

## L2-14 — Token-phase problem scope vs single-nucleotide models (PAT Background "Scope of the Token Phase Problem")

- **Why:** PAT: the phase challenge is *"an artifact specific to multi-mer tokenization"* and the
  paper should say so, and say why multi-mer tokenization is used at all.
- **Type:** background. **No Lane 1 dependency.** `nguyen2024evo` and `dallatorre2025nucleotide`
  are already in the bibliography.
- **Target location:** `main.tex` §2.4 *Genomic tokenization and alignment* (repo line ~193).
- **Draft text:**

  ```latex
  The phase problem is specific to multi-mer tokenization. Single-nucleotide models place one token
  per base, so an insertion or deletion shifts token positions without changing token identities,
  and a verifier faces an offset rather than a frame. Multi-mer tokenization is nevertheless widely
  used because it shortens sequences by the token width and lets a model cover more bases within a
  fixed context, which is why both models evaluated here use non-overlapping 6-mers. The cost is
  that six distinct phases must be considered at verification time, and that an indel changes the
  identity of every downstream token rather than only its position.
  ```

- **Deep Research prompt:**

  ```
  Establish, with citations, the current landscape of tokenization in genomic language models:
  which released models use single-nucleotide tokenization, which use fixed non-overlapping k-mers
  (and what k), and which use learned subword schemes such as BPE. For each family, report the
  stated motivation for the choice (context-length efficiency, compute, modeling quality) and any
  published evidence on how tokenization affects downstream performance or robustness to indels.
  Cover at least Evo and Evo 2, Nucleotide Transformer, DNABERT and DNABERT-2, HyenaDNA, Caduceus,
  GENERator, and any 2025-2026 releases. Date range: 2021 to September 2026.

  Output: a table of model, tokenization, k where applicable, stated motivation, citation; then
  five sentences suitable for a related-work paragraph on why multi-mer tokenization is common
  despite creating a phase ambiguity. Provide BibTeX for anything not likely already cited in a
  genomic watermarking paper. Do not speculate about unpublished models.
  ```

## L2-15 — Precision about SynthID's local context (PAT Background "Clarification of Local Context in LLM Watermarks")

- **Why:** PAT: hashing local token context is *"a standard structural feature of many foundational
  autoregressive LLM watermarking schemes (e.g., Kirchenbauer et al., 2023)"*, so presenting it as
  unique to SynthID imprecisely describes the literature. Correcting this costs two sentences and
  removes an easy target.
- **Type:** claim precision. **No Lane 1 dependency.** `kirchenbauer2023watermark` and
  `dathathri2024scalable` are already cited.
- **Target location:** `main.tex` §2.3 *SynthID* (repo line ~177).
- **Draft text:**

  ```latex
  Keying on a hash of recent tokens rather than on absolute position is a standard feature of
  autoregressive text watermarks, including the red/green-list construction of Kirchenbauer et al.
  We adopt SynthID not because local context is unique to it but because it combines that property
  with tournament sampling, whose distribution-preservation identity holds in expectation over
  fresh keyed functions. Local context is what makes verification possible at an unknown location;
  distribution preservation is what keeps the generated sequence usable as a sample from the
  model's own law.
  ```

- **Acceptance gate:** the sentence must preserve the repository's required hedge — SynthID's
  identity is an expectation over fresh keyed functions, and fixed-key sampling follows a
  calculated reweighted law (`paper/AGENTS.md`).

## L2-16 — Downstream biological benchmarks as future work (PAT-W3, PAT Discussion "Biological Validation Benchmarks")

- **Why:** PAT asks for BEND / GenBench / zero-shot variant-effect evaluation, and then supplies
  the cheaper answer itself: *"Acknowledging that future work could leverage standardized
  downstream tasks … would provide a practical, in-silico pathway."* Running them is outside the
  declared claim boundary (AD-4).
- **Type:** limitations / future work. **No Lane 1 dependency.**
- **Target location:** `main.tex` Limitations, the biological-proxy paragraph (repo line ~610).
- **Draft text (addition):**

  ```latex
  Between sequence statistics and wet-lab assays lies a class of standardized in-silico
  evaluations---supervised downstream task suites and zero-shot variant-effect benchmarks---that
  we do not use here. Our quality claim is deliberately confined to model likelihood and the 14
  declared sequence summaries, and it establishes only that watermarked and ordinary outputs are
  statistically indistinguishable under those measures. Evaluating watermarked sequences on
  standardized downstream genomic benchmarks would test whether functional signals are preserved,
  and is the natural next step before any claim about biological consequence.
  ```

- **Deep Research prompt:**

  ```
  Identify the standardized, publicly available benchmarks for evaluating genomic language model
  outputs on biologically meaningful tasks, as of September 2026. For each: what tasks it covers,
  what input it requires (sequence only, or sequence plus annotation), whether it evaluates
  generated sequences or only representations of natural sequences, its licence, and its compute
  cost. Cover at least BEND and GenBench, plus any zero-shot variant-effect prediction benchmarks
  and any 2025-2026 successors.

  Critically: state for each benchmark whether it can be applied to DE NOVO GENERATED sequences
  that have no ground-truth annotation, or whether it fundamentally requires labelled natural
  sequences. This determines whether it is usable for evaluating watermarked generations at all.

  Output: one table, then a 150-word assessment of which benchmarks could evaluate watermarked
  generated sequences and which could not, with reasons. BibTeX for each. Do not propose a study
  design.
  ```

- **Acceptance gate:** the text must not imply any biological result was obtained, and must not
  promise the benchmark study as committed work.

---

# Part C — Tasks whose number comes from Lane 1 (all branches drafted now)

Each task below is **fully written in every branch**. Lane 2 finishes them today and never waits.

## L2-17 — False-positive-rate precision (PAT-W4)

- **Target location:** `main.tex` §4.3 final paragraph, Limitations paragraph 2 (repo line ~601),
  Abstract, and Conclusion.
- **Placeholders:** `\evtag{synthid.v2.carbon.detector.clean.ordinary_rate}`,
  `\evtag{synthid.v2.generator.detector.clean.ordinary_rate}`,
  `\evtag{synthid.v2.detector.fpr_upper_bound}`, `\evtag{synthid.v2.cohort.identity}`.
- **What stays true in every branch:** the currently published sentence — one positive among 192
  independent prompts gives a 95% interval reaching 2.87%, and the zero-positive upper bound is
  1.90%. Those numbers are in the ledger and must not be deleted; a new run *adds* a tighter bound,
  it does not retract the old one.
- **Branch table:**

  | Outcome | Sentence to use |
  |---|---|
  | confirms (larger cohort, control rate still at or below target, tighter bound) | "On an independent cohort of \evtag{synthid.v2.cohort.identity} prompts, control positives remained compatible with the 1\% target, and the 95\% upper bound on the prompt-level false-positive rate tightened to \evtag{synthid.v2.detector.fpr_upper_bound}. The operational rate is therefore bounded near the declared target rather than merely consistent with it." |
  | weakens (bound tighter but above 1%) | "A larger independent cohort tightened the 95\% upper bound to \evtag{synthid.v2.detector.fpr_upper_bound}, which remains above the declared 1\% target. We therefore report the target as declared rather than validated, and state the bound as the operationally meaningful quantity." |
  | refutes (control rate clearly exceeds 1%) | "On a larger independent cohort the prompt-level control rate was \evtag{...}, above the declared 1\% target. We report the declared threshold as not attained at this read length and search size, and we identify the analytic null's independent-fair-bit assumption as the first candidate explanation." — **and** the Abstract's "at most one positive" claim must be rewritten and the Conclusion's "compatible with the declared target" deleted. |
  | inconclusive / not run | Keep the submitted text unchanged and strengthen Limitations: "With 192 independent prompts the 95\% interval reaches 2.87\% for a single positive prompt and 1.90\% for none. We did not scale the cohort for this version; precise estimation near a 1\% target requires roughly an order of magnitude more independent prompts, which we identify as required future work rather than a resolved question." |

- **Acceptance gate:** whichever branch is used, the Abstract, §4.3, Limitations and Conclusion all
  carry the same strength of claim. Lane 3 checks those four locations pairwise.
- **Assumptions logged:** `ASM-02` — Lane 2 assumes any new FPR run uses the same declared 1%
  target and the same four window lengths. If Lane 1 changed either, every sentence here is void.

## L2-18 — Carbon provenance discrepancy (PAT-W8, PAT Discussion "Contextualizing the Provenance Discrepancy")

- **Target location:** `main.tex` Limitations, the sentence beginning "For Carbon, the retained
  protocol document differs from the hash recorded in the detection result."
- **Placeholder:** `\evtag{synthid.v2.carbon.provenance.audit}`.
- **Branch table:**

  | Outcome | Sentence to use |
  |---|---|
  | confirms — confined to document text | "For Carbon, the retained protocol document does not match the hash recorded in the detection result. The document governs the cohort identity, the prompt split rule, the four window lengths, both orientations, the declared false-positive target, and the tournament and context settings. Each of these is independently recorded in the result artifact's own configuration and command fields and agrees with the reported analysis, so the discrepancy is confined to the document's text and does not affect the generative distribution or the detection statistic. We nonetheless treat the execution as unverified at the document level." |
  | weakens — affects the detection statistic | "…the discrepancy touches \evtag{...}, a setting that enters the detection statistic. We therefore report the Carbon detection results as unverified at the protocol level and rely on the GENERator execution for any claim that requires a verified protocol chain." |
  | refutes — affects generation | "…the discrepancy touches generation settings. We withdraw the Carbon numbers from the claims that depend on them, retain them as disclosed development history, and report the affected results as requiring re-execution." — **this also forces changes to the Abstract's dual-model framing.** |
  | inconclusive / unresolved | Keep the submitted sentence and add: "We were unable to determine which revision of the protocol document the recorded hash corresponds to. The parameters the document governs are the cohort identity, the prompt split rule, the window lengths, the orientations, the false-positive target, and the tournament and context settings; all are independently recorded in the result artifact, but the document-level chain for this execution cannot be closed, and we report it as an unresolved provenance gap rather than a resolved one." |

- **Acceptance gate:** the sentence must enumerate the governed parameters — that specific
  enumeration is what PAT asked for, and it is available in every branch, including the
  unresolved one.

## L2-19 — Cross-model detection-strength gap (PAT-W7, PAT Results "Unexplained Variance")

- **Target location:** `main.tex` §4.3, after the strength-separation sentence, and one Discussion
  sentence.
- **Placeholders:** `\evtag{synthid.v2.strength_gap.scored_tokens_per_read}`,
  `\evtag{synthid.v2.strength_gap.explained_component}`.
- **What stays true in every branch:** the values already in the ledger — Carbon's weakest clean
  correct-key read is 124.8 and GENERator's is 19.6 on the $-\log_{10} P_{\text{win}}$ scale,
  against a threshold of 6.21. Both are far above threshold; the gap is a question about margin,
  not about detection.
- **Branch table:**

  | Outcome | Sentence to use |
  |---|---|
  | confirms — mechanical explanation found | "The weakest marked read differs substantially between models, 124.8 in Carbon against 19.6 in GENERator, while both exceed the 6.21 threshold by orders of magnitude. The gap tracks the number of tokens actually scored per read: \evtag{synthid.v2.strength_gap.scored_tokens_per_read}. Because repeated 4-token contexts are excluded from scoring, a model that revisits contexts more often yields fewer scored bits and a smaller margin at identical watermark strength." |
  | weakens — partly explained | "…\evtag{synthid.v2.strength_gap.explained_component} of the gap is attributable to differences in the number of scored tokens per read; the remainder is consistent with differences in the models' predictive entropy, which we did not measure directly." |
  | refutes — mechanism is not scored-token count | "…the gap is not explained by scored-token counts. We report it as an open observation and note that margin, unlike the detection decision, depends on properties of the generating model that this study does not characterize." |
  | inconclusive / not run | "The weakest marked read differs substantially between models, 124.8 in Carbon against 19.6 in GENERator, while both exceed the 6.21 threshold by orders of magnitude. We do not attribute this margin difference to a specific cause. Candidate explanations include the number of tokens scored per read after repeated-context exclusion and differences in predictive entropy between the models; distinguishing them requires per-token analysis we leave to future work. The detection decision is unaffected: every marked read in both models cleared the corrected threshold." |

- **Acceptance gate:** no branch may present a hypothesis as a finding. The inconclusive branch is
  publishable as-is and is the default.
- **Assumptions logged:** `ASM-03` — Lane 2 assumes the 124.8 and 19.6 figures survive any
  re-derivation. They are `[A]` derived entries; if Lane 1's work changes them, every number in
  this task changes.

---

## Placeholder register

| Placeholder | Filled by | Task | If never filled |
|---|---|---|---|
| `synthid.v2.detector.search_seconds_per_read` | L1-04 | L2-07 | drop the final sentence |
| `synthid.v2.carbon.detector.clean.ordinary_rate` | L1-01 | L2-17 | use the inconclusive branch |
| `synthid.v2.generator.detector.clean.ordinary_rate` | L1-01 | L2-17 | use the inconclusive branch |
| `synthid.v2.detector.fpr_upper_bound` | L1-01 | L2-17 | use the inconclusive branch |
| `synthid.v2.cohort.identity` | L1-01 | L2-17 | use the inconclusive branch |
| `synthid.v2.carbon.provenance.audit` | L1-02 | L2-18 | use the unresolved branch |
| `synthid.v2.strength_gap.scored_tokens_per_read` | L1-03 | L2-19 | use the inconclusive branch |
| `synthid.v2.strength_gap.explained_component` | L1-03 | L2-19 | use the inconclusive branch |
| `synthid.v2.detector.effective_independent_windows` | L1-06 | L2-05 (optional) | omit; paragraph stands |

**Every placeholder has a branch in which it does not exist.** That is what makes this lane
independent. If a task ever needs a number with no such branch, stop and add the branch.

## Assumption register

| ID | Assumption | Assumed by | Confirmed by | Risk if wrong |
|---|---|---|---|---|
| `ASM-01` | clean-stretch length ≈ 1/r is an order-of-magnitude heuristic, not a measurement | L2-08 | L1-07 (not commissioned) | a commissioned sweep could contradict the predicted breakdown point; the paragraph is then a wrong prediction, not a stated limit |
| `ASM-02` | any new FPR run keeps the 1% target and the four window lengths | L2-17 | L1-01 protocol | every L2-17 sentence is void; thresholds and intervals change |
| `ASM-03` | the 124.8 / 19.6 strength values and the 6.21 threshold are stable | L2-19, L2-06 | L1-03, L1-05 | L2-06's verified arithmetic and L2-19's framing both change |
| `ASM-04` | `M = 16{,}136` and $\alpha = 0.01$ hold for the reads discussed | L2-05, L2-06, L2-07 | L1-01 config | the 6.2078, 49/60 and n≥21 figures all change |
| `ASM-05` | the submitted source will be supplied (AD-5) and its section titles match the repository's | all tasks | author | every "Target location" must be re-resolved |
| `ASM-06` | the figure axes will read "Jensen–Shannon drift" (`TERM-1`) | L2-11 | L1-05 | text and figures disagree again; PAT's point T7 unfixed |

## Rebuttal-only answers (post to OpenReview, no paper change)

- **On the requested edit-rate sweep:** "We agree this is the most important open question and we
  state its answer as far as the design determines it. Detection requires a contiguous region whose
  6-mer alignment survives and that carries at least 21 scored tokens, and our shortest evaluated
  window spans 384 bases. Independent indels at rate r leave expected clean stretches near 1/r
  bases, so the method should degrade near r = 0.1% and fail near r = 1%, where the expected clean
  stretch falls below our shortest window. We have added this reasoning and its boundary condition
  to the paper. We have not run the sweep: multiple-edit robustness is outside this study's declared
  threat model, and a credible sweep needs a shorter-window search with a correspondingly larger
  correction, which is a different verifier and a different study."
- **On the requested red/green-list baseline:** "Our contribution is the verifier, not a new
  watermark construction, and our study scope admits exactly one construction — the SynthID
  tournament — with ordinary categorical sampling as the only control. Implementing a
  distortionary red/green-list scheme for 6-mers would compare two constructions rather than two
  verifiers, and would confound the comparison we are making. We have instead added a structured
  property comparison against alignment-resilient text watermarks and recent generative biological
  watermarks, and we state the absence of a same-cohort empirical baseline as a limitation."
- **On downstream biological benchmarks:** "We agree, and we have added standardized in-silico
  benchmarks as the explicit next step. Our quality claim is deliberately confined to model
  likelihood and 14 declared sequence summaries, and we make no claim about function, viability or
  safety anywhere in the paper."
- **On sample size, if L1-01 does not complete:** "We agree that 192 independent prompts cannot
  validate a 1% target, which is why we report the interval rather than the point estimate — 2.87%
  for one positive prompt, 1.90% for none. We have sharpened this in Limitations and identify the
  larger-cohort measurement as required future work."

## Decline register

| PAT request | Declined on | Authority |
|---|---|---|
| Multiple-edit / higher-rate sweep | outside declared threat model; requires a different verifier | `AGENTS.md` "Do not add multiple-edit … experiments"; `docs/threat_model.md`; runner's own note that single edits are not an edit rate |
| Red/green-list or other watermark baseline | study admits one construction plus its ordinary control | `AGENTS.md` "Do not reintroduce other watermark constructions"; `PROJECT.md` retained scope |
| Downstream biological task evaluation | outside declared claim boundary | `PROJECT.md` "does not establish biological function, viability, safety" |
| Detector-query or detector-guided attacks (not requested, pre-empted) | outside threat model | `AGENTS.md` |

Each decline appears in the paper as a scope statement, not as a silence.

## Deep Research queue, in priority order

1. **L2-12** — text-domain synchronization vs genomic frameshift. Highest value: it converts the
   design choice into a motivated necessity and simultaneously supplies L2-13's comparison.
2. **L2-13 supplement** — the red/green-list vs distribution-preserving property table.
3. **L2-14** — genomic tokenization landscape.
4. **L2-16** — downstream genomic benchmarks, with the "can it evaluate generated sequences at
   all" question, which is the one that matters.

Deduplicate before running: L2-12 question 4 and L2-13 overlap substantially; run L2-12 first and
only top up.

## Coverage — every PAT point this lane answers

| PAT point | Lane 2 task | Needs Lane 1? |
|---|---|---|
| W1 / M4 / R2 / D1 edit rate | L2-08 + rebuttal | no |
| W2 / R5 baselines, overhead | L2-13, L2-07 | overhead number only, branched |
| W3 / R6 / D3 biological benchmarks | L2-16 | no |
| W4 FPR sample size | L2-17 | number only, branched |
| W5a GoF statistic | L2-01 | no |
| W5b / R4 256-state correction | L2-02 | no |
| W6 / R1 two window summaries | L2-03 | no |
| W7 / R3 strength gap | L2-19 | number only, branched |
| W8 / D2 provenance | L2-18 | verdict only, branched |
| W9 / A1 AI Use Statement | L2-09 | no |
| A2 code availability | L2-10 | no |
| B1 text-watermark contrast | L2-12 | no |
| B2 token-phase scope | L2-14 | no |
| B3 SynthID local context | L2-15 | no |
| M2 Bonferroni conservatism | L2-05 | no (optional number) |
| M3 short-window boundary | L2-06 | no |
| M5 complexity | L2-07 | timing only, branched |
| T1–T5 typos, hyphenation | L2-11 | no |
| T6 name max-effect measures | L2-04 | no |
| T7 drift vs shift terminology | L2-11 (text), L1-05 (figures) | no — `TERM-1` fixed in advance |
