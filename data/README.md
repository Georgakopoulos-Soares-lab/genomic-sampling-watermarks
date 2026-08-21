# Data policy

No dataset is committed to this repository. Use only public, benign genomic cohorts with documented license, revision, checksum, and preprocessing. Keep downloads under ignored `data/raw/` and derived material under ignored `data/processed/`.

Do not use patient, private, controlled-access, or otherwise sensitive genomic data. A small
provenance record must capture source, revision, license, checksum, and filtering without embedding
sequences in it.

The first prompt cohort is specified in `public_prompt_cohort.yaml`. Build or verify it with:

```bash
uv run python scripts/build_public_prompt_cohort.py
uv run python scripts/build_public_prompt_cohort.py --offline
```

The tracked manifest contains accessions, coordinates, usage-policy links, and sequence checksums.
The downloaded FASTA files and derived JSONL remain under ignored `data/raw/` and `data/processed/`.

The expected cohort digest is
`10495c987950b1c96a492ca39509747bdaa0dd43083cf20758c6210df6f84f9e`. An online build and a
network-free rebuild on 2026-08-21 produced that same digest for all 12 prompts.
