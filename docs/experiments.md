# Experiment plan

This document is the experiment checklist. E0-E13 are planning labels from the research plans, not
a workflow engine or a requirement to create thirteen directories. Later stages do not compensate
for failed sampler correctness or inadequate channel capacity.

## E0-E3: correctness and channel

### E0 — Synthetic sampler correctness

- exact toy distributions, degenerate support, balanced and imbalanced partitions;
- analytic marginal checks plus fixed-state Monte Carlo;
- deterministic replay and invalid-input tests.

Gate: no model integration until every exact-marginal method passes.

### E1 — Source audit and integration

- tokenizer round trips and edge cases;
- direct-token versus base-marginal paths;
- logits-processor inventory and exact revision capture;
- MPS/CPU parity fixtures.

### E2 — Real channel measurement

- entropy, inverse Simpson support, top-1 mass;
- keyed partition mass and imbalance;
- mutual information per token and per base;
- distribution stratification by prompt, position, model, policy, and temperature.

Gate: stop or redesign if the measured signal cannot plausibly support detection within 5 kbp.

Frozen shapes, results, and admission records live in the per-experiment protocol documents:
`docs/research/e2_capacity_protocol.md`, `docs/research/e3_distribution_preservation_protocol.md`,
and `docs/research/e4_clean_detection_protocol.md`.

### E3 — Distribution preservation

- fixed-state categorical goodness-of-fit;
- paired sequence-level proxy comparisons;
- simple unkeyed distinguishers with held-out prompts and keys;
- repeated-output analysis under key reuse.

## E4-E9: detection and robustness

### E4 — Clean standalone detection

Detection power versus sequence length at predeclared globally calibrated FPRs.

### E5 — Substitutions

Independent and clustered substitution channels, with edit locations shared across methods.

### E6 — Insertions and deletions

Separate insertion, deletion, and mixed-indel curves; report nucleotide edit rate and induced 6-mer disruption.

### E7 — Crops, strand, and phase

Unknown start position, forward/reverse-complement orientation, and all six blocking phases. Calibration repeats the same search.

### E8 — Resynchronization

Compare no synchronization, local phase-state dynamic programming, anchors/markers, and only later coding-based schemes. Account for runtime and search multiplicity.

### E9 — Null and wrong-key calibration

At minimum: ordinary model outputs, wrong keys, public benign DNA, and cross-model outputs. Report confidence intervals on empirical FPR and never extrapolate below supported resolution without a justified model.

## Numbering: this file versus the protocol documents

This file kept an early numbering that the protocol documents diverged from as the work was executed.
**The protocol documents are the operative convention** and the sources-of-truth table in `../CLAUDE.md`
follows them. The mapping:

| Protocol convention (operative) | This file's original slot |
|---|---|
| E5 substitutions | E5/E6 substitutions and indels |
| E6 crops, strand, phase | E7 |
| E7 insertions, deletions, and the windowed resynchronization search | E6 and E8 |
| E8/E9 matched baselines, inverse transform and exponential | E12 |
| E10 held-out unkeyed distinguishers | E10 |
| E11 key reuse and many-output analysis | part of E10 and E11 |
| E12 spoofing and removal | E11 |
| E13 ECC/PRC layer | E13, unchanged and not started |
| E14 runtime envelope | not in this file originally |
| E15 order-sensitive proxies | not in this file originally |

Nothing below has been renumbered, because the original plan is a record and rewriting it would erase
what was planned before the work was done. Read it as intent and the protocol documents as execution.

## E10-E13: attacks, comparators, and coding

### E10 — Unkeyed distinguishers

Sequence statistics and learned classifiers under held-out keys, prompts, and model policies. Evaluate single-output and many-output settings separately.

### E11 — Detector-query removal

Removal success versus nucleotide edit budget, query count, retained proxy utility, and attack knowledge.

### E12 — Matched literature baselines

ITS, EXP, unbiased reweighting/DiPmark if independently implemented, and one distortion-allowing reference. Use the same model policy and detector calibration budget.

### E13 — ECC/PRC layer

Begin only after E2-E9 identify the substitution/erasure/indel channel. Ordinary ECC plus keyed pseudorandom targets and actual PRCs are labeled separately. Any cryptographic claim requires its own proof and assumptions.

## Internal decision targets

These values come from the supplied research plans and are project gates, not literature constants:

- clean TPR at least 0.95 by 5 kbp at an initial FPR of `10^-3`;
- TPR at least 0.90 after 1% substitutions at 5 kbp;
- TPR at least 0.85 after 1% indels at 5 kbp, after declared synchronization;
- simple unkeyed single-output classifier AUC no greater than 0.55;
- warning if fewer than 1% generic edits remove the watermark;
- warning if mean information is below 0.01 bit/base and clean detection fails by 5 kbp.

Final paper claims follow measured confidence intervals, not these gates.
