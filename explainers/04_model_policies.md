# 04 — Why model policies matter

## A checkpoint is not a complete probability definition

The model produces raw scores, but generation code can transform those scores before sampling.
If two policies transform them differently, they define different next-token distributions.

The paper therefore names the policy in every experiment instead of reporting only “Carbon” or
“GENERATOR.”

## The four implemented policy IDs

| ID | Meaning | Role |
|---|---|---|
| `C_tok` | Carbon main revision, restricted and normalized over canonical 6-mers | Primary Carbon baseline |
| `C_bp` | Carbon's separate `fns` revision, converted to independent base marginals | Optional historical control |
| `G_tok` | GENERator raw canonical 4,096-way categorical law | Research baseline |
| `G_bp` | GENERator released base-marginal behavior | Released-policy baseline |

`C_deployed` is not enabled yet. We first need to inventory the exact main-revision processor stack
and decide how non-DNA vocabulary items are handled. Naming an unaudited behavior would create a
false sense of precision.

## Direct-token and base-product sampling differ

Use a two-base toy vocabulary to see the difference. Suppose the direct distribution is:

```text
P(AA) = 0.50
P(TT) = 0.50
P(AT) = 0
P(TA) = 0
```

The two positions are perfectly correlated: both are `A`, or both are `T`.

The marginal probability at each position is still 50% `A` and 50% `T`. If a policy samples the
positions independently from those marginals, it produces:

```text
P(AA) = 0.25
P(AT) = 0.25
P(TA) = 0.25
P(TT) = 0.25
```

Both policies have the same per-position base frequencies, but very different token distributions.
The real base-product transformation repeats this across six positions and four possible bases.

This is why a watermark result under `G_tok` cannot be presented as a result under `G_bp`.

## What the source audit established

We inspected revision-pinned upstream code and recorded the findings:

- Carbon's main checkpoint follows a standard causal-language-model path.
- Factorised Nucleotide Supervision is a training objective, not proof of a special deployed
  sampler on the main checkpoint.
- Carbon's separate `fns` revision contains a base-marginal processor.
- GENERator-v2's released custom generation path contains a base-marginal processor.
- In stochastic mode, the resulting `G_bp` token law is the product of six base marginals.

Carbon's custom tokenizer silently loads a Qwen tokenizer. Upstream does not provide a revision in
that call, so our adapter injects the audited Qwen revision during construction. This prevents a
future change to Qwen's `main` branch from silently changing Carbon token IDs.

## What remains open

The tokenizers, pure probability transformations, model weights, public-cohort paths, and
sequential capacity runs are verified. Local `G_bp` probabilities also match the pinned upstream
base-marginal helper on CPU and MPS.

Carbon's exact main-revision deployed processor stack (`C_deployed`) and the optional `C_bp`
control remain open. Source inspection tells us what code is intended to do; weight-backed tests
tell us what the complete installed system actually does. We require both before enabling a policy.

Next: [What we have built](05_what_we_have_built.md).
