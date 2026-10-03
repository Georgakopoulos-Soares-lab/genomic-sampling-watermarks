# Sampler-fidelity correction (2026-10-01)

## What was wrong

The sampler test reported in the manuscript draws the marked arm's 5,000 samples per state with
`random.choices` from the computed fixed-key law, then tests them against that same law. The
ordinary arm does the same with the model law (`scripts/run_{carbon,generator}_large_distribution.py`).
Agreement is therefore guaranteed in expectation. The test checks the sampling call and the
Monte Carlo test, but not how the fixed-key law is computed, and not the sampling routine that
generated the reads. The manuscript nonetheless said "Each sampler agreed with its intended
distribution".

## What was done

1. **Implementation tests run.**
   - The upstream parity tests against SynthID-Text commit `addb4a15` pass. They had been
     skipping because the reference clone was absent.
   - New tests in `tests/test_sampler_fidelity_v4.py` pass. They show that the NumPy computation
     used during generation agrees with the independent reference to within 1e-12. They show
     that computing the law once and applying the generation sampling step reproduces
     `_tournament_step` draw for draw. They also check that the correct samplers pass and a
     wrong one is rejected.
2. **Model-backed rerun not done.** A 256-state rerun through the generation code path was designed
   and frozen (`docs/research/synthid_v4_sampler_fidelity_protocol_2026_10_01.md`). The authors
   dropped it before any state completed: it would take about 45 hours on the available node,
   and the node restarted during the test run. No `synthid.v4.*` evidence exists.
3. **Manuscript corrected.**
   - Methods §3.5 now describes the implementation tests, which carry the correctness claim.
   - The same section now says what the 256-state test checks (the sampling step and the test,
     at realistic distributions) and what it does not (the computation of the fixed-key law).
   - The negative control is described accurately: draws from the model law tested against the
     fixed-key law.
   - Results §4.1, the Introduction, §3.2, and the Data and code availability statement were
     aligned with this.
   - No reported number changed. The rebuttal draft's W5a answer was updated to match.

The paper rebuilds to 17 pages with no warnings. The unit tests pass with and without the optional
numerical dependencies.
