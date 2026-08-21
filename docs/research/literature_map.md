# Literature map

Audit date: 2026-08-20. Prefer the linked primary paper, proceedings page, or official repository over secondary summaries.

## Genomic language models

| Source | Role in this paper |
|---|---|
| [Carbon: Decoding the Language of Life](https://www.biorxiv.org/content/10.64898/2026.05.22.727119v1) and [official code](https://github.com/huggingface/carbon) | Primary model family; 6-mer tokenizer, FNS training objective, and evaluation suite. |
| [Carbon-500M model card](https://huggingface.co/HuggingFaceBio/Carbon-500M) | Primary local checkpoint and exact released interface. |
| [GENERator](https://arxiv.org/abs/2502.07272) and [official code](https://github.com/GenerTeam/GENERator) | Predecessor model and tokenizer context. |
| [GENERator-v2](https://www.biorxiv.org/content/10.64898/2026.01.27.702015v2) | Primary 1.2B model and scientific context. |
| [GENERator-v2 1.2B checkpoint](https://huggingface.co/GenerTeam/GENERator-v2-eukaryote-1.2b-base/tree/main) | Released tokenizer and base-marginal generation implementation. |

## Core watermark constructions

| Source | Status | Role |
|---|---|---|
| [Robust Distortion-free Watermarks for Language Models](https://arxiv.org/abs/2307.15593), [official code](https://github.com/jthickstun/watermark) | Core baseline | ITS and exponential/Gumbel sampling, permutation testing, and edit-aware alignment. |
| [Unbiased Watermark for Large Language Models](https://openreview.net/pdf?id=uWVC5FVidc) | Core baseline | Exact-in-expectation reweighting and likelihood-aware/agnostic detector framing. |
| [DiPmark](https://proceedings.mlr.press/v235/wu24h.html), [official code](https://github.com/yihwu/DiPmark) | Secondary baseline | Distribution-preserving reweighting with a strength parameter. Reimplement from the paper only after license review; the audited repository exposes no license file. |
| [Undetectable Watermarks for Language Models](https://proceedings.mlr.press/v247/christ24a.html) | Theory comparator | Stronger multi-query security definitions; highlights the distinction between one-output marginal preservation and many-output undetectability. |
| [Provable Robust Watermarking for AI-Generated Text](https://openreview.net/pdf?id=SsmT8aO45L) | Distortion-allowing comparator | Fixed-group watermark and edit robustness; useful as a non-exact-marginal reference. |

## Genomic and biological-sequence watermarking

| Source | Role |
|---|---|
| [Protein watermarking](https://pmc.ncbi.nlm.nih.gov/articles/PMC12279293/) and [code](https://github.com/poseidonchan/ProteinWatermark) | Closest sampling-time biological-sequence precedent; amino-acid rather than DNA channel. |
| [DNAMark and CentralMark](https://proceedings.neurips.cc/paper_files/paper/2025/file/c85aaa3996e1dbc35646a17893a54495-Paper-Conference.pdf) | Direct DNA-watermark related work; generation and codon/central-dogma mechanisms differ from exact 6-mer sampling. |

## Coding and synchronization

| Source | Status | Role |
|---|---|---|
| [Pseudorandom Error-Correcting Codes](https://eprint.iacr.org/2024/235.pdf) | Later theory layer | Security definition and code-layer target after channel measurement. |
| [Pseudorandom Error-Correcting Codes with an Efficient Indexing Procedure](https://proceedings.neurips.cc/paper_files/paper/2024/hash/24c53bfa5b53fc2cf05644f5a7a26bb0-Abstract-Conference.html) | Later theory layer | Efficient indexing and robustness context. |
| [Synchronization Strings](https://arxiv.org/abs/1704.00807) | Later theory layer | Converts insertion/deletion structure to symbol corruption in a coding construction; not an initial dependency. |

## Attacks and limits

| Source | Required evidence it motivates |
|---|---|
| [Toward Breaking Watermarks in Distortion-Free Large Language Models](https://openreview.net/pdf?id=sZOCUHfeUA) | Many-sample key-reuse, removal, and spoofing analysis. |
| [Adaptive Attacks on Watermarking Language Models](https://proceedings.mlr.press/v267/diaa25a.html) | Detector-query attack budget and adaptive removal curve. |
| [Watermarks in the Sand](https://proceedings.mlr.press/v235/zhang24o.html) | Narrow claims and explicit attacker/resource assumptions. |
| [Detecting Spoofed LLM Watermarks](https://proceedings.mlr.press/v267/gloaguen25a.html) | Attribution versus detection and spoofing discussion. |

## Local execution references

- [PyTorch MPS backend](https://docs.pytorch.org/docs/stable/notes/mps.html): official Apple GPU backend.
- [Transformers on Apple Silicon](https://huggingface.co/docs/transformers/perf_train_special): unified-memory constraints, MPS loading, mixed precision, and CPU fallback.

## Implementation policy

Reference repositories are audited, not vendored. The Kuditipudi and DiPmark repositories did not expose a license file in the audited checkout, so no code is copied from them. Implementations in this repository are written from the papers and are cross-checked with independent tests. ProteinWatermark is licensed, but its code remains an external comparator because the protein interface and threat model differ.

