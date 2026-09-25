# Dual-model SynthID paper roadmap

The prior Carbon-first roadmap is complete development history. The active work is a fresh paper
identity covering Carbon-500M and GENERator-v2 1.2B together.

- [x] Audit the existing manuscript, evidence, tests, validators, and artifacts.
- [x] Design the dual-model rebuild and separate scientific gates from software assurance.
- [x] Update repository and paper scope instructions to make both models paper-bound.
- [x] Mark all version-one evidence and the current manuscript map legacy/development-only.
- [ ] Implement the shared resumable runner, environment checks, cross-model validator, and portable
  artifact manifest.
- [ ] Approve the quality non-inferiority margin and blinded power calculation.
- [ ] Build and freeze a new public prompt cohort disjoint from all prior prompts.
- [ ] Freeze the complete protocol, configurations, gates, source, and cohort hashes.
- [ ] Pass unit, upstream-parity, tamper, Ruff lint, Ruff format, schema, and GPU smoke gates.
- [ ] Run both models on a documented GPU environment through sampler, quality, clean detection, and one-base edit
  evaluations.
- [ ] Admit only new `synthid.v2.*` measurements and create an exact dual-model manuscript map.
- [ ] Rebuild all manuscript sections and generate tables directly from the evidence ledger.
- [ ] Pass the release validator, evidence audit, LaTeX build, and final claim review.
- [ ] Archive the portable release with a DOI and top-level SHA-256 digest.

See the [full rebuild plan](research/dual_model_synthid_paper_rebuild_plan.md) for gate definitions,
failure rules, artifacts, and paper structure.
