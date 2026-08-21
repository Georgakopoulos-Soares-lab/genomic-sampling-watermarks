# Contribution frame

## One-sentence contribution

We formulate and evaluate secret-key exact-marginal sampling as a model-free provenance channel for fixed 6-mer genomic language models, with source-accurate generation baselines and globally calibrated robustness to DNA synchronization errors.

## What may be novel

- Cross-model evidence on the realized watermark channel of Carbon and GENERator-v2 rather than an argument from nominal vocabulary size.
- Explicit separation of direct-token and base-marginal generation policies.
- Translation from nucleotide edits to a fixed-6-mer synchronization channel, with the full detector search included in calibration.
- A laptop-reproducible evidence pipeline for genomic sampling watermarks.

## What is not claimed as novel

- Inverse-transform or exponential/Gumbel watermark sampling.
- The general idea of unbiased/distribution-preserving language-model watermarks.
- Existing PRC or synchronization-string constructions.
- DNA watermarking in general.

## Publication outcomes

1. Positive cross-model result with usable clean and edited detection.
2. Positive clean channel but synchronization-limited result focused on indels.
3. Evidence that a generic text-watermark construction transfers without a new sampler.
4. Negative result showing insufficient realized channel capacity on these policies.

All four are legitimate outcomes if supported by the frozen protocol.

