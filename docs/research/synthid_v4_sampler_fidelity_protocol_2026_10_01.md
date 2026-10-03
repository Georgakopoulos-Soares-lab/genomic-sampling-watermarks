# SynthID v4 sampler-fidelity protocol (generation code path)

Frozen before the first model-backed state. Evidence namespace: `synthid.v4.*`.
Runner: `scripts/run_sampler_fidelity_v4.py`. Unit tests: `tests/test_sampler_fidelity_v4.py`.

## Question

Do the sampling routines that generated the second cohort's reads draw from the intended
distributions at realistic generation states, under that cohort's own keyed functions?

## Why a new test

The version-one test (`scripts/run_{carbon,generator}_large_distribution.py`) drew marked samples
with `random.choices` from the computed fixed-key law and tested them against that same law. It
therefore checked the draw call, not the generation sampler. This test draws through the
generation routines and compares the draws with an independently coded reference law. The
version-one results stay on record and are not relabelled.

## States

- **Cohort.** `ncbi_refseq_eukaryote_windows_fpr_v2_1608`, rebuilt from the frozen manifest. The
  `prompts.jsonl` SHA-256 must equal
  `cb19e90662fcb25f774b0840e2e696132e2dc9c54439d97597bd186d4948f775` before any state runs.
- **Prompts.** 256 prompts per model, ranked by SHA-256 under label
  `synthid-v4-sampler-fidelity/states`, from the 1,544 evaluation prompts of the frozen split
  (`carbon_synthid_validation_v1/prompt-split/v1`). Both models use the same prompts.
- **State construction.** Each state is the prompt plus a fresh 64-token ordinary continuation drawn
  by `generate_ordinary`, the generation script's ordinary path. Its seed is public:
  `synthid-v4-sampler-fidelity / policy / case id / ordinary-prefix`.
- **State distribution and context.** The state distribution $p$ is the model's next-token law
  restricted to the 4,096 canonical tokens. The watermark context is the last four generated
  tokens. Whether that context occurred earlier in the prefix is recorded, not acted on.
- **Why fresh continuations.** The second cohort's own continuations are on TACC scratch and are not
  available here. Fresh continuations give states of the same kind: a generation-regime position 64
  tokens into an ordinary continuation of a cohort prompt.

## Keyed functions

These are the second cohort's draw-zero generation functions:

- key: `fixture_key(0)`;
- domain: `carbon-synthid-fpr-v2/ncbi_refseq_eukaryote_windows_fpr_v2_1608/C_tok` for Carbon, and
  `generator-synthid-fpr-v2/…/G_tok` for GENERator;
- depth 30, four context tokens, history 1,024.

## Per-state checks

1. **Exactness.** The largest absolute difference between $p_k$ from the NumPy path
   (`_tournament_probabilities_numpy`, used by `_tournament_step`) and $p_k$ from the pure-Python
   `tournament_distribution_reference`. It passes at $\le 10^{-12}$.
2. **Marked arm.** 5,000 draws with `_sample_index_numpy` on the NumPy law, which is the sampling
   step inside `_tournament_step`. G-statistic against the reference $p_k$, with a 999-replicate
   Monte Carlo reference.
3. **Ordinary arm.** 5,000 draws with `sample_categorical`, the generation ordinary sampler.
   G-statistic against $p$, with 999 replicates.
4. **Negative control.** At 8 hash-selected states (label `…/negative-control`): ordinary draws
   tested against the reference $p_k$.
5. **Integration.** At 32 hash-selected states (label `…/integration`): 200 direct `_tournament_step`
   calls must equal, draw for draw, the efficient path under the same seed.
6. **Key-averaged identity.** The mean of $p_k$ over 256 fresh derived keys. Total-variation distance
   from $p$ is recorded after 1, 16, 64, and 256 keys.

## Analysis, fixed in advance

- **Primary family.** Four tests: two models × the marked and ordinary arms. Each is the one-sided
  exact binomial probability of at least the observed number of states with $P \le 0.05$ out of
  256, under Binomial(256, 0.05). Bonferroni-corrected at 0.05 across the four tests, so each is
  compared with 0.0125. A sampler fails if its arm is rejected.
- **Secondary.**
  - Benjamini–Hochberg rejections at 0.05 per arm.
  - A decile uniformity test of the per-state $P$-values, with a Monte Carlo reference on the
    1/1,000 grid.
  - The negative control: all 8 states rejected after Bonferroni correction within the control
    family. The version-one standard was rejection at every control state.
  - Exactness at every state.
  - Draw-for-draw identity at every integration state.
  - The key-averaged total-variation distance should shrink as keys are added. If the identity
    holds, it falls roughly with the square root of the number of keys. A plateau would indicate
    bias.
- **Reporting.** Each result is reported as observed, including any failure.

## Scope

This tests the sampling routines and the fixed-key law at 256 states per model. It is not a proof of
correctness at every state. It does not test detection, quality, or key secrecy. The formula itself
is checked separately against Google's reference implementation
(`tests/test_synthid_upstream_parity.py`, commit `addb4a15`).

## Environment

The run uses this CPU node: two threads, 7 GB RAM, no GPU. Python 3.12, PyTorch CPU build, and
Transformers 5.x, with model revisions pinned by the adapter (Carbon-500M `9796b752`,
GENERator-v2 `c41b0018`) and bfloat16 weights. Exact versions are recorded in the run summary.
Models run one at a time.

## Status, 2026-10-01: not run

The authors withdrew the model-backed run before any state finished, so this protocol produced no
results and no `synthid.v4.*` evidence exists.

- **Why.** On this node the run would take about 45 hours. Carbon takes about 7 minutes per state,
  because its adapter has no incremental cache; GENERator takes about 3 minutes. The machine also
  restarted during the 2-state test run, ending it before its first state completed.
- **Instead.**
  - The upstream parity tests were run and pass (`tests/test_synthid_upstream_parity.py`,
    reference commit `addb4a15`).
  - The checks in `tests/test_sampler_fidelity_v4.py` pass on toy distributions: exactness of
    the NumPy path against the reference, draw-for-draw identity with `_tournament_step`,
    acceptance of the correct samplers, and rejection of the wrong one.
  - The manuscript now describes the version-one 256-state test for what it checks, and rests
    the correctness claim on these implementation tests.
- **Reuse.** The runner `scripts/run_sampler_fidelity_v4.py` and this protocol remain available.
  Re-running would need a fresh protocol date and hash.
