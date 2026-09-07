# Carbon-500M `C_tok` SynthID tournament validation protocol

Frozen on 2026-08-29 before inspecting a complete 256-prompt result. This replaces the unfinished
INS/EXP/group-partition validation. The experiment has one watermark arm,
`synthid-tournament-v1`, and one matched ordinary categorical control. No result from the earlier
partial experiment may be pooled with this cohort.

## Scope

The run uses Carbon-500M revision `9796b752108258c1d365089f842e62e6c0547704`, policy `C_tok`,
temperature 1.0, no top-k or top-p truncation, 256 frozen public prompts, and two public fixture-key
draws. Each prompt/draw pair produces one 512-token tournament continuation and one matched
ordinary continuation. The full corpus is therefore 1,024 sequences, 524,288 generated 6-mer
positions, and 3,145,728 generated bases.

This first clean experiment deliberately excludes reverse-complement or phase search, key offsets,
windows, substitutions, insertions, deletions, crops, and other robustness conditions. The
standalone detector sees forward, phase-zero output DNA, a runtime key, and public configuration.
It does not receive the prompt, model, logits, generation seed, or generation trace.

## Tournament construction

The implementation adapts the binary non-distortionary tournament in Google DeepMind's
SynthID-Text release. It uses the released defaults of 30 tournament layers, four preceding output
tokens as context (`ngram_len = 5` in the reference), and a 1,024-context repetition history.
Anthropic describes its Claude watermark as a version of SynthID; that attribution does not imply
that this repository reproduces Anthropic's unreleased implementation.

For candidate `x`, context `c`, and layer `l`, a domain-separated HMAC-SHA-256 PRF supplies a binary
value `g_l(c, x)`. One layer maps a categorical law `p` to

```text
p'(x) = p(x) * (1 + g_l(c, x) - sum_y p(y) g_l(c, y)).
```

The code applies that exact probability-space update for 30 layers, which is equivalent to the
conceptual binary tournament without materializing `2^30` leaves. The first four output tokens are
ordinary samples so the detector can reconstruct every scored context from output alone. A context
already present in the rolling history is sampled ordinarily and masked from the detector.

A fixed key and fixed context intentionally define a reweighted conditional law. The
non-distortionary identity is an expectation over fresh pseudorandom `g` functions; it is not a
claim that the fixed-key conditional law equals `C_tok`, nor is it a many-output undetectability
claim. The HMAC construction is a repository-specific PRF adaptation, not copied reference code.

## Experiment A: one-step law

For each prompt, the audited state is the next-token law after 64 tokens of draw 0's ordinary
trajectory. At every state:

- 5,000 tournament samples are tested against the exact 4,096-way fixed-key tournament law;
- 5,000 ordinary samples are tested against the exact `C_tok` law;
- both use the existing G statistic with a 999-replicate parametric Monte Carlo null;
- the fixed-key tournament-to-model divergence is reported explicitly;
- the tournament law is averaged over 64 deterministic public fixture keys and its finite-key error
  to `C_tok` is reported without treating 64 keys as a proof of the expectation identity; and
- a frozen eight-state negative control samples from `C_tok` while being tested against the
  tournament law.

Family summaries retain nominal, Benjamini-Hochberg, and Bonferroni results. The state is the
independent unit for paired summaries. Passing the tournament-law goodness-of-fit test validates
the implementation at the tested resolution; it does not show that a fixed key leaves the model law
unchanged.

The 999-replicate Monte Carlo test has a minimum p-value of 0.001. This is coarser than the
256-state Bonferroni cutoff of 0.000195, so zero Bonferroni rejections is not usable evidence of fit
and must not be described as a pass. Interpretation uses the nominal rejection count relative to
its null expectation, the p-value distribution, and the eight-state negative control. The negative
control's Bonferroni cutoff is 0.00625 and is attainable at this Monte Carlo resolution.

## Experiment B: full continuations

Every generated sequence receives the declared sequence proxies and a teacher-forced Carbon
likelihood. The likelihood includes the prompt as context but scores only the 512 generated
canonical tokens under normalized `C_tok`. Comparisons are watermarked minus ordinary for the same
`(case_id, draw_id)`. The bootstrap resamples prompts and the sign-flip test gives both differences
from a prompt one shared sign. Benjamini-Hochberg is primary across metrics; Bonferroni is retained.

These are sequence and model proxies. They do not establish biological function, viability, or
safety.

## Experiment C: clean aligned detection

A frozen SHA-256 rank assigns 64 prompts to calibration and 192 to evaluation, keeping both draws
from a prompt in one partition. The score is the standardized mean binary `g` value across unique
contexts. There is exactly one hypothesis:

```text
forward orientation × phase 0 × full evaluated prefix × no key offset search
```

At 64, 128, 256, and 512 generated tokens, the strict decision rule is `statistic > threshold`.
The decision threshold is the one-sided standard-normal 0.99 quantile, 2.3263478740. Conditional on
the cryptographic idealisation that domain-separated HMAC output bits under an absent or independent
key behave as independent fair bits, unique scored contexts give `ones ~ Binomial(total, 1/2)` and
`(2 * ones - total) / sqrt(total)` has mean zero and variance one. The binomial statement is a
consequence of that assumption, not a proof about HMAC. The normal quantile is an approximation to
the resulting discrete null, not an empirically fitted order statistic; the exact binomial lattice
exceedance is recorded alongside each empirical fit check.

The original 64/192 prompt split is retained. Because no prompt score selects the analytic
threshold, all 256 prompts (512 corresponding-key ordinary trials) form the primary empirical
goodness-of-fit check. This gives a better check without shrinking the held-out detection set.
Evaluation continues to keep correct-key watermarked, corresponding-key ordinary, wrong-key
watermarked, independent-key ordinary, and public-RefSeq null families separate. Prompt-cluster
uncertainty and paired prompt-level tests are primary. No robustness claim is licensed by this clean
aligned experiment.

## Execution profiles and immutability

`configs/carbon_synthid_validation_v1.toml` remains the required MPS/CPU profile.
`configs/carbon_synthid_validation_hpc_v1.toml` is an optional Lonestar6 acceleration profile using
CUDA 12.8. Both profiles call the same model adapter, tournament, detector, analysis, and strict
validator; only orchestration, device, and recorded environment differ. The selected E16 execution
generated the corpus with CUDA bfloat16, then completed the fixed-state and teacher-forced analyses
with the documented CPU bfloat16 fallback from byte-identical generation artifacts. Its exact
environment is `configs/carbon_synthid_validation_cpu_analysis_resume_v1.toml`.

Each prompt completes as an immutable shard. Finalized files are assembled only when the declared
count exists and are never replaced by different content. Raw fixture keys are not serialized;
only public fixture indices and domains appear. Generated DNA and model caches remain under ignored
paths. Nothing is admitted to `evidence/measurements.yaml` until the full run and the strict
cross-artifact methodology/result validator pass.

The required artifact set is:

```text
cohort_manifest.yaml
prompts.jsonl
resolved_config.toml
generation/draw_00_sequences.jsonl
generation/draw_01_sequences.jsonl
generation/generation_summary.json
distribution/state_manifest.jsonl
distribution/fixed_state_trials.parquet
distribution/distribution_summary.json
sequence_comparison/sequence_metrics.parquet
sequence_comparison/sequence_comparison_summary.json
detection/calibration_trials.parquet
detection/evaluation_trials.parquet
detection/detector_comparison.json
detection/detection_summary.json
figures/manifest.json
report.md
artifact_digests.json
```

The execution-specific commands and source hashes are frozen in
[`carbon_synthid_e16_execution_2026_08_29.md`](carbon_synthid_e16_execution_2026_08_29.md), while
the reusable local and Slurm procedures remain in
[`tacc_slurm_execution.md`](tacc_slurm_execution.md). The four-prompt smoke passed the strict
validator before the 256-prompt job was submitted.


## Fidelity to the released SynthID-Text construction

Added 2026-08-29 after differential testing against the pinned upstream revision
`addb4a158143c7c6851a1308f78b89fceed59683` (`synthid_text_code` in `sources.yaml`).

### What is provably identical

`tests/test_synthid_upstream_parity.py` calls upstream's own `logits_processing.update_scores` and
asserts our probability-space update matches its log-space update to twelve places, across
vocabularies of 4, 8, 16, 64, and 256, depths 1, 3, and 30, flat and extremely peaked laws, and the
degenerate all-zero and all-one layers. The tests also assert the clone sits at the pinned revision,
so the comparison cannot silently drift to a later upstream commit.

The tournament formula is therefore not a reimplementation from the paper; it is checked against the
released code. `tests/test_synthid.py` independently enumerates the full `2**depth` conceptual
bracket with tie-breaking coins and confirms the closed-form update equals the actual tournament.

Configuration also matches the released defaults: depth 30, four context tokens (upstream's
`ngram_len` of 5 counts the candidate), context history 1,024, and repeated context n-grams sampled
ordinarily and excluded from detection.

### Deliberate divergences

| Aspect | This project | Upstream | Why |
|---|---|---|---|
| PRF | HMAC-SHA-256, domain-separated | its own hashing helper | keeps the core dependency-free and the key handling auditable; the construction requires only a PRF |
| Context bootstrapping | first four output tokens sampled ordinarily; the prompt is never given to the detector | context may be drawn from the prompt | makes every scored n-gram reconstructable from output DNA alone, which the threat model requires of a standalone verifier |
| Per-layer normalisation | renormalise after each layer | no renormalisation | the transform preserves total mass algebraically, so this only bounds floating-point drift over 30 layers; parity with upstream is asserted after normalising both |
| Vocabulary | 4,096 fixed canonical 6-mers | model text vocabulary | the genomic adaptation |

### Detector choice, and why the weighted mean was rejected

Upstream offers a mean, a weighted mean, and a Bayesian detector. Our statistic
`(2 * ones - total) / sqrt(total)` is upstream's `mean_score` under a monotone standardisation, so
it is the mean detector exactly.

The weighted mean was evaluated only on the frozen 64-prompt calibration split (two draws, 128
trials per arm), before inspecting evaluation-prompt detector performance, and it is **worse**
here. Measured separation between the watermarked and ordinary arms, in units of the ordinary
arm's own standard deviation:

| Detector | 384 bases | 3,072 bases |
|---|---|---|
| mean | **20.69** | **64.84** |
| weighted mean, upstream default weights | 19.02 | 56.84 |

The cause is the per-layer signal profile. Across the thirty layers, the calibration-arm
watermarked mean g spans only 0.7133--0.7551 at 384 bases and 0.7136--0.7492 at 3,072 bases, while
the ordinary arm is centered near 0.500. Upstream's default weights decrease linearly from 10 to 1,
which is far more aggressive than that profile justifies: at 384 bases the weighting raises the
watermarked mean from 0.7360 to 0.7405 but raises the ordinary standard deviation from 0.01133 to
0.01261; at 3,072 bases the corresponding changes are 0.7378 to 0.7424 and 0.00367 to 0.00427.
Net separation falls by about 8% and 12%, respectively.

Those weights are a reasonable default for natural-language vocabularies; on this 4,096-token DNA
vocabulary the near-flat per-layer profile makes near-uniform weights close to optimal. The mean
detector is therefore used on measured grounds, not as the simplest available option. A
signal-matched weighting was not fitted, because it would require another independent selection
split and held-out validation. The complete comparison, including input hashes and the exact
command, is recorded in `detection/detector_comparison.json`.

The Bayesian detector is not implemented and is not claimed.
