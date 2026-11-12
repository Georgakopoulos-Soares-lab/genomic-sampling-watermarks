# Evidence

`measurements.yaml` is the evidence ledger for the dual-model manuscript. It holds three groups:

| Namespace | Content | Admission |
|---|---|---|
| `synthid.carbon.*`, `synthid.detector.*`, `synthid.generator.*` | development cohort, both models | `../docs/research/dual_model_v1_admission_amendment_2026_09_09.md` |
| `synthid.v2.*` | detection cohort, strength analysis, search cost, conservatism, Carbon protocol audit | `../docs/research/synthid_v2_fpr_scaling_protocol_2026_09_21.md` |
| `synthid.v3.*` | non-adaptive edit-rate series | `../docs/research/threat_model_edit_rate_v3_admission_2026_09_29.md` |

Any new evidence needs a new namespace, a dated protocol, and a documented execution environment.
Results from removed watermark methods are not retained.

Add an entry only when a result exists. Each entry needs:

- a stable ID, value, and unit;
- `[V]` for measured or `[A]` for derived;
- enough scope to prevent misuse: model, cohort, sequence length, read condition, detector, and
  declared false-positive rate where relevant;
- uncertainty and sample count;
- the result file and exact command that produced it;
- a short note for exclusions or limitations.

Store ordinary outputs where the producing script naturally writes them. Commit only small result
summaries needed for reproducibility; `derived/` holds the compact derived artifacts the ledger
cites.

Completed result files are immutable; a correction or new study gets a new filename and measurement
ID. Raw keys, private sequences, model weights, datasets, and credentials are forbidden.

Public fixture keys are reproducibility material, not security evidence. `scripts/check_evidence.py`
verifies unique IDs and status labels, hashes locally cited artifacts, checks protocol and
execution-document paths, and confirms that every identifier in `paper/context/evidence_map.md`
exists in the ledger. It currently fails only on five Carbon development-cohort result files that
were never committed.
