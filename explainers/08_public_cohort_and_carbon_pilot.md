# 08 — The first real DNA prompt cohort

## Why synthetic DNA was not enough

Our first Carbon pilot used simple repeated and pseudorandom sequences. Those are excellent for
finding broken code, but nature does not distribute DNA like either extreme. A real genomic region
can make the model very uncertain or strongly favor one next 6-mer, and that changes the available
watermark capacity.

So we created a small reproducible cohort: 12 public DNA windows from four model organisms. The
same 12 prompts were sent to Carbon and the eukaryotic GENERator checkpoint.

## What “reproducible cohort” means

Think of an NCBI accession.version as a book plus its edition number:

```text
NC_001133.9   = exact chromosome record, exact edition
45967–46350   = exact pages to read
SHA-256       = fingerprint proving the text did not change
```

The manifest records all three. The script downloads only that window and checks:

1. the response names the expected accession.version;
2. the window is exactly 384 bases;
3. every character is A, T, C, or G;
4. its fingerprint equals the frozen fingerprint.

The actual DNA stays in ignored `data/raw/` and `data/processed/` directories. We commit the recipe
and fingerprints, not a new copy of the dataset.

## What happened with Carbon

Carbon produced a probability for each of the 4,096 possible next 6-mers after every prompt. For
most windows, the estimated watermark capacity was around 0.15–0.16 bit per DNA base. One window,
`arabidopsis_q50`, fell to about 0.087 bit/base.

Why? Its most likely next token alone had about 28.6% probability. Imagine dividing tokens into two
keyed groups. If one very heavy token lands in a group, the two groups can have quite unequal total
probability. Maximal coupling then has less room to encode a fair hidden bit while preserving the
model's original distribution.

This is the useful lesson:

```text
flatter next-token probabilities  → partitions tend to balance → more watermark capacity
one or more dominant tokens       → partitions may skew       → less watermark capacity
```

It does **not** mean Arabidopsis generally has low capacity. We measured only three windows from
one chromosome, and only one was low. It also does not yet prove a paper result because the pilot
used public test partition material rather than runtime secret keys.

## Did the MacBook handle it?

Yes. The pinned Carbon-500M model used about 1.08 GiB of MPS driver memory and evaluated about 35.9
states per second after loading. CPU and MPS selected the same most likely token on all 12 prompts.
Their full probability vectors were close but not identical because the run compared CPU
`float32` with MPS `bfloat16`.

The practical consequence is reassuring: Carbon-500M is nowhere near the 48 GiB memory ceiling,
so this research path does not need a Brev node or remote GPU.

## What happened next

The pinned GENERator-v2 eukaryote 1.2B checkpoint has now run the same 12 prompts through both
`G_tok` and the released base-product policy `G_bp`. Both pass the CPU/MPS gate in `float32`; its
MPS `bfloat16` path does not and was rejected. At that stage, the next decision was whether 12
prompts were enough for protocol design or whether the paper cohort needed a modest expansion. The
later sequential test did trigger a controlled expansion to 24 prompts;
[explainer 11](11_first_full_capacity_result.md) shows what happened.

Continue to [GENERATOR policies and numerical precision](09_generator_policies_and_precision.md),
or read the formal [cohort record](../docs/research/public_prompt_cohort.md).
