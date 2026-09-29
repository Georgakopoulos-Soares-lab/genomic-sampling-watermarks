# Lane 3 reconciliation — what changed since the 2026-09-22 manuscript (2026-09-29)

**Source:** `2026-09-21_lane3_reconciliation.md` (procedure), executed against the state left by
Lane 1 (`2026-09-21_lane1_hpc_runs.md`, PR merged 2026-09-25) and Lane 2
(`2026-09-21_lane2_claims_background.md`, PR merged 2026-09-22 — three days *before* Lane 1
finished). The manuscript was therefore stale relative to the evidence ledger; this reconciliation
closed that gap.

This document is the reconciliation **record**. The procedure document of the same stem at the
repository root is not; references elsewhere in the repository that cite `CONF-*` should point
here. The conflict ledger is in section 8 below.

Two passes were run. The first (2026-09-29, morning) produced CONF-01 through CONF-12 and applied
the manuscript edits. The second (2026-09-29, later the same day) re-ran the C1–C12 detection pass
against the edited tree, as the procedure's step 7 requires, and produced CONF-13 through CONF-23.
The second pass found that the first had propagated an error out of Lane 1's execution record
instead of catching it (CONF-13) and had stopped short of the outward propagation its own
correction sequence prescribes (CONF-15 through CONF-17).

## 1. New evidence admitted

Lane 1's delta packet (`evidence/derived/2026-09-21_results_delta.json`) reports 45 results.
Forty are ledger entries:

- `synthid.v2.*` (**35** ledger entries): a second, independently frozen 1,608-prompt cohort
  (1,544 evaluation), a second execution environment (TACC Lonestar6, A100 GPUs), scaled
  false-positive-rate measurement, a resolved Carbon provenance audit, measured detector search
  cost, and a measured Bonferroni-conservatism headroom estimate.
- `synthid.v3.*` (**5** ledger entries): a full-cohort, multi-rate, non-adaptive edit-robustness
  characterization plus its source manifest, admitted under an author sign-off recorded in
  `docs/research/threat_model_edit_rate_v3_admission_2026_09_29.md` (see CONF-01), confirmed by the
  author in session on 2026-09-29.

The remaining five delta results are deliberately not ledger entries: four superseded 96-prompt
pilot results (`synthid.pilot.*`, outcome `inconclusive`) and one pair of figure-regeneration
receipts (`synthid.v2.{carbon,generator}.figures.detection_rebuilt`, outcome `confirms`, carrying
no measured quantity). Both are accounted for in `paper/context/evidence_map.md`. No delta result
carries outcome `refutes`.

## 2. Claims that changed

| Claim | Before | After | Evidence |
|---|---|---|---|
| Operational false-positive rate | "compatible with, but do not establish" 1% (192 prompts) | bounded at ≤0.8499% across both models, all 4 primary conditions (1,608-prompt cohort) — retains the original 192-prompt interval alongside it | `synthid.v2.detector.fpr_upper_bound` (confirms) |
| Carbon protocol-hash discrepancy | "unresolved provenance gap" | resolved: confined to document text, does not affect the generative distribution or detection statistic | `synthid.v2.carbon.provenance.audit` (confirms) |
| Edit-rate robustness scope | untested order-of-magnitude prediction of failure near 1% | measured: full recovery through 2%/base on Carbon and 1%/base on GENERator; on both models ~93% for indels at 5% and collapse by 10%; original 1/*r* heuristic falsified (weakens→refines) | `synthid.v3.{carbon,generator}.detector.edit_rate_full_detection_ceiling` (confirms) |
| Detector search cost | analytic complexity only | measured: 0.0956 s/read at N=3,456 (median, single-threaded, AMD EPYC 7763) | `synthid.v2.detector.search_seconds_per_read` (confirms) |
| Bonferroni conservatism | qualitative argument only | measured: 9.5×/5.4× headroom vs. 1% target; effective test count ≈830–850 vs. 16,136 searched | `synthid.v2.detector.{empirical_familywise_rate,effective_independent_windows}` (confirms) |
| Window-score summary selection | stated without naming a model | now states the selection is independently verified for GENERator only; Carbon uses the same summary without an equivalent committed comparison | pre-existing gap, flagged by Lane 2's own post-implementation audit, not previously corrected in `main.tex` |

Every row above is a `weakens`→`confirms` upgrade or a precision gain; none is a `refutes`.

**The edit-rate ceiling is per model and must be stated that way.** Carbon's is 2% per base,
GENERator's is 1%, because GENERator's mixed-indel cell at 2% detects 3,087 of 3,088 reads. A
single joint "2% on both models" is false; a single joint "1% on both models" is true but discards
Carbon's measured result and violates the repository's own rule that a claim resting on one model
names that model. See CONF-13.

## 3. Clarifications (already closed by Lane 2, unaffected by this pass)

G statistic and Monte Carlo reference (W5a); 256-state Benjamini–Hochberg/Bonferroni correction
(W5b); two window-score summaries and selection rule, mean vs. weighted-mean (W6 — see the model-
naming correction above); named max-effect measures (T6); short-window boundary arithmetic,
independently re-verified exact (M3); algorithmic complexity, now with a measured constant (M5).

## 4. Declined, with reasons (unchanged)

Multiple-edit *sweep as an adaptive/detector-guided experiment* — still declined, `AGENTS.md`.
Red/green-list baseline — still declined, `AGENTS.md`/`PROJECT.md`, property comparison stands in
its place. Downstream biological benchmarks — still future work, `PROJECT.md` claim boundary.

## 5. Still open

- **Not fixable in this session (CONF-10):** `outputs/carbon_synthid_e16_v1/` and
  `outputs/carbon_synthid_position_independent_v1/` are absent from every checkout (never
  committed, not gitignore-exempted), so `scripts/check_evidence.py` cannot pass end-to-end on any
  machine that lacks them locally. Carbon's sampler, quality, and detection claims remain
  indirectly verified only, exactly as `paper/context/evidence_map.md` already discloses.
- **Deferred, cosmetic (CONF-11):** figure axis labels read "Jensen-Shannon" (hyphen);
  prose/captions read "Jensen–Shannon" (en dash). Not fixed here because regenerating Carbon's
  figures safely requires the same missing v1 artifacts as above; GENERator-only regeneration
  would leave the two models' figures on different code paths mid-cycle.
- **Not recoverable (CONF-21):** the first pass's conflict ledger was never committed. Rows
  CONF-02 through CONF-08 are referenced by no surviving document and their content cannot be
  reconstructed. Section 8 records what is evidenced and marks the gap rather than inventing rows.
- **AD-5 (informational, CONF-12):** the submitted PDF and the repository source remain separate
  lineages with different figure numbering. Authors chose to edit the repository version as-is.
  The mapping table lives in `paper/reviews/2026-09-21_openreview_rebuttal_draft.md`, which states
  the submitted PDF's numbering that any response must use.

## 6. Files touched

**First pass.** `paper/manuscript/source/main.tex` (§3.3 ×2, §4.3 ×2, Limitations ×3, Conclusion,
new `\label{sec:results}`); `docs/threat_model.md`; `paper/context/evidence_map.md`;
`2026-09-21_lane1_hpc_runs.md` (cross-reference only);
`paper/reviews/2026-09-21_pat_response_lane2.md` (Open items);
`paper/reviews/2026-09-21_openreview_rebuttal_draft.md` (W1, W4, W6, W8, M5, header note); new file
`docs/research/threat_model_edit_rate_v3_admission_2026_09_29.md`.

**Second pass.** `paper/manuscript/source/main.tex` (Abstract, Introduction ×2, Discussion ×2,
Limitations edit-rate paragraph, Figure 3 caption, `\evtag` macro removed from the preamble);
`docs/threat_model.md`; `paper/context/evidence_map.md`;
`docs/research/threat_model_edit_rate_v3_admission_2026_09_29.md`;
`docs/research/synthid_v3_edit_rate_execution_2026_09_24.md` (dated correction note appended, no
result or digest altered); `paper/reviews/2026-09-21_openreview_rebuttal_draft.md` (W1);
`paper/reviews/2026-09-21_pat_response_lane2.md` (cross-references); this document.

No files under `outputs/*_v1/` were touched. No evidence entry was modified in place. No figure was
hand-edited or regenerated.

## 7. Verification run after fixes

Re-run at the end of the second pass, against the fully edited tree:

- `PYTHONPATH=src python3 -m unittest discover -s tests -v` — 126 pass, 8 skipped (require a pinned
  upstream clone, expected on this machine).
- `cd paper && ./scripts/build.sh` — builds clean, no undefined references, only pre-existing
  underfull-hbox warnings.
- `python3 scripts/check_evidence.py` — fails only on the 5 pre-known missing Carbon v1 artifact
  paths (CONF-10); nothing else.
- `uv run ruff check .` — 7 pre-existing errors in `tests/test_multi_base_edit.py`, not touched by
  either pass.

## 8. Conflict ledger

Severity: **blocking** (a false or unsupported claim would ship), **major** (a reviewer point goes
unanswered or an inconsistency is visible), **minor** (wording, terminology, formatting).

| ID | Type | Severity | Evidence | Conflict | Rule applied | Fix | Verified by |
|---|---|---|---|---|---|---|---|
| CONF-01 | C10 | blocking | `synthid.v3.*`; `docs/threat_model.md` | Full-cohort v3 run admitted and cited with no independent sign-off; only self-referential authorization inside its own protocol/execution docs | Precedence 1 — declared scope outranks a reviewer request | Author sign-off recorded in `docs/research/threat_model_edit_rate_v3_admission_2026_09_29.md`; confirmed by the author in session 2026-09-29 | pass 2 |
| CONF-02 – CONF-08 | — | — | — | *Not recoverable.* The first pass's ledger was never committed; these rows are referenced by no surviving document | — | None possible; gap disclosed in §5 | pass 2 |
| CONF-09 | C10 | major | `2026-09-21_lane1_hpc_runs.md` | Lane 1 wrote `docs/threat_model.md` against its own declared write boundary, on a verbal instruction with no written record | Precedence 6 — disclose, do not smooth | Same sign-off document supplies the written record | pass 2 |
| CONF-10 | C11 | major | `outputs/carbon_synthid_e16_v1/`, `outputs/carbon_synthid_position_independent_v1/` | Carbon v1 artifacts never committed and not gitignore-exempt, so `check_evidence.py` cannot pass on any checkout | Precedence 6 | Not fixable here; tracked in §5 and already disclosed in `evidence_map.md` | pass 2 |
| CONF-11 | C8 | minor | `scripts/make_paper_figures.py` | Figure axes use a hyphen in "Jensen-Shannon"; prose uses an en dash | Precedence 6 | Deferred — regeneration blocked by CONF-10 | pass 2 |
| CONF-12 | C8 | major | submitted PDF vs. `main.tex` (AD-5) | Two lineages with different figure and section numbering | Author decision | Repository version edited as-is; mapping stated in the rebuttal draft's header | pass 2 |
| CONF-13 | C3 | blocking | ledger `synthid.v3.generator.detector.edit_rate_full_detection_ceiling` = 0.01 vs. `main.tex`, `docs/threat_model.md`, `evidence_map.md`, rebuttal draft, admission doc, all reading "2% on both models" | GENERator's ceiling is 1%: its mixed-indel cell at 2% detects 3,087/3,088. Error originates in `docs/research/synthid_v3_edit_rate_execution_2026_09_24.md`, which pass 1 propagated rather than checked | Precedence 3 — ledger outranks the manuscript | All five documents restated per model; dated correction note appended to the execution record | pass 2 |
| CONF-14 | C3 | major | same ledger entries | "substitutions still recovered every read" at 5% is false for GENERator (0.99968) | Precedence 3 | Restated as "every Carbon read and all but one GENERator read" in manuscript, threat model and rebuttal | pass 2 |
| CONF-15 | C5 | blocking | `main.tex` Abstract | Abstract kept "no more than one positive result for each model, control family, and condition" and "robustness beyond the evaluated non-adaptive single-base edits" after §4.3 and the threat model moved — the failure C5 names by hand | Precedence 5 — sections raised to the ledger-supported claim | Abstract rewritten: scaled-cohort bound, per-model edit ceilings, residual scope limited to an adaptive editor | pass 2 |
| CONF-16 | C5 | major | `main.tex` Introduction | Summary paragraph kept "control counts were compatible with the declared false-positive target"; §2.2 kept "tests statistical detection after one non-adaptive base edit" | Precedence 5 | Both updated | pass 2 |
| CONF-17 | C5 | major | `main.tex` Discussion | Discussion never propagated: no edit-rate result, no FPR upgrade; "no general guarantee against more extensive modification" now understated | Precedence 5 | Opening and alignment paragraphs updated | pass 2 |
| CONF-18 | C3/C11 | major | `main.tex` Limitations; rebuttal W1 | "roughly seventeen times" and "roughly 290 times" resolve to no ledger entry; both derive from the 96-prompt pilot's clean baseline, and the full cohort implies ≈19×, not 17× | `CLAUDE.md` — every manuscript number resolves to `evidence/measurements.yaml` | Replaced with the ledger-resident medians −994.67 (one indel) and −1778.65 (one substitution); the mechanism argument is unchanged | pass 2 |
| CONF-19 | C11 | major | this document §1; `evidence_map.md` | "45 v2 entries" and "4 v3 entries" both wrong; ledger holds 35 and 5, and 45 is the delta-packet total | Precedence 3 | Both corrected, with the five non-ledger delta results accounted for | pass 2 |
| CONF-20 | C2/C11 | major | delta packet vs. ledger | `synthid.v2.{carbon,generator}.figures.detection_rebuilt` described as "inconclusive/non-numeric" when the delta marks them `confirms` and they are not ledger entries at all; four `synthid.pilot.*` delta results unaccounted for anywhere | Precedence 3 | `evidence_map.md` now states what each of the five non-ledger results is and why it carries no ledger identity | pass 2 |
| CONF-21 | C11 | major | `lane1_hpc_runs.md`, `pat_response_lane2.md`, admission doc, `evidence_map.md` | All cite the root procedure template as the source of `CONF-*` rows; the template's ledger is an empty header. `pat_response_lane2.md` cites CONF-12 against a ledger that was never committed | Precedence 6 | Ledger committed here (§8); all cross-references repointed to this file | pass 2 |
| CONF-22 | C5 | minor | `main.tex` Figure 3 caption | "consistent with a false-positive rate below 1% without establishing one" reads as the paper's current position rather than as the 192-prompt cohort's | Precedence 5 | Caption scoped to its own cohort and pointed at the scaled bound | pass 2 |
| CONF-23 | C1 | minor | `main.tex` preamble | `\evtag` macro still defined with a comment requiring its removal before submission; zero uses remained | Procedure §5 acceptance item | Macro removed | pass 2 |

Checked and found clean in pass 2: C1 (zero `\evtag` uses), C2 (no `refutes` in the delta; every
unused result accounted for), C6 (α = 0.01 and the four window lengths unchanged; M = 16,136
unchanged), C9 (no citation added by pass 1 or 2), C10 (no biological-function, viability,
expression, safety, cryptographic-security, multiple-edit-as-adaptive, detector-guided or
second-construction claim entered either diff).
