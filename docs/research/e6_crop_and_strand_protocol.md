# E6 crop, strand, and phase protocol

Frozen before inspecting any cropped or reverse-complemented detector output.

## Question

Does the declared search recover a watermarked fragment that has been cropped or stored on the other
strand, and what does widening the key-stream offset search cost in false-positive multiplicity?

## The two distinct search axes

These are easy to conflate and must not be.

- **Key-stream offset.** Answers "where in the key stream does this fragment begin". A crop from the
  front of a sequence shifts the offset. This is the axis E6 varies.
- **Observed window.** Answers "which part of this sequence is watermarked". It matters when a
  watermarked fragment is spliced inside unwatermarked DNA. E6 declares **no** sliding observed
  window; partial or spliced watermarking is a separate experiment and is not measured here.

## Alignment arithmetic, stated before the run

Generated tokens occupy original bases `[6i, 6i + 6)`. Cropping `k` bases from the front means the
verifier must read at phase `p = (-k) mod 6`, and the first recoverable token is index
`ceil(k / 6)` — that is the key-stream offset the search must contain.

| Condition | Required phase | Required offset |
|---|---:|---:|
| `identity` | 0 | 0 |
| `reverse_complement` | 0, on the reverse-complement branch | 0 |
| `front_crop_1` | 5 | 1 |
| `front_crop_3` | 3 | 1 |
| `front_crop_6` | 0 | 1 |
| `front_crop_7` | 5 | 2 |
| `front_crop_47` | 1 | 8 |
| `front_crop_48` | 0 | 8 |
| `front_crop_300` | 0 | 50 |
| `front_crop_768` | 0 | 128 |
| `front_crop_3_reverse_complement` | 3, on the reverse-complement branch | 1 |

The grid is chosen so that offsets 0-2 sit inside the narrow search, 8 and 50 sit outside it but
inside the wide search, and 128 sits outside both. `front_crop_47` and `front_crop_48` bracket the
narrow search's edge from a non-zero and a zero phase respectively.

## Frozen shape

| Item | Frozen choice |
|---|---|
| Policies | `C_tok`, `G_tok`, `G_bp` |
| Corpus | the E4 generated corpus, unchanged; 8 prompts, 3,072 bases per prompt and arm |
| Observed length | exactly 1,536 bases for every condition, so length is held fixed |
| Conditions | the eleven rows above |
| Searches | `narrow` = offsets 0-7, 96 hypotheses; `wide` = offsets 0-127, 1,536 hypotheses |
| Positive trials | 8, one per prompt, per condition and search |
| N1 | wrong key on the transformed watermarked arm, 8 keys = 64 |
| N2 | any key on the transformed ordinary arm, 8 keys = 64 |
| Target FPR | 0.01, calibrated per condition and per search on pooled N1 and N2 |
| Uncertainty | percentile bootstrap over the 8 prompt clusters, 20,000 replicates, seed 2718 |
| Key material | published non-secret fixture, as in E4 and E5 |

Every condition is a deterministic transform, so there are no edit replicates: 8 prompts give 8
positive trials per cell and the detection rate has resolution 0.125. That is coarse on purpose. This
experiment asks a near-binary question — does the required offset lie inside the declared search —
not where a smooth curve crosses a threshold.

### Order of operations

The observed sequence is built from the 3,072-base generated sequence as follows, and the order
matters:

- `identity`: the first 1,536 bases.
- `reverse_complement`: the first 1,536 bases, then reverse-complemented.
- `front_crop_k`: bases `[k, k + 1536)`.
- `front_crop_3_reverse_complement`: bases `[3, 3 + 1536)`, then reverse-complemented.

Truncating before reverse-complementing is deliberate. Reverse-complementing the full 3,072-base
sequence and then taking a 1,536-base prefix would read the *suffix* of the original, which shifts
the offset by 256 and would silently confound the strand test with a large crop.

## Null calibration

Thresholds are calibrated per condition and per search, from that cell's own 128 pooled null trials,
so nothing is assumed about whether the null depends on the condition. Attainable false-positive
granularity is 1/128 = 0.0078.

Widening the offset search from 8 to 128 multiplies the hypothesis count by 16. The maximum of more
hypotheses is stochastically larger, so the calibrated threshold must rise. That rise is the cost of
covering larger crops, and quantifying it is a purpose of this experiment, not a nuisance.

## Predicted outcome, stated before the run

- The narrow search detects `identity`, `reverse_complement`, and the crops requiring offsets 1 and
  2. It fails on offsets 8, 50, and 128.
- The wide search additionally detects offsets 8 and 50, and still fails on 128.
- The wide search's null maximum is larger than the narrow search's. At 256 tokens the positive
  statistic is near `z = 15`, far above either threshold, so power should not fall measurably at this
  length even though the threshold rises. The multiplicity cost should therefore be visible in the
  threshold and invisible in the detection rate.

If the wide search fails to recover an in-range crop, the offset indexing is wrong and no robustness
number may be admitted until that is explained.

## Boundary

Crops from the front, full-fragment reverse complementation, and their composition, at one fixed
observed length. Not measured here: interior deletions, spliced or partial watermarking, sliding
observed windows, crops combined with substitution, and any adversary who chooses the crop to evade
a known search. Insertions and deletions are E7.

## Implementation status

- `src/genomic_watermarks/edits/channel.py` provides `crop`; `src/genomic_watermarks/dna.py`
  provides `reverse_complement`.
- `src/genomic_watermarks/detector/search.py` provides the declared search and calibration unchanged.
- `scripts/run_crop_strand_pilot.py` runs this experiment. It loads no model.

## Exact command

```bash
uv run python scripts/run_crop_strand_pilot.py \
  --sequences outputs/carbon_c_tok_e4_sequences_v1.jsonl \
  --cohort-jsonl data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl \
  --cohort-manifest data/public_prompt_cohort_v2.yaml \
  --observed-bases 1536 --narrow-offsets 8 --wide-offsets 128 --null-keys 8 \
  --target-fpr 0.01 --bootstrap-replicates 20000 --bootstrap-seed 2718 \
  --experiment-label e6-crop-strand-v1 \
  --output outputs/carbon_c_tok_e6_crop_strand_v1.json
```

Repeat for `G_tok` and `G_bp` with policy-specific names.

## Result (2026-08-21)

Run after the shape above was frozen, and after the decision-rule correction recorded in the E4 and
E5 protocol documents, so the rule here is strictly greater than the threshold throughout. 2,992
trials per policy in 138-142 seconds each, model-free.

Detection rate, 8 positive trials per cell, threshold calibrated per condition and search:

| Policy | Condition | Required orientation | Phase | Offset | Narrow TPR | Wide TPR |
|---|---|---|---:|---:|---:|---:|
| `C_tok` | `identity` | forward | 0 | 0 | 1.000 | 1.000 |
| `C_tok` | `reverse_complement` | reverse complement | 0 | 0 | 1.000 | 1.000 |
| `C_tok` | `front_crop_1` | forward | 5 | 1 | 1.000 | 1.000 |
| `C_tok` | `front_crop_3` | forward | 3 | 1 | 1.000 | 1.000 |
| `C_tok` | `front_crop_6` | forward | 0 | 1 | 1.000 | 1.000 |
| `C_tok` | `front_crop_7` | forward | 5 | 2 | 1.000 | 1.000 |
| `C_tok` | `front_crop_47` | forward | 1 | 8 | 0.000 | 1.000 |
| `C_tok` | `front_crop_48` | forward | 0 | 8 | 0.000 | 1.000 |
| `C_tok` | `front_crop_300` | forward | 0 | 50 | 0.000 | 1.000 |
| `C_tok` | `front_crop_768` | forward | 0 | 128 | 0.000 | 0.125 |
| `C_tok` | `front_crop_3_reverse_complement` | reverse complement | 3 | 1 | 1.000 | 1.000 |
| `G_tok` | `identity` | forward | 0 | 0 | 1.000 | 1.000 |
| `G_tok` | `reverse_complement` | reverse complement | 0 | 0 | 1.000 | 1.000 |
| `G_tok` | `front_crop_1` | forward | 5 | 1 | 1.000 | 1.000 |
| `G_tok` | `front_crop_3` | forward | 3 | 1 | 1.000 | 1.000 |
| `G_tok` | `front_crop_6` | forward | 0 | 1 | 1.000 | 1.000 |
| `G_tok` | `front_crop_7` | forward | 5 | 2 | 1.000 | 1.000 |
| `G_tok` | `front_crop_47` | forward | 1 | 8 | 0.000 | 1.000 |
| `G_tok` | `front_crop_48` | forward | 0 | 8 | 0.000 | 1.000 |
| `G_tok` | `front_crop_300` | forward | 0 | 50 | 0.000 | 1.000 |
| `G_tok` | `front_crop_768` | forward | 0 | 128 | 0.000 | 0.000 |
| `G_tok` | `front_crop_3_reverse_complement` | reverse complement | 3 | 1 | 1.000 | 1.000 |
| `G_bp` | `identity` | forward | 0 | 0 | 1.000 | 1.000 |
| `G_bp` | `reverse_complement` | reverse complement | 0 | 0 | 1.000 | 1.000 |
| `G_bp` | `front_crop_1` | forward | 5 | 1 | 1.000 | 1.000 |
| `G_bp` | `front_crop_3` | forward | 3 | 1 | 1.000 | 1.000 |
| `G_bp` | `front_crop_6` | forward | 0 | 1 | 1.000 | 1.000 |
| `G_bp` | `front_crop_7` | forward | 5 | 2 | 1.000 | 1.000 |
| `G_bp` | `front_crop_47` | forward | 1 | 8 | 0.000 | 1.000 |
| `G_bp` | `front_crop_48` | forward | 0 | 8 | 0.000 | 1.000 |
| `G_bp` | `front_crop_300` | forward | 0 | 50 | 0.000 | 1.000 |
| `G_bp` | `front_crop_768` | forward | 0 | 128 | 0.000 | 0.125 |
| `G_bp` | `front_crop_3_reverse_complement` | reverse complement | 3 | 1 | 1.000 | 1.000 |

Multiplicity cost of widening the offset search from 8 to 128, a sixteen-fold increase in scored
hypotheses:

| Policy | Narrow mean threshold | Narrow max null z | Wide mean threshold | Wide max null z | Threshold rise |
|---|---:|---:|---:|---:|---:|
| `C_tok` | 3.812 | 4.32 | 4.342 | 5.45 | +0.530 |
| `G_tok` | 3.869 | 4.20 | 4.188 | 4.70 | +0.319 |
| `G_bp` | 3.686 | 4.07 | 4.206 | 4.75 | +0.520 |

Reading against the preregistered prediction:

1. **Every condition whose required offset lies inside the declared search is detected in every
   prompt, for every policy.** That covers the identity control, full-fragment reverse
   complementation, sub-token phase shifts of 1 and 3 bases, whole-token crops of 6 and 7 bases, and
   the composition of a 3-base crop with reverse complementation. The validator additionally checks
   that each detected positive was recovered at exactly the required orientation, phase, and offset,
   not at some other alignment that happened to score well.
2. **Every condition whose required offset lies outside the declared search fails, as it must.** The
   narrow search misses offsets 8, 50, and 128; the wide search recovers 8 and 50 and misses 128.
   Pooling all positives whose alignment is unreachable gives 0 exceedances in 96 narrow trials and 2
   in 24 wide trials, that is 2 of 120 or 0.017 overall, consistent with the 0.01 target given that a
   single cell of 8 trials has resolution 0.125.
3. **The multiplicity cost is visible in the threshold and invisible in the detection rate**, exactly
   as predicted. The mean calibrated threshold rises by 0.32 to 0.53 in `z` units and the null
   maximum rises from 4.07-4.32 to 4.70-5.45, while every in-range detection rate stays at 1.0
   because the positive statistic at 1,536 bases is near `z = 15`.

The practical reading: covering larger crops is cheap at this length. It is not free, and at a length
where the positive statistic sits closer to the threshold the same sixteen-fold widening would cost
real power. The offset range a deployment declares should therefore be tied to the crop sizes it
actually expects, not made large by default.

One honest limitation. Each out-of-range cell has only 8 positive trials and its threshold comes from
128 nulls, so a single cell's realized false-positive rate can only be 0, 0.125, and so on. Two of
the three wide-search offset-128 cells show 0.125. That resolution, not a detector defect, is why the
pooled figure above is the one to read. More null keys would sharpen it and are owed if this becomes
a headline number.

## Evidence-admission review (2026-08-21)

Reviewed and admitted. `src/genomic_watermarks/crop_report.py` recomputes every reported aggregate
from the stored per-trial rows and independently recomputes the phase and key-stream offset each
declared crop requires, so a mislabelled condition cannot pass. It enforces both declared searches
(two strands, six phases, contiguous offsets from zero, no sliding window), that the wide search
strictly contains more offsets than the narrow one, the fixed observed length in every trial, the
per-condition trial counts, and the absence of raw DNA, key, logit, and probability fields. For any
condition whose required offset is inside the search, it asserts that every detected positive was
recovered at the required orientation, phase, and offset.

`scripts/analyze_crop_strand.py` binds provenance and records the two search axes explicitly, so a
reader cannot mistake the key-stream offset axis for a sliding observed window.

Admitted to `evidence/measurements.yaml`: six entries, one per policy and declared search,

- `e6.crop_strand.{c_tok,g_tok,g_bp}.{narrow,wide}.conditions_fully_detected`

Each value is the number of declared conditions detected in every prompt. The complete condition
grid is admitted inside each entry under `admitted_conditions`, with per-condition required
alignment, in-search flag, detection rate, interval, threshold, achieved false-positive rate, both
null exceedances, and separation statistics. The multiplicity summary and the pooled out-of-range
exceedance are admitted under `admitted_multiplicity` and
`admitted_out_of_range_exceedance`. Per-trial statistics are not admitted.

Cited artifact digests:

| Policy | Report | Analysis |
|---|---|---|
| `C_tok` | `1eee4e7db804354e8b23fc23fb9212a2d1b64c7dcaa0e0c85211d5c6654e0cbc` | `dd96e5118d9bf0b37fdb43e1ce0ea7da01b559280ba83e8aa5acb16cde85e9ca` |
| `G_tok` | `52b04f9e68d0efe0e0e65be5b4c3c5df4525fa930534c67f0432a9f855ab798f` | `df0a83069b98c08f7e545658a2804c05def1e79cb7f6062f3b7085f12d9e863e` |
| `G_bp` | `c60e392aabcb36d2b4aef39fa4b868c0f4a3e16a10f06134425125b12efe1bea` | `24a51c0a35e01c8dfe66d7aa48066139f386d630a8efc1f616e52f28a7ba883c` |

## Evidence boundary

Reports are engineering artifacts in ignored `outputs/`. No number moves into
`evidence/measurements.yaml` without explicit evidence-admission review.
