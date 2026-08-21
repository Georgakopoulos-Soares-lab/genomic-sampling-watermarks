# 03 — How the watermark works

## The key creates two groups

For each sampling context, the secret key deterministically divides the possible tokens into two
equal-size groups. Think of them as group 0 and group 1.

The real implementation ranks tokens with HMAC-SHA-256 and assigns half to each group. The raw key
is never stored in the repository.

For a four-token example, imagine the key produces this partition:

| Token | Model probability | Keyed group |
|---|---:|---:|
| `AAAAAA` | 0.40 | 0 |
| `GGGGGG` | 0.10 | 0 |
| `TTTTTT` | 0.30 | 1 |
| `CCCCCC` | 0.20 | 1 |

Each group has two tokens. In this example each group also happens to have probability mass 0.50.

Equal *size* does not normally imply equal *probability*. The code measures group probability mass
at every step.

## A hidden bit guides the draw

Assume the hidden target bit is fair: 0 or 1 with equal probability.

- For target 0, sample inside group 0.
- For target 1, sample inside group 1.

Within each group, preserve the model's relative probabilities:

| Target | Conditional draw |
|---|---|
| 0 | `AAAAAA` with 0.40 / 0.50 = 0.80; `GGGGGG` with 0.20 |
| 1 | `TTTTTT` with 0.30 / 0.50 = 0.60; `CCCCCC` with 0.40 |

Now average over the fair target bit:

```text
P(AAAAAA) = P(target 0) × P(AAAAAA | group 0)
          = 0.50 × 0.80
          = 0.40

P(TTTTTT) = 0.50 × 0.60 = 0.30
P(CCCCCC) = 0.50 × 0.40 = 0.20
P(GGGGGG) = 0.50 × 0.20 = 0.10
```

Those are exactly the original model probabilities. The hidden bit and output group agree every
time in this balanced example, yet the visible token marginal is unchanged.

## What if group probability is not 0.50?

Suppose group 1 contains 70% of the model probability. Always forcing the output group to equal the
fair target bit would incorrectly make group 1 appear only 50% of the time.

The maximal-coupling rule adjusts:

- If the target is 1, choose group 1.
- If the target is 0, choose group 0 with probability 0.60 and group 1 with probability 0.40.

The visible group-1 probability remains correct:

```text
P(group 1) = 0.50 × 1.00 + 0.50 × 0.40 = 0.70
```

Agreement is no longer perfect, but it is as high as possible while preserving the required group
mass. This is the trade-off the paper will measure on real model distributions.

## How detection uses the pattern

The detector recreates the same keyed group assignment for each observed 6-mer and compares it
with the expected target bits.

For example:

```text
expected targets:  0 1 1 0 1 0 0 1
observed groups:   0 1 0 0 1 0 1 1
matches:           ✓ ✓ · ✓ ✓ ✓ · ✓  = 6/8
```

One short sequence is not enough. The final decision needs a calibrated score over many blocks and
must account for every phase, strand, window, and offset the detector searched.

## What “exact marginal” does and does not mean

It means that, under the declared assumptions and fresh randomness, each next-token draw has the
same marginal distribution as ordinary sampling from the defined model policy.

It does not automatically prove:

- that whole generated sequences are indistinguishable under key reuse;
- that floating-point model execution is identical on CPU and MPS;
- that the detector survives insertions or deletions;
- that the implementation is a production cryptographic system.

Those require separate tests and claims.

Next: [Why model policies matter](04_model_policies.md).
