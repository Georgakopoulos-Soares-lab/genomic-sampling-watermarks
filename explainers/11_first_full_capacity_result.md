# 11 — What the first full capacity result taught us

## We followed the rule even when it created more work

The first full run used 12 prompts. Eleven `G_tok` prompts carried roughly 0.155–0.159 information
bit per generated base, but `arabidopsis_q50` carried only about 0.027. Removing it would have made
the result look cleaner, but it would also have hidden real model behavior.

Our rule said to add prompts if either the cluster interval was wider than 0.02 bit/base or removing
one prompt changed the mean by more than 0.01 bit/base. `G_tok` crossed both limits, so we expanded.

## How we expanded without choosing favorable DNA

We kept every original prompt. For each of the same four organisms, we selected one different
reference chromosome and took windows at the same 20%, 50%, and 80% positions. The selection was
written and checksummed before the models saw those windows:

```text
12 original prompts
+ 12 new prompts from different chromosomes
= 24 final prompt clusters
```

This is called output-blind selection: model results did not decide which new DNA locations were
included.

## What the final laptop run contained

For each policy:

```text
24 prompts × 128 sequential states = 3,072 model states
3,072 states × 32 public test partitions = 98,304 capacity evaluations
```

Across `C_tok`, `G_tok`, and `G_bp`, the MacBook processed 9,216 model states and 294,912 partition
evaluations. The three model runs themselves took about 2.1, 4.5, and 4.7 minutes.

## The stopping decision

| Policy | Mean bit/base | 95% prompt-cluster interval | Interval width | Expand again? |
|---|---:|---:|---:|---:|
| `C_tok` | 0.15395 | 0.15149–0.15579 | 0.00431 | no |
| `G_tok` | 0.15142 | 0.13979–0.15777 | 0.01798 | no |
| `G_bp` | 0.15744 | 0.15478–0.15926 | 0.00448 | no |

All widths are below 0.02, and no single prompt changes a policy mean by more than 0.01. The frozen
rule therefore says to stop expanding. It does **not** say that every genomic region has high
capacity: the unusual Arabidopsis window is still present and visible in the per-prompt results.

## What this does and does not prove

This establishes that the model distributions expose a plausible sampling channel on the chosen
public cohort. It does not yet prove that a standalone detector achieves useful power after global
false-positive calibration or DNA edits. That detector-backed sequence-length measurement is the
next scientific gate.

The values are still outside the evidence ledger until their result package passes explicit
admission review.

Return to the [explainer index](README.md).
