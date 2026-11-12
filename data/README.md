# Data policy

Two public RefSeq prompt cohorts are retained. The tracked files contain accession versions,
coordinates, selection rules, and checksums, not genomic sequences.

| Cohort | Prompts | Files | Description |
|---|---:|---|---|
| Development, `ncbi_refseq_eukaryote_windows_large_v1` | 256 | `public_prompt_cohort_large_v1_sources.yaml`, `public_prompt_cohort_large_v1.yaml` | `docs/research/public_prompt_cohort_large_v1.md` |
| Detection, `ncbi_refseq_eukaryote_windows_fpr_v2_1608` | 1,608 | `public_prompt_cohort_fpr_v2_sources.yaml`, `public_prompt_cohort_fpr_v2_1608.yaml` | `docs/research/synthid_v2_fpr_scaling_protocol_2026_09_21.md` |

Downloaded records stay under ignored `data/raw/`; derived prompt JSONL stays under ignored
`data/processed/`. Patient, private, controlled-access, human, organelle, plasmid, and
ambiguous-base inputs are excluded.

Rebuild commands. The first runs offline from already fetched records; the second is the build
command recorded in the ledger for the detection cohort:

```bash
uv run python scripts/build_large_public_prompt_cohort.py \
  --manifest data/public_prompt_cohort_large_v1.yaml --offline
python3 scripts/build_large_public_prompt_cohort.py \
  --source-spec data/public_prompt_cohort_fpr_v2_sources.yaml \
  --freeze-manifest data/public_prompt_cohort_fpr_v2_1608.yaml --raw-root data/raw
```

Content digests: development
`8f7f7bba52f26837cdef5f17b542e01ab61eb1ddf7735d43dcd6f7b8d0986308`, detection
`f6075a85bc056f5159952031618c544fb3a82864ed9029c913e7f5a7d03c5dc5`.
