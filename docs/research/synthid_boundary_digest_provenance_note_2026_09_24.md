# Provenance note — `synthid_boundary.py` digest change (2026-09-24)

Recorded so this cannot become a later mystery of the kind L1-02 had to reconstruct.

## The mismatch

The admitted v2 detection summaries pin the source digest of
`src/genomic_watermarks/synthid_boundary.py`:

```
outputs/{carbon,generator}_synthid_v2_fpr_position_independent/summary.json
  provenance.boundary_core.sha256 = b941504d71c9def7a52e5caa24864ae02c9f312c17d7a6f99fe00aeae1d06675
```

The file now hashes to
`d9193912afa4257a05f0595138be8e3fffd0b223649a281eff81ff0202626270`. Anyone re-verifying the v2
result after 2026-09-24 will see that disagreement.

## Why it changed

The L1-07 edit-rate work appended a second edit channel to the same module: the `MultiBaseEdit`
dataclass, `deterministic_multi_base_edit`, and its private `_digest_stream` helper.

## Evidence that the admitted results are unaffected

1. `git diff --stat` reports **101 insertions and 0 deletions**. No existing line was changed or
   removed.
2. The current file **begins with the entire previous file, byte for byte**; 3,939 bytes were
   appended after it. Every byte the v2 detection executed is unchanged.
3. `deterministic_single_base_edit`, the only function in this module that the v2 run calls, is
   untouched, and `tests/test_multi_base_edit.py::test_single_edit_channel_is_unchanged` asserts
   its behaviour independently.
4. The other two pinned scientific sources, `synthid.py` and `synthid_position_independent.py`,
   still match their recorded digests exactly for both models.

## Status

The v2 result files stay immutable and are **not** reissued. The v2 numbers in
`evidence/measurements.yaml` stand. This note is the record of why the module digest moved and of
the evidence that the move is additive. A future re-verification should compare the *prefix*, or
check `deterministic_single_base_edit` directly, rather than the whole-file digest.

To reproduce the v2 digest exactly, check out the module at the commit preceding the L1-07 work.
