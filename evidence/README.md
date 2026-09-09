# Evidence

`measurements.yaml` contains version-one Carbon and GENERator SynthID measurements. They are the
evidence for the current dual-model manuscript, admitted by
`../docs/research/dual_model_v1_admission_amendment_2026_09_09.md`, which also lists the execution
caveats the manuscript must disclose. Any *new* paper evidence still requires the `synthid.v2.*`
namespace, a fresh cohort, a new frozen protocol, and the M5 execution path defined in the active
rebuild plan. Results from removed watermark methods and their experiments are not retained.

Add an entry only when a result exists. Each entry needs:

- a stable ID, value, and unit;
- `[V]` for measured or `[A]` for derived;
- enough scope to prevent misuse: model, cohort, sequence length, read condition, detector, and
  declared false-positive rate where relevant;
- uncertainty and sample count;
- the result file and exact command that produced it;
- a short note for exclusions or limitations.

Store ordinary outputs where the producing script naturally writes them. Commit only small result
summaries needed for reproducibility.

Completed result files are immutable; a correction or new study gets a new filename and measurement
ID. Raw keys, private sequences, model weights, datasets, and credentials are forbidden.

Public fixture keys are reproducibility material, not security evidence. The rebuilt release must
run the planned strict evidence checker before paper review. The current checker verifies unique IDs
and status labels, hashes locally cited compact artifacts, checks protocol and execution-document
paths, and confirms that every exact identifier in the current legacy map exists in the ledger.
