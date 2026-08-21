# 02 — How genomic models generate DNA

## DNA becomes tokens

These models do not choose one nucleotide at a time in their basic vocabulary. They represent DNA
using fixed blocks of six bases, called **6-mers**.

For example:

```text
DNA:     ATCGGCAAAAAATTTTTT
6-mers:  ATCGGC | AAAAAA | TTTTTT
```

Each position can contain `A`, `T`, `C`, or `G`. A 6-mer vocabulary therefore contains:

```text
4 × 4 × 4 × 4 × 4 × 4 = 4,096 canonical 6-mers
```

`AAAAAA`, `ATCGGC`, and `GGGGGG` are canonical. A block containing `N` is not canonical for this
project.

## Generation is repeated probability prediction

Given the existing context, the model produces one score for every possible next token. We mask to
the 4,096 canonical DNA tokens and turn their scores into probabilities.

A simplified step looks like this:

```text
context: ATCGGC AAAAAA

model's next-block probabilities:
  TTTTTT  0.34
  ATCGGC  0.22
  AAAAAA  0.18
  ...     0.26 across the other 4,093 blocks
```

The sampler chooses one block. That block is appended to the context, and the model computes the
next distribution. Repeating this process creates a longer sequence.

The watermark operates at the **sampling step**. It does not retrain or modify the model weights.

## The starting phase matters

The same DNA string can be split into 6-mers in six ways, depending on where tokenization starts.

```text
phase 0: ATCGGC | AAAAAA | TTTTTT
phase 1:  TCGGCA | AAAAAT | TTTTT...
phase 2:   CGGCAA | AAAATT | TTTT...
```

A crop of one base changes phase 0 into phase 1. An insertion or deletion can shift every block
after the edit. This is a central difficulty for detection.

The repository never silently trims a GENERator context to make it divisible by six. A
misaligned context raises an error, because silent trimming would change the experiment.

## Carbon and GENERator frame DNA differently

The adapters create the model-specific prompt:

```text
Carbon:       <dna>ATCGGCAAAAAA
GENERATOR:    <s>ATCGGCAAAAAA
```

Carbon has a hybrid text-and-DNA vocabulary. Its dedicated DNA IDs must be read from its DNA
mapping, because a string such as `CCCCCC` can also exist in the text vocabulary with a different
ID.

GENERATOR has 32 special tokens followed by the 4,096 canonical 6-mers.

Our real tokenizer audits found:

| Model tokenizer | Canonical IDs | Result |
|---|---:|---|
| Carbon main and `fns` revisions | 151,672–155,767 | 4,096 unique, contiguous IDs |
| GENERator-v2 1.2B | 32–4,127 | 4,096 unique, contiguous IDs |

All audited IDs also convert back to the expected 6-mer. The audits passed again with network
access disabled, demonstrating that the recorded revisions are sufficient for the tokenizer step.

## Why the MacBook can run the required path

The primary checkpoints are Carbon-500M and GENERator-v2 1.2B. Both have completed full sequential
capacity runs on this machine. Carbon processed about 42 states/s in the final run. GENERator used
about 5 GiB of MPS driver memory and processed about 14 states/s in `float32`. The implementation
chooses Apple MPS first and falls back to CPU.

No required path uses CUDA, a cluster, Brev, or distributed inference. Carbon-3B is optional;
Carbon-8B is excluded from the required study.

Next: [How the watermark works](03_how_the_watermark_works.md).
