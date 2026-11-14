# SynthID v5 review-studies protocol (local cohort)

**Date:** 2026-11-12. **Namespace:** `synthid.v5.*`. **Status:** written before any v5 sequence was
generated and before any v5 outcome existed. Section 3 (cohort size, device, dtype) is completed
from a timing benchmark that reads no detection outcome; nothing else may change after generation
starts. Later changes go in a dated amendment, not in this file.

## 1. Why

The ICLR 2027 reviews of submission 32263 (`paper/reviews/2026-11-12_iclr_review_integration.md`)
ask for measurements the manuscript does not have:

| Study | Question | Reviewers |
|---|---|---|
| S1 layout | How does detection depend on region length, flank length, placement, strand, initial phase, and cropping? | GmoA, ot4K, zdRG |
| S2 detector comparison | What does the full search add over narrower detectors at the same sequence-level target, and at what cost? | GmoA |
| S3 null calibration | Is the sequence-level P-value valid across many independent keys, on model output and on DNA that no model generated? | zdRG |
| S4 entropy | Does per-token model entropy explain differences in strength between sequences and models? | ot4K |

The sequences of the detection cohort (`synthid.v2.*`) are not available on the machine used here,
so the studies run on a locally regenerated cohort. S0 establishes that cohort.

## 2. Scope boundary

- One watermark (`synthid-tournament-v1`), its ordinary control, and the unchanged verifier
  `synthid-position-independent-detector-v1`: 30 layers, four context tokens, 1,024-context
  history, window lengths 384, 768, 1,536, 3,072, both orientations, every base start, exact
  fair-binomial tail times the number of windows searched, compared with 0.01.
- **No verifier setting is tuned in any study.** The narrower and denser detectors in S2 are
  comparison baselines for one analysis. They do not replace or modify the verifier and are not
  used for any other result.
- No detector-query or detector-guided procedure. No multiple-edit condition. The only edits are
  the existing single-base conditions (S0) and one single insertion (S2). Truncation, flanking,
  cropping, and reverse complementation are layouts, chosen by public hash streams that never
  consult the detector, a key, or a score.
- No biological or secret-key claim follows from any result here. Keys are public fixtures.

## 3. Cohort and generation (S0)

- Prompts: the detection cohort `ncbi_refseq_eukaryote_windows_fpr_v2_1608`, content SHA-256
  `f6075a85bc056f5159952031618c544fb3a82864ed9029c913e7f5a7d03c5dc5`, rebuilt locally from the
  tracked manifest; `prompts.jsonl` must hash to
  `cb19e90662fcb25f774b0840e2e696132e2dc9c54439d97597bd186d4948f775`.
- Split: the existing rule and label (`carbon_synthid_validation_v1/prompt-split/v1`): the same 64
  reserved and 1,544 held-out prompts as the detection cohort. Reserved prompts are not used.
- Evaluated prompts: the first `N_eval` held-out prompts in split-rank order. `N_eval`, device, and
  dtype are fixed in the table below from the timing benchmark, before generation.
- Models, policies, temperature, truncation, tournament settings, two draws, two published
  fixture keys, and seeds rule: identical to the detection cohort protocol
  (`synthid_v2_fpr_scaling_protocol_2026_09_21.md`).
- New experiment labels `carbon-synthid-local-v5` and `generator-synthid-local-v5` enter the
  existing `experiment_label/cohort_id/policy_id` domain rule, so both models get new keyed
  functions and new sampling seeds. No v2 sequence is reused or reproduced.
- Each prompt yields two marked and two ordinary 512-token (3,072-base) continuations per model.

| Setting | Value |
|---|---|
| `N_eval` | 512 |
| Device | Apple M5 Pro (18 cores, 48 GB unified memory), PyTorch MPS backend |
| dtype | bfloat16, as in the detection cohort |

Fixed on 2026-11-12, before any v5 sequence was generated, from a timing benchmark under the
separate label `local-mps-benchmark-2026-11-12` (4 to 8 prompts per setting; no detector was run
on its output, and its sequences are not used). Measured cost with three concurrent processes:
about 24 s per prompt and draw for Carbon and 11 s for GENERator, so 512 prompts take about ten
hours for both models and all 1,544 about thirty. 512 is the smallest power of two for which zero
ordinary positives would give an exact one-sided 95% upper bound below 1% (0.58%; 256 prompts
would give 1.16%). Generation runs as three processes per model over disjoint prompts, each
writing its own directory; the per-prompt files are then collected unchanged into one directory
and assembled by the existing finalization step. The prompt-split file for S0 marks the 512
evaluated prompts as evaluation and every other prompt as not evaluated.

S0 detection: the existing position-independent runner, unchanged, on the reference layout
(384-base prompt followed by the 3,072-base continuation): three families (marked with correct key,
ordinary with the corresponding key, marked with the other draw's key) and four conditions
(unedited, one substitution, one insertion, one deletion). Reported exactly as for the detection
cohort: counts, prompt-level exact one-sided 95% upper bounds for controls, strength, and
strongest-window length.

This is a second execution in a different computing environment, by the same authors with the same
code and the same prompts. It is not an independent replication.

## 4. Common rules for S1 to S3

- Public label for every hash stream: `synthid-review-v5`.
- **Region.** The marked region of a read is a marked continuation or a prefix of it. The control
  read has the ordinary continuation of the same prompt and draw in the same layout with the same
  flanks. Prefix truncation keeps the first `l` bases, `l` a multiple of six.
- **Natural flanks.** Flank DNA is real genomic sequence, not model output. The pool is the 1,608
  public source spans of the cohort: 3,072 canonical bases each, from the 12 RefSeq records, of
  which the first 384 are the prompt. A flank is built from pieces chosen by SHA-256 of (label,
  cell, case id, draw, side, piece index): the hash selects a span other than the read's own, and
  for the first piece a start offset inside it. Pieces are concatenated and cut to the flank
  length, so a flank longer than one span joins DNA from several loci. Left and right flanks are
  drawn separately, and the marked read and its control share the same flanks. A forward cell and
  its reverse-complemented twin in Series C share one flank identity, so the second read is the
  exact reverse complement of the first.
- **Families.** `watermarked_correct_key` and `ordinary_corresponding_key`, both draws.
- **Statistics.** The prompt is the independent unit. Rates carry exact two-sided 95% intervals;
  control rates also carry the exact one-sided 95% upper bound. Strength is
  `-log10` of the smallest window P-value. Every sequence-level P-value includes the full
  correction for the search actually performed on that read.
- Results are written once to new paths. Failures and exclusions are recorded, never rerun
  selectively.

## 5. S1 layout study

All evaluated prompts, both draws, both models, both families. Cells:

| Series | Varies | Cells |
|---|---|---|
| A length, suffix | read = prompt + first `l` bases of the continuation; `l` in 384, 576, 768, 1,152, 1,536, 2,304, 3,072 | 7 |
| B length, embedded | read of 6,144 bases: natural left flank of 1,536, region of the same seven `l`, natural right flank filling the rest | 7 |
| C phase and strand | `l` in 768, 3,072; natural left flank of 384 + `o`, `o` in 0..5; natural right flank of 384; read supplied forward or reverse-complemented | 24 |
| D flank length | `l` in 768, 3,072; natural flanks of `f` on each side, `f` in 0, 384, 1,536, 4,608 | 8 |
| E placement | `l` = 768 in a 6,144-base read; region start at 0, 1,344, 2,688, 4,032, 5,376; natural DNA elsewhere | 5 |
| F cropping | a contiguous crop of the reference read, length 768, 1,536, or 2,304, start drawn by hash from all valid starts | 3 |

The lengths 576, 1,152, and 2,304 fall between verifier window lengths.

Recorded per read: decision, sequence-level P-value, strength, number of windows searched,
strongest-window orientation, start, and length, and for marked reads the number of bases of the
strongest window that lie inside the marked region. For F, the number of marked bases retained.

Interpretation, fixed in advance:

1. Series A at `l` = 3,072 is the reference layout and must reproduce the S0 unedited decisions
   exactly. Otherwise the study is invalid and reports nothing.
2. Series C: a read and its reverse complement must give the same smallest window P-value and the
   same number of windows. A mismatch is an implementation failure, not a result.
3. The ordinary rate must stay at or below 1% in every cell. A cell above 1% is reported as
   observed, and its marked rate is reported with that caveat.
4. Detection rates for marked reads have no pass threshold. They are the result: a low rate at a
   short length, a long flank, or an off-grid length is a legitimate statement about scope.
5. No cell is added, dropped, or redefined after outcomes are seen.

## 6. S2 detector comparison

Reads: the first 256 evaluated prompts in split-rank order, both draws, both models, both families.
Five cells: the reference layout; the reference layout after one insertion (the existing
deterministic single-base rule); and Series B at `l` = 768, 1,152, and 3,072.

Detectors, all with the same window statistic and the same 0.01 sequence-level target, each
corrected for its own search:

| Detector | Told | Search | Correction factor |
|---|---|---|---|
| Aligned oracle | strand, region start, region length | one window: the region from its first base, floored to a multiple of six | 1 |
| Phase-only | nothing | both strands, six phases, one window per frame: the whole read from that phase, floored to a multiple of six | 12 |
| Verifier | nothing | as in Section 2 | its window count |
| Fine-grid search | nothing | both strands, every base start, every length 384 + 96`j` that fits the read | its window count |

After the insertion, the oracle is told the original region start and length, not the edit.
The fine-grid search stands in for a search over all contiguous spans, which was not run.

Reported per detector and cell: detection rate and ordinary rate with exact intervals, median
corrected strength (`-log10` of the sequence-level P-value before capping at 1), and median
single-thread seconds per read on the named CPU.

Interpretation: descriptive. No detector is declared better from a difference whose exact 95%
intervals overlap. The verifier's settings do not change whatever the outcome.

## 7. S3 null calibration

Keys: 64 keys, key `i` = SHA-256 of `synthid-review-v5/null-key/<i>`, never used in generation,
with the fixed domain `synthid-review-v5/null`. The verifier is unchanged.

| Family | Reads | Decisions |
|---|---|---|
| Ordinary model output | draw 0 ordinary read of every evaluated prompt, reference layout, both models | reads x 64 |
| Natural DNA | the 1,608 public source spans of the cohort, 3,072 bases each, as retrieved | 1,608 x 64 |
| Marked output, independent key | draw 0 marked read of every evaluated prompt, reference layout, both models | reads x 64 |

A 3,072-base span is searched with 13,064 windows instead of 16,136; its correction uses its own
count.

Reported per family and model: positives over decisions at 0.01; the per-key rate distribution;
the fraction of reads positive under at least one key; and the fraction of decisions with
sequence-level P-value at or below 0.01, 0.05, 0.10, 0.25, and 0.50, each with an exact interval.

Interpretation: the P-value is supported as valid where every observed fraction is at or below its
nominal level. Any fraction whose exact one-sided 95% lower bound exceeds its nominal level is
reported as evidence against validity, for that family. Decisions on one read under different keys
share the read; the read-level summary is reported beside the pooled count for that reason.

## 8. S4 entropy and strength

For every marked and ordinary continuation of the evaluated prompts, one teacher-forced pass of
the generating model records the Shannon entropy, in nats, of the canonical 4,096-token
distribution at each generated position. Per sequence: mean entropy over generated positions.

Reported per model: the distribution of mean entropy; Spearman correlation between a marked
sequence's mean entropy and (i) its S0 unedited strength and (ii) its fraction of mark bits equal
to 1 in the full continuation window, with 95% intervals from a bootstrap over prompts (10,000
replicates).

Interpretation: the prior expectation, stated before measurement, is a positive correlation in
both models. The result is reported whatever its sign. A correlation is not a causal attribution.

## 9. Execution record and admission

Each study records device, CPU, memory, software versions, exact commands, input and output
digests, and code digests in `docs/research/synthid_v5_review_studies_execution_2026_11_12.md`.
Results enter `evidence/measurements.yaml` under `synthid.v5.*` only after S0 completes, the
Section 5 checks 1 and 2 pass, digests are recorded, and `scripts/check_evidence.py` and the unit
tests pass. Admission does not widen the threat model.
