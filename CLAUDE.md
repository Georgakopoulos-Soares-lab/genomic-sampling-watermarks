# CLAUDE.md — project charter

Claude-specific operating guide for this repository. `AGENTS.md` is the portable baseline for all
agents; this file adds project status, task routing, and Claude subagent roles. Read both before
making changes.

## Project in one line

Determine whether fixed 6-mer genomic language models can carry a secret-key, exact-marginal
sampling watermark that a standalone verifier can recover after realistic DNA edits.

## Objective

Produce **one combined paper** using Carbon and GENERator-v2 as complementary systems. The paper
must establish, in order:

1. what distribution each released generation policy actually samples;
2. whether each watermark construction preserves its declared marginal;
3. how much watermark information real model distributions carry per token and per base;
4. whether a model-free detector is calibrated after every strand, phase, window, offset, and
   synchronization search;
5. how substitutions, insertions, deletions, crops, reverse complementation, and adaptive removal
   change detection power; and
6. which conclusions are mathematical, cryptographic, empirical, or biological proxies.

A negative capacity result or a synchronization-limited result is valid. Never change the method,
threshold, sample, or claim to force a positive paper.

## Current phase

The repository scaffold, E0 partition-coupling reference, policy transforms, local runtime
selection, real tokenizer audits, and weight-backed model integration exist. Local `G_bp` math
matches the pinned upstream helper on MPS and CPU. E2 collected and validated 3,072 sequential
states per policy on a frozen 24-prompt public RefSeq cohort. The three E2 capacity, E3 stage-1
preservation, E4 clean detection, E5 substitution robustness, E6 crop/strand/phase, E7 stage-1 and
stage-2 indel, E10 unkeyed distinguisher, E14 runtime, **E8/E9 matched baseline**, and **E11/E12 key
reuse, spoofing, and removal**, and **E15 order-sensitive proxies** results have passed
evidence-admission review; `evidence/measurements.yaml` holds 103 entries plus five
`superseded_measurements` records.

E7 remains the project's synchronization result: the unwindowed detector tolerates indel rates 50 to
150 times below its substitution tolerance, and a declared sliding-window search moves that limit
five- to tenfold before meeting a second, information-theoretic wall near rate 0.02 to 0.05.

**E11/E12 is the project's security result, and it is negative.** A spliced forgery, assembled
position-wise from two watermarked outputs under the same key, is accepted at rate 1.000 at every
length on every policy, with a statistic indistinguishable from genuine output. The construction
authenticates a *distribution*, not a *sequence*: the statistic is a sum of per-position,
content-blind indicators, so nothing binds one position to another or to a nonce. This is a property
of the construction, not a parameter to tune. Removal by rearrangement also works — a full positional
shuffle drops detection to 0.000 — and it is nearly invisible to the nine admitted proxies, because
those are composition statistics and the attack preserves the 6-mer multiset exactly.

**E8/E9 is the project's honest-comparison result.** On the same policies, prompts, and 96-hypothesis
search, with each method calibrated on its own nulls, the exponential construction carries about 7.5
times partition coupling's standardized signal per token and inverse transform about 1.4 times.
Partition coupling is at its one-bit-per-token ceiling, not below it. Detection rate saturates at
1.000 for all three methods at every evaluated length down to the detector's 96-base floor, so the
preregistered "shortest fully detected length" headline is a null result and the per-token signal is
the comparison. Do not write the paper as if partition coupling wins; see
`paper/context/01_contribution.md`.

E8/E9 also produced an unplanned finding: natural public DNA under a wrong key exceeds thresholds
calibrated on model-generated nulls at rates above the 0.01 target, worst for the two baselines
(`its` 0.069 at 192 bases on `C_tok`, against partition coupling's worst of 0.025). Calibration does
not transfer from generated to natural sequences equally across methods.

Remaining work begins with:

- whether a coding layer is justified now that the edit channel is measured; the project rule is
  that PRC and ECC work begins only after that measurement, which now exists;
- resolving the two nominal `G_bp` unkeyed-distinguisher rejections; eighteen additional matched
  draws (six new keys per policy) were generated for this;
- a measure of long-range order that can price a bounded 6-mer rearrangement. E15 implemented both
  instruments `docs/baseline_definition.md` declared for this and **neither works**: the
  independent-model Markov score shifts by at most 0.024, and the reading-frame measure shows no
  directionally consistent change under any bounded shuffle, because a long reading frame in
  high-entropy DNA is a chance extreme-value statistic that a permutation re-rolls. The removal attack
  is therefore unpriced, and finding an instrument is open work rather than a neglected gap;
- resolution of the main-revision `C_deployed` processor stack;
- optional Carbon `fns`-revision `C_bp` control;
- ORF and independent-model-likelihood proxies declared in `docs/baseline_definition.md`;
- remaining tokenizer edge cases and broader MPS/CPU parity;
- a sampled high-water memory measurement, without which no peak-memory figure may be claimed.

GENERATOR-v2 must use MPS `float32` for current work. Its `bfloat16` path failed the 12-context
MPS/CPU parity gate; it is not a permitted optimization unless a later revision passes that gate.

**A first evidence-complete draft exists.** Abstract, introduction with contribution bullets, methods,
experimental design, results, discussion, and limitations are written; nine ledger-driven figures and
six generated tables are wired in; `paper/scripts/build.sh` produces a clean PDF with no undefined
references. See `paper/reviews/2026-08-24_first_full_draft.md` for what was checked and what remains.

Two mechanisms enforce the "every number resolves to the ledger" rule rather than relying on care:
prose cites `\newcommand` macros generated by `paper/scripts/make_tables.py`, each annotated with its
measurement id, and tables are generated whole. No empirical number is typed into prose. Regenerate
with `make_tables.py` and `make_figures.py`; audit with `scripts/check_figures.py` and
`scripts/check_generated_prose.py`.

Still open before submission, none of it an evidence gap: live citation checking, the security and
biological-proxy reviews, structure then style passes, and a final scan for host names or paths.

Seven times now a magnitude has looked like an effect and a properly paired test has dissolved it. Six
pieces of statistical machinery were replaced after a result looked wrong rather than merely
surprising: a non-strict detector decision rule, an unsigned drift range, a bootstrap that ignored
within-prompt noise, a sign-flip null that ignored a shared fitted direction, an interval that
ignored the calibrated threshold's uncertainty, and an interval that depended on the order its nulls
were pooled. The seventh was E15's reading-frame shift, which was large and directionless. Treat every
new resampling scheme as suspect until its null has been reproduced on synthetic data whose truth is
known, and **never report an unsigned magnitude as an effect** — the paired test is what decides. Two further standing rules, both earned:

- when a check disagrees with an admitted result, verify the **check** against the experiment's own
  pooling before believing it;
- run every validator against every artifact it claims to cover. A validator nobody ran looks exactly
  like one that passed, and one of them had been silently rejecting the run it was written for.

Artifacts now carry a reproducible **content digest** alongside the file digest
(`src/genomic_watermarks/content_digest.py`, `outputs/content_digests_v1.json`), so a rerun can be
verified rather than trusted.

## Locked decisions

- **Paper unit:** one cross-model paper, not one paper per research plan.
- **Required hardware:** one Apple M5 Pro MacBook Pro with 48 GB unified memory.
- **Execution:** single-process MPS with CPU fallback. No required CUDA, SLURM, Brev, distributed
  runtime, hosted inference endpoint, or remote GPU.
- **Primary models:** Carbon-500M and GENERator-v2 eukaryote 1.2B.
- **Optional confirmation:** Carbon-3B on a reduced cohort after the primary gates pass.
- **Excluded required model:** Carbon-8B.
- **Verifier inputs:** DNA, secret key supplied at runtime, and public configuration only.
- **Initial sampler families:** partition maximal coupling, inverse-transform sampling, and
  exponential/Gumbel sampling.
- **Coding:** PRC work begins only after the edit channel is measured. CSPRNG plus ECC is not a PRC.
- **Biology:** public benign DNA and proxy metrics only; no function, viability, or safety claims.

## Non-negotiable rules

1. **Never commit or print secret material.** No raw keys, `.env` files, credentials, access tokens,
   private genomic sequences, model weights, or dataset payloads.
2. **Never commit model or data caches.** `models/`, `data/raw/`, and `data/processed/` are ignored.
3. **Pin every external input.** Model, tokenizer, dataset, and reference-code revisions belong in
   `sources.yaml` or the result record before evidence collection.
4. **One completed run is immutable.** Corrections create a new run and measurement ID; never
   rewrite admitted evidence.
5. **Every paper number comes from the ledger.** `evidence/measurements.yaml` is the numeric source
   of truth. `[V]` is measured and `[A]` is derived. Unresolved results do not get placeholder rows.
6. **Calibrate the actual detector.** Null trials repeat the full orientation, phase, window,
   key-offset, and synchronization search. Never report the smallest nominal p-value as global.
7. **Name the model policy.** “Carbon” or “GENERATOR” alone is insufficient in a result. Use
   `C_tok`, `C_deployed`, `C_bp`, `G_tok`, or `G_bp`.
8. **Do not conflate claim classes.** Mathematical identities, cryptographic assumptions,
   empirical statistics, and biological proxies require different evidence.
9. **Keep the required path laptop-runnable.** Benchmark before increasing cohorts and prune weak
   branches before any main sweep.
10. **Read before editing.** Preserve unrelated work; do not commit, push, publish, or download
    large artifacts unless explicitly asked.

## Model-policy ground truth

### Carbon

The audited main Carbon-500M checkpoint is a standard causal-LM release. Factorised Nucleotide
Supervision is a training objective; it does not imply a special main-branch sampler. A separate
`fns` revision contains a base-marginal generator. Treat it as `C_bp`, an optional revision-pinned
control, not as current default Carbon generation.

### GENERator-v2

The audited released custom model uses `_BPLogitsProcessor`: it converts the 4,096-way DNA-token
distribution into six base marginals, chooses bases independently, and reconstructs a 6-mer. Treat
this as `G_bp`. `G_tok` is the research baseline that directly samples the processed 4,096-way
categorical distribution.

Do not compare different policies and attribute the difference solely to watermarking.

## Sources of truth

| Concern | File |
|---|---|
| Objective, facts, assumptions, non-goals | `PROJECT.md` |
| Combined argument and staged method | `docs/research/combined_research_plan.md` |
| Exact external revisions and source findings | `docs/research/model_source_audit.md`, `sources.yaml` |
| Public prompt provenance and pilot boundary | `docs/research/public_prompt_cohort.md`, `data/public_prompt_cohort.yaml`, `data/public_prompt_cohort_v2.yaml` |
| E2 pilot shape and expansion rule | `docs/research/e2_capacity_protocol.md` |
| E3 distribution-preservation shape | `docs/research/e3_distribution_preservation_protocol.md` |
| E4 clean-detection shape | `docs/research/e4_clean_detection_protocol.md` |
| E5 substitution shape | `docs/research/e5_substitution_robustness_protocol.md` |
| E6 crop, strand, and phase shape | `docs/research/e6_crop_and_strand_protocol.md` |
| E7 indel and synchronization shape | `docs/research/e7_indel_synchronization_protocol.md` |
| E8/E9 matched baseline shape | `docs/research/e8_e9_matched_baseline_protocol.md` |
| E11/E12 key reuse, spoofing, removal | `docs/research/e11_e12_key_reuse_and_attacks_protocol.md` |
| E15 order-sensitive proxies | `docs/research/e15_structure_proxies_protocol.md` |
| E10 unkeyed distinguisher shape | `docs/research/e10_unkeyed_distinguisher_protocol.md` |
| Runtime envelope and memory exclusion | `docs/research/e14_runtime_envelope_protocol.md` |
| When drafting may start | `paper/context/05_drafting_readiness_plan.md` |
| Literature roles and primary links | `docs/research/literature_map.md` |
| M5 Pro budgets and execution tiers | `docs/research/local_feasibility.md`, `configs/local_m5_pro.toml` |
| Generator, verifier, and attacker | `docs/threat_model.md` |
| Model and watermark baseline IDs | `docs/baseline_definition.md` |
| E0-E13 plan and gates | `docs/experiments.md` |
| Whole-project audit and open gaps | `docs/research/audit_2026_08_23.md` |
| Result admission rules | `evidence/README.md` |
| Paper-printable values | `evidence/measurements.yaml` |
| Manuscript rules and implementation status | `paper/AGENTS.md`, `paper/context/` |

## Repository layout

```text
src/genomic_watermarks/  Dependency-light core algorithms and model adapter interfaces
tests/                   Offline unit and statistical smoke tests
configs/                 Smoke and M5 Pro profiles
sources.yaml             Frozen external model and reference-code revisions
evidence/                Minimal ledger of paper-printable measurements
docs/                    Research audit, threat model, baselines, protocol, and roadmap
explainers/              Beginner-friendly walkthroughs; not a source of empirical truth
paper/                   Context, LaTeX manuscript, figures, reviews, and submission package
.claude/agents/          Specialized Claude subagents for implementation and paper work
```

## Base validation

These commands are repository-grounded and do not download models or datasets:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/check_evidence.py
python3 scripts/check_figures.py
python3 scripts/doctor.py
uvx ruff check .
uvx ruff format --check .
python3 -m compileall -q src tests scripts
```

Regenerate the ledger-driven figures with:

```bash
.venv/bin/python paper/scripts/make_figures.py
```

Every plotted value is read from `evidence/measurements.yaml`; a missing measurement raises rather
than falling back to a default, and `paper/figures/manifest.json` records which measurement ids each
figure drew from so `check_figures.py` can audit them.

Build the manuscript with:

```bash
cd paper && ./scripts/build.sh
```

Install optional local model dependencies only when model-backed work is authorized:

```bash
uv sync --extra dev --extra models --extra analysis
```

Model downloads are a separate, explicit step after revisions are pinned.

## Specialized agents

Use the narrowest applicable agent. Read-only auditors must remain independent of the code or prose
they review.

| Agent | Use for |
|---|---|
| `sampler-correctness` | E0 construction, proofs, edge cases, Monte Carlo marginal tests |
| `model-integration` | Carbon/GENERATOR tokenizers, policies, MPS adapters, revision parity |
| `experiment-runner` | E2-E13 execution, reproducible result files, ledger admission |
| `detector-statistics` | Global calibration, nulls, confidence intervals, synchronization search |
| `security-review` | Key derivation, reuse, spoofing/removal, cryptographic claim boundaries |
| `biological-proxies` | Public cohorts, sequence proxy metrics, interpretation boundaries |
| `evidence-auditor` | Read-only audit of numbers, tags, scope, result sources, and derivations |
| `paper-sources` | Read-only live verification of citations and bibliographic metadata |
| `paper-structure` | Manuscript argument, section order, contribution and limitation placement |
| `paper-style` | Academic prose and terminology after structure is stable |
| `paper-figures` | Ledger-driven, visually verified figures and captions |

Full routing guidance is in `.claude/README.md`.

## Definition of done

### Code change

- Correct source and protocol documents were read first.
- Public interfaces are typed and model-independent code remains dependency-light.
- Tests cover success, boundary, and failure cases.
- Offline validation passes; model-backed validation names the exact revision/device/dtype.
- Documentation and implementation-ground-truth status are updated.

### Experiment

- Protocol and resolved configuration were frozen before inspecting the result.
- The result record captures code, model, tokenizer, data, environment, device, dtype, seeds,
  exclusions, wall time, and peak memory.
- Secret keys and sequence payloads are absent from metadata.
- Completed artifacts are immutable and the ledger records value, unit, scope, uncertainty, and
  source.
- Detector results use calibration over the complete declared search.

### Paper change

- Every empirical number resolves to the ledger.
- Every citation has been checked against a primary source.
- Model policy, sequence length, edit channel, and FPR scope are explicit where required.
- Mathematical, cryptographic, empirical, and biological-proxy claims remain distinct.
- The manuscript builds, generated visuals are inspected, and a dated review is appended.

## Open decisions

- Repository license.
- Final venue and page budget.
- Carbon-3B confirmation after measured M5 Pro runtime.
