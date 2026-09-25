# Edit-rate breakdown — full-cohort execution and result (L1-07)

**Date:** 2026-09-24. **Protocol:** `docs/research/synthid_v3_edit_rate_protocol_2026_09_24.md`,
frozen before the run. **Namespace:** `synthid.v3.*`. **AD-2:** signed 2026-09-24.

## Execution

Slurm jobs `3468774` (Carbon) and `3468775` (GENERator) on `development`, 64 workers, both
`COMPLETED` in 7:45 and 7:26; the scoring itself took 444 s and 437 s. CPU only: the run re-scores
the frozen v2 reads and **does not regenerate**, so generation and its evidence are untouched.

All 1,544 evaluation prompts per model, both draws, 3,088 reads per cell. Edit-channel label
`synthid-edit-rate-v3`, distinct from the pilot label so the two can never be pooled. Detector
unchanged from the admitted runs.

## Predeclared checks, all passed

| # | Check | Result |
|---|---|---|
| 1 | full run reproduces the pilot's shape | pass — largest divergence 1.5 points |
| 2 | one event (0.0003) reproduces the admitted single-edit result | pass — 1.0000 for all four kinds, both models |
| 3 | power monotone non-increasing; indels cost more than substitutions | pass — monotone in all eight series; at 5% substitution 100% against indel ~93% |
| 4 | **falsification:** null stays at or below 0.01 at every rate and kind | pass — 0 cells above target |

Because check 1 passed, the pilot stands as a consistent smaller sample and is **not** withdrawn.

Pilot against full, at the two rates where they differ at all:

| Model | Kind | Rate | Pilot (96) | Full (1,544) | Difference |
|---|---|---|---|---|---|
| carbon | substitution | 5% | 100.0 | 100.0 | 0.0 |
| carbon | substitution | 10% | 19.3 | 19.7 | 0.4 |
| carbon | indel | 5% | 94.8 | 93.5 | 1.3 |
| carbon | indel | 10% | 5.7 | 5.5 | 0.2 |
| generator | substitution | 5% | 99.5 | 100.0 | 0.5 |
| generator | substitution | 10% | 17.2 | 18.7 | 1.5 |
| generator | indel | 5% | 92.7 | 92.9 | 0.2 |
| generator | indel | 10% | 6.8 | 5.4 | 1.4 |

## Result — correct-key detection rate (%)

| Model | Kind | 0.03% | 0.1% | 0.5% | 1% | 2% | 5% | 10% |
|---|---|---|---|---|---|---|---|---|
| carbon | substitution | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 19.7 |
| carbon | indel | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 93.5 | 5.5 |
| carbon | insertion | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 93.6 | 5.4 |
| carbon | deletion | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 93.3 | 5.9 |
| generator | substitution | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 18.7 |
| generator | indel | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 92.9 | 5.4 |
| generator | insertion | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 93.9 | 4.6 |
| generator | deletion | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 93.2 | 5.3 |

Events per read at those rates: 1, 3, 15, 31, 61, 154, 307 on a 3,072-base continuation.

**Full-detection ceiling: a 2% per-base rate for both models and all four kinds.** Detection
degrades near 5% for indels while substitutions still recover every read, and collapses by 10%.

## Null control

Pooled ordinary output under the corresponding key: 132/89,552 for Carbon (0.1474%) and
116/89,552 for GENERator (0.1295%), against the 0.01 target. No cell exceeds the target, and the
null does not climb with edit rate. The worst single cells are 0.2267% (Carbon, deletion at 5%) and
0.2915% (GENERator, indel at 1%).

## Why tolerance is this high

The frame-shift argument is right about relative cost and wrong about the absolute breakdown point.
Median correct-key `sequence_log_p_value` for Carbon falls from about -1822 clean to -1778.65 after
one substitution but to -994.67 after one indel, so an indel is roughly an order of magnitude more
damaging per event. The clean statistic nevertheless sits about 290 times above the firing
threshold near -6.2, so a large surplus of evidence is spent before any decision changes. The
direction-pure `insertion` and `deletion` channels degrade like mixed `indel`, so cumulative frame
offset is not the mechanism; per-event local damage is.

## Claim boundary

The channel is a **non-adaptive public replay** that never inspects the detector, the key, or any
score. An adaptive editor placing edits where they hurt most is not measured and must not be
inferred; `AGENTS.md` continues to forbid the detector-guided experiment that would measure it.
Admission of these numbers does **not** by itself move the declared threat model, which still
covers a single nucleotide event; that requires a separate amendment.

Nothing here concerns biological function, viability, or key secrecy.

## Artifacts

| Artifact | SHA-256 recorded in | Purpose |
|---|---|---|
| `evidence/derived/edit_rate_v3_carbon_2026_09_24.json` | ledger | Carbon cells |
| `evidence/derived/edit_rate_v3_generator_2026_09_24.json` | ledger | GENERator cells |
| `scripts/run_synthid_edit_rate_pilot.py` | source manifest | runner |
| `scripts/hpc/synthid_v3_edit_rate.sbatch` | source manifest | batch wrapper |
| `src/genomic_watermarks/synthid_boundary.py` | source manifest | edit channel |
| `tests/test_multi_base_edit.py` | — | 10 tests; full suite 126 passing |
