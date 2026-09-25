# Carbon detector protocol provenance audit — 2026-09-21

## 1. Mismatched document digest

The immutable `outputs/carbon_synthid_position_independent_v1/summary.json` records SHA-256
`f0feca50e0af76119d2f9d40f3e6b203c6af2a04191383aa4cdec6737241684c` for
`docs/research/carbon_synthid_position_independent_validation_protocol.md`. The retained file,
including the version in git commit `4602fc1`, hashes to
`d7aac7f40a0fd70a2e074eed197aa1ff776dda669542eb57513f7771227a9c70`. The bytes of the
originally hashed protocol have not been located. Git history for this path contains only the
retained version, so the exact text change cannot be reconstructed. This extends, and does not
replace, the [2026-09-03 provenance amendment](carbon_synthid_protocol_provenance_amendment_2026_09_03.md).

The summary and trial files still match the evidence ledger digests
`cc5f58d104e82b96ec87dfa3e0c305ea5d08717dbffe0b83d3cddbf5208bffa6` and
`323d998561843dda5b204c33d3de9d6a281aaa700ceddc535b0d7af32e0ac81c`, respectively.

## 2. Governing settings and independent recovery

The retained protocol governs the following settings. “Artifact” below means the immutable
summary or trial rows, or an input whose path and digest that summary records. “Code” means the
historical runner or detector source whose digest the summary records; this is stronger than
assuming that today's code was used. The original protocol text itself is unrecoverable in every
row, even where the *executed setting* is recoverable.

| Governed setting | Retained protocol value | Recovery independent of protocol text |
|---|---|---|
| Cohort ID and inputs | `ncbi_refseq_eukaryote_windows_large_v1`; stored 384-base prompts and 3,072-base continuations from the frozen Carbon generation bundle | The summary records the cohort file digest `01867c1a…` and two generation-file digests `3b363ff9…` and `40cea992…`; all three retained files match. Generation rows record the cohort ID, model policy, and continuation length. Trial rows record 384 prompt bases and 3,072 generated bases on clean reads. |
| Prompt split rule | Rank `sha256(label, case_id)`; first 64 calibration, remaining 192 evaluation | The summary records the split-file digest `c5945682…`, which matches the retained input. That file states the rule and all 256 assignments (64 calibration, 192 evaluation). The 192 case IDs in trial rows match its evaluation set. |
| Window base lengths and starts | Every nucleotide start for 384, 768, 1,536, and 3,072 bases | Summary `window_base_lengths` and every trial's `window_base_lengths_searched` contain these four values. Each trial also records `hypotheses_searched`; the counts 16,128/16,136/16,144 for 3,455/3,456/3,457-base reads equal two orientations times the sum of all valid starts for all four lengths. |
| Orientations | Forward and reverse complement | Summary `orientations` and every trial's `orientations_searched` list both. Winning orientation and coordinates are recorded per trial. |
| Target sequence FPR and global test | 0.01; exact fair-binomial upper tail, then one Bonferroni correction across the complete search | Summary and every trial record 0.01; trials record local and corrected probabilities, search count, and the final decision. The strict validator recomputes the local tail, full-search correction, and decision from these fields. |
| Tournament depth | 30 | For every winning region, trial `g_total = scored_tokens × 30`; the validator checks this. The recorded detector source digest matches the retained source, whose default configuration specifies depth 30. |
| Context tokens | Four previous 6-mers | Trial `scored_tokens + repeated_contexts = window_base_length / 6 - 4` at each winner; the validator checks this. The recorded detector source hash fixes the four-token default. |
| Context history size | 1,024 | This number is **not an explicit trial or summary field**. It is recovered from the recorded historical runner SHA-256 `383d2952…` (the exact source in git commit `4602fc1`), which constructs `PositionIndependentSynthIDConfig()` with no overrides, and the recorded detector source SHA-256 `db7a0116…`, whose default history size is 1,024. A row-level history trace is unavailable. |
| Single-edit rule | One deterministic substitution, insertion, or deletion inside the continuation; clean read unchanged | Summary and trial `conditions` enumerate the four cases. Each edited trial records the edit position and resulting read length. The summary records the boundary-core digest `b941504d…`, matching the retained deterministic edit procedure; paired generation files are separately digest checked. Trial rows omit the changed nucleotide, so the exact edit sequence is recoverable only by recomputing it from the retained input and hashed code, not from a trial row alone. |

The summary additionally says `generation_rerun: false` and `calibration_rerun: false`, and records
the two source generation-file digests. Its `command` field names the runner; the ledger records
`PYTHONPATH=src python scripts/run_carbon_synthid_position_independent.py --workers 4`.
The runner digest `383d2952…` is the exact `4602fc1` source, whereas the later refactored working
copy has a different digest. The detector, SynthID core, and boundary-core digests still match
their retained files. The run used the runner's default detector configuration, not settings read
from the protocol Markdown; the runner only checked that file existed and hashed its bytes into
the summary.

## 3. Verdict and limit

**Derived verdict: `confined_to_document_text` for the observed mismatch.** The mismatched input
is the protocol file digest, not a model or generation input. Generation was reused from two
independently matching source files. The settings that determine the detector statistic are
recoverable from the immutable trial fields and the digest-identified runner and detector code;
the strict validator verifies all 4,608 trial identities, search sizes, score calculations, and
decisions, then fails only at `provenance checksum mismatch: protocol`. Thus the *observed* hash
mismatch supplies no evidence that the generated distribution or recorded detection statistic
changed.

This is a bounded scientific verdict, not a claim to possess the originally hashed document. Its
missing bytes prevent a byte-level or line-level comparison, and the summary does not store a
separate context-history trace. Keep the protocol-hash caveat attached to the version-one result.
Do not edit that result or its existing measurement IDs. Any corrected or repeated measurement
needs a new artifact and evidence ID.

## Reproduction checks

Run `sha256sum` on the protocol, summary, trial, cohort, split, and two generation files; compare
them with the digests above and in the summary. Run
`python3 scripts/check_evidence.py`, then
`python3 scripts/validate_carbon_synthid_position_independent.py --output-dir outputs/carbon_synthid_position_independent_v1`.
On 2026-09-21 the ledger checker passed (`39 measurements, 13 artifact digests`), and the strict
validator reached only `ValueError: provenance checksum mismatch: protocol` after validating the
other fields.
