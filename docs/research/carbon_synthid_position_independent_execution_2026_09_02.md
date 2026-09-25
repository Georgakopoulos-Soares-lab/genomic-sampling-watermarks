# Carbon SynthID position-independent detector execution — 2026-09-02

## Outcome

The complete frozen validation passed. The detector evaluated 192 held-out prompts with two stored
draws, three key/family conditions, and four edit conditions, producing all 4,608 expected
sequence-level decisions. It received no prompt boundary, phase, strand, or position offset. It
searched both orientations, every nucleotide start, and all four declared lengths in one globally
corrected decision.

No Carbon generation or calibration was rerun. This execution uses only the SynthID tournament
implementation and its matched ordinary Carbon arm.

## Detection results

| Condition | Correct-key SynthID TP | Ordinary Carbon FP | Wrong-key SynthID FP |
|---|---:|---:|---:|
| Clean | 384/384 (100%) | 1/384 (0.2604%) | 0/384 (0%) |
| One substitution | 384/384 (100%) | 1/384 (0.2604%) | 0/384 (0%) |
| One insertion | 384/384 (100%) | 1/384 (0.2604%) | 0/384 (0%) |
| One deletion | 384/384 (100%) | 1/384 (0.2604%) | 0/384 (0%) |

All 192 prompt clusters had both correct-key draws detected in every condition. The prompt-level
exact 95% lower confidence bound for this all-success result is 98.097%.

The four displayed ordinary false positives are not four independent failures. They are the same
prompt and draw (`cele_chr02_s00`, draw 1) in all four conditions. Its winning 384-base
reverse-complement interval is bases 245–629 of the supplied read. Every deterministic edit occurs
well after that interval, so the winning score remains unchanged. The corrected sequence-level
probability is approximately 0.00404. No other ordinary sequence and no wrong-key sequence passed.

For one ordinary detection among 192 prompt clusters, the prompt-level exact 95% interval is
0.0132%–2.8676%. For zero wrong-key detections, the prompt-level exact upper bound is 1.9030%.
Therefore the observed null behavior is compatible with the declared 1% target, but the cohort is
not large enough to prove that the operational false-positive rate is below 1%.

## Signal margin

The weakest correct-key sequence in each condition remained far below the globally corrected 0.01
decision threshold:

| Condition | Weakest corrected probability | Best-region statistic |
|---|---:|---:|
| Clean | `2.69e-121` | 23.73 |
| One substitution | `1.28e-120` | 23.67 |
| One insertion | `1.11e-78` | 19.18 |
| One deletion | `3.47e-111` | 22.75 |

By comparison, the single ordinary false positive had statistic 5.04 and corrected probability
0.00404. The strongest wrong-key case had corrected probability approximately 0.0326 and therefore
did not pass. Even the weakest edited correct-key result has a very large margin; the perfect TP
rates are not borderline threshold effects.

## What the winning windows show

Every correct-key winner used the supplied forward orientation. Clean and one-substitution reads
almost always selected the full 3,072-base window: 383/384 trials, with one 1,536-base winner. Of
the clean full-length winners, 373/383 started exactly at the true but undisclosed generation
boundary.

After one insertion, the winner was 3,072 bases in 203 trials, 1,536 bases in 180, and 768 bases in
one. After one deletion, it was 3,072 bases in 232 trials, 1,536 bases in 151, and 768 bases in one.
This is the expected synchronization behavior: an insertion or deletion disrupts the 6-mer grouping
near the edit, while a candidate window beginning on a restored downstream phase or lying mainly on
one side of the edit retains a strong signal.

Null winners were split roughly evenly between forward and reverse-complement orientations and
were usually 384-base windows. That is not a detection defect: null reads offer many noisy local
maxima, and the global correction includes all of them.

## Complete search and false-positive correction

Clean and one-substitution reads contained 16,136 tested regions. One-insertion reads contained
16,144 and one-deletion reads contained 16,128. These counts include both orientations and every
start for 384, 768, 1,536, and 3,072-base windows. At a sequence-level target of 0.01, the local
probability needed to pass was about `6.2e-7`, not 0.01. This is why searching thousands of possible
positions does not silently inflate the false-positive rate.

## Validation checks

The historical run log recorded a larger repository test suite and evidence ledger before the
SynthID-only cleanup. The current, relevant verification is the 2026-09-03 manuscript-evidence
review: 108 retained tests passed with four optional upstream-comparison skips, and all 33 current
measurements plus their cited artifact hashes were verified. The dedicated detector tests and the
strict result checks described below remain in the retained suite.

- The dedicated tests passed, including exact small-binomial enumeration, two unknown prefix
  lengths, reverse complementation, complete hypothesis counting, and each single-base edit.
- Ruff passed for the complete repository.
- Environment diagnostics completed and the current 33-measurement evidence ledger passed its
  consistency, document, artifact-hash, and manuscript-mapping checks.
- The strict result validator checked all 4,608 trial identities, key mappings, read lengths,
  hypothesis counts, coordinate transforms, repetition accounting, statistics, exact and log
  probabilities, decisions, summaries, and source hashes.
- An in-memory changed global probability was rejected by the validator as inconsistent.

The strict validation command returned:

```text
{"decisions": 4608, "experiment_id": "carbon_synthid_position_independent_v1",
 "prompts": 192, "rate_cells": 12, "status": "ok"}
```

## Artifacts and provenance

| Artifact | SHA-256 |
|---|---|
| `summary.json` | `cc5f58d104e82b96ec87dfa3e0c305ea5d08717dbffe0b83d3cddbf5208bffa6` |
| `trials.jsonl` | `323d998561843dda5b204c33d3de9d6a281aaa700ceddc535b0d7af32e0ac81c` |
| `report.md` | `ea9b2957a6b88990ba3fa5df7da3756a5fb48b4ebe02114875aeccd614266022` |
| frozen protocol | `f0feca50e0af76119d2f9d40f3e6b203c6af2a04191383aa4cdec6737241684c` |
| position-independent detector | `db7a0116281d8c07b46b7c6c6196907526578480a22eb2ab6c55a9260f78c901` |
| boundary-search core | `b941504d71c9def7a52e5caa24864ae02c9f312c17d7a6f99fe00aeae1d06675` |
| SynthID generation/scoring core | `a50fa22c451548e901c75d59b0e6583d9e9015fd6e414cf379d57c7258933082` |
| validation runner | `383d29528d3affcfcba1bf8999d285896c313812056c31c699d9b553bda6be0c` |
| strict validator | `d12196756ba3e7fad2f375c0653cf7b1dbefd0261b68ee3bd00b4d8c0e8f2ef7` |

The result bundle is at `outputs/carbon_synthid_position_independent_v1`. The immutable summary was
created with a pending-review label; its reviewed measurements are now listed in the evidence
ledger.

A later manuscript audit found that the current working copy of the protocol document does not
match the protocol hash stored in this immutable summary. All scientific trial and decision checks
still pass before the validator reaches that final file-provenance check. The mismatch and its
required resolution by a new result identity are recorded in
`carbon_synthid_protocol_provenance_amendment_2026_09_03.md`.

## Interpretation boundaries

The result supports the implementation claim: the SynthID detector works without knowing where
generation began, and one substitution, insertion, or deletion did not reduce detection in this
corpus. Because detection is applied after generation and the source generation files were reused
unchanged, it cannot alter Carbon token choices or sequence quality. This run does not newly measure
quality; it preserves the earlier generation-quality evidence.

The declared edit scope is exactly one ordinary nucleotide event; multiple-edit and
detector-guided settings are outside the threat model. The result also does not establish
biological function, viability, sequence authenticity, or secret-key recovery resistance. The
execution host was Linux x86-64 CPU. The detector is dependency-light and CPU/MPS-independent.
Confirmatory replay requires a new result identity and documentation of the actual environment.
