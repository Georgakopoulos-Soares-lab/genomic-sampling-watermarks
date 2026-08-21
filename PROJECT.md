# Project charter

## Working title

**Secret-Key Sampling Watermarks for Genomic Language Models**

## Paper thesis

Carbon and GENERator-v2 are not two separate paper targets. They are complementary test beds for one question: can the sampling freedom of fixed 6-mer genomic language models carry a secret-key provenance signal while preserving the intended generation distribution, and can that signal be verified from edited DNA without model access?

## Candidate contributions

These are targets, not accepted claims.

1. A source-grounded baseline taxonomy separating direct 6-mer sampling from base-marginal generation in Carbon and GENERator-v2.
2. A reusable exact-marginal sampler and standalone detector for fixed 6-mer genomic outputs.
3. A cross-model measurement of entropy, keyed partition balance, and attainable watermark information per token and per base.
4. A calibrated account of how substitutions, indels, crops, phase, strand orientation, and detector search affect detection.
5. A reproducible, laptop-scale evidence pipeline whose primary results run on one Apple M5 Pro with 48 GB unified memory.

## Facts

- Both research plans target secret-key sampling-time watermarks with no model retraining.
- The verifier must not require the prompt, model weights, logits, or generation seed.
- Carbon uses a hybrid tokenizer with fixed non-overlapping 6-mers inside DNA tags.
- The current Carbon checkpoints use a standard causal-LM path; a separate `fns` revision contains a base-marginal generation implementation.
- The audited GENERator-v2 checkpoint uses a base-marginal logits processor during its released generation path.
- A single nucleotide insertion or deletion changes the 6-mer phase of every downstream token under fixed blocking.

## Assumptions to test

- Real next-token distributions have enough effective support for detectable information within 1-5 kbp.
- Exact marginal preservation at each step is sufficient to avoid simple unkeyed distinguishers at the sequence level under the tested key-use policy.
- Searching strand and phase hypotheses can recover clean crops without invalidating false-positive calibration.
- Lightweight synchronization can recover useful power under low-rate indels without model access.

## Non-goals

- Training or fine-tuning Carbon or GENERator-v2.
- Running Carbon-8B as a required experiment.
- Treating a pseudorandom bit stream plus ECC as a pseudorandom code.
- Claiming wet-lab function, biological safety, viability, or cryptographic security from proxy experiments.
- Using sensitive or private genomic data.

## Decision rule

The project proceeds to a full paper only if E2 shows adequate information per base and E4 shows calibrated clean detection at a useful sequence length. Failure under indels can motivate a synchronization paper; failure under clean conditions stops watermark elaboration rather than expanding compute.

