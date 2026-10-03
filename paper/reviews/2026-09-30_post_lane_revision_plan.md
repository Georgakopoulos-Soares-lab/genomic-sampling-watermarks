# Post-lane consistency review and manuscript revision plan (2026-09-30)

**Scope.** Lane 1 runs (v2 scaled FPR cohort, L1-02 to L1-06, v3 edit-rate sweep), Lane 2 prose,
and the partial Lane 3 reconciliation (`paper/reviews/2026-09-29_lane3_reconciliation.md`),
checked against `main.tex` at commit `647de7b`, `evidence/measurements.yaml`, the derived
artifacts, and `paper/figures/*`. This note covers only findings that change what a reader
concludes or that a reviewer would catch. Lane 3 already closed number drift (CONF-13 to CONF-23)
and those items are not repeated here.

**Bottom line.** Every printed number spot-checked (v2 bounds 0.8499%/1.0150%, FWER 0.105%/0.186%,
9.5x/5.4x, M_eff 830-850, timing 0.0956/0.245/0.902 s, 27.9-69.1 MiB, 0.0167 s, 6.3x, v3
ceilings) matches the ledger. The problems are elsewhere. Two paragraphs misread admitted evidence.
Headline claims rest on a cohort and an edit channel that Methods never describes and that no
table or figure shows. Two cross-cohort comparisons are not like-for-like. **No new run is
required.** Every fix uses artifacts that already exist, plus CPU-only derived (`[A]`) ledger
entries.

---

## Findings, ranked

### F1. The cross-model strength-gap paragraph contradicts admitted evidence (major)

- **Paper:** §4.3, `main.tex` 584-592. The paper presents Carbon 124.8 versus GENERator 19.6 as
  a "difference in margin" between models. It names "the number of tokens scored per read after
  repeated-context exclusion" as a candidate cause and defers "per-token analysis" to future
  work. The rebuttal draft (W7, lines 147-154) says the same.
- **Evidence:** L1-03 performed the analysis (`synthid.v2.strength_gap.*`):
  - The median scored-token count in the winning window is **508 in both models**.
  - Aggregate repeated-context exclusion is 0.18% (Carbon) and 0.13% (GENERator), lower in
    GENERator.
  - The scored-token shortfall accounts for **9%** of the weakest-read gap.
  - Median clean strengths are **790.6 versus 798.8** (ledger note on `explained_component`).
  - GENERator's weakest read is one repeat-heavy read: 174 excluded contexts, 334 scored tokens,
    positive-bit fraction 0.546.
- **v2 cohort** (`figure_values*_v2.json`, 3,088 reads per model): the medians are **792.9
  versus 799.7**, and the weakest reads are **237.6 versus 123.8**. Each model's minimum moves
  by about 100 units between cohorts. GENERator's v2 minimum nearly equals Carbon's v1 minimum.
- **Why it happened:** L1-03 was labelled `inconclusive` (about entropy), so Lane 2's
  "inconclusive / not run" branch went in verbatim. That branch was written for the case where
  nothing was computed.
- **Consequence:** the paper implies a model-level strength difference that neither cohort
  supports. It also calls for an analysis that has already been done and admitted.
- **Fix:** rewrite the paragraph around the following points:
  1. Typical strength is indistinguishable between models (report medians from both cohorts).
  2. The minimum is a single-read extreme that varies with the cohort.
  3. The v1 GENERator minimum is a repeat-rich read, and scored-token loss accounts for about 9%
     of that read's shortfall.
  4. Predictive entropy remains an untested explanation for low-signal reads, not for a model
     difference.

  Delete "we leave to future work", and update rebuttal W7 to match.

### F2. The edit-rate paragraph uses an undefined natural-log scale for one model (major)

- **Paper:** Limitations, 821-823. It reads: "median correct-key sequence log P-value is −994.67
  after one indel against −1778.65 after one substitution".
- **Evidence:** `sequence_log_p_value` is `ln P_read`, the natural log after the full-search
  correction (`src/genomic_watermarks/synthid_position_independent.py:278`). Every other strength
  in the paper, including Figures 3-4, 124.8, 19.6 and the 6.21 threshold, is `-log10 P_win`.
  On the paper's scale the two values are about 436 and 777. Both are **Carbon-only** (GENERator:
  −1003.81 and −1795.19), yet the sentence names no model, which breaks the dual-model rule.
- **Upstream error:** the v3 execution record and the Lane 1 status say "the clean statistic sits
  near −1822 against a firing threshold near −6.2, about 290 times". That compares a natural-log
  statistic with a log10 threshold. The same-scale ratio is about 127x (793/6.21). The 2026-09-29
  correction note calls the figure "valid as execution-record reasoning"; it is not. The paper
  already dropped it, but the record should be corrected so it does not return.
- **Fix:** state the per-event cost in `-log10 P_win` for both models, via a derived `[A]` ledger
  entry or a units field on the existing medians. Append a dated units correction to
  `synthid_v3_edit_rate_execution_2026_09_24.md`.

### F3. The edit-rate result is a headline claim with no Methods, Results, figure, or table (major, structural)

- It appears in the Abstract (93-95), Introduction (141-143) and Discussion (705-708), but its only
  data description is in Limitations (807-832).
- Methods §3.6 (487) still says "Each edited read contains exactly one substituted, inserted, or
  deleted base". The Results introduction (501-502) promises only single-base edits. §4.4
  (693-694) still ends "It does not imply a general guarantee against more extensive ...
  modification".
- **The Conclusion (869-880) omits the edit-rate result entirely**, which is a C5 failure across
  sections.
- Limitations cites `docs/research/threat_model_edit_rate_v3_admission_2026_09_29.md`,
  `synthid.v3.*` and `docs/threat_model.md`, and narrates an "author sign-off". `paper/AGENTS.md`
  forbids local paths and internal details. To a reviewer, this reads as a threat model widened
  after the results were seen. In fact the full-cohort protocol was frozen before the run, with
  predeclared falsification checks, and that is the framing the paper should use.
- Limitations 801-802 still calls the single-edit regime "a declared scope boundary rather than an
  incidental limit", while 829-830 says the threat model was widened. The two statements
  contradict each other.
- **Fix:**
  - Add a Methods subsection for the edit-rate channel covering: `round(r × 3072)` events;
    positions from a public hash stream; four kinds; seven rates; frozen v2 reads without
    regeneration; the unchanged detector; correct-key plus ordinary-null families; and the
    predeclared checks.
  - Add a Results subsection with a new figure (below).
  - Reduce Limitations to scope only: non-adaptive, no wrong-key battery, adaptive editor out of
    scope.
  - Remove the repository paths, namespaces and governance narrative.

### F4. The per-model "ceiling" turns one read into a model difference (major, framing)

- GENERator's 1% ceiling (versus Carbon's 2%) comes from **one read in 3,088** (mixed indel at 2%:
  3,087/3,088). At 5%, GENERator substitution also misses one read. At every rate and kind the two
  models agree within about one point (for example, indel at 5%: 93.5% versus 92.9%).
- An "every read recovered" ceiling is an extreme statistic that can only fall as n grows. It is
  not a property of the method.
- The Abstract, Introduction and Discussion all headline "2% on Carbon and 1% on GENERator".
  Readers will take this as Carbon being more robust.
- Lane 3 (CONF-13) was right that "2% for both" was false, but the replacement over-reads the
  data.
- **Fix:** report per-cell detection rates with exact intervals (already in the ledger
  `uncertainty` blocks). State that detection was complete or near-complete (at least 3,087 of
  3,088 reads in every cell) through 2% in both models, with Carbon at 3,088/3,088 in all four
  kinds. State that the two models' curves agree at every rate. Keep the model names, but do not
  headline the ceiling difference.

### F5. The v2 cohort carries headline claims but is undescribed and untabulated (major)

- **Methods:** §3.4 (449-459) describes only the 256-prompt cohort. The v2 cohort has these
  properties:
  - 1,608 prompts, 134 windows from each of **12 chromosomes**.
  - The chromosomes are a **strict subset of v1's 16**, covering 6 organisms (v1 had 8, including
    mouse and *S. cerevisiae*).
  - A 64/1,544 split.
  - New domain labels, and therefore new keyed functions.
  - Generation on A100 GPUs.
- **Corpus wording:** "independently frozen" is accurate about selection. However, the Discussion
  (724-725) and Conclusion (880, "wider sequence coverage") must not imply a broader corpus,
  because v2 is narrower.
- **Missing table:** no per-condition v2 counts appear anywhere, only the maximum bound. Add a
  table with, per model and condition: correct-key 3,088/3,088; ordinary k/1,544 with a one-sided
  bound; wrong-key k/1,544 with a one-sided bound.
- **Unlike-for-like intervals:** v1 reports exact **two-sided** 95% intervals (upper 1.903% and
  2.868%), while v2 reports **one-sided** 95% upper bounds. The sentence "tightened this bound"
  compares a 97.5% bound with a 95% bound. The one-sided v1 equivalents are 1.548% and 2.447%.
  Methods §3.6 mentions only two-sided intervals.
- **Level mismatch:** the 1% target is a read-level α, but the bound is on the prompt-level rate
  (either draw positive), which is roughly twice the read-level rate. The comparison is
  conservative and should say so.
- **Wording:** the Abstract (90-91), Introduction (140-141) and Discussion (704-705) say the
  cohort "bounded the operational false-positive rate". It gave a one-sided 95% upper confidence
  bound. The Conclusion (875-877) already phrases this correctly.
- **Asymmetry:** the Abstract reports v1 ordinary *and* wrong-key controls, but for v2 only the
  ordinary family, omitting the 1.0150% wrong-key cell. The v2 protocol did **predeclare**
  ordinary as primary and wrong-key as secondary. Say so in Methods and treat both cohorts the
  same way; otherwise the designation looks post hoc.

### F6. v2 is an internal replication of detection that the paper under-reports (major)

- v2 reproduces the headline recall: 3,088/3,088 in all four conditions for both models, with new
  keyed functions, a second execution platform, and 8x the prompts. The paper gives it one clause
  (598-600).
- The Abstract still leads with "all 384 held-out marked reads". Limitations says "one execution
  per model" (780) and that "headline detection ... still come[s] from the original
  single-execution cohort" (787-789). The Reproducibility statement lists "the outstanding
  independent replication" (909).
- **Orphaned figures:** `fig3_detection_v2`, `fig4_edits_v2` and their GENERator counterparts were
  built and digest-recorded (`figure_values*_v2.json`), but no manuscript line references them.
- **Fix:** present v2 as a scaled internal replication alongside v1. Keep "independent (external)
  replication" as a limitation, but distinguish it from same-team replication at scale. Include
  the v2 detection figure (main or supplementary), or delete the orphans. Before §4.4 claims the
  window-length pattern replicates, check the v2 best-window counts in `figure_values*_v2.json`.

### F7. A statistical misstatement about control counts (moderate)

- **Paper:** §3.3, 394-396: "the reported control counts should be read as an upper bound on the
  operational false-positive rate rather than an estimate of it."
- This is wrong. Ordinary-read counts *are* the empirical estimate of the realized false-positive
  rate. Under the conservative Bonferroni rule, the upper bound is the nominal α. The sentence
  also contradicts §4.3, which uses those counts to bound the rate.
- The measured FWER (0.105%/0.186%) sits in Methods, comes from the v2 cohort, and is not labelled
  as such.
- **Fix:** correct the sentence and move the measured headroom to the v2 Results subsection with
  its cohort named.

### F8. Reproducibility statements are inconsistent, and a fresh clone cannot verify Carbon (moderate)

- **Protocol hash wording:** the Reproducibility statement (909-910) says "unresolved Carbon
  protocol hash discrepancy". Limitations (790-797) says it is characterized and confined to
  document text.
- **Audit overstatement:** Limitations says each governed parameter "is independently recorded in
  the result artifact's own configuration". The audit found 8 of 9; context-history size is
  recovered only from code-digest defaults.
- **Data availability:** 921-923 says "Carbon result files are not committed". The v2 Carbon files
  now are; only the v1 files are missing.
- **Fresh clone:** `scripts/check_evidence.py` fails on 5 missing Carbon v1 artifacts (CONF-10).
  Meanwhile the paper says every number resolves to an available ledger. Lane 1 regenerated the
  Carbon v1 figures, so the files exist on at least one machine. Committing them gzipped, as was
  done for v2, would fix this and unblock CONF-11.

### Outside the manuscript (brief)

- The v3 admission document records the sign-off as given by christos.galanopoulos@... "in
  session" and was itself written in an agent session. The L1-07 pilot sign-off is by
  kimonaspro99@.... The named co-author should confirm the admission in their own words.
- The rebuttal draft needs a re-sync after the revision: W7 (F1), W1 (F3/F4), W4 (F5), and any
  new figure numbers against the submitted PDF's numbering (AD-5).

---

## Author decisions needed before editing

| ID | Decision | Recommendation |
|---|---|---|
| D1 | Role of the v2 cohort | Scaled internal replication shown alongside v1, with its own table; v1 keeps quality and sampler results. |
| D2 | Where the edit-rate result lives | A Results subsection and figure. If authors prefer Limitations-only, it must come out of the Abstract, Introduction and Discussion headlines. |
| D3 | Commit the Carbon v1 artifacts | Yes, gzipped, if size allows; restores `check_evidence.py` on a clean clone. |
| D4 | v2 detection figure | Supplementary figure (keeps main-figure numbering stable against the submitted PDF). |

## Revision sequence

Follows the Lane 3 correction order: ledger, then figures, then Results, then outward, then
Limitations, then rebuttal.

1. **Ledger (CPU only, `[A]` entries).**
   - v2 clean correct-key strength median and minimum per model (from the committed v2 trial
     files).
   - v3 per-event cost in `-log10 P_win` for both models.
   - Optional one-sided v1 bounds (0/192 and 1/192) for a like-for-like comparison.
   - v2 best-window counts, if cited.
   - Update `paper/context/evidence_map.md`.
2. **Figures (never hand-edited).**
   - Extend `scripts/make_paper_figures.py` with a digest-checked mode that reads the v3
     artifacts. Panels: detection rate against per-base rate (log axis) for four kinds and both
     models, with exact intervals and the ordinary-null rate against the 1% line.
   - Settle the v2 figures under D4.
   - If D3 lands, regenerate to fix the en-dash (CONF-11).
3. **Methods.**
   - §3.1: note the second execution platform.
   - §3.3: F7 sentence.
   - §3.4: v2 cohort (F5).
   - §3.6: one-sided versus two-sided bounds, prompt-level versus read-level, and the predeclared
     family roles.
   - New subsection: edit-rate channel (F3).
4. **Results.**
   - §4.3: split v1 (Table 1) from v2 (new table plus FWER headroom); rewrite the strength-gap
     paragraph (F1).
   - §4.4: point forward instead of disclaiming.
   - New §4.5: edit-rate characterization (F2, F4).
5. **Outward propagation.** Abstract, then Introduction, Discussion, and Conclusion:
   - "Bounded" becomes an upper confidence bound.
   - Symmetric control reporting.
   - Ceiling framing per F4.
   - Add edit-rate and v2 replication to the Conclusion.
   - Corpus wording.
6. **Limitations and statements.**
   - Remove paths, namespaces and the sign-off narrative.
   - Reconcile "declared scope boundary" with the widened regime.
   - Replication wording (F6).
   - Protocol-audit wording, Reproducibility and Data availability (F8).
7. **Rebuttal draft.** Re-sync W1, W4, W7, M2 and M5 with the revised text and figure numbers.
8. **Verification.**
   - `check_evidence.py`, unit tests, `ruff`.
   - Paper build. The current container has no TeX engine, so build elsewhere.
   - Re-run Lane 3 checks C1-C12, then an evidence-auditor pass over the new sections.

---

## Applied, 2026-09-30

All findings above were fixed in the working tree. The manuscript builds cleanly (18 pages, no
undefined references), `scripts/check_evidence.py` fails only on the five known missing Carbon
primary-cohort files, and the unit tests pass (131, 9 skipped).

| Finding | Change |
|---|---|
| F1 | §4.3 strength paragraph rewritten: medians 790.6/798.8 and 792.9/799.7; the weakest GENERator read explained (174 excluded contexts, 334 scored tokens, 54.6% ones, 9% of gap); "future work" removed. |
| F2 | Natural-log values removed; the per-edit cost is now given as median window strength from the second cohort's single-edit reads (about 2% lost per substitution, about 45% per insertion or deletion). Units correction appended to the v3 execution record and the Lane 1 document. |
| F3 | New Methods subsection (edit-rate series) and Results §4.6 with new Figure 5 (`fig5_edit_rate`, rendered by `make_paper_figures.py --edit-rate`, values in `figure_values_edit_rate.json`). Limitations no longer cites repository paths, namespaces, or the sign-off; the "declared scope boundary" versus "widened" contradiction is gone; the Conclusion now reports the result. |
| F4 | Abstract, Introduction, Discussion, and Conclusion state "complete or nearly complete through 2% in both models"; the one-read GENERator exception is stated in §4.6 with the one-point agreement between models. |
| F5 | Methods describe the second cohort (12 of the 16 records, six organisms, new keyed functions), the one-sided bound, the prompt-level versus per-read comparison, and the ordinary/wrong-key roles fixed before generation. New Table 2 gives every cell. "Bounded the rate" replaced by "upper confidence bound"; the wrong-key cell appears in the Abstract. |
| F6 | §4.5 presents the second cohort as a replication of detection; Supplementary Figures S1 and S2 use the previously orphaned v2 figures; Limitations and the Reproducibility statement distinguish this internal repeat from an independent replication. |
| F7 | §3.3 sentence corrected; measured conservatism moved to §4.5. |
| F8 | Reproducibility, Data availability, and Limitations reworded (audit recovers eight of nine settings). |
| New, F9 | §3.3 said detection *requires* a region whose alignment survives across a full 384-base window. The edit-rate results contradict this (every read detected at 2% indels, where stretches between indels average about 50 bases). Rewritten: tokens that lose frame or context only dilute the count, so a window needs enough intact tokens, not an intact span. Rebuttal M3 updated to match. |

New derived evidence (no rerun): `scripts/derive_strength_summary.py` →
`evidence/derived/strength_summary_2026_09_30.json`, ledger entries
`synthid.v2.strength_gap.cohort_strength_summary`,
`synthid.v2.detector.correct_key_strength_by_condition`, and
`synthid.v3.detector.edit_rate_model_agreement`, with `tests/test_strength_summary.py`.
`paper/context/evidence_map.md` lists every identifier the revised text cites. The rebuttal draft's
W1, W4, W7, W8, A2, and M3 responses were rewritten to match.

### Still open

- **D3 not done.** The Carbon primary-cohort result files are not in this checkout, so they could
  not be committed. Whoever holds them should add them (compressed, as for the second cohort);
  that restores `check_evidence.py` and allows the Carbon figures to be regenerated with the en dash
  in "Jensen–Shannon" (CONF-11).
- The v3 admission document names a co-author's sign-off given "in session"; that co-author
  should confirm it in writing.
- `CLAUDE.md` and `AGENTS.md` still say multiple-edit experiments are outside the threat model,
  while `docs/threat_model.md` and now the manuscript include the edit-rate series. The authors
  should reconcile the instruction files.
- Seven lint errors predate this revision (`tests/test_multi_base_edit.py`,
  `scripts/build_large_public_prompt_cohort.py`, `scripts/hpc/run_direct_synthid_fpr.py`,
  `scripts/run_synthid_edit_rate_pilot.py`, `src/genomic_watermarks/synthid_boundary.py`).
- The language and flow pass is next: `paper/context/language_flow_prompt.md`.
