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
| Many-output and key-reuse nulls | `e11.key_reuse.*` | **admitted** for all three policies |
| ITS and EXP matched baselines | `e8.e9.matched_baseline.*` | **admitted** for all three policies |
| Held-out unkeyed distinguishers | `e10.unkeyed_distinguisher.*` | **admitted** for all three; `G_bp` has two unresolved nominal rejections; the additional draws that would sharpen the null require mains power and have not been run |
| Calibration transfer to natural DNA | `e8.e9.matched_baseline.*.public_dna_exceedance` | **admitted**; an unplanned finding, reported as an observation |
| Key reuse and detector-query removal | `e11.spoofing.*`, `e12.removal.*` | **admitted** for all three policies |
| Spoofing under key reuse | `e11.spoofing.*` | **admitted**; a negative security result, see the sign rule below |
| Pricing the removal attack | `e15.structure_proxies.*` | **admitted as a negative**: both declared order-sensitive instruments are blind to a bounded 6-mer rearrangement |
| Abstract, contribution list, conclusion | every row above | **unblocked**: every required row is admitted |

The abstract is written last. Its claim strength is whatever the admitted evidence supports, which
includes the negative and synchronization-limited outcomes listed in `context/01_contribution.md`.

Every Wave-3 row is now admitted, so the manuscript is evidence-complete for a first full draft. What
remains before submission is prose, figures, citation checking, and the reviews listed below — not
more experiments. Two experiments are still *desirable* and neither gates drafting: additional `G_bp`
draws to resolve two nominal distinguisher rejections, and the ORF and independent-model-likelihood
proxies that would price the removal attack.

### Two sign rules that a draft can silently violate

1. **`e11.spoofing.*` reports a detection rate of 1.000 and that is a vulnerability.** It is the only
   detection rate in the ledger whose sign is inverted. It may not appear on the same axis, in the
   same table column, or in the same sentence pattern as the intended-detection rates, and it may
   never be averaged with them.
2. **`e12.removal.*` reports a detection rate of 0.000 and that is a successful attack.** It must be
   presented beside its utility column, because a rearrangement that destroys the sequence is not a
   useful attack — and the admitted utility numbers are small mainly because every implemented proxy
   is blind to a 6-mer permutation, which the text must say.
3. **`e15.structure_proxies.*` relative shifts must never be quoted without their paired p-value.**
   The relative shift of the longest reading frame is large and directionless; quoting the magnitude
   alone would assert an effect the data denies. The admitted value in that family is the *count of
   conditions with a directional effect*, which is 0 or 1 of 8, precisely so a reader cannot pick up
   the magnitude by accident.

## Section-by-section evidence contract

Each results paragraph must name, in the text or its table: the model policy, the sequence length in
bases, the edit condition, the calibrated false-positive rate and how it was calibrated, the number
of prompts and trials, the resampling unit for the interval, and the key setting (single-output,
wrong-key, many-output, or adaptive).

Numbers not in the ledger may not appear, including in captions, appendices, and the abstract. If a
draft needs a number that is not admitted, the fix is an admission review, not a sentence.

## Figures

Figures are generated from the ledger by `paper/scripts/make_figures.py`, never hand-drawn or
hand-edited. Every plotted value is read from `../evidence/measurements.yaml`; nothing is computed in
the figure script, read from a result artifact, or hand-entered, and a missing measurement raises
rather than falling back to a default. Regenerate with:

```bash
.venv/bin/python paper/scripts/make_figures.py
```

`paper/figures/manifest.json` records, per figure, the measurement ids it drew from, the caption claim
it supports, and the direction its axis points. That manifest is what `evidence-auditor` checks
against the ledger, so a figure cannot quietly drift from an admitted number.

### Built and visually inspected, 9 figures from 57 admitted measurements

1. `fig01_capacity.pdf` — Realized maximal-coupling watermark information per DNA base for the three released generation policies, with equal-weight prompt-cluster percentile intervals over 24 frozen public prompts. **Sign:** higher is more channel
2. `fig02_clean_detection.pdf` — Left: correct-key detection rate on clean watermarked DNA against generated length, at a false-positive rate calibrated by repeating the identical declared search on null trials. **Sign:** higher is intended detection; on the right, a wider gap is a stronger result
3. `fig03_calibration.pdf` — Top: the decision threshold chosen empirically from null trials that repeat the complete declared search of two orientations, six phases, and eight key-stream offsets. **Sign:** lower achieved FPR is stricter
4. `fig04_substitution.pdf` — Detection rate against per-base substitution rate, by policy and generated length, at the calibrated false-positive rate. **Sign:** higher is more robust
5. `fig05_crop_strand.pdf` — Detection rate per crop, phase, and reverse-complement condition under the narrow and the wide declared key-offset search. **Sign:** higher is more robust; a shaded failure is a search-coverage limit, not a fragility
6. `fig06_indel_synchronization.pdf` — Detection against per-base edit rate at 1,536 bases, the longest length the indel experiments evaluated. **Sign:** higher is more robust
7. `fig07_runtime.pdf` — Wall-clock time per stage for one policy on one Apple M5 Pro laptop, from single observations under uncontrolled desktop load. **Sign:** lower is faster
8. `fig08_baseline_signal_per_token.pdf` — Standardized signal per 6-mer token for the three exact-marginal constructions, each in units of its own null standard deviation, as a band across the evaluated lengths. **Sign:** higher is more signal per token; the dashed line is a structural cap, not a target
9. `fig09_key_reuse_attacks.pdf` — Left: a sequence spliced position-wise from two watermarked outputs under the same key scores indistinguishably from genuine output at every length, so the verifier accepts it every time. **Sign:** INVERTED. Left panel: high is bad. Right panel: low means the attack succeeded. Neither may share an axis with the intended-detection figures.

### Deliberately not plotted

- no peak-memory panel, because no memory figure is admitted;
- no detection-rate panel for the baseline comparison, because it is 1.000 in every cell and would
  present a null result as agreement;
- no per-trial statistic distributions, because they are not admitted evidence.

### The two inverted-sign figures

`fig09` is the only figure whose axes point the other way, and it carries both directions at once: a
high spoofing statistic is a vulnerability and a low removal detection rate is a successful attack.
It must never share an axis or a panel with the intended-detection figures, and its caption must say
which direction is which. The figure script marks forgeries with a distinct colour and marker for
exactly this reason.

## Draft status, 2026-08-24

A first evidence-complete draft exists and builds. Written: abstract, introduction with contribution
bullets, methods, experimental design, results, discussion, limitations, and the figure floats. Not
written: nothing that the evidence supports. The remaining work is checking, not drafting.

Dated review at `../reviews/2026-08-24_first_full_draft.md`.

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
