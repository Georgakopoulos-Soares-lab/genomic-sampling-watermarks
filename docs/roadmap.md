# Roadmap

Updated 2026-11-13.

## Done

- [x] Development cohort: sampler checks, 14 quality proxies, detection, single-base edits, both
  models. Admitted 2026-09-09.
- [x] Detection cohort of 1,608 prompts: detection, false-positive bounds, single-base edits.
- [x] Non-adaptive edit-rate series, admitted 2026-09-29.
- [x] Strength analysis, search cost, correction conservatism, Carbon protocol audit.
- [x] arXiv submission, 2026-10-03.
- [x] ICLR 2027 reviews received (submission 32263) and integrated into the manuscript text,
  2026-11-12: `paper/reviews/2026-11-12_iclr_review_integration.md`.
- [x] Local review studies S0 to S4 (items 1 to 4 below) executed on a locally regenerated 512-prompt
  cohort and admitted as `synthid.v5.*`, 2026-11-13: protocol
  `docs/research/synthid_v5_review_studies_protocol_2026_11_12.md`, execution record
  `docs/research/synthid_v5_review_studies_execution_2026_11_13.md`. Manuscript use is still to do;
  the S4 sampling-path cross-check is pending.

## ICLR revision, open

Wording cannot close these. Items 1 to 4 were measured locally (`synthid.v5.*`, executed
2026-11-13); the measurements are not yet in the manuscript.

1. [x] Detection by region length, flank length, placement, strand, and initial phase (all three
   reviewers). Measured as S1; manuscript text pending.
2. [x] Comparison with narrower detectors (aligned, phase-only, span search) at the same
   sequence-level false-positive target, with runtime (Reviewer GmoA). Measured as S2; manuscript
   text pending.
3. [x] Calibration of the full search across many independent keys and on genomic DNA that no
   model generated (Reviewer zdRG). Measured as S3; manuscript text pending.
4. [x] Per-token entropy against strength (Reviewer ot4K). Measured as S4; the sampling-path
   cross-check is pending; manuscript text pending.
5. [ ] Author confirmation that no verifier setting changed after outcomes were observed (Reviewer
   zdRG).
6. [ ] Decide whether to admit more of the existing GENERator aligned-prefix validation artifact.
7. [ ] ICLR-format, anonymized build of the revised manuscript, and the author responses.

## Outstanding from before the reviews

- [ ] Restore the five Carbon development-cohort result files so `scripts/check_evidence.py`
  passes on a fresh clone and the development-cohort figures can be regenerated with current
  labels (`paper/reviews/2026-10-01_remaining_fixes.md`).
- [ ] Written co-author confirmation of the edit-rate sign-off
  (`docs/research/threat_model_edit_rate_v3_admission_2026_09_29.md`).
- [ ] Independent replication with a fresh cohort in a documented environment
  (`docs/research/dual_model_synthid_paper_rebuild_plan.md`).

## Out of scope

Other watermark constructions, detector-query or detector-guided attacks, and further multiple-edit
experiments (`CLAUDE.md`).
