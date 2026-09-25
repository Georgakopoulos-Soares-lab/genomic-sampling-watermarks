# Threat-model amendment — edit rate (2026-09-24)

Amends the **Edit model** section of `docs/threat_model.md`. Authorised by the author in session on
2026-09-24 (AD-2), with the stated condition that the threat model change only if the results
honestly support it.

## What changed in the evidence

Before this date the repository had run no multiple-edit experiment, and the threat model recorded
that such experiments were "not planned". One has now been run as a pilot, governed by
`docs/research/synthid_v3_edit_rate_pilot_protocol_2026_09_24.md` and reported in
`docs/research/synthid_edit_rate_pilot_execution_2026_09_24.md`. That sentence is therefore no
longer accurate and is corrected below.

## What the covered regime still is

**The declared covered regime is unchanged: exactly one ordinary nucleotide event per read.** The
pilot does not expand it. Admitted evidence in this study rests on 1,544 evaluation prompts per
model; the pilot used 96, is classified `pilot_not_admitted_evidence`, and none of its numbers may
enter `evidence/measurements.yaml` or the manuscript.

Expanding the covered regime to a declared edit *rate* requires a full-cohort run under the
`synthid.v3.*` namespace with a frozen non-pilot protocol. Until that exists, the manuscript must
continue to say that the retained experiment covers a single nucleotide event.

## What the pilot indicates, stated as preliminary

Against a **non-adaptive public-replay** edit channel, correct-key detection held at 100% for
substitutions, mixed indels, pure insertions and pure deletions through a 2% per-base rate on both
Carbon-500M and GENERator-v2 1.2B, degraded to roughly 92–99% at 5%, and collapsed by 10%. The
ordinary-output null stayed flat as the rate rose, so the channel manufactures no structure.

The mechanism is margin, not frame preservation. A single indel is about seventeen times more
damaging per event than a substitution, exactly as frame-shift reasoning predicts, but the clean
statistic carries roughly 290 times the evidence that firing requires, so detection survives until
that surplus is spent.

## What remains explicitly out of scope

- **Detector-guided and detector-query editing stay out of scope**, unchanged, and remain forbidden
  by `AGENTS.md`. The pilot channel is chosen without reference to the detector, the key, or any
  score. An adaptive editor placing edits where they hurt most would do better, and this study
  does not and will not measure that.
- Consequently **no adversarial-robustness claim follows from the pilot**. The result is about
  random editing, and the distinction must survive into any prose that cites it.
- The outside observer still cannot obtain, query, or optimise against the detector score.

## Replacement text for the Edit model section

> The retained experiment covers an unchanged read and exactly one ordinary nucleotide event inside
> the generated continuation: one substitution, one insertion, or one deletion. The event location
> and affected base are selected by a frozen public random procedure, not by inspecting detector
> behavior.
>
> A separate pilot, not admitted as evidence, has measured detection against higher rates of the
> same public-replay editing; see the edit-rate amendment. It indicates tolerance well beyond a
> single event under non-adaptive editing, but the declared covered regime remains the single
> event until a full-cohort run exists. Detector-guided editing remains outside this threat model.
