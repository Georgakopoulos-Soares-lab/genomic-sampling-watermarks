# synthid.v3.* full-cohort edit-rate admission (2026-09-29)

Records the author sign-off for the full-cohort, multi-rate edit experiment already executed and
recorded under `synthid.v3.*`, and its consequence for the declared threat model. This supersedes
the narrower scope of `docs/research/threat_model_edit_rate_amendment_2026_09_24.md`, which
authorized only a 96-prompt pilot and explicitly stated that authorization "does not cover a
full-cohort `synthid.v3.*` run."

## Gap this closes

The full-cohort run (1,544 evaluation prompts per model, both draws, seven per-base edit rates from
0.03% to 10%, four edit kinds) was executed and admitted to `evidence/measurements.yaml` and cited
in `docs/threat_model.md` before this document existed. The only recorded authorization at the time
was a self-referential note inside the run's own protocol and execution documents
(`docs/research/synthid_v3_edit_rate_protocol_2026_09_24.md`,
`docs/research/synthid_v3_edit_rate_execution_2026_09_24.md`), which is not an independent sign-off.
A 2026-09-29 reconciliation review (Lane 3; procedure `2026-09-21_lane3_reconciliation.md`, record
and conflict ledger `paper/reviews/2026-09-29_lane3_reconciliation.md`) flagged this as a
scope-boundary violation under `AGENTS.md`'s rule against multiple-edit experiments without a
recorded author sign-off (CONF-01).

## Sign-off

**Authorised by the repository's designated author, christos.galanopoulos@performance.gr, in
session on 2026-09-29**, after review of the full-cohort result and its evidentiary basis (the
predeclared falsification checks, the flat ordinary-output null across all rates, and the
reproduction of the pilot's shape to within 1.5 points). Authorization covers exactly the
full-cohort run as executed and already admitted under `synthid.v3.*`. It does not authorize any
further multiple-edit experiment beyond this one, and it does not authorize any detector-guided or
detector-query experiment, which `AGENTS.md` continues to forbid outright.

## Threat-model consequence

The declared covered regime is widened from exactly one nucleotide event to also include
non-adaptive, public-replay editing up to each model's measured full-recovery ceiling — a 2%
per-base rate on Carbon and a 1% rate on GENERator — and, as characterized degradation and
collapse rather than recovery, up to 10%. This is reported alongside the primary single-event
condition rather than replacing it. `docs/threat_model.md` is updated accordingly.

The per-model split is the ledger's, not a rounding of it: `synthid.v3.carbon.detector.edit_rate_
full_detection_ceiling` is 0.02 and `synthid.v3.generator.detector.edit_rate_full_detection_ceiling`
is 0.01, because GENERator's mixed-indel cell at 0.02 detects 3,087 of 3,088 reads. The execution
record `docs/research/synthid_v3_edit_rate_execution_2026_09_24.md` states a single 2% ceiling for
both models; that summary line is superseded by the ledger entries it derives from. The regime
remains strictly non-adaptive: no claim follows about an editor that inspects the detector, the key,
or any score, and `AGENTS.md`'s prohibition on detector-guided or detector-query experiments is
unchanged and unaffected by this admission.

## Also resolves

This sign-off is also the recorded authorization, requested but not previously supplied, for Lane
1's write-boundary crossing into `docs/threat_model.md` (`2026-09-21_lane1_hpc_runs.md` states Lane 1
"never writes... `docs/threat_model.md`"), which the runner's own status note attributed to a
verbal, session-level author instruction with no independent written record (CONF-09).

## Amendment, 2026-09-29 (second reconciliation pass)

The threat-model consequence above originally repeated the execution record's single 2% ceiling for
both models. A follow-up review checked it against `evidence/measurements.yaml` and corrected it to
the per-model ceilings now stated. The author sign-off itself is unchanged and was confirmed in
session on 2026-09-29; only the measured rates it describes were corrected.
