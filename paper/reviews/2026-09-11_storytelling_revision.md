# Storytelling and readability revision

Date: 2026-09-11

## Objective

Improve the manuscript's narrative flow without changing its empirical scope, numerical results, or
claim boundaries.

## Changes

- Removed the front-loaded terminology table so the Introduction can move directly from provenance
to DNA-specific alignment uncertainty and the study contribution.
- Reframed the Abstract and Introduction around the provenance question, the shared sampling
policy, and the DNA synchronization problem that motivates position-independent detection.
- Condensed the background survey and made the direct canonical-token policy an explicit shared
experimental design choice in Methods.
- Added a Results opening that states the three linked evaluation questions and identifies
position-independent detection as the primary practical outcome.
- Rewrote sampler, proxy-quality, detection, and edit prose so that each paragraph begins with its
interpretation rather than a sequence of statistics.
- Paired the Carbon and GENERator panels in Figures 2--4, with Carbon in panels a,b and GENERator
in panels c,d, labelled each stacked model panel directly, and updated the evidence map accordingly.
- Removed duplicated Results prose introduced during the paired-panel transition.
- Moved all pending full-width result figures before the Discussion, ensuring that the reader sees
the visual evidence before its interpretation.
- Consolidated the Limitations section into three boundaries: generalization and execution
provenance, false-positive-rate precision, and biological/security scope.

## Preserved boundaries

All values remain traceable to the evidence ledger. The manuscript continues to distinguish
fixed-key sampling from expectation over fresh keyed functions, reports full-search correction,
limits edit claims to the tested single-base non-adaptive conditions, and does not claim biological
function, operational false-positive control below 1%, or secret-key security.

## Verification

- `cd paper && ./scripts/build.sh` completed successfully.
- The rebuilt PDF was rendered and checked visually: all result figures precede the Discussion, the
paired panels remain legible, and no stale Carbon-only or ``not retained'' claims remain.
- `PYTHONPATH=src python scripts/derive_generator_paper_analysis.py --check` verified the retained
GENERATOR-derived analysis artifact.
- `scripts/check_evidence.py` still reports the five pre-existing missing Carbon artifacts; it
reported no new map or derived-GENERator inconsistency.
