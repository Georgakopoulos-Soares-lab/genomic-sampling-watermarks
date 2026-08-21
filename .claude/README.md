# Claude agent routing

The root `CLAUDE.md` is the Claude project charter. The files under `agents/` are narrow task roles,
not competing sources of project truth.

## Route by task

| Task | Primary agent | Independent follow-up |
|---|---|---|
| Add or modify an exact-marginal sampler | `sampler-correctness` | `security-review` |
| Integrate Carbon or GENERator-v2 | `model-integration` | `sampler-correctness` for distribution boundary |
| Plan or execute E2-E13 | `experiment-runner` | `evidence-auditor` |
| Change detection, p-values, nulls, or synchronization search | `detector-statistics` | `evidence-auditor` |
| Change key derivation, nonce use, reuse policy, or security language | `security-review` | `evidence-auditor` for paper scope |
| Add datasets or biological sequence metrics | `biological-proxies` | `paper-sources` for provenance |
| Draft or reorganize manuscript sections | `paper-structure` | `paper-evidence` equivalent is `evidence-auditor` |
| Polish settled manuscript prose | `paper-style` | `evidence-auditor` |
| Add citations or related work | `paper-sources` | `paper-structure` |
| Add or revise plots | `paper-figures` | `evidence-auditor` |

## Separation of duties

- `evidence-auditor`, `paper-sources`, and `security-review` are read-only reviewers. They report
  findings and do not fix their own audit targets.
- `experiment-runner` may admit evidence only after the relevant protocol and checks pass.
- `paper-style` does not alter numbers, evidence tags, scope, or claim strength.
- `paper-figures` never hard-codes measured values outside the evidence ledger.
- `model-integration` does not redesign model math to make watermarking easier.

## Common handoffs

```text
sampler-correctness -> security-review -> experiment-runner -> evidence-auditor
model-integration   -> experiment-runner -> evidence-auditor
detector-statistics -> experiment-runner -> evidence-auditor
biological-proxies  -> experiment-runner -> evidence-auditor
paper-sources + evidence-auditor -> paper-structure -> paper-style -> paper-figures
```

Do not invoke every agent for every change. Use the smallest route that covers the risk.

