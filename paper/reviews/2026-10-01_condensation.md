# Condensation and co-author edits (2026-10-01 to 2026-10-03)

Two changes to `paper/manuscript/source/main.tex`:

1. A condensation pass run from `paper/context/condense_and_number_check_prompt.md`. It was
   interrupted before its checks and this note. The checks were completed afterwards and are
   recorded below.
2. Ilias Georgakopoulos-Soares's comments on the PDF of 2026-10-01.

The pre-condensation source and PDF are kept outside the repository at
`/workspaces/gsw-runtime/main_before_condense.{tex,pdf}`. The number register is
`paper/reviews/2026-10-01_number_register.md`.

## Length

| Section | Before | After |
|---|---|---|
| Abstract | 304 | 206 |
| Introduction | 520 | 478 |
| Background | 1,336 | 766 |
| Methods | 2,561 | 1,644 |
| Results | 1,564 | 847 |
| Discussion | 578 | 371 |
| Limitations | 886 | 573 |
| Conclusion | 164 | 112 |
| **Main text** | **7,609** | **4,791** |

The PDF is now 16 pages, down from 17. It builds with no LaTeX or BibTeX warnings. One overfull
column of 1.6 pt remains on the references pages, from column balancing, and is not visible.

## Structure

- **One study, two cohorts by role.** The development cohort (256 prompts) supplies window-score
  selection, the sampler checks, the quality measures, and a confirming detection run. The detection
  cohort (1,608 prompts, 1,544 held out) supplies detection, the false-positive rate, single edits,
  and the edit-rate series.
- **Moved to the Supplementary information:**
  - window-score selection (S1);
  - window geometry (S2);
  - conservatism of the correction (S3);
  - search cost and computing environment (S4);
  - development-cohort detection, with its table, now Table S1 (S5);
  - strength and the weakest sequence (S6);
  - the GENERator aligned-detector diagnostic (S7);
  - strength and window length by edit, with a new Table S2 that gathers values previously
    printed in the text (S8).
- **Cut:** the frameshift argument repeated across Background §2.2 and §2.4; repeated biological
  and secret-key disclaimers, which now remain in the Abstract, Limitations, and Ethics statement;
  and the Discussion's restatement of Results.

## Numbering

| | Before | After |
|---|---|---|
| Detection counts, detection cohort | Table 2 | Table 1 |
| Detection counts, development cohort | Table 1 | Table S1 |
| Strength and window length by edit | in text | Table S2 |

Figures 1–5 and Supplementary Figures S1–S2 keep their numbers. The rebuttal draft's mapping
table and `paper/context/evidence_map.md` were updated to match.

## Numbers

- **Discrepancy found by the register and fixed.** "A second cohort eight times larger" was wrong:
  the cohort has 6.3 times the prompts (1,608 vs 256). Only the held-out prompts and sequences
  differ by about eight times. The comparison is no longer printed.
- **Values no longer printed anywhere.**
  - 0.26%, the share of 1 positive in 384 sequences. It is derivable from Table S1.
  - The rounded "about 93%". The exact range, 92.9–93.9%, remains in Results.
- **New values:** none. Every other value is unchanged and still reported in the text, a table,
  or the Supplementary information.
- **Required scope qualifiers, all present:**
  - the one-sided 95% upper confidence bound;
  - the 1.015% wrong-key cell;
  - edits made without reference to the detector;
  - the 1–5-base indel events;
  - "not an independent replication";
  - eight of nine settings recovered by the protocol audit;
  - sampler correctness resting on the implementation tests;
  - preservation in expectation over fresh keyed functions;
  - no claim of biological function, secret-key security, or robustness to an adaptive editor.

## Co-author edits (Ilias Georgakopoulos-Soares)

| # | Comment | Change |
|---|---|---|
| 1–3, 5, 6 | Say "sequence", not "read". Reads suggest sequencing-length fragments. | "read" becomes "sequence" throughout: text, captions, tables, and figure labels. "read-level" becomes "sequence-level", and $P_{\mathrm{read}}$ becomes $P_{\mathrm{seq}}$. The term is defined once in §3.4 as the 3,456-base *test sequence*. Figures 1, 3, 4, and 5 were regenerated with the new labels, with identical plotted values. Supplementary Figures S1–S2 need the missing Carbon development-cohort files to be regenerated, so they keep "reads" in their panel labels, and their captions say so. |
| 4 | Drop the Introduction's closing disclaimer. | Already removed by the condensation. The disclaimers remain in the Abstract, Limitations, and Ethics statement. |
| 7 | "could provide a provenance signal" | Applied in the Abstract. |
| 8 | "using only the DNA sequence, a key, and fixed public settings", and what are the public settings? | Applied in the Abstract as "published detector settings". §3.3 defines them: the generation domain label, the four window lengths, the 30 tournament layers and four-token context, the 1,024-context repetition history, and the significance level $\alpha = 0.01$. It adds that in deployment only the key would be secret. |
| 9 | Background wording on generation-time watermarking | Applied in §2.1. |
| 10 | "The weakest detected GENERator read contained a highly repetitive continuation." | Applied in Results §4.3 and Supplementary S6, with "sequence". |
| 11 | Remove "We did not test that setting…" | Removed. The sentence stating that an adaptive editor was not tested remains, because it is a scope qualifier. |
| 12 | Title without "SynthID" | "Tracing model-generated DNA with position-independent watermarking", also in the PDF metadata. SynthID is still named in the Abstract and text. |

## Checks

- Built 16 pages with no LaTeX or BibTeX warnings.
- Every `\ref` and all 42 `\cite` keys resolve.
- `scripts/check_evidence.py` fails only on the five known missing Carbon development-cohort files.
- Unit tests pass, with and without NumPy, PyTorch, and the SynthID-Text reference.
- `ruff` is clean on the changed scripts.
- The PDF was read in full.

## Found outside the manuscript and not changed

These were found by the number register.

- The ledger note on `synthid.v2.detector.search_seconds_per_read` still says "6.3x". Its value
  fields give 5.7, which is what the paper prints.
- `evidence/measurements.yaml` does not parse under a strict YAML loader at
  `synthid.v3.source_manifest` (`supersedes_manifest`). `check_evidence.py` uses regular
  expressions and is unaffected.
- A duplicate `notes:` key remains in `synthid.generator.detector.strongest_window_length`.
