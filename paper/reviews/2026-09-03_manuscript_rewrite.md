# Manuscript rewrite for readability — 2026-09-03

## What changed

`manuscript/source/main.tex` was rewritten end to end for a reader who is not already inside this
project. No result changed, no claim was strengthened, and no measurement was added to the paper
that was not already reviewed.

Specific changes:

- **One vocabulary.** Table 1 of the manuscript now fixes one word and one symbol per idea. Terms
  that previously appeared as synonyms are gone: `region` is always `window`; `sequence-level` is
  always `read-level`; `matched ordinary sampling control` is always `ordinary`; the three detection
  families are always `marked, right key`, `ordinary`, and `marked, wrong key`; the edit conditions
  are always `none`, `substitution`, `insertion`, `deletion`. The same words and symbols are used in
  the figures, the tables, and the axis labels.
- **Named symbols.** $N$, $L$, $M$, $n$, $S$, $P_{\text{win}}$, $P_{\text{read}}$, $\alpha$, $m$,
  $p$, $p_k$, $g$, and $k$ are defined once and used consistently. "Window strength" is defined once
  as $-\log_{10} P_{\text{win}}$ and is the only score scale used in the figures.
- **Plain sentences.** Stacked modifiers were removed. The verifier is introduced by its full
  identifier once, in Methods, and is "the verifier" everywhere else.
- **Structure.** Introduction, Results, Discussion, Conclusion, Methods. The method is stated in
  Results with the layer equation and the correction rule, so the reader meets the construction
  before the numbers. Limitations are three named paragraphs in the Discussion rather than a list.
- **Four figures added.** There were none before.

## Figures

`scripts/make_paper_figures.py` builds all four. It verifies the recorded SHA-256 of each source
artifact before plotting and refuses to run on a mismatch, and it writes every plotted value plus
the figure digests to `paper/figures/figure_values.json`.

| Figure | Content | Provenance |
|---|---|---|
| 1 | one keyed layer; what the verifier searches | 1a illustrates the layer equation and carries no measurement; 1b uses the recorded window count |
| 2 | model-score difference; all 14 declared summaries | `outputs/carbon_synthid_e16_v1/sequence_comparison_summary.json` |
| 3 | window strength by family; prompt-level rates with exact intervals | `outputs/carbon_synthid_position_independent_v1/trials.jsonl` and the ledger intervals |
| 4 | window strength by edit condition; length of the strongest window | `outputs/carbon_synthid_position_independent_v1/trials.jsonl` |

The palette is the validated categorical set for the three families and a single-hue ordinal ramp
for window length. Every series carries a direct label, so identity never depends on colour alone.

## Ledger additions

Three derived entries were added so that no plotted value sits outside the ledger. All three are
`[A]`, all three cite the same immutable artifacts and digests as the measurements they accompany,
and none of them states a new conclusion:

- `synthid.carbon.quality.metric_family_effects` — the 14 declared summaries as standardized effects
  with their intervals rescaled to those units, backing Figure 2b. The conclusion (0 of 14 after
  correction) was already recorded by `synthid.carbon.quality.corrected_rejections`.
- `synthid.detector.strength_separation` — weakest marked and strongest control window strength per
  read condition, against the 6.2078 threshold implied by 16,136 windows at a 1% target, backing
  Figures 3a and 4a.
- `synthid.detector.strongest_window_length` — the length of the best-scoring window per read
  condition, backing Figure 4b and the manuscript's explanation of why an insertion or deletion does
  not hide the mark.

`paper/context/evidence_map.md` now maps figures as well as printed numbers.

## Claims

The manuscript states, and does not exceed:

- no measurable quality loss was found, with the interval given;
- every marked read in the tested corpus was found, in all four conditions;
- the control counts are consistent with the declared 1% target and do not establish it;
- public fixture keys do not test key recovery; and
- nothing here is a biological result.

The GENERator replication is not referenced in the manuscript.

## Open gates carried forward

Both open gates from the evidence-consolidation review are now written into the manuscript's
discussion rather than held only in review notes: the Linux-CPU execution and the required M5 Pro
replay, and the protocol-document hash mismatch recorded in the provenance amendment. Neither is
resolved by this rewrite.

## Verification

- 108 unit tests pass, with the four optional upstream comparisons skipped.
- Ruff passes.
- `scripts/check_evidence.py` resolves 36 measurements, 12 artifact digests, 9 documents, and 19
  manuscript mappings.
- The manuscript builds to a 9-page PDF with `latexmk` and reports no LaTeX warnings. The build
  script's preferred engine, `tectonic`, is still absent from this environment.
