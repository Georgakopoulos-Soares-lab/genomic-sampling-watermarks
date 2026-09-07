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

The completed GENERator-v2 1.2B replication is reviewed evidence but stays out of this manuscript
until its scope is explicitly expanded. The planned dual-model rebuild is described in the
[dual-model rebuild plan](../docs/research/dual_model_synthid_paper_rebuild_plan.md) and will use a
fresh `synthid.v2.*` evidence namespace.

## Figures

`figures/*.pdf` are built by `../scripts/make_paper_figures.py`. The script verifies the SHA-256 of
every source artifact before plotting and writes each plotted value, with figure digests, to
`figures/figure_values.json`. Regenerate with:

```bash
python3 scripts/make_paper_figures.py
```

Generated experiment outputs are not tracked in the repository, so the run directories the script
reads must be present locally.

## Build

```bash
./scripts/build.sh
```

The script uses `tectonic` if present and otherwise `latexmk`.
