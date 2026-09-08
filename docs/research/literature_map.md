# Sources used by the retained study

## SynthID

The method follows the binary tournament construction and repeated-context masking in the public
DeepMind SynthID-Text implementation pinned in `sources.yaml`. The accompanying Nature paper is the
primary source for the non-distortionary construction and its evaluation setting.

## Carbon

Carbon-500M and its tokenizer are pinned in `sources.yaml`. The experiment uses the main checkpoint
and direct categorical sampling over canonical DNA 6-mers. No alternate Carbon branch is part of
the retained results.

## GENERator

The GENERator-v2 1.2B checkpoint, model repository, and exact revisions are pinned in
`sources.yaml`. The retained policy is the direct categorical distribution over its 4,096 canonical
6-mer tokens; the released base-marginal helper (`_BPLogitsProcessor` in the pinned checkpoint's
`modeling_generator.py`) is deliberately not part of the retained result.

GENERator-v2 is a **co-primary paper model** of the rebuilt dual-model study, alongside Carbon-500M.
Its existing version-one measurements are legacy development history on exactly the same footing as
Carbon's, so they inform runtime and blinded power planning and are not confirmatory evidence, and
they must not be inserted into the legacy Carbon-only draft.

## Public DNA

Prompts come from versioned NCBI RefSeq records. Accession versions, coordinates, checksums, and the
deterministic selection rule are documented in
`docs/research/public_prompt_cohort_large_v1.md` and the tracked data manifests.
