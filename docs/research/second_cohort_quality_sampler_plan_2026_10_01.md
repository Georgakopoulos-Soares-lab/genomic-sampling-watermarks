# Plan: sampler fidelity and quality measures on the second cohort (2026-10-01)

**Status:** plan, not a protocol. Nothing here has been run. Before any measurement, a frozen
protocol and a new evidence identity are required (`CLAUDE.md`, `AGENTS.md`).

## Why

The manuscript's sampler-fidelity and sequence-quality results come only from the 256-prompt
development cohort. The 1,608-prompt second cohort supplies detection, false-positive, and
edit-rate evidence, but it was never scored for quality or checked for sampler fidelity. Running
both on the second cohort would do three things:

- put every claim in the paper on the large cohort: 3,216 matched pairs instead of 512 for the
  quality comparison;
- check the sampler under the second cohort's own keyed functions, the ones its reads were
  generated with;
- remove the paper's dependence on the Carbon development-cohort files for these claims. Those
  files are missing from the repository, and Carbon's corrected sampler count is not retained.

## Finding that changes the sampler design

The existing sampler test (`scripts/run_{carbon,generator}_large_distribution.py`) works as
follows. It computes the fixed-key watermark distribution $p_k$ with `tournament_distribution`.
It draws the marked arm's 5,000 samples with `random.choices(weights=p_k)`. It then runs the G-test
against that same $p_k$. The ordinary arm does the same with $p$.

Agreement is therefore guaranteed in expectation. The G-test checks Python's `random.choices`, not
the tournament computation and not the sampler that generated the reads (`_tournament_step` in
`src/genomic_watermarks/synthid.py`). The meaningful parts of the current test are these:

- **The negative control:** draws from $p$ tested against $p_k$, which shows the test can tell the
  two distributions apart at each state.
- **The key-averaged identity:** $p_k$ averaged over 64 fresh keys should return $p$.
- **The upstream parity tests** (`tests/test_synthid_upstream_parity.py`) against Google's
  reference implementation. These skip unless the reference code is present, so they have not
  been running.

The manuscript's sentence "Each sampler agreed with its intended distribution" therefore claims
more than the test shows. Two fixes follow.

1. **Manuscript, now:** describe what was tested, independent of any new run. Draws matched the
   computed fixed-key distribution, averaging that distribution over fresh keys recovered the
   model's distribution, and a deliberately wrong sampler was rejected at every control state.
2. **New run:** test the sampler that generated the reads, against an independent computation of
   $p_k$ (design A below).

## Design A: sampler fidelity, redesigned

Use the same model state as before: token index 64 of the first ordinary continuation for each
prompt. At each state:

- **Marked arm.** Exercise the generation sampler's two steps with the second cohort's generation
  domain label and keys. First compute $p_k$ once per state with the NumPy path that
  `_tournament_step` uses (`_tournament_probabilities_numpy`). Then draw 5,000 tokens with its
  sampling routine (`_sample_index_numpy`). Compare the counts with $p_k$ computed by the
  **pure-Python reference** `tournament_distribution_reference`, a different code path.
  - Do not call `_tournament_step` 5,000 times. It recomputes $p_k$ on each call (about 350 s per
    state).
  - As a direct integration check, call `_tournament_step` itself 200 times at 32 hash-selected
    states.
- **Ordinary arm.** Draw 5,000 samples with the generation code's ordinary sampler and compare the
  counts with $p$.
- **Exactness check.** Compare $p_k$ from the NumPy path with the reference path at every state,
  with an absolute tolerance written into the protocol.
- **Key-averaged identity.** Average $p_k$ over 256 fresh keys and report the total-variation
  distance from $p$, against its expected finite-key size.
- **Negative control.** Keep it: draws from $p$ tested against $p_k$ at eight states.
- **Statistics.** Use the G-statistic with a 999-replicate Monte Carlo reference, as before. With up
  to 1,608 states per arm, make the **primary** test the count of nominal rejections at 0.05
  against Binomial($N$, 0.05), together with a uniformity test of the per-state $P$-values.
  Report Benjamini–Hochberg as secondary. At 999 replicates the attainable $P$-value floor
  (0.001) is above the Bonferroni cutoff, so Bonferroni carries no information, as in the paper.
- **Upstream parity.** Clone `google-deepmind/synthid-text` at commit `addb4a15` and run the parity
  tests. This needs CPU PyTorch only and takes minutes.

## Design B: quality measures on the second cohort

Use the same 14 measures, model, token restriction, and statistics as the development cohort:

- teacher-forced negative log-likelihood per generated token (the model score);
- 13 sequence statistics;
- an equal-weight bootstrap over prompts (20,000 replicates);
- a paired sign-flip test (100,000 replicates);
- one Benjamini–Hochberg family of 14.

Use all 1,608 prompts: the 64 set-aside prompts were not used for anything in this cohort. Score
1,608 prompts × 2 draws × 2 arms = 6,432 sequences per model.

## Prerequisites

0. **Copy the generated sequences off TACC scratch now. This is the most urgent item.**
   - The second cohort's continuations exist only under `/scratch/10899/kimopro/synthid_v2_fpr/`
     `{carbon,generator}/`. The repository kept only summaries and detection trials.
   - Lonestar6 purges scratch files not accessed for about 10 days. These were last read for
     the edit-rate series around 2026-09-24.
   - Copy each model's `generation/` directory and `generation_summary.json` to `$WORK` or to
     this repository, compressed, as was done for `trials.jsonl.gz`. Then verify every sequence
     checksum against the generation summary.
   - The files are small: about 20 MB of sequence per model before compression.
   - If they are purged, regeneration needs about 10 GPU-hours per model on A100s. It might not
     reproduce the same bytes, which would cut the link to the detection results.
1. **Pinned environment.** Use the versions of the earlier CPU run
   (`configs/carbon_synthid_validation_cpu_analysis_resume_v1.toml`): Transformers 5.15.1 and the
   same model revisions. Pin the PyTorch build and record it.
2. **Frozen protocol.** Write `docs/research/synthid_v4_quality_sampler_protocol_<date>.md`. It
   holds designs A and B, the predeclared tests and tolerances, the state rule, and the evidence
   identity `synthid.v4.*`. Freeze it and record its hash before the first model call.
3. **Code changes, with tests.**
   - A `--sampler-path generation` option, or a new script, so the marked arm calls
     `_tournament_step` and is compared with `tournament_distribution_reference`.
   - A key-averaging count option.
   - The binomial-count and uniformity summaries.
   - Unit tests on a toy distribution, with no model downloads.

## Compute: can it run on this node?

**This node:** 2 virtual CPUs (one AMD EPYC 9V74 core, two threads), 7 GB RAM, no GPU, about
18 GB free in the workspace and 40 GB in `/tmp`.

**Measured on this node on 2026-10-01** (bfloat16, two threads, the repository's own model
adapters, pinned model revisions):

| Operation | Carbon-500M | GENERator-v2 1.2B |
|---|---|---|
| Model load | 19 s | 52 s |
| One sampler state (128-token context) | 7.6 s | 16.4 s |
| Teacher-forced likelihood, one 3,456-base read | 34.5 s | 72.3 s |
| Peak memory | 1.7 GB | 5.9 GB of 7 GB |

Work outside the model, measured: one exact watermark distribution takes 0.07 s, so 65 per state
take about 4 s. A 999-replicate G-test takes about 2.4 s per arm. Each state therefore adds about
9 s beyond the model call, plus about 0.07 s for each extra key average.

**Estimated run time** (sequential, from the measurements above):

| Work | Carbon-500M | GENERator-v2 1.2B | Both |
|---|---|---|---|
| Design B: 6,432 likelihoods per model | 62 h | 129 h | **191 h (8.0 days)** |
| Design A: 1,608 states, 64 key averages (about 17 s and 26 s per state) | 7.6 h | 11.6 h | 19 h |
| Design A: 1,608 states, 256 key averages (about 30 s and 39 s per state) | 13.4 h | 17.4 h | 31 h |
| Design A: 512 hash-selected states, 256 key averages | 4.3 h | 5.5 h | 10 h |

**Verdict for this node.**

- **It works.** Both models load and run in bfloat16, and memory fits, though GENERator reaches
  5.9 GB of 7 GB.
- **The full plan is not practical here.** It needs roughly 9–10 days of uninterrupted
  computation, with no room for parallel workers: there are only two threads, and GENERator
  leaves about 1 GB of memory free. A Codespace also stops when idle, which would interrupt the
  run. The run is resumable, but repeated restarts would stretch it further.
- **What to run here:**
  - the code changes and unit tests;
  - the upstream parity tests;
  - the 4-prompt smoke run once the sequences are copied;
  - optionally, design A on a predeclared subset (about 10 hours).
- **Where to run the full scoring:**
  - **A Lonestar6 CPU node** (128 cores, 256 GB). About 30 shard workers with 4 threads each
    would finish both designs in well under a day.
  - **One A100.** Teacher-forced scoring takes a fraction of a second per read on a GPU, so
    design B takes about an hour per model.

  Both use the same resumable `--case-id` sharding.

## Steps

1. Copy and verify the second cohort's generated sequences (prerequisite 0).
2. Fix the manuscript's sampler-fidelity wording (see "Finding" above). This needs no run.
3. Implement the code changes with tests. Run the upstream parity tests here.
4. Write and freeze the protocol, and assign `synthid.v4.*`.
5. Smoke run: 4 prompts per model through both designs. Validate the shards and record timings.
6. Full run, sharded by prompt with `--case-id` and resumable. Run design B first, because it backs
   the paper's quality claim.
7. Finalize with `--finalize`. Derive ledger entries, update `paper/context/evidence_map.md`, and run
   `scripts/check_evidence.py`.
8. Manuscript: report sampler fidelity and quality from the second cohort, with the development
   cohort as a consistency check. Then present the study as one study with two cohorts, as
   discussed on 2026-10-01.

## Risks and decisions for the authors

- **Data loss.** If prerequisite 0 is missed, the plan needs regeneration and new detection.
- **Memory.** GENERator's weights are 4.65 GB in float32, so they must load directly in bfloat16
  (measured above). Do not run both models in one process.
- **Scope.** The sampler redesign is a new test, not a repeat. Its result must be reported for what
  it is, including if it rejects.
- **Number of states.** Up to 1,608 states per model is affordable. A predeclared hash-selected
  subset (for example 512) would halve the time with little loss for a calibration check. Decide
  this in the protocol, not after seeing results.

## Decision, 2026-10-01

- **Design A, the sampler test, was not run.** The authors dropped the 256-state run after the
  timing measurements: about 45 hours on this node, with the node restarting during the test run.
  The implementation tests were run instead, and the manuscript's sampler-fidelity text was
  corrected (see the protocol's status note).
- **Design B, the second-cohort quality measures, was not run.** It needs the second cohort's
  generated sequences from TACC scratch and about 8 days on this node. The quality claim remains on
  the development cohort.
- **Prerequisite 0 still stands.** Copy the second cohort's generated sequences off TACC scratch.
