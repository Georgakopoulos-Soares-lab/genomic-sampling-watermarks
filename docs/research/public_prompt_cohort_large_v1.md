# Large public RefSeq prompt cohort

## Frozen cohort

`ncbi_refseq_eukaryote_windows_large_v1` contains 256 public, forward-strand,
384-base canonical DNA prompts. The windows come from 16 accession-versioned RefSeq chromosome
records across eight public model organisms:

- *Saccharomyces cerevisiae* S288C;
- *Arabidopsis thaliana* Columbia;
- *Caenorhabditis elegans* Bristol N2;
- *Drosophila melanogaster*;
- *Schizosaccharomyces pombe* 972h-;
- *Oryza sativa* Japonica Group cultivar Nipponbare;
- *Danio rerio* Tuebingen; and
- *Mus musculus* C57BL/6J.

Human, patient, controlled-access, organelle, plasmid, and ambiguous-base spans are excluded. NCBI
is the public source through EFetch. Its molecular-data reuse statement is recorded as a usage
policy, not represented as an SPDX license.

The tracked source specification is
[`data/public_prompt_cohort_large_v1_sources.yaml`](../../data/public_prompt_cohort_large_v1_sources.yaml).
The checksum-complete frozen manifest is
[`data/public_prompt_cohort_large_v1.yaml`](../../data/public_prompt_cohort_large_v1.yaml).

## Output-blind deterministic selection

Each chromosome record is divided into 16 non-overlapping coordinate segments. Within segment `s`,
the builder hashes the frozen selection label, accession.version, segment index, and retry index.
The first 64 digest bits are mapped by integer remainder to a start for which a complete 3,072-base
span fits inside that segment. The first canonical span is accepted. Its first 384 bases form the
model prompt; the complete 3,072-base span is retained as the same prompt's public-RefSeq detector
null so that the public null can be evaluated at every declared generation length.

Canonical filtering is the only retry condition. It was applied before any Carbon or GENERator
generation, quality, or detector result existed. Three of 256 selected spans required one retry
because attempt zero contained ambiguous bases. No prompt was removed or moved after model
inspection.

The 16 segments per record ensure broad coordinate coverage. Accepted 3,072-base spans do not
overlap within an accession. Prompt identity remains the 384-base window; the longer public span is
not supplied to either model.

## Frozen validation result

The initial public fetch and an immediate network-free rebuild both produced:

| Field | Frozen value |
|---|---:|
| Prompts | 256 |
| Accession-version records | 16 |
| Organisms | 8 |
| Prompt length | 384 bases |
| Public-null span length | 3,072 bases |
| Cohort content SHA-256 | `8f7f7bba52f26837cdef5f17b542e01ab61eb1ddf7735d43dcd6f7b8d0986308` |
| Public-null cohort SHA-256 | `0fe45bb2b1ebf0ef2eb16379eb8068c0fb04ece48e1c65abe439d0424a3b3bb5` |
| Frozen manifest SHA-256 | `99ce4a911897e110c04b5f47d310c810e30169bdfc9381537eb45eb21611e302` |

The builder validates 256 unique case IDs, canonical 384-base prompts, unique prompt and public-null
sequences, every sequence checksum, exact accession.version headers, segment containment, and no
within-accession source-span overlap.

## Rebuild commands

The completed manifest is never overwritten. Initial freezing was:

```bash
uv run python scripts/build_large_public_prompt_cohort.py \
  --freeze-manifest /tmp/public_prompt_cohort_large_v1.yaml
```

The ordinary build may fetch a missing accepted span at its already-frozen coordinates. The required
offline verification is:

```bash
uv run python scripts/build_large_public_prompt_cohort.py \
  --manifest data/public_prompt_cohort_large_v1.yaml --offline
```

FASTA payloads and the derived JSONL remain under ignored `data/raw/` and `data/processed/` paths.
