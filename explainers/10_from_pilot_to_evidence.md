# 10 — From engineering pilot to evidence

## Why 24 prompts do not mean only 24 measurements

A prompt is the DNA context where generation starts. After the model chooses one new 6-mer, that
6-mer becomes part of the context and the model produces a new probability distribution. One
continuation therefore gives us many sequential model states:

```text
384-base prompt
    ↓ predict 6 bases: state 1
390-base context
    ↓ predict 6 bases: state 2
396-base context
    ↓ ...
```

The initial E2 pilot collected 128 states after each of 12 prompts. Its stability rule required an
output-blind expansion to 24 prompts. The final calculation is:

```text
24 prompts × 128 states = 3,072 states per model policy
```

With `C_tok`, `G_tok`, and `G_bp`, the final pilot evaluated 9,216 model states in total while
retaining a small, understandable public cohort.

## Why 3,072 is not the statistical sample size

States from one continuation share a prompt and all preceding generated DNA. They are related, not
3,072 independent experiments. A simple average can summarize them, but an uncertainty interval
must preserve the 24 prompt groups.

Imagine a classroom study with 24 classrooms and 128 students per classroom. Treating all students
as unrelated would hide the fact that students in one classroom share a teacher and environment.
Here, the prompt is the classroom.

We therefore bootstrap prompt clusters: resample the 24 prompts, carrying all their states with
them. We also print each prompt's summary so one unusual region cannot hide inside a mean.

## Why each state gets 32 partitions

A key-derived partition divides the 4,096 possible 6-mers into two equal-size groups. Different
keys create different partitions and therefore slightly different probability mass balance.

We can evaluate 32 partitions on one already-computed probability vector:

```text
one model forward pass → one 4,096-way distribution
                       → partition 1 capacity
                       → partition 2 capacity
                       → ... partition 32 capacity
```

This measures partition variation without running the model 32 times. Those partitions are not
additional genomic observations, and the analysis will not count them as such. For one policy, we
reuse the same 32 public test partitions across every state. Think of this as measuring every model
state with the same 32 rulers instead of manufacturing new rulers for every measurement.

The collector and validator now implement this loop. Every final policy report contains 3,072
states with 32 measurements each. Reports deliberately store only summaries and checksums—not the
prompt, generated 6-mers, logits, or the dense 4,096-way distribution.

## When would we add more prompts?

We expanded the initial 12 prompts only if they were too unstable:

- the 95% interval for mean information/base is wider than 0.02 bit/base; or
- leaving out one prompt changes the mean by more than 0.01 bit/base.

`G_tok` crossed both thresholds on v1, so we retained those prompts and added 12 windows from
different chromosomes before inspecting their model outputs. All three policies pass both
thresholds on the final 24 prompts, so expansion stops. These engineering aggregates remain
outside the evidence ledger until explicit admission review.

Return to the [explainer index](README.md).
