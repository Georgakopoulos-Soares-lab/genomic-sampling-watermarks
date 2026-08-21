# Public prompt cohort

## Purpose

`ncbi_refseq_eukaryote_windows_v1` is the first shared real-DNA input set for Carbon and
GENERATOR-v2 integration. It is intentionally small: four eukaryotic model-organism chromosome
records, with three 384-base forward-strand windows per record. It tests whether conclusions drawn
from synthetic DNA survive ordinary genomic context without creating a large dataset framework.

## Frozen sources

| Organism | Accession.version | Assembly | Windows |
|---|---|---|---:|
| *Saccharomyces cerevisiae* S288C | `NC_001133.9` | `GCF_000146045.2` | 3 |
| *Arabidopsis thaliana* Columbia | `NC_003070.9` | `GCF_000001735.4` | 3 |
| *Caenorhabditis elegans* Bristol N2 | `NC_003279.8` | `GCF_000002985.6` | 3 |
| *Drosophila melanogaster* | `NT_033779.5` | `GCF_000001215.4` | 3 |

The source is NCBI RefSeq through the documented [EFetch API](https://www.ncbi.nlm.nih.gov/books/NBK25499/).
NCBI states that it places no restrictions on molecular data reuse, while warning that original
submitters may retain rights in some jurisdictions; this is a reuse-policy statement, not an SPDX
license. See the [NCBI data policy](https://www.ncbi.nlm.nih.gov/home/about/policies/).

Human, patient, controlled-access, ambiguous-base, organelle, and plasmid records are excluded.
The exact accessions, coordinates, update dates, filters, and sequence hashes are frozen in
[`data/public_prompt_cohort.yaml`](../../data/public_prompt_cohort.yaml).

## Deterministic selection

For a record of length `L`, each 384-base window starts at:

```text
floor(position × (L - 384)) + 1
```

where `position` is 0.2, 0.5, or 0.8 and coordinates are one-based and inclusive. For example, the
20% window of `NC_001133.9` is bases 45,967–46,350. A sequence is accepted only when its FASTA
header contains the exact accession.version, it has exactly 384 canonical A/T/C/G bases, and its
SHA-256 matches the tracked value.

Build once online and reproduce from the cache offline:

```bash
uv run python scripts/build_public_prompt_cohort.py
uv run python scripts/build_public_prompt_cohort.py --offline
```

Both builds on 2026-08-21 produced 12 prompts and cohort SHA-256
`10495c987950b1c96a492ca39509747bdaa0dd43083cf20758c6210df6f84f9e`.
FASTA and derived prompt files remain ignored.

## Cross-model engineering diagnostics

Pinned Carbon-500M `C_tok` revision `9796b752...` processed every prompt on the 48 GiB M5 Pro.
The complete 4,096-way next-token distributions were compared between MPS `bfloat16` and CPU
`float32`.

| Diagnostic | Result |
|---|---:|
| Contexts | 12 |
| Median capacity estimate | 0.15565 bits/base |
| Context range | 0.08653–0.15978 bits/base |
| CPU/MPS top-token agreement | 12/12 |
| Mean CPU/MPS total-variation distance | 0.00745 |
| MPS inference after load | 35.9 states/s |
| MPS driver allocation | 1.08 GiB |

This result shows two useful engineering facts: the laptop has ample room for the primary Carbon
path, and real contexts can produce meaningfully different capacity. The lowest-capacity window
was `arabidopsis_q50`; it had a 0.286 top-token probability, so a keyed half-vocabulary partition
could receive much less balanced probability mass than in flatter states.

The same prompts were then evaluated with pinned GENERator-v2 revision `c41b0018...`. The model's
MPS `bfloat16` path failed parity and was rejected: `G_tok` retained the same top token in only 4/12
contexts and had mean total-variation distance 0.238 from CPU `float32`. Repeating with `float32` on
both devices passed the engineering gate.

| Policy | MPS dtype | Median information/base | Range | Top-token agreement | Mean TV | MPS driver memory |
|---|---|---:|---:|---:|---:|---:|
| `C_tok` | `bfloat16` | 0.15565 | 0.08653–0.15978 | 12/12 | 0.00745 | 1.08 GiB |
| `G_tok` | `float32` | 0.15842 | 0.08810–0.16109 | 12/12 | 0.0000206 | 5.03 GiB |
| `G_bp` | `float32` | 0.15979 | 0.10228–0.16291 | 12/12 | 0.00000266 | 5.03 GiB |

`G_bp` is slightly flatter on this cohort, especially for `arabidopsis_q50`, but 12 contexts are
too few for a general policy ranking.

These numbers are **not paper evidence**. The cohort is small, the 16 partitions per state use
public non-secret fixture material, and no sampling uncertainty or chromosome-level independence
claim is attached. Detailed reports stay in ignored `outputs/`; `evidence/measurements.yaml`
remains empty. This v1 cohort became the initial 1,536-state-per-policy E2 pilot described in
[`e2_capacity_protocol.md`](e2_capacity_protocol.md), with expansion permitted only by the frozen
prompt-cluster trigger.

## Output-blind v2 expansion

The full v1 sequential `G_tok` run crossed both frozen stability thresholds because
`arabidopsis_q50` remained much lower-capacity than the other prompt clusters. The prompt was not
removed. Before inspecting any replacement model output, v2 retained all 12 windows and added one
different chromosome for each existing organism, using the unchanged 20%, 50%, and 80% coordinate
rule.

| Organism | Added accession.version | Added chromosome | Added windows |
|---|---|---:|---:|
| *S. cerevisiae* | `NC_001134.8` | II | 3 |
| *A. thaliana* | `NC_003071.7` | 2 | 3 |
| *C. elegans* | `NC_003280.10` | II | 3 |
| *D. melanogaster* | `NT_037436.4` | 3L | 3 |

The exact 24-prompt manifest is `data/public_prompt_cohort_v2.yaml`. Its offline build produces
cohort SHA-256 `1bb980d4be5dad5769e9ccc18a78133d7638e0bf78ebd2df2dcfdcf0d2a254ed`.
All three policies pass the final expansion rule on this cohort. The v1-to-v2 history and full
engineering summaries are recorded in [`e2_capacity_protocol.md`](e2_capacity_protocol.md).
