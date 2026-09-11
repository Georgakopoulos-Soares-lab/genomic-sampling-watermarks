# Academic style and title-page revision

Date: 2026-09-11
Scope: manuscript prose, title-page metadata, and rebuilt PDF. No experiments were run and no
measurement ledger entry, result artifact, equation, result-table value, or figure asset was changed.

## Requested changes

- Replaced the title with “Tracing Model-Generated DNA with Position-Independent SynthID
  Watermarking” in the manuscript and PDF metadata.
- Added Aris Karatzikos and Charalambos Koilakos with the existing University of Texas at Austin
  affiliation. Preserved the two equal-contribution designations and the corresponding author.
- Replaced the correspondence initials with the linked address `ilias@austin.utexas.edu`.
- Rewrote the Abstract and Introduction in academic language and extended the revision to the
  Background, Methods, Results, Discussion, Limitations, Conclusion, table definitions, and captions.
- Added a brief opening Discussion paragraph summarising the implementation, evaluation, and findings.
- Removed references to pinned model revisions and the prescribed replication machine, as requested.
  Retained actual execution platforms, outstanding independent replication, and the unresolved
  Carbon protocol-hash discrepancy. Exact provenance and future-run requirements remain in the
  repository evidence and protocol documentation.

## Claim precision

- Replaced “any” single-base edit with the tested edit conditions, avoiding an implication that all
  possible edit locations or nucleotides were exhaustively evaluated.
- Preserved the distinction between expectation over fresh keyed functions and fixed-key reweighting.
- Included fixed public settings in descriptions of the verifier's inputs.
- Described the full-search Bonferroni correction and clarified that its window count is recomputed
  when an edit changes read length, consistent with the detector and validators.
- Kept window-strength and selected-window interpretations specific to Carbon. Replaced assertions
  that shorter windows usually dominate with the supported increase in their frequency.
- Identified the prompt-level summary rows of Table 2 as the unedited condition; the per-condition
  read counts are unchanged.
- Retained uncertainty about operational false-positive rates, biological function, and key security.

## Verification

- The LaTeX build succeeds. Tectonic retrieved missing standard font files during the first build.
- Citation keys, equations, the complete detection table, and figure references were compared with
  the previous manuscript and are unchanged.
- `git diff --check` passes.
- `python3 scripts/check_evidence.py` reports the same five missing Carbon artifacts documented in
  earlier reviews: three files under `outputs/carbon_synthid_e16_v1/` and `summary.json` and
  `trials.jsonl` under `outputs/carbon_synthid_position_independent_v1/`. This prevents a complete
  local artifact check; no evidence files were modified.
- All 11 pages of the final PDF were rendered and visually inspected, including the title page,
  tables, figures, Discussion opening, and bibliography. No clipping or overlapping content was
  observed. Minor underfull-box warnings remain in the prose and existing bibliography.
- The verified PDF replaces `paper/manuscript/main.pdf`.
