# Repository guidance

This is the single instruction file for the repository. It replaces the former `AGENTS.md` and
`PROJECT.md` (merged 2026-11-12); earlier documents cite those names and mean this file.
Manuscript rules are in `paper/CLAUDE.md` (formerly `paper/AGENTS.md`).

## Research question

Can the SynthID tournament watermark be added while two genomic language models generate DNA,
without exceeding a pre-specified model-quality loss bound, and can a verifier find the watermark
when it does not know where the generated part begins?

## Retained scope

- One watermark: `synthid-tournament-v1`. One control: ordinary categorical sampling from the same
  model-specific distribution. One verifier: `synthid-position-independent-detector-v1`.
- Two paper models, and no others:
  - Carbon-500M, revision `9796b752108258c1d365089f842e62e6c0547704`, restricted to its 4,096
    canonical DNA 6-mer tokens;
  - `GenerTeam/GENERator-v2-eukaryote-1.2b-base`, revision
    `c41b0018da9ee13b9e96ee54647de8da381ccd72`, with its direct 4,096-token canonical policy
    `G_tok`. Neither model uses a base-marginal policy.
- The verifier receives DNA, a secret key, the public generation domain, and fixed public
  settings. It does not receive the prompt, model, model probabilities, generation seed, strand,
  6-mer phase, or generation boundary.

Do not reintroduce other watermark constructions or their experiments. Do not add detector-query or
detector-guided attack experiments: they are outside the declared threat model. The only
multiple-edit evidence in scope is the non-adaptive edit-rate series admitted by
`docs/research/threat_model_edit_rate_v3_admission_2026_09_29.md`; do not add further multiple-edit
experiments.

## Status

- The manuscript is `paper/manuscript/source/main.tex`: on arXiv since 2026-10-03 and under review
  at ICLR 2027 as submission 32263. The revision is on branch `iclr-2027-revision`.
- Manuscript evidence, all in `evidence/measurements.yaml`:
  - the development cohort for both models, admitted by
    `docs/research/dual_model_v1_admission_amendment_2026_09_09.md`, with its execution caveats
    disclosed in the manuscript's Limitations section (one execution per model, and the Carbon
    protocol-hash discrepancy);
  - the detection cohort (`synthid.v2.*`);
  - the non-adaptive edit-rate series (`synthid.v3.*`).
- These are executed results, not independently replicated ones. The design for a confirmatory
  replication is `docs/research/dual_model_synthid_paper_rebuild_plan.md`.
- Open items and next steps: `docs/roadmap.md`.

## Read order

1. This file
2. `docs/roadmap.md`
3. `docs/threat_model.md`
4. `docs/baseline_definition.md`
5. `evidence/README.md`
6. `paper/context/evidence_map.md`
7. `docs/README.md` for the protocol and execution record of each evidence group

Read `paper/CLAUDE.md` before editing manuscript material.

## Claim boundary

- The study measures statistical watermark detection and model-based sequence-quality proxies. It
  does not establish biological function, viability, safety, sequence authenticity, or formal
  secret-key security. Do not infer any of these from sequence statistics or model likelihood.
- Keep statistical detection claims separate from biological function and from secret-key
  security. Separate mathematical identities, cryptographic assumptions, empirical statistics, and
  biological proxies.
- SynthID preservation is an expectation over fresh keyed functions; a fixed key and context use a
  deliberately reweighted distribution. Say so wherever preservation is claimed.
- The assumed attacker does not know the key and cannot see or query the detector score.

## Evidence rules

- Every manuscript number must resolve to `evidence/measurements.yaml`.
- Ledger entries are `[V]` for measured or `[A]` for derived. Unresolved claims stay out of the
  ledger.
- New runs require a dated protocol, a documented execution environment, and a new evidence
  identity. Record the exact code, model, tokenizer, dataset, configuration, environment, and
  command with each paper-bound result.
- Treat result files cited by the ledger as immutable. Corrections create a new result and ID.
- Calibrate the maximum detector statistic over every searched orientation, phase, and window.
  Never report the smallest nominal p-value as a global p-value.
- Never store raw secret keys, private genomic sequences, model weights, tokens, `.env` files, or
  credentials in the repository.
- Protocols, execution records, and dated review notes are history. Do not rewrite them; add a
  dated note or amendment instead.

## Hardware contract

- Required experiments may run on a documented local or HPC GPU or CPU environment, including A100
  CUDA nodes. Record the device, accelerator and memory details, software environment, and exact
  commands with each result.
- Keep batch sizes configurable and benchmark both model profiles before scaling.
- Benchmark before increasing sample counts. Use sequential evidence gates instead of a large
  Cartesian sweep.

## Engineering conventions

- Python 3.11+; package source lives under `src/`.
- Keep model-independent core code dependency-light and deterministic under an explicit seed.
- Unit tests must not download models or datasets.
- Prefer small modules and typed public interfaces.
- Use standard cryptographic primitives from maintained libraries or the standard library; do not
  invent bespoke cryptography.
- Preserve unrelated user changes and update docs alongside protocol changes.

## Commands

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/doctor.py
python3 scripts/check_evidence.py
uv run ruff check .
cd paper && ./scripts/build.sh
```

`check_evidence.py` currently fails only on five Carbon development-cohort result files that were
never committed.

## Agents

The files under `.claude/agents/` are narrow task roles, not competing sources of project truth.
Use the smallest route that covers the risk.

| Task | Primary agent | Independent follow-up |
|---|---|---|
| Change the SynthID sampler or its ordinary control | `sampler-correctness` | `security-review` |
| Change a Carbon or GENERator adapter | `model-integration` | `sampler-correctness` |
| Plan or execute a new run | `experiment-runner` | `evidence-auditor` |
| Change detection, p-values, nulls, or the search | `detector-statistics` | `evidence-auditor` |
| Change keyed code or security wording | `security-review` | `evidence-auditor` |
| Add datasets or sequence measures | `biological-proxies` | `paper-sources` |
| Reorganize manuscript sections or answer reviews | `paper-structure` | `evidence-auditor` |
| Polish settled manuscript prose | `paper-style` | `evidence-auditor` |
| Add citations or related work | `paper-sources` | `paper-structure` |
| Add or regenerate figures | `paper-figures` | `evidence-auditor` |

`evidence-auditor`, `paper-sources`, and `security-review` are read-only reviewers.
