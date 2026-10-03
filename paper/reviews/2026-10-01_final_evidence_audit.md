# Final evidence audit (2026-10-01)

An independent read-only audit traced every number in `paper/manuscript/source/main.tex` to
`evidence/measurements.yaml` or a digest-recorded figure manifest. It also checked claim strength,
consistency between sections, and the evidence map. Nearly every value resolved with the correct
rounding, model, cohort, and condition; those it verified are listed below. The fixes below were
applied, and the paper rebuilds to 17 pages with no LaTeX or BibTeX warnings. One overfull column
of 6 pt remains on the first references page, from column balancing, and is not visible.
`scripts/check_evidence.py` fails only on the five missing Carbon primary-cohort files.

## Fixed

| # | Finding | Fix |
|---|---|---|
| 1 | The Methods described the edit-rate series as if each insertion or deletion changed one base. The code draws a 1–5-base span per insertion or deletion event, so the per-base rate counts events. | Methods, Background, and the Figure 5 caption now say so. "Single-base" is added where the single-edit medians are quoted. The span is recorded in the evidence map and the v3 execution record. |
| 2 | "6.3× speed-up" did not follow from the printed 0.0956 s and 0.0167 s; it came from an unledgered single-worker wall time. | "throughput … one read per 0.0167 s … 5.7 times the single-threaded rate", from ledger fields. |
| 3 | "Neither … sampler produced a rejection under either correction in either model" is not carried by the ledger for Carbon. No retained artifact holds Carbon's Benjamini–Hochberg count. | Stated for GENERator only. For Carbon, the paper says the corrected count was not retained and gives the 13 and 12 nominal rejections against 12.8 expected. |
| 4 | "no single rate and edit type exceeded 0.30%" | "largest value … 0.29% (GENERator, mixed series at 1%)". |
| 5 | "roughly 830–850" | "about 828–852" (ledger 827.7–852.4). |
| 6 | 0.85% in the Abstract and Conclusion, 0.850% elsewhere | 0.850% everywhere. |
| 7 | The Abstract's 1.015% wrong-key bound did not name the model. | "(Carbon, after a deletion)". |
| 9 | The Abstract said the second cohort came "from the same chromosome records". | "from 12 of the same chromosome records". |
| 10 | "peak resident memory of 27.9–69.1 MiB" | "peak memory per process of 27.9 MiB at 3,456 bases and 69.1 MiB at 13,824". |
| 11 | "the equivalent Carbon comparison was not retained" | It is recorded in the run notes, not as a retained result. The text now says so. |
| 14 | `paper/AGENTS.md` and the evidence map named only `figure_values.json`. | Both now list all four figure manifests. |

The rebuttal draft's W1, W5b, W4, and M5 answers were brought in line with fixes 1–5 and 10.

## Not changed

- **8, model names in the Abstract.** The audit suggested restoring the model sizes. The author
  asked on 2026-10-01 for them to be removed from the Abstract. The full names remain in the
  Introduction and Methods.
- **12, ledger hygiene.** `synthid.generator.detector.strongest_window_length` has two `notes:`
  keys, so YAML loaders keep only the second. This is left in place under the
  ledger-immutability rule. A corrected entry should merge the notes when the ledger is next
  amended.
- **13, figure manifests.** The digests of the `figure_values*.json` files themselves are not
  recorded in the ledger or checked by `check_evidence.py`. Every figure and every source digest
  inside the manifests does match.
- **Audit boundary.** Carbon primary-cohort values were checked against the ledger only, because
  their source files are absent. The figure images were checked through their manifests; the
  visual check was done separately.

## Verified clean

- Every cell of Tables 1 and 2, with the exact intervals and one-sided bounds recomputed.
- Every strength median, minimum, and window count, in both cohorts.
- The weakest-read analysis.
- Every edit-rate value, recomputed from both artifacts.
- The quality and sampler numbers.
- Timing, apart from the speed-up (fix 2).
- The analytic values (M, 6.21, 1,004 of 1,800, 21 bits).
- Caption counts against the figure manifests.
- Every figure and table cross-reference.
- Scope wording: the false-positive rate appears only as a one-sided upper confidence bound; the
  wrong-key cell is reported; the paper makes no robustness-difference claim, no biological or
  secret-key claim, and no adaptive-editor claim; distribution preservation is stated as an
  expectation over fresh keyed functions.
- No host names, local paths, run IDs, keys, internal identifiers, or process jargon in the
  manuscript.
