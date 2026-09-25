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


---

# Background literature map

Added 2026-09-22 from the Lane 2 deep-research pass (L2-12, L2-13, L2-14, L2-16). Everything below
was verified against a publisher record, an arXiv listing, a model card, or a tokenizer config.
Claims are labelled by what the source actually establishes. Full working notes, including findings
not used in the manuscript, are in the session scratchpad and summarized here.

## Desynchronization in text watermarking, and why it does not transfer

The verdict of the sweep is **inapplicable, structurally** — not "weaker". Every text mechanism that
claims indel robustness relies on one of two things surviving: a large fraction of unchanged token
identities, or a representation defined above the tokenizer. Non-overlapping k-mer tokenization
destroys the first globally from a single nucleotide indel, and offers no natural instance of the
second.

| Mechanism | Source | What it assumes | Why it fails under permanent frameshift |
|---|---|---|---|
| Edit-distance alignment to a key sequence | `kuditipudi2024robust` | a surviving token sequence to align | there is none; the whole suffix re-tokenizes |
| Span search with calibrated FPR (WinMax) | `kirchenbauer2024reliability` | token identities stable within the span | identities change, not just positions |
| Context-free green lists | `zhao2024provable` | nothing about context — the strongest case | removes key desync entirely and still fails, because a shifted six-mer is a different vocabulary item with an independent mark bit |
| Indexed pseudorandom codes | `golowich2024edit` | ability to index the stream | conceptual transfer only; we cannot insert index symbols into DNA |
| Semantic/embedding-level units | `hou2024semstamp` | an encoder at verification, and natural segmentation | we verify without model access, and DNA has no intrinsic segmentation |
| Drift as a latent variable (HMM forward-backward) | `davey2001reliable` | the decoder controls the encoding | a sampling watermark has no inner code; but this is the principled alternative to enumerating offsets |

`zhao2024provable` is the load-bearing citation: it isolates the failure mode. The paper's §2.2
argument rests on it rather than on a general appeal to novelty.

## Tokenization in genomic language models

| Model | Scheme | k | Stated motivation |
|---|---|---|---|
| Evo, Evo 2 | byte-level single-nucleotide | 1 | near-linear scaling of compute and memory with context |
| HyenaDNA | single-nucleotide | 1 | k-mers lose the resolution at which SNPs act |
| Caduceus | character level | 1 | k-mer tokenization means minor input changes produce drastically different tokenizations |
| DNABERT | **overlapping** k-mers, stride 1 | 3--6 | richer context per base |
| Nucleotide Transformer | non-overlapping k-mers | 6 | trade-off between sequence length and embedding size |
| GENERator | non-overlapping k-mers | 6 | k-mer outperforms BPE for next-token pretraining |
| DNABERT-2, METAGENE-1 | learned BPE | n/a | computational efficiency without k-mer sample inefficiency |

Two findings worth keeping in view:

- **GENERator randomizes the tokenization start offset between 0 and 5 for each training sample.**
  One of this study's two models therefore sees all six phases during training. This is a training
  augmentation, not a verification mechanism, and it does not reduce the verifier's search — but it
  is the closest thing in the literature to an acknowledgement that phase is a real problem.
- **The phase argument does not apply to every multi-mer model.** DNABERT's k-mers are overlapping,
  so every frame is present at once and there is no phase to choose; its failure mode is masked-LM
  information leakage. For BPE models the ambiguity is not a mod-k phase at all but unbounded
  re-segmentation, which a verifier cannot resolve by trying k offsets. The manuscript's claim is
  therefore specific to fixed non-overlapping k-mer tokenization, and is written that way.

## Standardized biological benchmarks

The decisive finding: **no standardized public benchmark, as of September 2026, evaluates de novo
generated sequences.** BEND, GenBench, GENEB, Genomic Benchmarks, and the Nucleotide Transformer task
set are probe-or-finetune protocols — a metric exists only because a held-out label tied to a genome
coordinate exists. A generated sequence carries neither, so these suites are unusable rather than
merely awkward for evaluating watermarked generations.

Two partial exceptions, neither sufficient: DART-Eval's motif-footprinting task compares likelihood
on motif-bearing versus shuffled sequence and needs no coordinates, but motif presence is itself the
ground truth; Nullsettes scores engineered, evolutionarily implausible sequences without genome
annotation, but requires a designed cassette paired with a designated loss-of-function mutation.

Compute cost is **not reported** for any of them. Licences verified from repository files: BEND
BSD 3-Clause, GenBench Apache-2.0, Genomic Benchmarks Apache-2.0; DART-Eval has no retrievable
LICENSE file, so no licence should be asserted for it.

This is why the manuscript's Limitations paragraph no longer calls a benchmark study "the natural
next step" without qualification. It states that the suites do not transfer, and that closing the
gap needs either a paired design or an assay.

## Do not cite without further checking

- `GenBench` is an arXiv preprint. The NeurIPS 2024 record is a **workshop** poster under a different
  title, "GeneGench", with a longer author list. Do not cite it as a NeurIPS main-track paper.
- Schwartzman, Gavrilov and Adler, "Peak Detection as Multiple Testing" (arXiv:1008.1924), supports
  the claim that a fixed candidate search costs only a constant in the null threshold. The journal
  version was not confirmed; not cited in the manuscript for that reason.
- DNABERT-2's BPE vocabulary size is not exposed in its published tokenizer config.
- No primary source was found for the common secondary claim that BPE is more indel-robust than
  k-mer tokenization. It appears only in summaries.
- `Pattern-mark` is Chen et al., "A Watermark for Order-Agnostic Language Models" (arXiv:2410.13805),
  evaluated on ProteinMPNN and CMLM. It is unrelated to `zhang2025securing` (DNAMark/CentralMark),
  and FoldMark is a third, separate work. The three must not be conflated.

## A note on bibliographic verification

Two author lists supplied from memory during this cycle were wrong, and both were caught only by
checking the publisher record: `dathathri2024scalable` carried two people who are not authors of that
paper, and a draft `hou2024semstamp` entry listed an author who is not on the ACL Anthology page while
omitting three who are. Every entry added in this pass was checked against a primary record. Entries
predating this pass have not all been checked.
