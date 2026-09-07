# AGENTS.md

## Purpose

This repository will produce one dual-model paper and evidence trail for the SynthID tournament
watermark on Carbon-500M and GENERator-v2 1.2B. Existing version-one runs and the Carbon-only draft
are legacy development material; the rebuilt paper uses only new `synthid.v2.*` evidence.

## Read order

1. `PROJECT.md`
2. `docs/research/combined_research_plan.md`
3. `docs/threat_model.md`
4. `docs/baseline_definition.md`
5. `docs/experiments.md`
6. `evidence/README.md`

Read `paper/AGENTS.md` before editing manuscript material.

## Hardware contract

- All required experiments must run on the documented M5 Pro MacBook with 48 GB unified memory.
- Prefer MPS, support CPU fallback, and keep batch sizes configurable.
- Do not introduce CUDA-only kernels, SLURM jobs, distributed launchers, Brev dependencies, or remote services into the required path.
- Carbon-500M and GENERator-v2 1.2B are the only retained models. Both must use the required M5
  path for paper-bound evidence; other models are outside scope.
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
