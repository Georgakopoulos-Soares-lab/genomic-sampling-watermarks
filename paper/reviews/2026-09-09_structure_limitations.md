# Manuscript structure alignment: metric-named Results and a standalone Limitations section

Date: 2026-09-09
Scope: `paper/manuscript/source/main.tex` structure only. No number, evidence tag, scope word, claim
strength, table value, or figure changed.

## Reason

Co-author request for the section skeleton Abstract, Introduction, Background, Methods, Results
(recall, accuracy), Discussion, Limitations. The draft already carried Abstract, Introduction,
Background, Methods, Results, Discussion, Conclusion. Two gaps were structural: limitations were
prose inside Discussion with no header, and Results subsections were narrative claims that never
named the reported quantities.

## Changes

1. Results subsections renamed to lead with the measured quantity, keeping the existing claim as the
   second clause: sampler fidelity, sequence quality, recall and false-positive rate, edit
   robustness.
2. The detection paragraph now names the metrics it already reported: recall of 100% for
   `synthid.detector.*.correct_key_rate` (384/384) and a false-positive rate of 0.26% for
   `synthid.detector.clean.ordinary_rate` (1/384). Both figures are the admitted ledger values, not
   new derivations.
3. One sentence added stating that recall and the two false-positive rates are reported separately
   rather than as a pooled accuracy, because the marked, ordinary, and wrong-key arm sizes are a
   cohort design choice and a pooled figure would track that choice rather than the verifier. No
   pooled accuracy is reported.
4. New `\section{Limitations}` between Discussion and Conclusion, carrying the previously embedded
   scope, false-positive-resolution, key-secrecy, and biological-function paragraphs. Wording is
   unchanged except for the dropped in-paragraph lead-in that the header now supplies, and the split
   of one long paragraph into three at existing sentence boundaries.
5. The complementary-work comparison to `zhang2025securing` stayed in Discussion; only the
   scope-and-replication sentences moved to Limitations.

## Verification

- `./paper/scripts/build.sh` succeeds; remaining warnings are pre-existing underfull hboxes in
  `main.bbl`.
- `python3 scripts/check_evidence.py` reports five missing Carbon version-one artifacts. This is
  pre-existing and unrelated: `/outputs/*` is gitignored except the GENERator directories, and those
  Carbon result files are not present in this working copy.

## Still outstanding

The co-author request also asks Methods to describe adapting SynthID to both models. The manuscript
remains Carbon-only, no `synthid.v2.*` measurement exists in `evidence/measurements.yaml`, and
`paper/AGENTS.md` forbids reusing version-one numbers in the rebuilt paper. That gap needs either
the dual-model M5 runs in `docs/research/dual_model_synthid_paper_rebuild_plan.md` or an explicit
descope decision. It is not addressable by editing prose.
