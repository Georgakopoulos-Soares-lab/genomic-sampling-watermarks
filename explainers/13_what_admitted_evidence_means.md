# 13 — What "admitted evidence" means

## Passing a test is not the same as being a paper number

The capacity runs finished, validated, and produced clean JSON. None of that made them paper
numbers. In this project a number becomes citable only when it is written into
`evidence/measurements.yaml` after a deliberate review. Everything else stays an engineering
artifact in ignored `outputs/`.

The reason is simple. A JSON file can be correct and still be unusable in a paper, because a paper
sentence needs to know *what the number is about*: which model, which revision, which device and
numeric precision, which prompts, how many samples, what the uncertainty covers, and what the
number is not allowed to claim.

## What the review actually checked

1. **Digests.** Every completed artifact's SHA-256 matched its recorded value, so nothing had been
   silently edited.
2. **Protocol shape.** The strict validator re-confirmed 24 prompts, 3,072 sequential states, 32
   evaluation partitions per state, correct context growth, and the absence of raw prompts, tokens,
   logits, dense probability vectors, and secret fields.
3. **Derivations.** Each stored information value was recomputed from its stored partition mass.
4. **Provenance.** One gap was found: the analysis files recorded the digest of their input report
   but not the model revision, device, precision, or any cohort digest. A reader holding only the
   analysis file could not tell which checkpoint produced it.

## How the gap was closed without breaking immutability

The rule is that a completed run is never rewritten. So the model runs were *not* repeated and the
existing files were *not* edited. Instead the analyzer was extended to record full provenance, and
it was re-run over the same immutable capacity reports to produce new `v3` analysis files. Their
cluster means, bootstrap interval, leave-one-out means, and expansion decision are identical to the
previous version — only the provenance is richer.

That is the general pattern: correct forward, never in place.

## What is now admitted, and what is not

Admitted: one mean value per policy, in information bits per DNA base, with its 95% prompt-cluster
interval.

| Policy | Mean bit/base | 95% prompt-cluster interval |
|---|---:|---:|
| `C_tok` | 0.1540 | 0.1515–0.1558 |
| `G_tok` | 0.1514 | 0.1398–0.1578 |
| `G_bp` | 0.1574 | 0.1548–0.1593 |

The mathematical ceiling is `1/6 ≈ 0.1667` bit per base, because one 6-mer token carries at most one
coupled bit and covers six bases.

Not admitted, and deliberately so:

- **Per-prompt and per-state numbers.** They exist in the reports but no paper sentence needs them
  yet.
- **Any cross-policy difference.** Each policy uses its own key-domain-separated partition
  fixtures, so the gap between two policies mixes a policy difference with a fixture difference. It
  is not a watermarking effect.
- **Anything about detection.** These are unwatermarked-path channel measurements. They say the
  channel exists. They say nothing about how many bases a detector needs.

## What the uncertainty interval means

It is uncertainty across the 24 frozen prompts, holding the 32 public evaluation partitions and the
unwatermarked continuation path fixed. It is *not* an interval over 98,304 independent observations,
because sequential states within a prompt are dependent and the partitions are reused. Explainer 10
covers why.

## Why this matters for what comes next

The channel estimate is now a fixed, citable reference point. The next experiments — watermarked
generation, distribution preservation, and a calibrated standalone detector — will be compared
against it rather than against a moving target.

Return to the [explainer index](README.md).
