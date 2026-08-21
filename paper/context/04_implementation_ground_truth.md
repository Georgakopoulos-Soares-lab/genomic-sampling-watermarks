# Implementation ground truth

## Implemented

- canonical DNA normalization and reverse complement;
- all 4,096 canonical 6-mers in A/T/C/G product order;
- complete forward/reverse-complement and phase 0-5 hypothesis enumeration;
- HMAC-SHA-256 equal-cardinality keyed partitions;
- fair-bit maximal coupling to arbitrary partition mass;
- conditional categorical sampling;
- entropy, effective support, partition mass, and mutual-information utilities;
- deterministic substitution, insertion, deletion, and crop fixtures;
- standard-library unit and statistical smoke tests;
- revision-pinned Carbon and GENERator policy specifications and prompt contracts;
- canonical-vocabulary extraction that handles Carbon's dedicated DNA ID mapping;
- executable pinning of Carbon's transitive Qwen tokenizer revision;
- direct-token and independent base-product next-distribution transforms;
- lazy Hugging Face adapter loading with MPS-first/CPU-fallback runtime selection;
- tokenizer-only audit and one-state model distribution probe commands;
- one weight-backed Carbon-500M `C_tok` forward pass on MPS and a paired CPU comparison;
- an eight-context synthetic Carbon capacity pilot with a four-context CPU parity subset;
- a checksum-frozen 12-window public RefSeq cohort and full Carbon MPS/CPU engineering pilot;
- pinned weight-backed GENERator-v2 `G_tok` and `G_bp` public-cohort pilots;
- a revision guard for GENERator's internal tokenizer reload;
- an empirical requirement for GENERator MPS `float32` after `bfloat16` failed parity;
- a 12-context MPS/CPU audit matching local `G_bp` math to upstream `compute_bp_probs`;
- an unwatermarked sequential capacity collector with fixed public partition fixtures and a real
  four-state MPS smoke;
- a strict sequential-report validator and deterministic prompt-cluster bootstrap;
- a frozen, checksum-verified 24-prompt expansion selected before new model inspection;
- complete 3,072-state engineering capacity runs for `C_tok`, `G_tok`, and `G_bp` on MPS;
- a shared cohort content digest used by both the cohort builder and the capacity analyzer;
- provenance-binding analysis artifacts that record policy, revision, device, dtype, cohort
  content and manifest digests, metric definition, and uncertainty scope;
- three admitted E2 capacity measurements in `evidence/measurements.yaml`;
- the `partition_mc` autoregressive generation loop, its matched ordinary control, a keyed
  position-indexed partition/latent-bit stream, and model-free keyed recomputation from DNA;
- a runtime-only key path with a published non-secret fixture key for smoke runs;
- real-model matched generation smokes for `C_tok` and `G_bp` on MPS in which keyed recomputation
  from DNA alone reproduced the generator's agreement pattern exactly;
- a parametric Monte Carlo categorical goodness-of-fit test with a negative control proving it
  rejects a plausible within-group sampling bug;
- a frozen E3 stage-1 distribution-preservation protocol, its runner, its strict validator, and a
  provenance-binding analyzer;
- six admitted E3 stage-1 family summaries in `evidence/measurements.yaml`;
- E3 stage-2 sequence proxies with an exact paired sign-flip permutation test, run under one fixed
  key and deliberately not admitted;
- the standalone model-free detector: a declared strand/phase/window/offset search, the standardized
  keyed-agreement statistic, a keyed-partition cache, empirical threshold calibration, and empirical
  global p-values;
- a matched generated corpus of 3,072 bases per prompt and arm for all three policies;
- the E4 clean-detection pilot, its strict validator that recomputes every aggregate from stored
  per-trial rows, and its provenance-binding analyzer;
- twelve admitted E4 clean-detection rates with their calibration and null-exceedance numbers;
- a shared keyed-partition cache across sequences, verified to reproduce the admitted E4 artifact
  trial for trial while running 15.6 times faster;
- the E5 substitution-robustness sweep, its strict validator, its provenance-binding analyzer, and
  twelve admitted entries carrying the complete rate-versus-detection curves;
- an empirical confirmation that the null statistic distribution does not depend on the edit rate.

## Not yet implemented

- Carbon's `C_deployed` processor inventory;
- ITS and EXP samplers and matched detectors;
- a key-averaged E3 stage-2 design and its admission;
- sliding-window search and its calibration, needed for crops and synchronization;
- insertion, deletion, crop, and reverse-complement robustness;
- learned unkeyed distinguishers;
- biological proxy suite;
- ECC or PRC layer.

## Important boundary

The current partition code establishes a testable E0 reference construction. It is not a
production cryptographic system, and deterministic `random.Random` fixtures do not supply
cryptographic randomness. The three E2 mean-capacity aggregates have passed protocol
validation and evidence-admission review and are now ledger-admitted `[V]` values. All other E2
artifact fields, including per-prompt and per-state summaries, remain engineering results.
