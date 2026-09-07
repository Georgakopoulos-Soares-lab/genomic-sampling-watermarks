# Sources used by the retained study

## SynthID

The method follows the binary tournament construction and repeated-context masking in the public
DeepMind SynthID-Text implementation pinned in `sources.yaml`. The accompanying Nature paper is the
primary source for the non-distortionary construction and its evaluation setting.

## Carbon

Carbon-500M and its tokenizer are pinned in `sources.yaml`. The experiment uses the main checkpoint
and direct categorical sampling over canonical DNA 6-mers. No alternate Carbon branch is part of
the retained results.

## GENERator supplementary replication

The GENERator-v2 1.2B checkpoint, model repository, and exact revisions are pinned in
`sources.yaml`. The replication uses the direct categorical distribution over its 4,096 canonical
6-mer tokens. The released base-marginal helper is not part of the retained result. GENERator is
reviewed supplementary evidence and is not part of the current Carbon-only manuscript.

## Public DNA

Prompts come from versioned NCBI RefSeq records. Accession versions, coordinates, checksums, and the
deterministic selection rule are documented in
`docs/research/public_prompt_cohort_large_v1.md` and the tracked data manifests.
