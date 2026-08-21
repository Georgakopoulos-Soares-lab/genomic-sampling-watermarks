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
- three admitted E2 capacity measurements in `evidence/measurements.yaml`.

## Not yet implemented

- the watermarked `partition_mc` generation loop and its matched ordinary control;
- Carbon's `C_deployed` processor inventory;
- ITS and EXP samplers and matched detectors;
- global null calibration over windows, offsets, and synchronization;
- learned unkeyed distinguishers;
- biological proxy suite;
- ECC or PRC layer.

## Important boundary

The current partition code establishes a testable E0 reference construction. It is not a
production cryptographic system, and deterministic `random.Random` fixtures do not supply
cryptographic randomness. The three E2 mean-capacity aggregates have passed protocol
validation and evidence-admission review and are now ledger-admitted `[V]` values. All other E2
artifact fields, including per-prompt and per-state summaries, remain engineering results.
