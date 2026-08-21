# 12 — From capacity to detection

## Capacity is a possibility, not a detector result

The E2 experiment examined each model's probability distribution and asked how much information a
maximal-coupling partition could carry. The final means were around 0.15 information bit per base.
That says the channel is plausible. It does not say a detector already achieves high accuracy.

Naive arithmetic illustrates the distinction:

```text
1,000 generated bases × 0.15 information bit/base ≈ 150 information bits
```

Those 150 bits are not a guaranteed payload or detection score. Model states are sequentially
dependent, partition masses vary, the verifier searches unknown alignment hypotheses, and edits can
destroy synchronization. The detector experiment must measure the combined effect.

## The next implementation has two paths

For each prompt and policy, generate matched continuations:

```text
ordinary categorical sampler ──→ unwatermarked continuation

same model distribution
        + secret-key target stream
        + maximal coupling ─────→ watermarked continuation
```

The watermark path must preserve the declared model marginal. Tests begin on fixed toy
distributions, then move to real model states and complete sequences. Runtime secret keys are never
written to reports or repository files.

## The standalone detector sees less than the generator

The generator knows the model state and key. The detector receives only:

- the emitted DNA;
- the runtime key;
- public configuration.

For the first clean experiment, the detector scores the known orientation and phase as an internal
check. The paper-facing detector then repeats its full search over both strands, six phases, windows,
and key offsets. Null calibration must repeat that same search before a false-positive rate is
claimed.

## The next measurable question

For lengths such as 384, 768, 1,536, 3,072, and about 5,000 bases, measure:

- true-positive rate under the correct key;
- empirical false-positive rate on unwatermarked and wrong-key sequences;
- confidence intervals based on independent prompt/sequence clusters;
- runtime and memory on the M5 Pro;
- distribution-preservation diagnostics between ordinary and watermarked generation.

Only then can we say how many bases are required for clean detection. Substitutions, crops, strand
changes, and indels follow after the clean detector is globally calibrated.

Return to the [explainer index](README.md).
