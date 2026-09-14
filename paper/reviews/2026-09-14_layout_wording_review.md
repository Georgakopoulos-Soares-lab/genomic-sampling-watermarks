# Layout and wording review

Date: 2026-09-14

## Scope

The author requested repairs to the whitespace around Section 4.4 and the isolated Figure 3,
followed by a thorough wording review without revising the scientific claims or research code.
The working tree was clean at the start; the source baseline was
`a86e7924e1f34dc2cfbfe1a750a028610d3bb285`.

Changes are limited to `manuscript/source/main.tex`, the refreshed `manuscript/main.pdf`, and this
review record. No experiment, analysis code, protocol, evidence entry, bibliography entry, or
figure asset was changed. Existing figure PDFs were used directly by the manuscript build.

## Layout

- Removed the forced page break before Discussion that left Section 4.4 in a partly empty column
  and flushed Figures 3 and 4 onto separate pages.
- Allowed full-width floats at the top of text pages or on a shared float page, with consistent
  spacing. Figure 3 now shares page 6 with the detection table, immediately after Section 4.3.
- Reformatted the detection table into side-by-side Carbon and GENERator columns. The caption
  explicitly identifies the correct-key and wrong-key columns as marked reads. Every result and
  interval retains its original model, condition, and control-family association.
- Placed Figure 4 before its short Results subsection in the float queue and kept Section 4.4
  together. The full subsection now appears beneath Figure 4 on page 7, with Discussion beginning
  in the adjacent column.
- Discouraged orphan and widow lines and hyphenated word breaks between columns or pages.
- Tightened the closing prose so the Conclusion ends on page 8; availability and declarations
  begin on page 9.
- Used ragged-right reference formatting to remove stretched spaces around long URLs, and the
  standard LaTeX `balance` package to balance the final reference columns.
- The rebuilt manuscript has 10 pages; the previous viewed PDF had 11. Body text size, page
  margins, figure dimensions, author details, and title are preserved.

## Wording review

Reviewed the Abstract, Introduction, Background, every Methods and Results subsection, captions,
Discussion, Limitations, Conclusion, and closing declarations. Changes shorten long sentences,
replace vague or promotional framing with direct descriptions, clarify grammatical subjects,
and reduce repeated summaries. American spelling and the established terminology are retained.
The authors' September 13 title, author list, abstract wording, funding statement, and stated
future-work direction remain in place.

Representative edits:

| Before | After | Purpose |
|---|---|---|
| “corrects one read-level test over both strands” | “applies one read-level correction across both strands” | Describe the correction directly. |
| “the model-policy interface on which every comparison rests” | Methods begins with the models and sampling policy. | Remove abstract introductory framing. |
| “states fell below the nominal 0.05 level” | “tests for … states yielded nominal P-values below 0.05” | Make the statistical test the grammatical subject. |
| “No real arm produced a rejection” | “Neither the marked nor the ordinary arm produced a rejection … in either model” | Identify the arms explicitly. |
| “The primary outcome is unambiguous” | “In both models, the verifier detected …” | Lead with the result. |
| “not solely a thresholding artifact” | “separation between marked reads and controls relative to the corrected detection threshold” | Describe what Figure 3 shows without rhetorical framing. |
| “The strongest-window distribution provides a consistent explanation” | “The distribution of strongest-window lengths shows a consistent pattern” | Distinguish the observed pattern from its subsequent interpretation. |

The expectation over fresh keyed functions versus fixed-key reweighting, full-search correction,
tested single-edit scope, model-specific results, uncertainty about rare false positives, public
fixture keys, execution-platform caveat, and Carbon provenance discrepancy are retained. No new
scientific claim or external literature review was introduced.

## Verification

- `./paper/scripts/build.sh` succeeds. The final TeX pass has no overfull boxes or unresolved
  references; minor underfull-box warnings remain in the sequence-measures and Conclusion prose.
- All 10 final pages were rendered with Poppler and visually inspected. Figures and table labels
  are legible; no clipping, overlap, empty text column, isolated heading, or isolated figure page
  remains. After the final closing-prose edits, pages 1–7 were rendered again and their image
  hashes matched the already reviewed renders; pages 8–10 were inspected again.
- A source comparison confirmed identical displayed equations, citation groups, figure-file
  references, and all numeric tokens outside the reformatted table. Every table value was checked
  by condition and model against the original vertical blocks.
- `git diff --check` passes.
- `python3 scripts/check_evidence.py` still reports the five missing Carbon artifacts documented
  in earlier reviews: `distribution_summary.json`, `sequence_comparison_summary.json`, and
  `generation_summary.json` under `outputs/carbon_synthid_e16_v1/`, plus `summary.json` and
  `trials.jsonl` under `outputs/carbon_synthid_position_independent_v1/`. This pre-existing local
  artifact gap prevents a complete evidence check; no evidence was changed in this editorial pass.
- The visually reviewed build replaces `manuscript/main.pdf` so the usual paper link opens the
  revised version.
