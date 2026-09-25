# Paper workspace

`manuscript/source/main.tex` is the dual-model Carbon-500M and GENERator-v2 1.2B SynthID
manuscript. It reports sampler validation, sequence-quality proxies, and position-independent
detection for one watermark (`synthid-tournament-v1`) and one verifier
(`synthid-position-independent-detector-v1`). Every printed number resolves to an identifier in
[`context/evidence_map.md`](context/evidence_map.md) and from there to
[`../evidence/measurements.yaml`](../evidence/measurements.yaml).

The manuscript uses one word and one symbol per idea; the list is Table 1 of the paper itself. Any
edit that introduces a synonym for `read`, `window`, `mark`, `ordinary`, `draw`, or a symbol already
in that table should be rejected.

Version-one Carbon and GENERator evidence is admitted for the current manuscript by the
[dual-model admission amendment](../docs/research/dual_model_v1_admission_amendment_2026_09_09.md)
and its [September 11 panel-analysis extension](../docs/research/generator_v1_analysis_amendment_2026_09_11.md).
The execution caveats are disclosed in the manuscript's Limitations section and tracked in
`context/evidence_map.md`:

1. generation ran on GPU hardware and detection on x86-64 CPUs, with one execution per model;
2. the Carbon protocol file recorded inside the stored detection result does not match the bytes of the
   retained protocol document, as recorded in
   `../docs/research/carbon_synthid_protocol_provenance_amendment_2026_09_03.md`.

Each model contributes one execution, so confirmatory replication remains outstanding. The September
11 derivation supplies paired GENERator panels for Figures 2--4; the aligned-detector ordinary-null
fit remains specific to GENERator. Confirmatory replication in a documented execution environment,
with a fresh cohort and a new evidence namespace, is still the intended next step and is described in the
[dual-model rebuild plan](../docs/research/dual_model_synthid_paper_rebuild_plan.md).

## Figures

`figures/*.pdf` are built by `../scripts/make_paper_figures.py`. Figures 2--4 pair Carbon panels
`a,b` with GENERator panels `c,d`. The script verifies the SHA-256 of every source artifact before
plotting and writes each plotted value, with figure digests, to `figures/figure_values.json`.
Regenerate with:

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
