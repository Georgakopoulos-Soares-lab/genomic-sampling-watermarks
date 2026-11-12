# Position-independent SynthID for genomic DNA generation

This repository contains one sampling watermark (`synthid-tournament-v1`), its matched ordinary
control, and one standalone verifier (`synthid-position-independent-detector-v1`), evaluated on
Carbon-500M and GENERator-v2 1.2B. The verifier needs the observed DNA, the key, the generation
domain, and fixed public settings. It does not need the prompt or the model.

## Status

- Manuscript: `paper/manuscript/source/main.tex`, posted to arXiv on 2026-10-03
  (`paper/submission/arxiv_2026-10-03/`) and under review at ICLR 2027 as submission 32263
  ([OpenReview forum](https://openreview.net/forum?id=vo1qxcMxxx&noteId=LyX9i394f8)).
- Current work: the ICLR revision, on branch `iclr-2027-revision`. The reviews, the changes made
  in response, and the open items are in
  [`paper/reviews/2026-11-12_iclr_review_integration.md`](paper/reviews/2026-11-12_iclr_review_integration.md).
- Next steps: [`docs/roadmap.md`](docs/roadmap.md).

## Evidence in the manuscript

Every manuscript number resolves through
[`paper/context/evidence_map.md`](paper/context/evidence_map.md) to
[`evidence/measurements.yaml`](evidence/measurements.yaml).

| Part | Cohort | What it supports |
|---|---|---|
| Sampler checks, 14 quality proxies, window-score selection | development, 256 prompts (192 held out) | no detectable quality change; sampler follows its distributions at tested states |
| Detection, false-positive bounds, single-base edits | detection, 1,608 prompts (1,544 held out) | every marked sequence found; one-sided 95% upper bounds on the ordinary false-positive rate at most 0.850% |
| Edit-rate series | detection cohort, rescored | detection complete or nearly complete up to a 2% per-base rate of random edits |

Detection-cohort positives per model and condition, out of 3,088 sequences:

| Edit | Carbon correct key | Carbon ordinary | Carbon wrong key | GENERator correct key | GENERator ordinary | GENERator wrong key |
|---|---:|---:|---:|---:|---:|---:|
| None | 3,088 | 3 | 5 | 3,088 | 5 | 2 |
| One substitution | 3,088 | 3 | 5 | 3,088 | 5 | 2 |
| One insertion | 3,088 | 3 | 6 | 3,088 | 6 | 2 |
| One deletion | 3,088 | 4 | 9 | 3,088 | 7 | 3 |

The wrong-key bound for Carbon after a deletion is 1.015%, above the 1% target, and the manuscript
reports it.

## Scope

- Statistical detection and sequence-quality proxies only. No claim of biological function,
  viability, safety, or secret-key security.
- Every test sequence has one layout: a 384-base prompt followed by a 3,072-base generated region.
  Other region lengths and placements are untested.
- Edits are random and never consult the detector. Detector-query and detector-guided editing are
  outside the threat model, and no further multiple-edit experiment is in scope.
- The experimental keys are published for reproducibility and are not deployment secrets.
- The detection cohort is not an independent replication.

## Detector command

```bash
export GENOMIC_SYNTHID_KEY='<hex-encoded-secret-key>'
PYTHONPATH=src python3 scripts/detect_synthid_position_independent.py \
  --input observed.fasta --domain '<generation-domain>'
```

The command does not print the key or the input DNA. See
[the detector protocol](docs/research/synthid_position_independent_detector_protocol.md).

## Verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/doctor.py
python3 scripts/check_evidence.py
uv run ruff check .
cd paper && ./scripts/build.sh
```

`check_evidence.py` fails on five Carbon development-cohort result files that were never committed;
their digests are in the ledger. Model weights and source DNA are not stored in this repository.
