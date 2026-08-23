# Drafting readiness plan

When drafting starts, and what each section is allowed to say. Drafting is downstream of evidence:
no section may be written from expected results.

## Rule for starting

Prose drafting of a results-bearing section starts only when every number that section needs is
already admitted to `../evidence/measurements.yaml`. Sections with no empirical content
(terminology, problem statement, construction, threat model) may be drafted earlier, because their
correctness does not depend on a pending run.

There are three drafting waves. Do not start a later wave to fill time while an earlier gate is
open.

## Wave 1 — method and framing (unblocked now)

Draftable today, because the required support already exists.

| Section | Required support | Status |
|---|---|---|
| Terminology | `context/00_terminology.md` | ready |
| Problem and threat model | `../docs/threat_model.md` | ready |
| Model-policy definitions | `../docs/research/model_source_audit.md`, `../docs/baseline_definition.md` | ready |
| Construction and marginal argument | `src/genomic_watermarks/watermark.py`, E0 tests | ready |
| Detector definition and declared search | `src/genomic_watermarks/detector/search.py`, `../docs/research/e4_clean_detection_protocol.md` | ready |
| Reproducibility and hardware envelope | `../docs/research/local_feasibility.md`, measured wall times | ready |
| Related work | `../docs/research/literature_map.md`, verified by `paper-sources` | ready, needs live citation check |

Wave-1 sections must state the marginal-preservation argument as a proposition with its proof
obligation, and must state explicitly that the detector statistic is a maximum over a declared
search whose nominal tail is not a p-value.

## Wave 2 — channel and correctness results (open)

| Section content | Required admitted evidence | Status |
|---|---|---|
| Realized channel capacity per policy | `e2.capacity.*` | **admitted** |
| One-step marginal preservation at real states | `e3.preservation.*` | **admitted** |
| Clean detection versus length, with calibrated FPR | `e4.clean_detection.*` | **admitted** |
| Runtime envelope | `e14.runtime.*` | **admitted**; peak memory deliberately excluded |

Every Wave-2 row is now admitted, so the channel, preservation, clean detection, and feasibility
subsections are all draftable. This is the point at which the paper has a spine: a
measured channel, a preserved distribution, and a calibrated detector.

## Wave 3 — robustness, adversarial, and headline claims (open)

| Section content | Required admitted evidence | Status |
|---|---|---|
| Sequence-level proxy comparison | `e3.stage2.*` | **admitted** for all three policies |
| Substitution robustness curves | `e5.substitution.*` | **admitted** |
| Crop, phase, and strand robustness | `e6.crop_strand.*` | **admitted** |
| Insertion and deletion, unwindowed detector | `e7.deletion.*`, `e7.insertion.*` | **admitted** |
| Windowed detector and resynchronization | `e7.stage2.*` | **admitted** |
| Wrong-key and public-DNA nulls | admitted with `e4.clean_detection.*` | **admitted** |
| Many-output and key-reuse nulls | E10/E11 admission | not started |
| ITS and EXP matched baselines | E8/E9 admission | samplers and invariants implemented; comparison run not started |
| Held-out unkeyed distinguishers | `e10.unkeyed_distinguisher.*` | **admitted** for all three; `G_bp` has two unresolved nominal rejections |
| Key reuse and detector-query removal | E11/E12 admission | not started |
| Abstract, contribution list, conclusion | every row above | blocked |

The abstract is written last. Its claim strength is whatever the admitted evidence supports, which
includes the negative and synchronization-limited outcomes listed in `context/01_contribution.md`.

## Section-by-section evidence contract

Each results paragraph must name, in the text or its table: the model policy, the sequence length in
bases, the edit condition, the calibrated false-positive rate and how it was calibrated, the number
of prompts and trials, the resampling unit for the interval, and the key setting (single-output,
wrong-key, many-output, or adaptive).

Numbers not in the ledger may not appear, including in captions, appendices, and the abstract. If a
draft needs a number that is not admitted, the fix is an admission review, not a sentence.

## Figures

Figures are generated from the ledger by `paper-figures`, never hand-drawn or hand-edited. The
planned minimum set:

1. realized channel capacity per policy, with prompt-cluster intervals (evidence admitted);
2. detection rate versus generated length at the calibrated FPR, per policy (evidence admitted);
3. calibrated threshold and null-family exceedance rates per length (evidence admitted; the
   per-trial statistic distributions are *not* admitted, so a violin or histogram of them would
   need its own admission);
4. detection rate versus substitution rate per length and policy (evidence admitted);
5. detection by crop condition under the narrow and wide offset searches, with the threshold rise
   annotated (evidence admitted);
6. detection versus indel rate per channel and length, with the substitution curve overlaid to show
   the two-order-of-magnitude gap (evidence admitted);
7. wall-clock time per experiment stage (evidence admitted; no memory panel, because no memory
   figure is admitted).

A figure whose evidence is pending is not stubbed in the manuscript.

## Pre-submission checklist

Run in order, and record the outcome under `reviews/` with a date:

1. `evidence-auditor` over every number, tag, scope word, and derivation in the manuscript;
2. `paper-sources` over every citation against a primary source;
3. `security-review` over every cryptographic or adversarial sentence;
4. `biological-proxies` over every sequence-statistic sentence;
5. `paper-structure`, then `paper-style`, in that order;
6. `./scripts/build.sh`, then visual inspection of every generated figure;
7. confirm no host names, local paths, run IDs, or key material appear anywhere in the source.

## Open non-technical decisions that gate submission, not drafting

- repository license;
- venue and page budget;
- whether Carbon-3B confirmation is justified by measured runtime.
