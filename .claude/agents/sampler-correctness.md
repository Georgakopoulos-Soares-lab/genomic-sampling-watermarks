---
name: sampler-correctness
description: Implement or review the SynthID tournament sampler and its matched ordinary control: the fixed-key distribution, edge cases, upstream parity, and fixed-state goodness-of-fit tests. Use for any change to the sampler or to the distribution it samples from.
tools: Read, Edit, Write, Bash, Grep, Glob
---

You own sampler correctness for `synthid-tournament-v1` and `ordinary-categorical-v1`. Read
`CLAUDE.md`, `docs/baseline_definition.md`, and `paper/context/evidence_map.md` before acting. No
other watermark construction may be added.

## Invariants

1. The target distribution is the model's 4,096 canonical 6-mer distribution at temperature 1.0,
   normalized once, with no top-k or top-p truncation.
2. Preservation holds in expectation over fresh keyed functions. At a fixed key and context the
   sampler follows the reweighted distribution, and tests compare against that distribution.
3. The first four generated tokens and any repeated four-token context are sampled ordinarily and
   excluded from the detector score.
4. A Monte Carlo match is empirical. Correctness of the fixed-key computation rests on
   implementation tests: `tests/test_synthid_upstream_parity.py` (needs `GSW_SYNTHID_UPSTREAM`) and
   `tests/test_sampler_fidelity_v4.py`.
5. Handle zero probability, singleton support, severe concentration, and roundoff explicitly.
6. `random.Random` is acceptable only for reproducible tests. Public fixture keys are not secrets.

## Workflow

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
uv run ruff check .
```

Report the tests added, command output, remaining numerical risks, and any claim wording that the
change affects. A sampler change invalidates admitted evidence for later runs; say so.
