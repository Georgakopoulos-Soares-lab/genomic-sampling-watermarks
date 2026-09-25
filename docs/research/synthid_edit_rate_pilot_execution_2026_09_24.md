# Edit-rate breakdown pilot — execution and result (L1-07 pilot)

**Date:** 2026-09-24. **Classification:** `pilot_not_admitted_evidence`.
**Protocol:** `docs/research/synthid_v3_edit_rate_pilot_protocol_2026_09_24.md`, frozen before any
measurement (SHA-256 of the amended document recorded below).

This pilot is **not** admitted evidence and no number here may enter
`evidence/measurements.yaml` or the manuscript. It exists to locate where the single-edit
guarantee stops holding.

## Authorisation and scope

AD-2 was authorised by the author in session on 2026-09-24 with the condition that the threat model
change only if the results honestly support it. The lane note's `Author sign-off` line should be
signed by the author directly; this document records the instruction, it does not stand in for it.

The edit channel is a **fixed public replay**. It never inspects the detector, the key, or any
score, so this is not a detector-guided or detector-query attack and stays inside the prohibition
in `AGENTS.md`. The detector is untouched: same depth 30, four-token context, 1,024 repetition
history, window set {384, 768, 1536, 3072}, both orientations, every base start, same full-search
correction at the same 0.01 target. No detector parameter was tuned to the edit rate.

## Method

Existing frozen v2 reads, no regeneration and no GPU. 96 evaluation prompts selected by the frozen
`carbon_synthid_validation_v1/prompt-split/v1` digest order alone, both draws, both models.
Rates 0, 0.0003, 0.001, 0.005, 0.01, 0.02, 0.05 and 0.10 per base, realised as
`round(rate x 3072)` events: 0, 1, 3, 15, 31, 61, 154, 307. Kinds: `substitution`,
`indel` (direction chosen per event), and the direction-pure `insertion` and `deletion`.

## The predeclared prediction was wrong

The lane note stated in advance that at a 1% indel rate an indel falls roughly every 100 bases
against a 384-base minimum window, so no window retains a clean reading frame and detection should
fail. **It does not fail.** Correct-key detection rate:

| Model | Kind | 0.03% | 0.1% | 0.5% | 1% | 2% | 5% | 10% |
|---|---|---|---|---|---|---|---|---|
| Carbon | substitution | 100 | 100 | 100 | 100 | 100 | 100 | 19.3 |
| Carbon | indel | 100 | 100 | 100 | 100 | 100 | 94.8 | 5.7 |
| Carbon | insertion | 100 | 100 | 100 | 100 | 100 | 91.7 | 6.2 |
| Carbon | deletion | 100 | 100 | 100 | 100 | 100 | 94.8 | 4.7 |
| GENERator | substitution | 100 | 100 | 100 | 100 | 100 | 99.5 | 17.2 |
| GENERator | indel | 100 | 100 | 100 | 100 | 100 | 92.7 | 6.8 |
| GENERator | insertion | 100 | 100 | 100 | 100 | 100 | 91.7 | 5.7 |
| GENERator | deletion | 100 | 100 | 100 | 100 | 100 | 94.8 | 3.1 |

Detection is complete through a 2% rate for every kind and both models, and collapses only at 10%.
The two models agree to within a few percent everywhere.

## Why the prediction missed

The frame-shift reasoning was directionally right but the margin was not accounted for. Median
correct-key `sequence_log_p_value`, where firing requires about -6.2:

| Model | Kind | clean | 0.03% | 1% | 5% | 10% |
|---|---|---|---|---|---|---|
| Carbon | substitution | -1822.2 | -1780.9 | -963.6 | -74.9 | -0.8 |
| Carbon | indel | -1822.2 | -1075.2 | -190.9 | -13.9 | 0.0 |
| GENERator | substitution | -1826.4 | -1787.9 | -959.1 | -75.1 | -0.4 |
| GENERator | indel | -1826.4 | -1065.9 | -190.5 | -13.9 | 0.0 |

A single indel costs over 700 log-units while a single substitution costs about 41, so per event an
indel is roughly seventeen times more damaging, exactly as the frame-shift argument predicts. What
the prediction omitted is that the clean statistic sits near -1822 against a threshold near -6.2,
about 290 times more evidence than firing requires. Decay is smooth and monotonic, and detection
holds until the margin reaches the threshold. The scheme does not resist editing by preserving
frame; it resists editing by starting with an enormous surplus of evidence.

## The amendment's own hypothesis was refuted

Amendment 1 proposed that mixed `indel` might survive because insertions and deletions cancel, so
the cumulative frame offset random-walks back to zero. If that were the mechanism, the
direction-pure channels would degrade faster. They do not: at 5% Carbon gives 94.8% for mixed
indel, 91.7% for pure insertion and 94.8% for pure deletion, and GENERator gives 92.7, 91.7 and
94.8. Cumulative frame offset is not the mechanism; per-event local damage is.

## Controls

- Edit counts scale exactly as declared: 1, 3, 15, 31, 61, 154, 307.
- Substitutions preserve length and change exactly `k` bases; direction-pure kinds move length one
  way only.
- The null family is flat. Median `sequence_log_p_value` for ordinary output under the
  corresponding key is exactly 0.00 at every rate and kind for both models. Null detections total
  1/5,568 for Carbon (0.018%) and 10/5,568 for GENERator (0.180%), both under the 0.01 target. The
  edit channel therefore manufactures no structure, which is the falsification check the protocol
  predeclared.
- The 10% collapse confirms the pipeline responds to edits rather than always firing.

## What this does and does not support

It supports a statement that detection tolerates **random, non-adaptive** editing up to roughly a
2% per-base rate at full margin, degrading through 5% and failing by 10%, consistently across both
models.

It does not support an adversarial-robustness claim. The channel is a public replay chosen without
reference to the detector; an adaptive editor who places edits where they hurt most would do
better, and `AGENTS.md` forbids the detector-guided experiment that would measure it. It is also a
pilot: 96 prompts against the 1,544 that admitted evidence uses, one cohort, no calibration rerun.

A paper-bound result would need the `synthid.v3.*` namespace, the full evaluation cohort, a frozen
non-pilot protocol, and a threat-model amendment that keeps detector-guided editing out of scope.

## Artifacts

| Artifact | Purpose |
|---|---|
| `evidence/derived/edit_rate_pilot_carbon_2026_09_24.json` | Carbon cells |
| `evidence/derived/edit_rate_pilot_generator_2026_09_24.json` | GENERator cells |
| `scripts/run_synthid_edit_rate_pilot.py` | pilot runner |
| `src/genomic_watermarks/synthid_boundary.py` | `deterministic_multi_base_edit` channel |
| `tests/test_multi_base_edit.py` | 10 tests; full suite 126 passing |

The single-edit channel that the declared threat model rests on is unchanged, and a test asserts it.
