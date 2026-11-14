# Documentation index

## Current state

- [Repository guidance](../CLAUDE.md): the question, scope, evidence rules, and claim limits.
- [Roadmap](roadmap.md): the ICLR revision and what remains open.
- [Threat model](threat_model.md): what the observer knows and which edits are in scope.
- [Baseline definition](baseline_definition.md): model-specific generation and the ordinary control.
- [Evidence ledger](../evidence/README.md) and the
  [manuscript evidence map](../paper/context/evidence_map.md).
- [Paper workspace](../paper/README.md).

## Protocols and execution records

All under `research/`. The ledger cites these files; do not rename or rewrite them.

| Evidence | Protocol | Execution and amendments |
|---|---|---|
| Development cohort, Carbon | `carbon_synthid_validation_v1_protocol.md`, `carbon_synthid_position_independent_validation_protocol.md` | `carbon_synthid_e16_execution_2026_08_29.md`, `carbon_synthid_position_independent_execution_2026_09_02.md`, `carbon_synthid_protocol_provenance_amendment_2026_09_03.md`, `carbon_provenance_discrepancy_audit_2026_09_21.md` |
| Development cohort, GENERator | `generator_synthid_validation_v1_protocol.md`, `generator_synthid_position_independent_validation_protocol.md` | `generator_synthid_execution_2026_09_03.md`, `generator_synthid_validator_amendment_2026_09_03.md`, `generator_v1_analysis_amendment_2026_09_11.md` |
| Admission of both development runs | | `dual_model_v1_admission_amendment_2026_09_09.md`, `dual_model_gate_audit_2026_09_08.md` |
| Verifier | `synthid_position_independent_detector_protocol.md` | |
| Detection cohort | `synthid_v2_fpr_scaling_protocol_2026_09_21.md` | `synthid_v2_fpr_direct_a100_execution_2026_09_21.md`, `synthid_boundary_digest_provenance_note_2026_09_24.md` |
| Edit-rate series | `synthid_v3_edit_rate_protocol_2026_09_24.md` (pilot: `synthid_v3_edit_rate_pilot_protocol_2026_09_24.md`) | `synthid_v3_edit_rate_execution_2026_09_24.md`, `synthid_edit_rate_pilot_execution_2026_09_24.md`, `threat_model_edit_rate_amendment_2026_09_24.md`, `threat_model_edit_rate_v3_admission_2026_09_29.md` |
| Sampler fidelity recheck | `synthid_v4_sampler_fidelity_protocol_2026_10_01.md`, `second_cohort_quality_sampler_plan_2026_10_01.md` | |
| Strength analysis | | `cross_model_strength_analysis_2026_09_21.md` |
| Local review studies S0 to S4 (`synthid.v5.*`) | `synthid_v5_review_studies_protocol_2026_11_12.md` | `synthid_v5_review_studies_execution_2026_11_13.md` |

Supporting references: `literature_map.md`, `model_source_audit.md`,
`public_prompt_cohort_large_v1.md`, `tacc_slurm_execution.md`, `carbon_synthid_hpc_smoke_2026_08_29.md`.

## History

These describe earlier stages and are kept because later documents cite them. They do not describe
the current state.

- [Experiment record](experiments.md): the development-cohort runs as first written up.
- [Manuscript evidence packet](research/manuscript_evidence_packet.md): the development-cohort
  writing summary.
- [Dual-model rebuild plan](research/dual_model_synthid_paper_rebuild_plan.md) and
  [research plan pointer](research/combined_research_plan.md): the plan for a confirmatory study
  under a fresh identity. The admission amendment replaced it for the current manuscript.
- [Lane notes, 2026-09-21](history/): the three work-lane briefs behind the detection cohort, the
  edit-rate series, and the 2026-09-29 reconciliation. Later notes cite them by file name.
