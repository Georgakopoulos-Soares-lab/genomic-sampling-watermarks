# Paper agent instructions

## Ground truth

The manuscript is downstream of code and evidence. Read, in order:

1. `../PROJECT.md`
2. `../evidence/README.md`
3. `context/00_terminology.md`
4. `context/02_claims_and_limits.md`
5. `context/03_source_map.md`
6. `context/04_implementation_ground_truth.md`

## Rules

- This is one cross-model paper, not a Carbon paper plus a GENERator paper.
- Every empirical number must resolve to `../evidence/measurements.yaml`.
- `[U]` evidence may appear only as future work or an explicit unresolved item, never as a result.
- Preserve the distinction between direct-token and base-marginal generation policies.
- “Distribution-preserving” must state whether it is per-step exact, in expectation, or empirically tested.
- Report detector FPR only after calibrating the full orientation/phase/window/offset/synchronization search.
- Do not claim biological function, viability, safety, or cryptographic security without the corresponding evidence class.
- Do not include host names, local paths, raw run IDs, keys, or internal infrastructure details in the manuscript.
- Figures and tables must be generated from admitted evidence, not manually edited.
- Add dated review notes under `reviews/`; do not overwrite review history.

## Build

```bash
./scripts/build.sh
```
