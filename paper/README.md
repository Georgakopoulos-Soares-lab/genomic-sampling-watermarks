# Paper workspace

`manuscript/source/main.tex` is the Carbon-500M SynthID manuscript. It reports the sampler check,
the sequence-quality comparison, and the position-independent detection result for one watermark
(`synthid-tournament-v1`) and one verifier
(`synthid-position-independent-detector-v1`). Every printed number resolves to an identifier in
[`context/evidence_map.md`](context/evidence_map.md) and from there to
[`../evidence/measurements.yaml`](../evidence/measurements.yaml).

The manuscript uses one word and one symbol per idea; the list is Table 1 of the paper itself. Any
edit that introduces a synonym for `read`, `window`, `mark`, `ordinary`, `draw`, or a symbol already
in that table should be rejected.

The manuscript is not submission-ready. Two execution gates remain open. They are deliberately not
printed in the manuscript, which states only the scientific scope limit that follows from them, and
they are tracked here and in `context/evidence_map.md`:

1. the detection run was executed on Linux CPU and must be replayed on the documented Apple M5 Pro
   under the repository's hardware contract; and
2. the protocol file recorded inside the stored detection result does not match the bytes of the
   retained protocol document, as recorded in
   `../docs/research/carbon_synthid_protocol_provenance_amendment_2026_09_03.md`.

GENERator-v2 1.2B is a co-primary model of this manuscript. Its completed version-one replication
was admitted alongside Carbon's by
[the dual-model admission amendment](../docs/research/dual_model_v1_admission_amendment_2026_09_09.md),
and both gates above are now disclosed in the manuscript's Limitations section rather than held only
here. The two runs are unequal in coverage: window strengths, per-measure effect sizes, and winning
window lengths exist for Carbon only, the aligned-detector null fit for GENERator only, and all four
figures are Carbon. Confirmatory replication on the documented M5 Pro path, with a fresh cohort and a
new evidence namespace, is still the intended next step and is described in the
[dual-model rebuild plan](../docs/research/dual_model_synthid_paper_rebuild_plan.md).

## Figures

`figures/*.pdf` are built by `../scripts/make_paper_figures.py`. The script verifies the SHA-256 of
every source artifact before plotting and writes each plotted value, with figure digests, to
`figures/figure_values.json`. Regenerate with:

```bash
# from the repository root
python3 scripts/make_paper_figures.py
```

Generated experiment outputs are not tracked in the repository, so the run directories the script
reads must be present locally.

## Build

```bash
./scripts/build.sh
```

The script uses `tectonic` if present and otherwise `latexmk`.
