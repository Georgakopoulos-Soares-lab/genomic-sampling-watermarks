# GENERator-v2 1.2B `G_tok` SynthID tournament validation

> Validation report. Only values with explicit entries in `evidence/measurements.yaml` are admitted manuscript evidence.

| Question | Metric | Watermarked | Ordinary/null | Difference | 95% CI | p-value |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| One-step law | TV distance | n/a | n/a | -0.20402 | [-0.2098, -0.19792] | 9.9999e-06 |
| Full sequence | Mean NLL/token | 7.7947 | 7.8003 | -0.0056371 | [-0.056142, 0.043782] | 0.82991 |
| Clean detection | TPR/FPR at 384 bp | 1 | 0.0052083 | score Δ 19.735 | [19.367, 20.059] | 9.9999e-06 |
| Clean detection | TPR/FPR at 768 bp | 1 | 0.013021 | score Δ 28.704 | [28.261, 29.076] | 9.9999e-06 |
| Clean detection | TPR/FPR at 1536 bp | 1 | 0.010417 | score Δ 41.079 | [40.542, 41.506] | 9.9999e-06 |
| Clean detection | TPR/FPR at 3072 bp | 1 | 0.0078125 | score Δ 58.724 | [58.186, 59.157] | 9.9999e-06 |

## Explicit answers

1. **Unique prompts:** 256.
2. **Generated sequences:** 512 watermarked and 512 ordinary.
3. **Generated material:** 3,145,728 bases and 524,288 generated 6-mer positions.
4. **One-step reproduction:** 5 of 256 watermarked arms reject their exact fixed-key tournament law at nominal alpha 0.05, versus 12.8 expected under the null. The Monte Carlo p-value floor 0.001 is too coarse for the 256-state Bonferroni cutoff 0.00019531, so zero Bonferroni rejections is not interpreted as evidence. Fixed-key tournament laws are intentionally reweighted relative to G_tok; 64-key marginal errors are recorded separately.
5. **Errors versus ordinary sampling:** mean paired TV difference -0.20402, 95% CI [-0.2098, -0.19792], p = 9.9999e-06.
6. **GENERATOR NLL/perplexity:** mean NLL/token difference -0.0056371, 95% CI [-0.056142, 0.043782], BH-adjusted p = 0.82991.
7. **Sequence proxies after correction:** none.
8. **Held-out TPR:** 384 bp: 1; 768 bp: 1; 1536 bp: 1; 3072 bp: 1.
9. **Held-out primary FPR:** 384 bp: 0.0052083; 768 bp: 0.013021; 1536 bp: 0.010417; 3072 bp: 0.0078125.
10. **Analytic-null fit check:** 384 bp: 0.0039062 over 512 trials (exact-binomial expectation 0.0098044); 768 bp: 0.011719 over 512 trials (exact-binomial expectation 0.010381); 1536 bp: 0.011719 over 512 trials (exact-binomial expectation 0.009783); 3072 bp: 0.0078125 over 512 trials (exact-binomial expectation 0.010038).
11. **Detector choice:** calibration-only mean/weighted-mean separation was 384 bp: 21.837/20.376 ordinary-arm SD; 3072 bp: 60.164/52.662 ordinary-arm SD; the mean detector was selected.
12. **Confidence intervals:** prompt-cluster 95% intervals are recorded for every TPR, null-family FPR, sequence metric, and paired score difference in the JSON summaries.
13. **Matched detector-score significance:** 384 bp: Δ=19.735, p=9.9999e-06; 768 bp: Δ=28.704, p=9.9999e-06; 1536 bp: Δ=41.079, p=9.9999e-06; 3072 bp: Δ=58.724, p=9.9999e-06.
14. **Largest finite-key marginal errors:** `cele_chr01_s02` (0.48816 TV; top-1 0.0018211), `scer_chr01_s13` (0.48299 TV; top-1 0.00069373), `drer_chr02_s12` (0.48126 TV; top-1 0.0014544), `scer_chr02_s14` (0.47908 TV; top-1 0.00135), `cele_chr01_s14` (0.47874 TV; top-1 0.0022663).
15. **Negative or unexpected results:** the deliberately broken sampler that skips the tournament was run on 8 frozen states and produced 8 nominal rejections. Ordinary size-control rejections and all unfavorable watermarked states remain in the artifacts.

## Claim separation

- Experiment A checks ordinary samples against `G_tok`, tournament samples against their exact fixed-key reweighted law, and finite-key averaging separately.
- Experiment B concerns matched full-continuation NLL and sequence-proxy shifts, clustered by prompt.
- Experiment C uses the analytic standard-normal mean-g threshold. All prompts contribute corresponding-key ordinary scores to its empirical fit check; detection and null-family rates use only the disjoint evaluation prompts.

These results must not be collapsed into the claim that the watermark ‘does not change GENERATOR.’ Fixture keys are public reproducibility material, and proxy similarity is not biological function, viability, or safety.

## Artifact digests

- `/scratch/10899/kimopro/generator_synthid_validation_hpc_v1/detection/calibration_trials.parquet` — `1aacaebe0faa003489d2586c1f7874e067c24f18c7a7a71b375436f91e02b7a7`
- `/scratch/10899/kimopro/generator_synthid_validation_hpc_v1/detection/detector_comparison.json` — `3623ba5990b3ee6a36a37dd4ab4e7e41db540b5f81c62f9f058a927856182d7c`
- `/scratch/10899/kimopro/generator_synthid_validation_hpc_v1/detection/evaluation_trials.parquet` — `0caddc6cc1dc843273d35644ce60e3bd4492ec458b37bbeb489dce639aefc1d5`
- `/scratch/10899/kimopro/generator_synthid_validation_hpc_v1/distribution/fixed_state_trials.parquet` — `032841cf662d7429aa8766d3abda5e804a7fbb53f4e47f3384bc7f987adc8543`
- `/scratch/10899/kimopro/generator_synthid_validation_hpc_v1/distribution/state_manifest.jsonl` — `48a294ed383178989e66eb4b3ddeef6740937bf36148b44c0be8e0dada7db872`
- `/scratch/10899/kimopro/generator_synthid_validation_hpc_v1/generation/draw_00_generation.json` — `acd446080717548496fd1108600f59574972b995b8d6b74ce4aa0a4a2e89fa2c`
- `/scratch/10899/kimopro/generator_synthid_validation_hpc_v1/generation/draw_00_sequences.jsonl` — `039b6dc291e7d372dc1c6b9d2a3f3515338005c95ef0ecc1139b70a5c46f32ca`
- `/scratch/10899/kimopro/generator_synthid_validation_hpc_v1/generation/draw_01_generation.json` — `c49d3dac589bedbbd28fca4fa40cdad3451ed076e2344ed124c7f7b07d631274`
- `/scratch/10899/kimopro/generator_synthid_validation_hpc_v1/generation/draw_01_sequences.jsonl` — `8f45d1be33f636be2004b50f0fb9fd966d4ec440bffb3a92d01df41e4fec724a`
- `/scratch/10899/kimopro/generator_synthid_validation_hpc_v1/sequence_comparison/sequence_metrics.parquet` — `91b752af763e40602829af2112236de0d25efa884428dec3305b2bf106522c6a`
