# Evidence

Keep this layer small. `measurements.yaml` contains only numbers that the paper may print. It is not
an experiment database, task tracker, or copy of the manuscript.

Add an entry only when a result exists. Each entry needs:

- a stable ID, value, and unit;
- `[V]` for measured or `[A]` for derived;
- enough scope to prevent misuse: model policy, cohort, sequence length, edit condition, detector,
  and calibrated FPR where relevant;
- uncertainty and sample count;
- the result file and exact command that produced it;
- a short note for exclusions or limitations.

Store ordinary outputs where the producing script naturally writes them. Commit only small result
summaries needed for reproducibility. Do not build a generic run/manifest framework unless repeated
experiments show that one is necessary.

Completed result files used by the paper are immutable; a correction gets a new filename and
measurement ID. Raw keys, private sequences, model weights, datasets, and credentials are forbidden.

Run `python3 scripts/check_evidence.py` before paper review.
