# SynthID edit-rate breakdown pilot protocol (L1-07 pilot)

**Frozen before any edit-rate measurement.** This protocol governs a *pilot* only. Its results are
classified `pilot_not_admitted_evidence` and may not enter `evidence/measurements.yaml` or the
manuscript. A paper-bound run would need a threat-model amendment, a full protocol, the
`synthid.v3.*` namespace, and the full 1,544-prompt cohort.

## Why this exists, and what it is not

The declared threat model covers a **single** nucleotide event per read. PAT repeatedly asked for an
edit *rate*. The lane note records the prediction in advance: at a 1% indel rate an indel occurs
roughly every 100 bases while the shortest evaluated window is 384 bases, so no candidate window
retains a clean reading frame and detection should fail. **The breakdown point is the deliverable,
not a defence.** This pilot measures where the breakdown falls.

This is not a detector-guided or detector-query attack. The edit channel is a fixed public replay
that never inspects the detector, the key, or any score.

## Design

- **Reads:** the existing frozen v2 reads. No regeneration, no GPU, no new cohort.
- **Prompt subsample:** the first 96 evaluation prompts under the existing frozen
  `carbon_synthid_validation_v1/prompt-split/v1` SHA-256 ordering. Selection is by that fixed
  digest order alone, never by any observed score.
- **Draws:** both, as in the main run.
- **Edit rates:** 0 (clean), 0.0003, 0.001, 0.005, 0.01 per base. On a 3,072-base continuation
  these realise 0, 1, 3, 15 and 31 events. The 0.0003 cell reproduces the single-edit regime the
  declared threat model already covers and acts as the bridge to the admitted result.
- **Edit kinds:** `substitution` (one base per event) and `indel` (insertion or deletion of 1–5
  bases per event, chosen by public digest).
- **Families:** `watermarked_correct_key` for power and `ordinary_corresponding_key` for the null.
  The wrong-key family is not needed to locate a breakdown.
- **Edit channel:** `deterministic_multi_base_edit`, positions drawn without replacement from a
  public SHA-256 stream keyed by label, kind, rate, case id and draw. Applied right to left.
- **Detector:** unchanged. Same 30 layers, four-token context, 1,024 repetition history, window set
  {384, 768, 1536, 3072}, both orientations, every base start, same full-search correction at the
  same 0.01 target. **No detector parameter is tuned to the edit rate.**

## Predeclared interpretation

Recorded before any measurement, so no reading can be chosen afterwards:

1. The single-edit cell (0.0003) must reproduce the admitted result: correct-key detection at or
   near 1.0. If it does not, the pilot is broken and reports nothing else.
2. Detection power is expected to fall monotonically with rate, and to fall faster for indels than
   for substitutions, because an indel shifts the reading frame for everything downstream while a
   substitution damages only the 6-mers overlapping it.
3. At 0.01 indels, detection is expected to fail. A high detection rate there would contradict the
   stated frame-shift reasoning and must be investigated, not reported as a win.
4. The null family must stay at or below the 0.01 target at every rate. A null rate that climbs
   with edit rate would indicate the edit channel is manufacturing structure and would invalidate
   the power readings.

## Outcome rule

The honest deliverable is the breakdown curve, including the rate at which power first drops below
0.95 and the rate at which it collapses. A result showing early failure is a legitimate and
reportable finding about scope, not a reason to withhold the pilot.

## Amendment 1 — 2026-09-24, recorded before the full pilot run

A two-prompt smoke on Carbon reads returned correct-key detection of 4/4 at **every** declared
rate, including 0.01 mixed indels (31 events on a 3,072-base continuation). Under predeclared
interpretation 3 this contradicts the frame-shift reasoning and must be investigated rather than
reported as a win. Two changes follow, both recorded before the full run:

1. **The rate ladder did not reach the breakdown.** It is extended upward to
   0.02, 0.05 and 0.10. The declared deliverable is the breakdown curve, so extending the ladder
   completes it; the original rungs are unchanged and still reported.
2. **A candidate mechanism for the surprise must be separated.** The `indel` channel chooses
   insertion or deletion per event, so the cumulative frame offset performs a random walk modulo
   six and returns to zero whenever the events balance, leaving long correctly framed stretches.
   Two direction-pure channels, `insertion` and `deletion`, are added. They hold one direction, so
   the frame offset accumulates and cannot cancel. If frame shift is the mechanism, the
   direction-pure channels must degrade faster than mixed `indel` at the same rate.

Per-cell minimum, median and maximum `sequence_log_p_value` are now recorded, because the pass rate
alone hides how much margin remains. The detector is still untouched, and the null family remains
the falsification check: if `ordinary_corresponding_key` detection climbs with edit rate, the edit
channel is manufacturing structure and the power readings are void.
