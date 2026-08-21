# 09 — GENERATOR policies and numerical precision

## One model, two probability rules

GENERATOR-v2 produces one score for each of 4,096 possible next 6-mers. We study two ways to turn
those scores into a draw:

- `G_tok` directly samples one 6-mer from the 4,096-way distribution;
- `G_bp` computes six distributions over A/T/C/G, samples each base independently, and joins the
  bases into a 6-mer.

For a tiny two-base analogy, suppose the direct distribution is:

```text
AA: 45%   AT: 5%   TA: 5%   TT: 45%
```

At each position, A and T both have 50% marginal probability. Independent base sampling therefore
produces:

```text
AA: 25%   AT: 25%   TA: 25%   TT: 25%
```

The base marginals are preserved, but the token distribution is not. That is why a result must say
`G_tok` or `G_bp`, not just “GENERATOR.”

## What the public cohort showed

On the 12 public 384-base prompts, the median engineering capacity estimate was:

| Policy | Median | Range |
|---|---:|---:|
| `G_tok` | 0.15842 bits/base | 0.08810–0.16109 |
| `G_bp` | 0.15979 bits/base | 0.10228–0.16291 |

The base-product rule was slightly flatter overall and helped most on the unusually concentrated
`arabidopsis_q50` state. This does not prove that `G_bp` is always better: 12 prompts and 16 public
partition fixtures per state are enough for an engineering decision, not a biological or paper
claim.

## Why float32 is required

Computers approximate real numbers. `bfloat16` stores fewer precision bits than `float32`, making
models smaller and often faster. That shortcut is acceptable only if it preserves the distribution
closely enough.

It did not for GENERATOR-v2. Across the 12 prompts, MPS `bfloat16` versus CPU `float32` had:

```text
same top token: 4 out of 12
mean total-variation distance: 0.238
```

With `float32` on both devices, `G_tok` improved to:

```text
same top token: 12 out of 12
top-10 and top-100 overlap: 100%
mean total-variation distance: 0.0000206
```

`G_bp` was closer still, with mean total-variation distance `0.00000266`. Therefore the repository
requires MPS `float32` for GENERATOR-v2. This is a good example of why “the model runs” is not the
same as “the model is numerically suitable for an exact-distribution experiment.”

We also compared our `G_bp` calculation directly with GENERATOR's own base-marginal helper on all
12 prompts. The worst total-variation distance was below `0.000000065` on both CPU and MPS—much
smaller than the frozen `0.00001` tolerance. So `G_bp` now means the same distribution in our code
and the pinned upstream code, within ordinary floating-point rounding.

## Does float32 still fit the MacBook?

Yes. The 12-context runs used about 5.03 GiB of MPS driver memory and processed approximately 14.2
states/s for `G_tok` and 16.2 states/s for `G_bp` after loading. That leaves a large margin within
the 48 GiB unified-memory budget.

The capacity protocol then ran on 12 prompts, triggered its frozen expansion rule for `G_tok`, and
stopped after all policies passed on 24 prompts. Continue to
[From engineering pilot to evidence](10_from_pilot_to_evidence.md).

Return to the [explainer index](README.md).
