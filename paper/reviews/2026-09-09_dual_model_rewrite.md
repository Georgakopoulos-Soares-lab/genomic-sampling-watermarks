# Dual-model rewrite on admitted version-one evidence

Date: 2026-09-09
Decision: author instruction to set aside the `synthid.v2.*`-only rule and write the dual-model paper
from existing evidence. Recorded as `docs/research/dual_model_v1_admission_amendment_2026_09_09.md`.

## What changed

`paper/manuscript/source/main.tex` is now a dual-model manuscript on Carbon-500M and
GENERator-v2-eukaryote-1.2b-base. Every GENERator number came from the 17 `synthid.generator.*`
entries already in `evidence/measurements.yaml`. Nothing was rerun, recomputed, or estimated.

- **Abstract, Introduction, Conclusion**: two models, per-model counts, and an explicit statement that
  running one implementation through two models tests portability of the implementation and not
  equivalence of the models.
- **Table 1**: `model` now means either of the two, with `Carbon` and `GENERator` as the fixed short
  names, keeping the one-word-per-idea rule.
- **Methods**: both pinned checkpoints; a note that GENERator is driven through its direct canonical
  token distribution rather than the base-by-base path its released code uses by default; per-model
  generation, sampler check, and scoring; a statement that each model is scored only under itself and
  the two model scores are never compared; and the execution hardware stated factually.
- **Results**: all four subsections now carry both models. Sampler 13/256 and 5/256 against 12.8
  expected, ordinary arms 12 and 14, none surviving correction, all broken controls rejected in each.
  Model score +0.00852 nat/token in Carbon and -0.00564 in GENERator, both intervals covering zero.
  14 measures, none surviving correction, smallest adjusted P 0.85 and 0.73. Detection table split
  into a Carbon block and a GENERator block. GENERator's aligned-detector ordinary null fit added.
- **Discussion**: a paragraph on what two models buy and what they cannot buy.
- **Limitations**: scope restated as two models on one shared cohort; a paragraph on the unequal
  coverage of the two runs; and a paragraph disclosing GPU generation, x86-64 CPU detection, the
  Carbon protocol-hash discrepancy, and the outstanding replication.

## The asymmetry, handled explicitly

The two runs did not record the same things, and the manuscript says so at each point rather than
implying symmetry:

- Carbon only: largest standardized effect among the 14 measures (0.084 s.d.), window-strength
  separation (weakest marked 124.8 against threshold 6.21), edit-by-edit median strengths, and the
  winning window length. The Results text attributes the frame-shift *mechanism* to Carbon and the
  frame-shift *outcome* to both.
- GENERator only: aligned-detector ordinary null fit at four lengths.
- All four figures are Carbon. Every caption now says so. They were not regenerated: the Carbon source
  artifacts are gitignored and absent from this working copy, so `scripts/make_paper_figures.py`
  cannot run here, and no figure was hand-edited.

The mirrored control pattern is reported as it stands, not smoothed: Carbon's single control positive
is an ordinary read, GENERator's is a wrong-key read, and GENERator's disappears after the deletion.

## Ledger and map

- `evidence/measurements.yaml`: only stale scope annotations changed — three `evidence_role` fields
  and one `notes` field that described the GENERator fence. No value, status, artifact, digest,
  interval, or command touched.
- `paper/context/evidence_map.md`: retitled dual-model, with two new tables covering all 17
  `synthid.generator.*` identifiers, an explicit record of which quantities exist for one model only,
  a note that the ledger calls the wrong-key family `other_key_rate` for GENERator and
  `wrong_key_rate` for Carbon while the manuscript uses one word, and rewritten writing boundaries.
- `AGENTS.md`, `CLAUDE.md`, `PROJECT.md`, `paper/AGENTS.md`, `paper/README.md`, `evidence/README.md`:
  updated to point at the amendment, so the repository rules and the manuscript no longer contradict
  each other. All keep the requirement that *new* runs use the M5 path and a new evidence identity.

## Verification

- Every GENERator figure in the prose was checked against the ledger mechanically, by parsing
  `measurements.yaml` and comparing rounded values: sampler counts, both arm means, the paired
  difference, both interval bounds, the P-value, the standardized effect, the smallest adjusted
  P-value, the four null-fit counts and P-values, and all twelve detection cells. All matched.
- `./paper/scripts/build.sh` succeeds. Rebuilt with `--keep-logs`: zero undefined citations and zero
  undefined references. 16 pages.
- `python3 scripts/check_evidence.py` reports no unknown measurement identifiers, so all 17 new map
  entries resolve. It still fails on the same five gitignored Carbon artifacts, unchanged by this
  pass. Note the asymmetry: the GENERator artifacts are present in the repository and the Carbon ones
  are not, so the GENERator half of the paper is currently the more auditable half.
- `python3 -m unittest discover -s tests`: 108 tests, zero failures, 8 documented skips.

## Open, and deliberately not decided here

- Confirmatory M5 Pro replication of both models. This is the reason the paper says "executed once"
  rather than "measured".
- The false-positive rate is still bounded only to 2.87% by 192 prompts, in both models.
- `Data and code availability` still says the keys are published in one place and everything is
  "available from the authors on request" in another. That contradiction predates this pass and is an
  author decision, so it was left alone.
- Whether the four figures should be regenerated to cover both models. That needs the Carbon
  artifacts restored and `scripts/make_paper_figures.py` extended, and GENERator has no retained
  window-strength data to plot, so a matched Figure 3 or 4 is not currently possible.
