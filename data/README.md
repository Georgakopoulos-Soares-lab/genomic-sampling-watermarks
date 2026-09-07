# Data policy

Only the 256-prompt public RefSeq cohort used by the Carbon SynthID validation and the matched
GENERator replication is retained. The tracked files contain accession versions, coordinates,
selection rules, and checksums, not genomic sequences.

- `public_prompt_cohort_large_v1_sources.yaml` declares the public source records and selection.
- `public_prompt_cohort_large_v1.yaml` is the frozen checksum-complete manifest.
- `docs/research/public_prompt_cohort_large_v1.md` explains construction and exclusions.

Downloaded records stay under ignored `data/raw/`; derived prompt JSONL stays under ignored
`data/processed/`. Patient, private, controlled-access, human, organelle, plasmid, and
ambiguous-base inputs are excluded.

An offline rebuild from already fetched public records is:

```bash
uv run python scripts/build_large_public_prompt_cohort.py \
  --manifest data/public_prompt_cohort_large_v1.yaml --offline
```

The frozen prompt content digest is
`8f7f7bba52f26837cdef5f17b542e01ab61eb1ddf7735d43dcd6f7b8d0986308`.
