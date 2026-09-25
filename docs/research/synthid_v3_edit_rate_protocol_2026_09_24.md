# SynthID v3 edit-rate protocol (full cohort)

Frozen before the full-cohort run. Supersedes the pilot protocol
`synthid_v3_edit_rate_pilot_protocol_2026_09_24.md` for evidence purposes; the pilot and its
results remain on record and are not re-labelled.

## Authorisation and boundary

AD-2 is signed (2026-09-24). The edit channel is a fixed public replay that never inspects the
detector, the key, or any score, so this is not a detector-guided or detector-query experiment and
remains inside the `AGENTS.md` prohibition. **No detector parameter is tuned to the edit rate.**

## Question

At what per-base rate of ordinary, non-adaptive editing does the position-independent detector stop
recovering the mark, and does the ordinary-output null stay at or below the declared 0.01 target
across that range?

## Cohort, reads and identity

- The frozen v2 reads. **No regeneration**: generation is unchanged and is not repeated.
- Cohort `ncbi_refseq_eukaryote_windows_fpr_v2_1608`, content SHA-256
  `f6075a85bc056f5159952031618c544fb3a82864ed9029c913e7f5a7d03c5dc5`.
- All **1,544** evaluation prompts under the frozen
  `carbon_synthid_validation_v1/prompt-split/v1` split, both draws, both models. The 64
  calibration prompts stay excluded.
- Namespace `synthid.v3.*`. Edit-channel label `synthid-edit-rate-v3`, which is distinct from the
  pilot label, so pilot and full results can never be confused or pooled.

## Edit channel

`deterministic_multi_base_edit`. Event count is `round(rate x 3072)`. Positions are drawn without
replacement from a public SHA-256 stream keyed by label, kind, rate, case id and draw, and applied
right to left.

- Rates: 0, 0.0003, 0.001, 0.005, 0.01, 0.02, 0.05, 0.10 per base, giving 0, 1, 3, 15, 31, 61, 154
  and 307 events.
- Kinds: `substitution`; `indel` with direction chosen per event; and the direction-pure
  `insertion` and `deletion`, which prevent cumulative frame offset from cancelling.
- Families: `watermarked_correct_key` for power, `ordinary_corresponding_key` for the null.

## Detector

Unchanged from the admitted runs: depth 30, four preceding tokens, 1,024-context repetition
history, window set {384, 768, 1536, 3072} bases, both orientations, every base start, exact
fair-binomial upper tail multiplied by the searched hypothesis count and compared with 0.01.

## Predeclared interpretation

Recorded before the run, and before any full-cohort number exists.

1. The pilot at 96 prompts found complete detection through a 2% rate, roughly 92-99% at 5%, and
   collapse by 10%, on both models. The full run is expected to reproduce that shape. A
   qualitatively different shape means the pilot subsample was unrepresentative and the pilot
   result must be withdrawn, not averaged with this one.
2. The 0.0003 rate is one event and must reproduce the admitted single-edit result, at or near 1.0
   correct-key detection. If it does not, the run is invalid and reports nothing else.
3. Power must fall monotonically with rate. Indels must cost more per event than substitutions.
4. **Falsification check.** `ordinary_corresponding_key` detection must stay at or below 0.01 at
   every rate and kind. If the null climbs with edit rate, the channel is manufacturing structure
   and every power reading in this run is void.
5. The reported quantity is the breakdown curve, plus the highest rate at which every kind still
   detects every read. A low breakdown point is a legitimate result about scope.

## Admission

Results may enter `evidence/measurements.yaml` under `synthid.v3.*` only after the null check in 4
passes and the artifact digests are recorded. Admission does **not** by itself expand the declared
threat model: the covered regime moves only by a separate amendment that states the measured
envelope and keeps detector-guided editing out of scope.

## Claim boundary

This measures **non-adaptive** editing. An adaptive editor placing edits where they hurt most is
not measured here and must not be inferred. Nothing here concerns biological function, viability,
or key secrecy.
