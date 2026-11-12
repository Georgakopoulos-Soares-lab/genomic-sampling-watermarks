# Paper workspace

`manuscript/source/main.tex` is the dual-model Carbon-500M and GENERator-v2 1.2B SynthID
manuscript. It reports sampler validation, sequence-quality proxies, position-independent
detection, single-base edits, and a non-adaptive edit-rate series for one watermark
(`synthid-tournament-v1`) and one verifier (`synthid-position-independent-detector-v1`). Every
printed number resolves to an identifier in [`context/evidence_map.md`](context/evidence_map.md)
and from there to [`../evidence/measurements.yaml`](../evidence/measurements.yaml).

## Versions

| Version | Where | Notes |
|---|---|---|
| ICLR 2027 submission 32263 | [OpenReview](https://openreview.net/forum?id=vo1qxcMxxx&noteId=LyX9i394f8); PDF not in the repository | development cohort only; the version the reviewers read |
| arXiv, 2026-10-03 | `submission/arxiv_2026-10-03/` | adds the detection cohort and the edit-rate series |
| ICLR revision, in progress | `manuscript/source/main.tex`, branch `iclr-2027-revision` | review comments integrated 2026-11-12 |

Reviewers cite the submitted PDF's numbering. The mapping to the current manuscript is in
`reviews/2026-09-21_openreview_rebuttal_draft.md`, and the review-by-review status is in
`reviews/2026-11-12_iclr_review_integration.md`.

## Terminology

The manuscript holds one term per concept: marked sequence, ordinary sequence, wrong-key control,
development cohort, detection cohort, window, strength, token phase, per-base edit rate, verifier.
Reject an edit that introduces a synonym. `context/language_flow_prompt.md` lists the internal
vocabulary that must not appear and the checks to run after a prose edit.

## Disclosed caveats

The Limitations section states these, and `context/evidence_map.md` tracks them:

1. every test sequence has one layout, a 384-base prompt followed by a 3,072-base generated region;
2. the detection cohort is not an independent replication;
3. the Carbon development-cohort protocol document does not match the hash recorded in its result
   (`../docs/research/carbon_provenance_discrepancy_audit_2026_09_21.md`);
4. edits are random and never consult the detector;
5. no narrower detector and no other watermark construction was compared.

## Figures

`figures/*.pdf` are built by `../scripts/make_paper_figures.py`, which verifies the SHA-256 of
every source artifact and writes each plotted value to a manifest.

| Figure | Content | Manifest |
|---|---|---|
| 1 | method illustration and search count | `figure_values.json` |
| 2 | quality proxies, development cohort | `figure_values.json` |
| 3, 4 | detection and single-base edits, detection cohort | `figure_values_v2.json`, `figure_values_generator_v2.json` |
| 5 | edit-rate series | `figure_values_edit_rate.json` |
| S1, S2 | detection and single-base edits, development cohort | `figure_values.json` |

Carbon is in panels `a,b` and GENERator in `c,d`, except Figure 5. Regenerating the
development-cohort figures needs the Carbon development-cohort result files, which are not in the
repository; the commands are in `reviews/2026-10-01_remaining_fixes.md`.

## Build

```bash
./scripts/build.sh
```

The script uses `tectonic` if present and otherwise `latexmk`, and writes
`manuscript/build/main.pdf`. Copy it to `manuscript/main.pdf` when the tracked PDF should change.

## Review notes

Add a dated note under `reviews/` for every pass. Do not overwrite earlier notes.
