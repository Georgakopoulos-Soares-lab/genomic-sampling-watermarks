# Gate audit — 2026-09-08

First pass over the `Full restructure` baseline (`4602fc1`) against the gates and phases declared in
`dual_model_synthid_paper_rebuild_plan.md`. This records what was actually executed, not what the
roadmap asserts.

Baseline: `4602fc1`, 307 files, +41,436 / −44,609. HEAD at audit time was `5c448cc`
(bibliography verification), which changes no code.

## S2 — sampler mathematics: evaluated for the first time, and it passes

This gate had never been evaluated on this machine. `tests/test_synthid_upstream_parity.py` skips
unless `GSW_SYNTHID_UPSTREAM` points at a clone of the pinned upstream, and the variable was unset,
so the four parity tests had always been reported as skips inside an `OK` result.

The pinned revision was cloned and checked out:

```bash
git clone https://github.com/google-deepmind/synthid-text.git
git -C synthid-text checkout addb4a158143c7c6851a1308f78b89fceed59683
export GSW_SYNTHID_UPSTREAM=$PWD/synthid-text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests
```

Result: **108 tests, zero failures, zero errors, zero skips.** All four parity tests pass, including
the guard that the clone is at the pinned revision, with agreement to 12 decimal places on random,
peaked, flat, and constant-layer distributions.

Consequences:

- **S2 passes.** The local tournament reweighting is numerically identical to the pinned DeepMind
  implementation on the tested laws.
- **Q1 passes as written** — "zero unexplained skips" — only when the upstream clone is present.
  Without it the suite still reports `OK`, which is how four unevaluated differential tests stayed
  invisible. Any receipt for Q1 must record whether the upstream variable was set; an `OK` alone does
  not distinguish 108 passing tests from 104 passing and 4 skipped.
- The manuscript's new citation of the pinned reference implementation is now backed by an executed
  differential test rather than by the pin alone.

This is a software-equivalence result. It says the formula matches upstream; it says nothing about
detection power, genomic quality, or key security.

## Q4 — lint and formatting: failed on the baseline, now fixed

`ruff check .` passes. `ruff format --check .` failed: **14 files would be reformatted**, all
introduced or modified by `4602fc1` and none touched since:

```text
scripts/make_paper_figures.py
scripts/run_carbon_large_distribution.py
scripts/run_carbon_synthid_position_independent.py
scripts/run_generator_large_distribution.py
scripts/run_generator_parallel_generation.py
scripts/run_generator_synthid_position_independent.py
scripts/validate_carbon_large_validation.py
scripts/validate_carbon_synthid_position_independent.py
scripts/validate_generator_large_validation.py
scripts/validate_generator_synthid_position_independent.py
src/genomic_watermarks/models/huggingface.py
tests/test_gof.py
tests/test_synthid_boundary.py
tests/test_synthid_position_independent.py
```

The differences are pure formatting — collapsing wrapped calls and comprehensions that fit inside the
configured 100-column limit — not lint errors.

**This was first misdiagnosed as formatter-version drift and it is not.** `uvx ruff` resolves the
newest release, 0.16.6, while `uv.lock` pins 0.16.4, so version drift was the obvious suspect. Running
the *locked* 0.16.4 from `.venv` reproduces the same failure. The baseline simply fails Q4 under its
own frozen toolchain; the formatter had not been run on these files.

Two separate problems, both now fixed:

1. **No formatter version was recorded**, which Q4 explicitly requires. `pyproject.toml` requested
   `ruff>=0.9`, an open lower bound. It now pins `ruff==0.16.4`, matching what the lock already
   resolved, so `uv lock` changed exactly one line — the specifier — and no dependency moved.
2. **The files were unformatted.** `ruff format` was run once under the pinned version: 14 files
   reformatted, 114 unchanged. `ruff format --check` and `ruff check` now both pass over 128 files.

The reformat was verified to be semantically inert rather than assumed to be: every one of the 14
files was parsed before and after and compared by `ast.dump`, and all 14 ASTs are identical. The full
suite was then re-run with the upstream clone present and still reports 108 tests, zero failures, zero
skips.

Gate receipts should invoke the locked formatter — `uv run --frozen ruff ...`, as the plan's own
receipt block does — and never `uvx ruff`, which ignores the lock.

## Q1 — a test failed instead of skipping under a legitimate install

Running `uv sync --frozen --extra dev`, which is precisely what gate Q0 describes, produced a hard
failure rather than a clean result:

```text
FAIL: test_g_bit_matrix_matches_scalar_g_values (test_synthid.SynthIDAcceleratedPathTest)
AssertionError: unexpectedly None : NumPy is required for this test
```

NumPy lives in the `models`/`analysis` extras, not `dev`. `KeyedTournament.candidate_g_bits` returns
`None` when NumPy is absent, and two tests in `SynthIDAcceleratedPathTest` require the accelerated
path to exist. One of them asserted NumPy's presence instead of skipping, so a dev-only install — a
configuration the plan's own Q0 receipt implies is valid — reported a red suite for an absent optional
dependency. The sibling tests in the same class are unaffected because they remove NumPy deliberately
to exercise the pure-Python fallback, so they pass either way.

Both NumPy-requiring tests now carry a `requires_numpy` skip guard, matching how the repository
already gates the upstream parity tests on `GSW_SYNTHID_UPSTREAM`. Verified in both configurations:
with the full environment the suite is 108 tests, zero failures, zero skips; with NumPy forced absent
the module runs 13 tests with two skips and no failures, where it previously produced one failure.

Two things follow for Q1 receipts. The suite's result depends on which extras are installed *and* on
whether the upstream clone is present, so a receipt must record both. And the environment for a
paper-bound Q1 run is `--extra dev --extra models --extra analysis`, not `--extra dev` alone.

## Phase 0 — scope propagation: was incomplete, now closed

`docs/roadmap.md` marks "Update repository and paper scope instructions to make both models
paper-bound" as done. Three files still described GENERator-v2 as supplementary, which is exactly the
condition Phase 0 declares as its exit criterion:

- `docs/research/literature_map.md` — section heading "GENERator supplementary replication", and
  "reviewed supplementary evidence and is not part of the current Carbon-only manuscript";
- `paper/README.md` — "stays out of this manuscript until its scope is explicitly expanded";
- `paper/context/evidence_map.md` — "It remains supplementary and must not be inserted into this
  Carbon manuscript without a separate scope decision".

`AGENTS.md`, `PROJECT.md`, `CLAUDE.md`, and `paper/AGENTS.md` were already correct.

All three are now reworded so GENERator-v2 is stated as a co-primary model of the rebuilt study while
its version-one measurements remain legacy development history on the same footing as Carbon's. The
fence matters and was preserved: the reason those numbers stay out of the current draft is now that
both models' version-one evidence is legacy, not that one model is a supplement. The roadmap checkbox
is accurate as of this audit.

## Phase 1 — deliverables confirmed absent

The plan discloses this honestly ("the current scripts do not yet implement all of them"); recorded
here so the gap is measured rather than assumed:

| Planned | Status |
| --- | --- |
| `scripts/validate_dual_model_release.py` (cross-model validator, gates S11/Q8) | missing |
| `scripts/doctor.py --strict --profile m5-pro-48gb` (Q6) | no `--strict`; script prints six fields and checks no pinned revisions |
| `scripts/check_evidence.py --strict` (Q7) | no `--strict` |
| Shared parameterized M5 supervisor replacing per-model orchestration | not present; per-model `run_*`/`validate_*` scripts remain |
| Tamper tests for doctor, evidence checker, release validator, table generator (Q3) | not present |

## Q7 — evidence audit cannot run here

`scripts/check_evidence.py` fails on five missing artifacts under
`outputs/carbon_synthid_e16_v1/` and `outputs/carbon_synthid_position_independent_v1/`. Those paths
are gitignored run outputs, so this is an environment gap rather than a defect — but it means Q7
cannot be used as a green light on this machine, and a clean local run of it is not evidence of a
pass.

## Correction to an earlier note

`paper/reviews/2026-09-08_sources_and_solidity_review.md` flags the loss of mechanical
number-to-ledger enforcement when `make_tables.py` was deleted. That flag stands as a description of
the current state, but it should not be read as an oversight: Phase 7 step 1 and gate Q9 of the
rebuild plan both require generated tables with hashes matching a manifest. The enforcement is a
scheduled deliverable, not a forgotten one.

## Gate status summary

| Gate | Status at this audit |
| --- | --- |
| S2 sampler mathematics | **pass**, executed here for the first time |
| Q1 unit and property tests | **pass** with all extras and the upstream clone present: 108 tests, zero skips. One test was changed to skip rather than fail when NumPy is absent |
| Q4 lint | pass |
| Q4 format | **pass** after pinning Ruff to 0.16.4 and formatting 14 baseline files |
| Q6 strict doctor | not implemented |
| Q7 evidence audit | not runnable here; run artifacts absent |
| Q8 release-bundle audit | validator not written |
| Q9 manuscript build | LaTeX builds clean, 12 pages, no unresolved references or citations; generated tables not yet part of the build |
| S0, S1, S3–S11 | not evaluated; they require the frozen protocol and new M5 runs |
