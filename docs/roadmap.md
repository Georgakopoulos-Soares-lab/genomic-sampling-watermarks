# Roadmap

## Gate 0 — Repository and protocol

- [x] One combined paper charter
- [x] Source and literature audit
- [x] M5 Pro hardware contract
- [x] Evidence ledger and manuscript skeleton
- [x] Synthetic partition-coupling smoke implementation

## Gate 1 — E0 sampler correctness

- [ ] Extend fixed-distribution tests to ITS and EXP
- [ ] Add analytic proofs to paper context
- [ ] Add high-draw Monte Carlo evidence with uncertainty bounds
- [ ] Freeze sampler API v1

## Gate 2 — E1 model integration

- [x] Download and audit pinned tokenizer artifacts locally
- [x] Add Carbon/GENERATOR canonical-vocabulary and policy-transform tests
- [x] Add revision-declared local adapter and MPS/CPU runtime selection
- [x] Freeze and enforce Carbon's transitive Qwen tokenizer revision
- [x] Download pinned GENERator-v2 weights locally
- [x] Download pinned Carbon-500M weights locally
- [x] Validate Carbon `C_tok` against a real MPS forward pass
- [x] Add a single-state MPS/CPU distribution comparison
- [x] Run a small synthetic multi-context capacity, parity, throughput, and memory pilot
- [ ] Carbon optional `C_bp` branch tests
- [x] Validate GENERator-v2 `G_tok` and `G_bp` against real forward passes
- [x] Reject GENERator MPS `bfloat16` and freeze `float32` for current integration
- [x] Match local `G_bp` probabilities to upstream `compute_bp_probs` on MPS and CPU
- [x] Repeat Carbon parity and capacity sampling on a versioned public prompt cohort

## Gate 3 — E2 capacity decision

- [x] Collect real-logit engineering pilot states from a versioned public prompt cohort
- [x] Estimate information per base on sequential model states
- [ ] Convert capacity into detector-backed sequence-length requirements
- [x] Freeze the 12-prompt, 1,536-state-per-policy E2 pilot protocol
- [x] Implement and smoke-test sequential state collection
- [x] Implement prompt-cluster uncertainty and expansion-trigger analysis
- [x] Run all three policies on the initial 12-prompt cohort
- [x] Apply the frozen trigger and select a 24-prompt output-blind expansion
- [x] Run and validate all three policies on the final 24-prompt cohort
- [x] Complete evidence-admission review for the three E2 aggregates

## Gate 4 — E3-E9 core paper evidence

- [ ] Distribution-preservation audit
- [ ] Globally calibrated clean detector
- [ ] Substitution, indel, crop, phase, and strand curves
- [ ] Resynchronization ablation
- [ ] Wrong-key, public-DNA, and unwatermarked nulls

## Gate 5 — E10-E12 adversarial and comparative evidence

- [ ] Held-out unkeyed distinguishers
- [ ] Key-reuse and many-output audit
- [ ] Detector-query removal
- [ ] Matched literature baselines

## Gate 6 — Optional coding and manuscript

- [ ] Decide whether E13 is justified by the measured channel
- [ ] Freeze all headline measurements in the ledger
- [ ] Generate figures and tables from admitted evidence
- [ ] Complete internal review and submission package

## Open decisions

- Repository license.
- Final venue and page budget.
- Whether Carbon-3B confirmation is worth the measured local runtime.
