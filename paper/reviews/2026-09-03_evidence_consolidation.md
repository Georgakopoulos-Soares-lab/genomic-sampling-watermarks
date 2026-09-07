# Evidence consolidation review — 2026-09-03

## Decision

The current manuscript remains a Carbon-500M SynthID paper. Its 16 exact measurement identifiers
are now enumerated in `paper/context/evidence_map.md`; no wildcard mapping remains. The manuscript
source was not changed during this review.

The completed GENERator-v2 1.2B run is accepted as reviewed supplementary evidence. Its sampler,
quality, aligned-null-fit, and position-independent detector measurements are in
`evidence/measurements.yaml`, but they are not authorized for insertion into the Carbon manuscript
without a separate scope decision.

## Materials reviewed

- frozen Carbon and GENERator generation/validation protocols;
- both model-specific execution records;
- compact generation, sampler, quality, aligned-detection, and final-detector artifacts;
- the GENERator rare-event validator amendment;
- all 33 ledger measurements and their source hashes; and
- the manuscript abstract, methods, results, discussion, and evidence map.

## Result of review

The Carbon manuscript numbers agree with the reviewed ledger. Both models show no measurable
model-quality loss and 384/384 correct-key detections for clean, substitution, insertion, and
deletion conditions. Carbon has one ordinary positive prompt and zero other-key positive prompts;
GENERator has zero ordinary positive prompts and one other-key positive prompt. Both null results
are compatible with the declared 1% target and neither proves an operational rate below 1%.

The consolidated writing source is `docs/research/manuscript_evidence_packet.md`. It separates
paper-targeted measurements, supplementary evidence, engineering diagnostics, assumptions, and
claims that remain unsupported.

Repository verification passed 108 retained unit tests with four optional upstream-comparison
skips, Ruff, shell-script syntax checks, environment diagnostics, and the expanded evidence audit.
The complete and position-independent GENERator artifact validators both passed. A PDF manuscript
build was attempted but this environment has neither `tectonic` nor `latexmk`; no TeX source was
changed in this consolidation, and the missing engine remains an environment limitation rather
than a successful build claim.

## Open gate

The paper hardware contract still requires replaying the final paper-bound Carbon detector result
on the documented M5 Pro, or an explicit decision revising that contract. Until then, the manuscript
must retain its current Linux-CPU execution limitation.

The audit also found that the Carbon detector summary's frozen protocol hash does not match the
current protocol file. All 4,608 scientific decisions validate before the final protocol-provenance
check. The original result remains immutable, and
`docs/research/carbon_synthid_protocol_provenance_amendment_2026_09_03.md` records the mismatch. The
M5 replay must freeze the current protocol under a new result identity, which will close both open
gates together. The next manuscript revision must add this provenance caveat; the manuscript source
was deliberately not rewritten during this evidence-gathering review.
