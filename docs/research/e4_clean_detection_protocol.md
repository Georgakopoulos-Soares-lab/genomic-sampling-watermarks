# E4 clean-detection protocol

Frozen before inspecting any detector output.

## Question

With only DNA, a runtime key, and public configuration, how many generated bases does the
standalone detector need for useful power at a globally calibrated false-positive rate, before any
edit is applied?

## Detector inputs and search

The verifier receives the DNA, the key, and the public configuration. It has no model, prompt,
logits, generation seed, or reference sequence.

The declared search for this pilot is:

| Component | Declared set | Count |
|---|---|---|
| Orientation | forward, reverse complement | 2 |
| Phase | 0-5 | 6 |
| Window | full evaluated prefix only | 1 |
| Key-stream offset | 0-7 | 8 |

That is 96 scored hypotheses per sequence and length. The reported statistic is the maximum
standardized keyed group agreement `z = (2m - n) / sqrt(n)` over all 96. It is a maximum over a
search, so its nominal normal tail is not a p-value. Every p-value and every false-positive rate in
this experiment comes from null trials that repeat the identical 96-hypothesis search.

Windows are deliberately not swept in this pilot. Sliding windows are part of the crop and
synchronization experiments and will be declared there, with their own calibration.

## Generation

| Item | Frozen choice |
|---|---|
| Policies | `C_tok`, `G_tok`, `G_bp` |
| Prompts | the eight `q20` and `q80` windows of the v1 records |
| Cohort | `ncbi_refseq_eukaryote_windows_v2` |
| Generated length | 512 tokens, 3,072 bases, per prompt and arm |
| Arms | `partition-mc-v1` and `ordinary-categorical-v1` |
| Temperature / truncation | 1.0 / none |
| Key material | published non-secret fixture |
| Runtime | MPS, `bfloat16` for `C_tok` and `float32` for GENERATOR |

The approximately 5,000-base length in the original plan is deferred to the main run. This pilot
must first show that the detector separates at all and must produce a measured runtime before a
longer corpus is generated.

### Why a published fixture key

Detection power is a statistical property of the construction, not of one key. Using a published
fixture key makes the pilot exactly reproducible, and the wrong-key nulls below use different keys,
so the calibration is still meaningful. This is a correctness and power measurement, not a security
claim, and it must never be reported as one. The runtime-only secret-key path is implemented and
tested separately.

## Evaluated lengths

Each generated sequence is evaluated as prefixes: 384, 768, 1,536, and 3,072 bases, that is 64,
128, 256, and 512 tokens. Prefixes share the keyed partition cache, so all four lengths cost one
pass.

## Positives and nulls

Every trial runs the identical 96-hypothesis search at the evaluated length.

| Family | Definition | Trials per policy and length |
|---|---|---|
| Positive | correct key on watermarked DNA | 8 |
| N1 | wrong key on watermarked DNA | 8 prompts x 20 keys = 160 |
| N2 | any key on the matched ordinary arm | 8 prompts x 20 keys = 160 |
| N3 | any key on unwatermarked public prompt DNA | 8 prompts x 20 keys = 160, 64-token length only |

The 20 null keys are published fixture keys derived from public labels. N3 uses the 384-base public
prompt windows themselves, so it exists only at the 64-token length; it is the check that real
genomic DNA is not spuriously attributed.

## Calibration and reporting

- The headline threshold pools N1 and N2 at each length, since both are "this key did not write this
  sequence" cases with the same length and search.
- Target false-positive rate 0.01. The achieved and attainable rates are both reported; with 320
  pooled trials the attainable granularity is 1/320.
- N3 exceedance at the pooled threshold is reported separately, not folded into the threshold.
- Detection rate is reported per length with a percentile bootstrap over the eight prompt clusters,
  20,000 replicates, public seed 2718. Prompts are the resampling unit; null keys are not.

## Preregistered reading

- A detector that separates has, at some evaluated length, a detection rate of 1.0 at the calibrated
  0.01 threshold with the null families at or below their target.
- If the pooled null maximum exceeds the positive minimum at every length, the detector is not
  usable at these lengths and that is the result. Do not enlarge the search or the key set to
  rescue it.
- If N3 exceeds the pooled threshold more often than N1 and N2, real genomic DNA is not exchangeable
  with model output under this statistic, and the calibration must be redone against N3.

## Boundary

This experiment measures clean detection only. Substitutions, indels, crops, reverse
complementation, adaptive removal, and key reuse are separate experiments with their own frozen
shapes. No claim about them may be drawn from this pilot.

## Implementation status

- `src/genomic_watermarks/detector/search.py` implements the declared search, the statistic, the
  partition cache, empirical calibration, and empirical p-values.
- `scripts/generate_watermarked.py` produces the generated corpus.
- `scripts/run_detection_pilot.py` runs the detector pilot. It needs no model and loads no weights.

## Exact commands

```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 uv run python scripts/generate_watermarked.py \
  --policy C_tok \
  --cohort-jsonl data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl \
  --case-id yeast_q20 --case-id yeast_q80 \
  --case-id arabidopsis_q20 --case-id arabidopsis_q80 \
  --case-id celegans_q20 --case-id celegans_q80 \
  --case-id drosophila_q20 --case-id drosophila_q80 \
  --steps 512 --experiment-label e4-clean-detection-v1 --public-fixture-key \
  --cache-dir .cache/huggingface --local-files-only \
  --output outputs/carbon_c_tok_e4_generation_v1.json \
  --sequences-output outputs/carbon_c_tok_e4_sequences_v1.jsonl

uv run python scripts/run_detection_pilot.py \
  --sequences outputs/carbon_c_tok_e4_sequences_v1.jsonl \
  --cohort-jsonl data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl \
  --token-lengths 64 128 256 512 --stream-offsets 8 --null-keys 20 \
  --target-fpr 0.01 --bootstrap-replicates 20000 --bootstrap-seed 2718 \
  --output outputs/carbon_c_tok_e4_detection_v1.json
```

Repeat both for `G_tok` and `G_bp` with policy-specific names.

## Result (2026-08-21)

Run after the shape above was frozen. Generation: 393 s for `C_tok`, 1,298 s for `G_tok`, 1,360 s for
`G_bp` on MPS. Detection: 802-826 s per policy, 1,472 trials each, no GPU and no model.

Generator-side agreement rates on the watermarked arm were 0.984 (`C_tok`), 0.992 (`G_tok`), and
0.997 (`G_bp`), and keyed recomputation from DNA alone reproduced the generator's agreement pattern
exactly for every sequence.

| Policy | Bases | Threshold | Achieved FPR | TPR | Min positive z | Max pooled null z | N1 | N2 | N3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `C_tok` | 384 | 3.654 | 0.00938 | 1.0 | 7.50 | 3.91 | 0.0188 | 0.0250 | 0.0125 |
| `C_tok` | 768 | 3.816 | 0.00938 | 1.0 | 10.61 | 4.17 | 0.0188 | 0.0063 | n/a |
| `C_tok` | 1536 | 3.750 | 0.00938 | 1.0 | 15.38 | 4.20 | 0.0188 | 0.0063 | n/a |
| `C_tok` | 3072 | 4.066 | 0.00938 | 1.0 | 21.30 | 4.56 | 0.0188 | 0.0063 | n/a |
| `G_tok` | 384 | 3.654 | 0.00938 | 1.0 | 7.75 | 4.25 | 0.0188 | 0.0500 | 0.0188 |
| `G_tok` | 768 | 3.816 | 0.00625 | 1.0 | 10.96 | 4.17 | 0.0125 | 0.0125 | n/a |
| `G_tok` | 1536 | 3.820 | 0.00938 | 1.0 | 15.62 | 4.32 | 0.0063 | 0.0188 | n/a |
| `G_tok` | 3072 | 3.760 | 0.00625 | 1.0 | 22.01 | 4.56 | 0.0125 | 0.0188 | n/a |
| `G_bp` | 384 | 3.906 | 0.00938 | 1.0 | 8.00 | 4.41 | 0.0125 | 0.0125 | 0.0000 |
| `G_bp` | 768 | 3.712 | 0.00938 | 1.0 | 11.14 | 3.99 | 0.0188 | 0.0063 | n/a |
| `G_bp` | 1536 | 3.569 | 0.00938 | 1.0 | 15.62 | 3.82 | 0.0188 | 0.0125 | n/a |
| `G_bp` | 3072 | 3.536 | 0.00625 | 1.0 | 22.27 | 3.67 | 0.0063 | 0.0188 | n/a |

N1, N2, and N3 are the exceedance rates of the three null families at the calibrated threshold. N3
exists only at the 384-base prompt length.

Reading against the preregistered rule:

1. **Separation at every length, for every policy.** Detection rate is 1.0 and every positive
   statistic lies strictly above every pooled null statistic. The empirical global p-value is at its
   floor, 1/321, for every positive trial.
2. **Real genomic DNA is not spuriously attributed.** N3 exceedance is 0.0125, 0.0188, and 0.0000 for
   the three policies, comparable to or below N1 and N2, so the calibration does not need redoing
   against N3.
3. **The calibration is doing real work.** The maximum over 96 hypotheses reaches z = 3.7-4.6 under
   the null. A naive single-test one-sided 1% cutoff of 2.33 would have been badly anticonservative;
   the calibrated threshold sits more than a full standard deviation higher.

The margin at the shortest evaluated length is large: at 384 bases the smallest positive statistic is
7.50-8.00 against a null maximum of 3.91-4.41. That margin is the budget the edit experiments will
spend.

Two consequences for the main run. First, the approximately 5,000-base length is not needed to
demonstrate clean detection and remains deferred; it becomes relevant only if an edit condition
pushes power down. Second, lengths below 384 bases are now the interesting direction for the clean
curve, and they are cheap, because they are prefixes of the existing corpus.

## Evidence-admission review (2026-08-21)

Reviewed and admitted. `src/genomic_watermarks/detection_report.py` recomputes every reported
aggregate from the report's stored per-trial rows: each trial's statistic from its match count, the
per-trial token total from its length and phase, the calibrated threshold, the achieved and
attainable false-positive rates, the detection rate, the prompt-cluster bootstrap, the empirical
global p-values, every null-family exceedance rate, and the separation summary. It also enforces the
declared search (both strands, all six phases, offsets 0-7, no sliding windows), the 4,096-token
support, the fixture key sources, the trial counts per family, and the absence of raw DNA, key,
logit, and probability fields.

`scripts/analyze_detection.py` then binds provenance: the detection report digest, the generation
report digest with its model revision, device, and dtype, the sequences file digest, the recomputed
cohort content and manifest digests, and explicit calibration, null, uncertainty, security, and edit
scope. It refuses a generation report whose policy, label, cohort, or sequences path disagrees, or
one that did not verify keyed recomputation.

A first pilot run without stored per-trial rows was superseded rather than admitted. The reruns
reproduced its aggregates exactly, which is expected because the detector is deterministic, and only
the reruns are cited.

Admitted to `evidence/measurements.yaml`: twelve entries, one per policy and evaluated length,

- `e4.clean_detection.{c_tok,g_tok,g_bp}.b{384,768,1536,3072}.detection_rate`

each carrying its calibrated threshold, target/achieved/attainable false-positive rate, pooled null
trial count, minimum positive and maximum pooled null statistic, minimum empirical global p-value,
and all three null-family exceedance rates. Per-trial statistics are not admitted.

Detection artifact digests:

| Policy | Detection artifact | SHA-256 |
|---|---|---|
| `C_tok` | `outputs/carbon_c_tok_e4_detection_v2.json` | `edeb7e6cf7d046083b442131bcce5deb52321f5aac899bb0cf6e1135141e41f8` |
| `G_tok` | `outputs/generator_g_tok_e4_detection_v2.json` | `0be384730ab8193cf1eb1e5cc35f8523a3466dbed3c146cdcf32cb9efde90420` |
| `G_bp` | `outputs/generator_g_bp_e4_detection_v2.json` | `8a398f71bdb10a386290a0070684d6de7d7758332e12eb1130036ffd58a56cab` |

Analysis artifact digests:

| Policy | Analysis artifact | SHA-256 |
|---|---|---|
| `C_tok` | `outputs/carbon_c_tok_e4_detection_analysis_v2.json` | `5a4a31e40c59b3e2015d083d3d150d1ab0f923adf8d20246818c42e728c28678` |
| `G_tok` | `outputs/generator_g_tok_e4_detection_analysis_v2.json` | `2b1cf6a09d3dcb61ed6f317d4b7b033a47bbc17d9bff69fa2c423156aecef88e` |
| `G_bp` | `outputs/generator_g_bp_e4_detection_analysis_v2.json` | `1f7095944b4cd4cab7969a84936cd7888292f352e8eb9677c2dacf26da1154f7` |

Generated-corpus digests:

| Policy | Generation report | Sequences file |
|---|---|---|
| `C_tok` | `e5d3fe68bc021014d850f3e9b9a01a28ae6f4a4ce4c808d1e89f9550fe6df631` | `21859f133a1b8517f5ddd4f7fa767c36d0bb6678df71cfa9e5eb9820c2fba71d` |
| `G_tok` | `4c2ba3c9f7b372c8dd2202a8055dd0f6416e5b7bd01db64d03e17454e70ba348` | `0660ed273ebd758fd794f3bf91fef9d65ddb0efa51fdec47d82deb0954d85e21` |
| `G_bp` | `277253e83f9f0573de71480e6f2b0a1a8fb3296c7aa60762ff586831f8e672bd` | `3e716fa3a3771534902cf7d1a1bb73d893a125f1cb6bdb1fff284942c8dce061` |

## Decision-rule correction (2026-08-21)

The first admitted revision of this experiment used a calibration that counted null exceedances
strictly above the threshold while applying a greater-than-or-equal decision rule. With a discrete
statistic and a threshold that is itself a null order statistic, ties at the threshold were counted
as detections, so the realized false-positive rate exceeded the reported one: 0.0125 against a
reported 0.009375 and a target of 0.01.

The rule is now strictly greater than the threshold everywhere, including the bootstrap indicators
in every runner and validator, with a regression test over tied statistics. The experiment was
re-run: **no detection rate, threshold, or achieved false-positive rate changed.** The reported
achieved rate had already used the strict count, and now the rule that is applied matches it. Twelve
measurement IDs were reissued with a `.v2` suffix and the supersession is recorded in the ledger.

Cited artifact digests, corrected revision:

| Policy | Detection report | Analysis |
|---|---|---|
| `C_tok` | `1ea2e9023e0fecea006ad5c6e12b3cc6c31703e03e84fd46d84d715ad29fe1a0` | `24cafb1da1b65515955091896d4b8f5eb8bd20562d32befca4a647d3278128ea` |
| `G_tok` | `ba28bb5f2e18e04c3e81549c9b97e60d71d5f2e6fb141ef2f55873b4863c8c45` | `8a7eac7dde379f82ec8b26bf2de1ac6e4258827495b42d74fb15b050e63e0cbe` |
| `G_bp` | `4a256e912238eb60cd8b5791c11abbbcb4335993c7820a455aeda0f2f48f590b` | `f8e57b57303029b4f51b63229c8dd5003e592d23fdff5d79cf1b5ee34050d4e4` |

## Evidence boundary

Generation and detection reports are engineering artifacts in ignored `outputs/`. Only the twelve
admitted detection rates and the calibration and null numbers attached to them are paper-printable.
Cross-policy detection differences are not admitted: each policy has its own generated corpus, so a
difference between them is not a watermarking comparison.
