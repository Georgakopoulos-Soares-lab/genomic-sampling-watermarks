# Amendment: GENERator version-one panel analyses

Date: 2026-09-11

## Scope and authority

The user authorised deriving the GENERator counterparts of the Carbon quality, detection-strength,
and single-edit panels and updating the associated evidence and manuscript files. This amendment
extends the 2026-09-09 dual-model admission to three derived `[A]` entries from already admitted,
unchanged version-one artifacts. It introduces no generation, model scoring, detector search,
calibration, new cohort, or new edit condition. The then-current M5 execution rule was superseded
on 2026-09-21; future experiments still require a new `synthid.v2.*` identity and a documented
execution environment.

The earlier manuscript and review notes incorrectly described GENERator's window strengths,
strongest-window lengths, and per-measure effects as unavailable or not retained. They were absent
from the manuscript's derived ledger entries and figures, but are present in the retained source
files. This amendment corrects that interpretation without rewriting historical review notes or
the original execution records.

## Verified sources

| Artifact | SHA-256 |
|---|---|
| `outputs/generator_synthid_e16_v1/sequence_comparison_summary.json` | `d8e3c03b2d0e3a2639c521889ea29dd804e8a741d3cf43818cb79f31ae821401` |
| `outputs/generator_synthid_position_independent_v1/trials.jsonl` | `3de1d8f7b8a946d3a5149f48ac30e357ceb2fa812eddbe6a11a5e836c7106d99` |
| `outputs/generator_synthid_position_independent_v1/summary.json` | `ac28bf5ed078fccd1eac5a97cabdd4f2a4e67f07a75d291aa3c5e0abd15830f7` |

These hashes match the existing ledger. All 4,608 trial records were checked for the declared
orientation/start/window search, exact local binomial tails, full-search corrected probabilities,
decisions, coordinates, repetition accounting, and the complete prompt/draw/family/condition grid.
Prompt-level exact intervals were independently recomputed and compared with the retained summary.
This checks recorded arithmetic and consistency, not a replay of each search or a verification of
the original generation files on their original execution platform.

## Derivation and execution

Run from the repository root with Python 3.11+ and SciPy:

```bash
.venv/bin/python scripts/derive_generator_paper_analysis.py
.venv/bin/python scripts/derive_generator_paper_analysis.py --check
MPLCONFIGDIR=.cache/matplotlib .venv/bin/python scripts/make_paper_figures.py --model generator
```

The first command creates `evidence/derived/generator_v1_paper_analysis_2026_09_11.json` exclusively
and refuses to overwrite it. The second recomputes and checks the values, source hashes, and analysis
code hashes without writing. A changed analysis requires a new identity and output file.

The derivation ran on Darwin arm64 CPU under Python 3.12.13 in approximately 12.2 seconds. The
artifact records the exact interpreter command, base Git revision, executed source hashes, macOS
version, and SciPy version. Source artifacts and the original execution narrative retain the exact
model/tokenizer revisions, cohort, generation policy, configurations, and execution provenance. No
model was loaded and no GPU or MPS computation was used.

Quality effects and their raw bootstrap bounds already existed. The bounds are multiplied by the
observed standardized-effect/mean-difference ratio, matching Carbon's figure convention. This is
a change of units, not a bootstrap confidence interval that re-estimates the denominator.
Window strength is `-minimum_local_log_p_value / log(10)`, retaining finite evidence when the
ordinary probability has underflowed. Strongest-window lengths are tallied directly. Prompt-level
recall requires both draws; control positives require either draw. Every edit condition remains
separate, including GENERator's zero wrong-key positives after deletion.

## Added evidence

- `synthid.generator.quality.metric_family_effects`: all 14 effects and rescaled intervals; maximum
  absolute effect 0.1113797288168427 for mean homopolymer-run length.
- `synthid.generator.detector.strength_separation`: all family/condition summaries; weakest marked
  clean strength 19.614793673583744 and weakest marked insertion strength 10.297484891648768.
- `synthid.generator.detector.strongest_window_length`: 184/384 shorter strongest windows after
  insertion and 157/384 after deletion, compared with 3/384 on unedited reads.

Figures 2–4 each pair the retained Carbon a/b panels with corresponding GENERator c/d panels using
the same axis limits, units, colour encodings, and definitions. Original Carbon PDF/PNG hashes are
checked before reuse. The five missing Carbon source artifacts remain an open audit limitation;
their absence does not block independent verification and plotting of the present GENERator data.

This adds supporting analyses, not independent replication. The shared cohort, two fixture keys,
single-edit scope, finite null sample, original execution platforms, Carbon protocol discrepancy,
and absence of biological/security validation continue to qualify the manuscript.
