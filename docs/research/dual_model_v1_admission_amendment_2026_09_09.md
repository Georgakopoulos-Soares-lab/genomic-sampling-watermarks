# Amendment — 2026-09-09 — admission of version-one evidence for the dual-model manuscript

## Status

This amendment records an author scope decision. It supersedes, for the current manuscript only, the
rule in `PROJECT.md`, `AGENTS.md`, `CLAUDE.md`, and `paper/AGENTS.md` that version-one Carbon and
GENERator measurements are development history excluded from paper claims, and the requirement that
manuscript numbers come from a `synthid.v2.*` namespace.

The decision was taken deliberately and with the costs stated below. It is not a finding that the
earlier rule was wrong.

## What was decided

The manuscript becomes a dual-model paper on Carbon-500M and GENERator-v2-eukaryote-1.2b-base, drawn
from the existing version-one evidence:

- `synthid.carbon.*` — 6 measurements, already in the manuscript;
- `synthid.generator.*` — 17 measurements, previously fenced out.

No new run was performed and no number was recomputed. The two model evaluations share one prompt
cohort (`ncbi_refseq_eukaryote_windows_large_v1`), one watermark (`synthid-tournament-v1`), one
detector (`synthid-position-independent-detector-v1`), one 4,096-way canonical 6-mer policy shape,
and the same 192 held-out prompts with two draws each.

## Why it is defensible

The rule it supersedes exists to stop *silent* reuse of superseded numbers. The costs of reuse are
therefore disclosed in the manuscript rather than removed from it:

1. Generation ran on GPU hardware and detection on x86-64 CPUs, not on the Apple M5 Pro path that
   the replication plan declares for paper-bound stages.
2. For the Carbon position-independent run, the retained protocol document does not match the
   protocol hash recorded in the result, as recorded in
   `carbon_synthid_protocol_provenance_amendment_2026_09_03.md`.
3. Confirmatory replication of both runs is outstanding.

All three are stated in the manuscript's Limitations section. The prior justification for omitting
them — that the manuscript instead carried the scientific statement that follows from them — no
longer applies now that the numbers themselves are paper-bound.

## Ledger annotations changed

`evidence/measurements.yaml` measurement values, statuses, artifacts, digests, and commands are
untouched. Only stale scope annotations were updated, because they described a fence that the authors
have lifted:

- `evidence_role` on the three `synthid.generator.*` scope anchors, from
  `supplementary replication, excluded from Carbon-only manuscript` to a statement that the entries
  are admitted as co-primary model evidence by this amendment;
- two `notes` fields that asserted the GENERator result "does not alter the Carbon-only manuscript".

No result file was edited. Under `AGENTS.md`, corrections to measured quantities require a new result
and a new identifier; a scope annotation is not a measured quantity.

## What this amendment does not do

- It does not admit any measurement that does not already exist in the ledger.
- It does not claim the two models, their distributions, or their biological usefulness are
  equivalent. Replication across two models supports portability of the implementation only.
- It does not lift the hardware contract for future runs. New paper-bound runs still require the
  documented M5 Pro path.
- It does not close the gates in `dual_model_synthid_paper_rebuild_plan.md`. S0, S1, S3–S11 remain
  unevaluated, and the confirmatory M5 replication remains the intended follow-up.

## Asymmetry in what the two models can support

The two version-one runs are not identical in coverage. The manuscript must not imply otherwise:

| Quantity | Carbon | GENERator |
|---|---|---|
| Fixed-state sampler check | yes | yes |
| Paired model-score difference | yes | yes |
| 14 declared summaries after correction | yes | yes |
| Largest standardized effect among the 14 | yes | **no ledger entry** |
| Position-independent detection, 4 read conditions | yes | yes |
| Window-strength separation and threshold margin | yes | **no ledger entry** |
| Length of the strongest window | yes | **no ledger entry** |
| Aligned-detector ordinary null fit | **no ledger entry** | yes |

The four retained figures are generated from Carbon artifacts only, by
`scripts/make_paper_figures.py` with SHA-256 verification. They are not regenerated here, the
GENERator run has no figure of its own, and every figure caption now names Carbon explicitly so no
figure is read as covering both models.
