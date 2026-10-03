# Remaining fixes after the language pass (2026-10-01)

Follows `2026-09-30_post_lane_revision_plan.md` and `2026-09-30_language_flow_pass.md`. The
manuscript builds to 17 pages with no undefined references. One overfull column of 0.9 pt remains
on the last references page, from column balancing, and is not visible.
`scripts/check_evidence.py` fails only on the five missing Carbon primary-cohort files, and the
unit tests pass. Body numbers changed only where intended: the abstract no longer repeats
"3,087 of 3,088" (still in Results §4.6), and Limitations now gives 2.868% and 1.903%, matching
Results and Table 1.

## Done

| Item | Change |
|---|---|
| Title | "synthID" corrected to "SynthID" in the title and the PDF metadata, matching the text. |
| Abstract | Shortened from 353 to 298 words (286 before the revision). Every scope qualifier is kept: the one-sided bound, the 1.015% wrong-key cell, "without reference to the detector", and the biological and security disclaimers. |
| Zhao et al. sentence | Now says that the fixed partition doubles the edit tolerance of the context-dependent soft watermark but does not make the mark immune to edits, following `docs/research/literature_map.md`. |
| Rounding | Limitations uses 2.868% and 1.903%, as Results and Table 1 do. |
| Bibliography | Commentary and revision hashes removed from five entries: the SynthID-Text code, the Aaronson slides, Christ and Gunn, and the Carbon and GENERator model cards. This follows the 2026-09-11 decision to keep pinned revisions out of the manuscript; they remain in the evidence ledger. |
| Rebuttal draft | W2 now points to Limitations and W6 to Methods (Prompts and generation). Responses cite the revised PDF's numbering, and a mapping table from the submitted PDF replaces the earlier instruction to use the submitted numbering. The submitted column comes from the draft's own notes; check it against the submitted file, which is not in the repository. |
| Instruction files | `CLAUDE.md` and `AGENTS.md` no longer forbid all multiple-edit experiments while the paper reports one. They now name the admitted non-adaptive edit-rate series as the only multiple-edit evidence in scope and still forbid further multiple-edit, detector-query, and detector-guided experiments. |
| Figure labels (prepared) | `scripts/make_paper_figures.py` now labels the marked family "Marked, correct key" and the drift axes "Jensen–Shannon" (en dash). The evidence map uses "correct key". |

## Still blocked

**The figures still show "Marked, right key" (Figure 3, Supplementary Figure S1) and
"Jensen-Shannon" with a hyphen (Figure 2).** Regenerating them needs the Carbon primary-cohort
result files, which are not on this machine and were never committed:

- `outputs/carbon_synthid_e16_v1/{distribution,sequence_comparison,generation}_summary.json`
- `outputs/carbon_synthid_position_independent_v1/{summary.json,trials.jsonl}`

Only the second-cohort figures could be rebuilt today. Doing that alone would make Figure 3 and
Figure S1 disagree with each other, so nothing was regenerated. Once the files are restored
(their digests are in `evidence/measurements.yaml`), run:

```bash
python3 scripts/make_paper_figures.py --model carbon
python3 scripts/make_paper_figures.py --model generator
python3 scripts/make_paper_figures.py \
  --trials outputs/carbon_synthid_v2_fpr_position_independent/trials.jsonl.gz \
  --trials-sha256 a299c61368eef4645fb1c09ca01145f4beb3bf672870082c35bd55be38698414 \
  --evaluation-prompts 1544 --stem-suffix _v2 --panels ab \
  --manifest paper/figures/figure_values_v2.json
python3 scripts/make_paper_figures.py \
  --trials outputs/generator_synthid_v2_fpr_position_independent/trials.jsonl.gz \
  --trials-sha256 96f6ad073c25ec0e562d4f1d565ac75ffdfd1ca5697d75bfce9e388a4c609977 \
  --evaluation-prompts 1544 --stem-suffix _generator_v2 --panels cd \
  --manifest paper/figures/figure_values_generator_v2.json
python3 scripts/check_evidence.py
```

Then rebuild the paper. Committing the restored files, compressed as for the second cohort, also
lets `check_evidence.py` pass on a fresh clone.

**Not something an edit can fix:** the co-author named in
`docs/research/threat_model_edit_rate_v3_admission_2026_09_29.md` should confirm the edit-rate
sign-off in writing.
