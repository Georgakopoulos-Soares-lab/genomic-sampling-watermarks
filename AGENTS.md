# AGENTS.md

## Purpose

This repository will produce one dual-model paper and evidence trail for the SynthID tournament
watermark on Carbon-500M and GENERator-v2 1.2B. Both models' version-one measurements are admitted
as paper evidence by `docs/research/dual_model_v1_admission_amendment_2026_09_09.md`, which
supersedes the earlier `synthid.v2.*`-only rule for the current manuscript; the execution caveats
that rule guarded against are disclosed in the manuscript's Limitations section. New runs still
require a new evidence identity and a documented execution environment.

## Read order

1. `PROJECT.md`
2. `docs/research/combined_research_plan.md`
3. `docs/threat_model.md`
4. `docs/baseline_definition.md`
5. `docs/experiments.md`
6. `evidence/README.md`

Read `paper/AGENTS.md` before editing manuscript material.

## Hardware contract

- Required experiments may run on a documented local or HPC GPU or CPU environment, including A100 CUDA nodes. Record the device, accelerator and memory details, software environment, and exact commands with each result.
- Keep batch sizes configurable and benchmark both model profiles before scaling.
- Carbon-500M and GENERator-v2 1.2B are the only retained models; other models are outside scope.
- Benchmark before increasing sample counts. Use sequential evidence gates instead of a large Cartesian sweep.

## Evidence rules

- A manuscript number must resolve to an entry in `evidence/measurements.yaml`.
- Ledger entries are `[V]` for measured or `[A]` for derived. Unresolved claims stay out of the
  measurement ledger.
- Record the exact code, model, tokenizer, dataset, configuration, environment, and command with
  each paper-bound result.
- Treat result files cited by the ledger as immutable. Corrections create a new result and ID.
- Calibrate the maximum detector statistic over every searched orientation, phase, window, and key offset. Never report the smallest nominal p-value as a global p-value.
- Never store raw secret keys, private genomic sequences, model weights, tokens, `.env` files, or credentials in the repository.

## Claim discipline

- Separate mathematical identities, cryptographic assumptions, empirical statistics, and biological proxies.
- State clearly that SynthID preservation is an expectation over fresh keyed functions; a fixed key
  and context use a deliberately reweighted distribution.
- Do not infer biological function, viability, or safety from sequence statistics or model likelihood.
- Do not reintroduce removed watermark methods or multiple-edit and detector-guided attack studies.

## Engineering conventions

- Python 3.11+; package source lives under `src/`.
- Keep model-independent core code dependency-light and deterministic under an explicit seed.
- Unit tests must not download models or datasets.
- Prefer small modules and typed public interfaces.
- Use standard cryptographic primitives from maintained libraries or the standard library; do not invent bespoke cryptography.
- Preserve unrelated user changes and update docs alongside protocol changes.

## Commands

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/doctor.py
python3 scripts/check_evidence.py
uv run ruff check .
```

The LaTeX manuscript can be checked with:

```bash
cd paper && ./scripts/build.sh
```
