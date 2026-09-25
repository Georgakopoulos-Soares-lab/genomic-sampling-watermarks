# Lane 1 — HPC runs and regenerated artifacts (RUNNER)

**Date:** 2026-09-21
**Source of tasks:** Google Paper Assistant Tool (PAT) feedback on ICLR 2027 submission 32263,
posted 2026-09-17 11:49 as *LLM Feedback by Program Chairs* (note `LyX9i394f8`) on forum
`vo1qxcMxxx`.
**Owner:** the person with TACC Lonestar6 / Slurm + GPU access.
**This document is self-contained. Do not read the Lane 2 document, and do not wait for it.**

## Write ownership (hard boundary)

Lane 1 **writes** only: `scripts/**`, `configs/**`, `outputs/**`, `evidence/**`,
`paper/figures/**`, `docs/research/*protocol*`, `docs/research/*execution*`, `tests/**`.

Lane 1 **never writes**: `paper/manuscript/source/main.tex`, `paper/manuscript/source/refs.bib`,
`docs/research/literature_map.md`, `docs/threat_model.md`, `paper/reviews/**` (except appending to
this file).

Reading anything in the repository is allowed for both lanes. Only writes are partitioned.

Lane 1 never edits manuscript prose. Every number it produces leaves through one file:
`evidence/derived/2026-09-21_results_delta.json` (the **Results Delta Packet**, template at the end
of this document). Lane 3 merges it.

## Shared constants, fixed now so neither lane waits

| ID | Constant | Value |
|---|---|---|
| `TERM-1` | canonical name of the k-mer distribution-shift metric, in text **and** figure axes | **Jensen–Shannon drift** (never "shift") |
| `NS-1` | evidence namespace for any new run in this cycle | `synthid.v2.*` |
| `TAG-1` | placeholder macro Lane 2 uses for not-yet-measured numbers | `\evtag{<evidence id>}` |

`TERM-1` obliges Lane 1 to relabel figure axes (task L1-05). It obliges Lane 2 to use "drift" in
prose and captions. Neither has to ask the other.

## AUTHOR DECISIONS required before some tasks can run

These are scope or contract questions. **Flagged, not decided. Do not run a `SCOPE-GATED` task
without written author sign-off in this file.**

1. **AD-1 — Resolved 2026-09-21 by the author's explicit instruction.** New paper-bound runs may
   use the documented Lonestar6 A100 profile with a new `synthid.v2.*` evidence identity and full
   environment provenance. The active hardware guidance has been amended accordingly. The frozen
   `configs/*_hpc_v1.toml` retain their original classifications as historical inputs. This run
   executes directly inside the current GPU allocation; the resumable commands and gates are in
   `docs/research/synthid_v2_fpr_direct_a100_execution_2026_09_21.md`.
2. **AD-2 — Edit-rate sweep (PAT's most repeated request).** `AGENTS.md`: *"Do not add multiple-edit
   … experiments: they are outside the declared threat model."* `CONDITIONS` in
   `scripts/run_*_synthid_position_independent.py` is a fixed four-tuple and the runner itself
   records *"Single edits are one nucleotide event, not a one-percent edit rate."* Running a sweep
   requires a code change, a threat-model change, and a new protocol.
   **Recommendation: do not run it this cycle.** Lane 2 answers PAT analytically (the short-window
   boundary condition already bounds where the verifier must fail) and in Limitations. If authors
   disagree, sign off on AD-2 and L1-07 becomes live.
3. **AD-3 — Competing-watermark baseline.** PAT asks for a red/green-list baseline adapted to
   6-mers. `AGENTS.md` and `PROJECT.md` forbid reintroducing other watermark constructions. This is
   in the **Do-not-do list**, not a task. **Recommendation: decline; Lane 2 answers in prose.**
4. **AD-4 — Downstream biological benchmarks** (BEND / GenBench / variant-effect). Outside the
   declared claim boundary (`PROJECT.md`: the study "does not establish biological function").
   **Recommendation: decline as an experiment; Lane 2 adds it as future work.**

---

## L1-01 — Scale the false-positive-rate evidence for both models

- **Answers:** PAT-W4 (sample size insufficient for a 1% FPR target), and supplies the numbers PAT
  asks for in its Results segment.
- **Why:** PAT: *"The sample size of 384 reads per condition is statistically insufficient to
  rigorously validate the declared 1% false positive rate."* The manuscript already concedes a 95%
  interval reaching 2.87% for one positive prompt among 192.
- **Type:** new run (generation + position-independent detection), both models.
- **Severity:** blocking.
- **Scope change?** No — same watermark, same detector, same single-edit regime, same threat model.
  Only the number of independent prompts changes. **Gated on AD-1 only.**
- **Preconditions (all satisfiable without Lane 2):** Lonestar6 login node; `tacc_watermark`
  Conda environment reconciled; both model revisions already in the offline HF cache
  (`--local-files-only` makes a missing cache a hard failure, by design); TACC allocation.
- **Protocol:** a *new* frozen protocol document and hash. Copy the structure of
  `docs/research/carbon_synthid_position_independent_validation_protocol.md` into
  `docs/research/synthid_v2_fpr_scaling_protocol_2026_09_21.md` and freeze it **before** any run.
  Per `evidence/README.md`, new evidence needs a new cohort, a new protocol, and the
  `synthid.v2.*` namespace.
- **Target size:** ≥ 1,536 independent prompts per model (8× the current 192). Rationale: at the
  1% target, one positive in 192 prompts gives a 95% upper bound of 2.87%; 1,536 prompts with the
  same observed rate tighten the upper bound to roughly 0.9–1.0%, which is what "validating a 1%
  target" requires. Record the exact planned bound in the protocol before running, not after.
- **Commands** (smoke first; never submit from `idev` or inside another job):

  ```bash
  # 0. New, previously uninspected cohort (required for a new evidence identity)
  python3 scripts/build_large_public_prompt_cohort.py \
    --source-spec sources.yaml \
    --processed-root data/processed \
    --request-interval-seconds 0.36
  # record the new cohort id + sha256 into the new protocol document and into
  # configs/carbon_synthid_v2_fpr_hpc.toml and configs/generator_synthid_v2_fpr_hpc.toml

  # 1. Environment reconcile (login shell)
  bash scripts/hpc/create_tacc_watermark_env.sh
  python3 scripts/hpc/check_tacc_cuda.py

  # 2. Smoke, both models
  python3 scripts/hpc/submit_carbon_synthid_validation.py \
    --profile smoke --account "$TACC_ALLOCATION" \
    --cohort-jsonl data/processed/<new_cohort_id>/prompts.jsonl \
    --output-root "$SCRATCH/synthid_v2_fpr/carbon"
  python3 scripts/hpc/submit_generator_synthid_validation.py \
    --profile smoke --account "$TACC_ALLOCATION" \
    --cohort-jsonl data/processed/<new_cohort_id>/prompts.jsonl \
    --output-root "$SCRATCH/synthid_v2_fpr/generator"

  # 3. Full workload only after each smoke post job passes
  python3 scripts/hpc/submit_carbon_synthid_validation.py \
    --profile full --account "$TACC_ALLOCATION" \
    --cohort-jsonl data/processed/<new_cohort_id>/prompts.jsonl \
    --output-root "$SCRATCH/synthid_v2_fpr/carbon"
  python3 scripts/hpc/submit_generator_synthid_validation.py \
    --profile full --account "$TACC_ALLOCATION" \
    --cohort-jsonl data/processed/<new_cohort_id>/prompts.jsonl \
    --output-root "$SCRATCH/synthid_v2_fpr/generator"

  # 4. Position-independent detection over the new reads
  python3 scripts/run_carbon_synthid_position_independent.py \
    --validation-root "$SCRATCH/synthid_v2_fpr/carbon" \
    --cohort-jsonl data/processed/<new_cohort_id>/prompts.jsonl \
    --protocol docs/research/synthid_v2_fpr_scaling_protocol_2026_09_21.md \
    --output-dir outputs/synthid_v2_fpr_carbon --workers 16
  python3 scripts/run_generator_synthid_position_independent.py \
    --validation-root "$SCRATCH/synthid_v2_fpr/generator" \
    --cohort-jsonl data/processed/<new_cohort_id>/prompts.jsonl \
    --protocol docs/research/synthid_v2_fpr_scaling_protocol_2026_09_21.md \
    --output-dir outputs/synthid_v2_fpr_generator --workers 16

  # 5. Validate, then freeze
  python3 scripts/validate_carbon_synthid_position_independent.py \
    --output-dir outputs/synthid_v2_fpr_carbon
  python3 scripts/validate_generator_synthid_position_independent.py \
    --output-dir outputs/synthid_v2_fpr_generator
  python3 scripts/hpc/freeze_source_manifest.py
  ```

- **Note on the config files:** the existing `configs/*_hpc_v1.toml` are frozen inputs to completed
  runs. Do **not** edit them. Create `configs/carbon_synthid_v2_fpr_hpc.toml` and
  `configs/generator_synthid_v2_fpr_hpc.toml`, changing only `experiment_id`, `cohort_id`,
  `cohort_sha256`, `prompt_count`, and `[detection] evaluation_prompts` /
  `calibration_prompts`. Keep the tournament, distribution, and detection settings identical, so
  the new numbers are comparable to v1.
- **Expected cost:** v1 ran 256 prompts × 2 draws × 2 arms per model. Scaling to 1,536 prompts is
  6× that generation load plus a detector search that is linear in read count. Estimate from the v1
  execution records (`docs/research/carbon_synthid_e16_execution_2026_08_29.md`,
  `docs/research/generator_synthid_execution_2026_09_03.md`) and the smoke timings — **do not
  guess in the delta packet; record measured node-hours.**
- **New evidence IDs** (all `status: V` except where noted):
  - `synthid.v2.carbon.detector.clean.correct_key_rate` — reads detected / reads tested
  - `synthid.v2.carbon.detector.clean.ordinary_rate` — positives / reads, with exact prompt-level
    95% interval
  - `synthid.v2.carbon.detector.clean.wrong_key_rate`
  - the same three for `substitution_1nt`, `insertion_1nt`, `deletion_1nt`
  - the same twelve under `synthid.v2.generator.detector.*`, of which Lane 2 names
    `synthid.v2.generator.detector.clean.ordinary_rate` and
    `synthid.v2.carbon.detector.clean.ordinary_rate` explicitly in its branch tables
  - `synthid.v2.detector.fpr_upper_bound` `[A]` — the exact one-sided 95% upper bound on the
    prompt-level false-positive rate, per model and condition
  - `synthid.v2.cohort.identity` `[V]` — new cohort id, sha256, prompt count
- **Acceptance gate:** every validator passes; the source manifest is frozen; each new artifact's
  SHA-256 is recorded; the protocol hash recorded in the result matches the protocol document
  **(the exact failure v1 had for Carbon — see L1-02)**; `python3 scripts/check_evidence.py` passes
  after the ledger entries are added.
- **Failure branch:** if the full workload does not complete, record
  `outcome: "not_run"` or `"inconclusive"` per ID with the reason. Lane 2 has already drafted the
  prose for that branch; nothing needs to be asked.
- **Emits to delta packet:** all IDs above, each with `outcome` ∈
  `confirms | weakens | refutes | inconclusive | not_run`.

## L1-02 — Resolve or fully characterize the Carbon protocol-hash discrepancy

- **Answers:** PAT-W8 and PAT's Discussion segment point *"Contextualizing the Provenance
  Discrepancy."*
- **Why:** PAT: *"it would be beneficial to briefly specify what parameters the protocol document
  governs … Clarifying whether this mismatch could plausibly alter the underlying generative
  distributions or detection statistics."* The manuscript currently discloses the discrepancy
  without characterizing it.
- **Type:** provenance audit (no GPU; CPU and file hashing only).
- **Severity:** blocking — it is the cheapest credibility win available, and it is entirely inside
  Lane 1's ownership.
- **Scope change?** No.
- **Commands:**

  ```bash
  # 1. Recompute the hash of the retained protocol document and compare with the recorded value
  sha256sum docs/research/carbon_synthid_position_independent_validation_protocol.md
  python3 - <<'PY'
  import json, pathlib
  s = json.loads(pathlib.Path("outputs/carbon_synthid_position_independent_v1/summary.json").read_text())
  print(json.dumps({k: v for k, v in s.items() if "protocol" in k.lower() or "hash" in k.lower()}, indent=1))
  PY

  # 2. Diff the retained protocol against the amendment trail
  git log --follow -p -- docs/research/carbon_synthid_position_independent_validation_protocol.md
  cat docs/research/carbon_synthid_protocol_provenance_amendment_2026_09_03.md

  # 3. Confirm the run's actual parameters from the artifact itself, not the document
  python3 scripts/check_evidence.py
  ```

- **Deliverable:** `docs/research/carbon_provenance_discrepancy_audit_2026_09_21.md` stating, in
  this order: (1) which recorded hash disagrees with which document; (2) **exactly which
  parameters that document governs** — enumerate them (cohort id, prompt split rule, window base
  lengths, orientations, target FPR, tournament depth, context tokens, context history size, edit
  rule); (3) which of those parameters are *independently recoverable* from the artifact's own
  recorded command and config fields; (4) a reasoned verdict on whether the mismatch could have
  altered the generative distribution or the detection statistic, or is confined to document
  text. Add a ledger `notes:` update path only through a new ID if any value changes — existing
  result files stay immutable.
- **Acceptance gate:** every parameter in (2) is either matched to the artifact or explicitly
  listed as unrecoverable. No hand-waving verdict: state the evidence for it.
- **Failure branch:** if the governing document cannot be identified at all, record
  `outcome: "inconclusive"` for `synthid.v2.carbon.provenance.audit` and say so plainly. That is a
  legitimate result and Lane 2 has prose for it.
- **New evidence ID:** `synthid.v2.carbon.provenance.audit` `[A]` — value ∈
  `{confined_to_document_text, affects_detection_statistic, affects_generation, unresolved}`.
- **Emits to delta packet:** `synthid.v2.carbon.provenance.audit`, plus the enumerated parameter
  list as a structured field.

## L1-03 — Explain the cross-model detection-strength gap

- **Answers:** PAT-W7 and PAT's Results segment point *"Unexplained Variance in Detection Strength
  Between Models."*
- **Why:** Carbon's weakest clean correct-key read is 124.78 `-log10 P_win`
  (`synthid.detector.strength_separation`); GENERator's is 19.61
  (`synthid.generator.detector.strength_separation`); the threshold is 6.2078. PAT asks for a
  hypothesis, naming predictive entropy.
- **Type:** derived analysis over **existing** admitted artifacts. **No GPU, no regeneration, no
  new detector search.** This is the pattern `scripts/derive_generator_paper_analysis.py` already
  follows.
- **Severity:** major.
- **Scope change?** No.
- **Method:** from the retained trial files
  (`outputs/carbon_synthid_position_independent_v1/trials.jsonl`,
  `outputs/generator_synthid_position_independent_v1/trials.jsonl`) and the admitted
  sequence-comparison artifacts, compute per model: the distribution of per-read mark-bit
  positive fractions; the number of *scored* tokens per read after context exclusion and repeated-
  context masking; and the correlation between a read's strength and its scored-token count. Then
  test the entropy hypothesis with quantities already measured — the model-score (NLL) entries
  (`synthid.*.quality.nll_difference` carries per-arm means: GENERator 7.79465 / 7.80029 nat per
  token) and the stored `base_entropy_bits` / `dinucleotide_entropy_bits` effects.
- **Commands:**

  ```bash
  # new script, modelled on scripts/derive_generator_paper_analysis.py
  python3 scripts/derive_cross_model_strength_analysis.py \
    --carbon-trials outputs/carbon_synthid_position_independent_v1/trials.jsonl \
    --generator-trials outputs/generator_synthid_position_independent_v1/trials.jsonl \
    --output evidence/derived/cross_model_strength_2026_09_21.json
  python3 scripts/derive_cross_model_strength_analysis.py --check
  PYTHONPATH=src python3 -m unittest discover -s tests -v
  ```

  Add `tests/test_cross_model_strength.py`; unit tests must not download models or datasets.
- **New evidence IDs:**
  - `synthid.v2.strength_gap.scored_tokens_per_read` `[A]` — median and range, per model
  - `synthid.v2.strength_gap.repeated_context_exclusion_rate` `[A]` — fraction of tokens masked
    as repeated-context, per model
  - `synthid.v2.strength_gap.explained_component` `[A]` — how much of the gap the scored-token
    count accounts for, with the statistic used
- **Acceptance gate:** the analysis must distinguish *mechanical* causes (fewer scorable tokens,
  more repeated-context masking) from *distributional* ones (predictive entropy). If it cannot
  separate them, say so; a labelled hypothesis beats an unlabelled one.
- **Failure branch:** `outcome: "inconclusive"` with the quantities that were computed. Lane 2's
  hedged branch is already written.

## L1-04 — Measure the detector's search cost

- **Answers:** PAT's Methods segment point *"Algorithmic Complexity and Implementation Details"*
  (measured half), and the "computational search overhead" clause of PAT-W2.
- **Why:** PAT: *"The text does not provide an explicit theoretical analysis of time and space
  complexity, nor does it discuss algorithmic optimizations."* Lane 2 writes the theory; Lane 1
  supplies the measurement. Independent halves.
- **Type:** timing / resource measurement.
- **Severity:** major.
- **Scope change?** No.
- **Method:** time the position-independent search on a fixed set of reads at read lengths
  N ∈ {3456, 6912, 13824} with the frozen window set {384, 768, 1536, 3072} and both orientations,
  single-threaded and at `--workers 16`. Record wall clock per read, peak RSS, and the realized
  window count M per N (v1: M = 16,136 at N = 3456).
- **Commands:**

  ```bash
  for N in 3456 6912 13824; do
    /usr/bin/time -v python3 scripts/detect_synthid_position_independent.py \
      --domain "<public domain string from the frozen config>" \
      --target-fpr 0.01 --depth 30 --context-tokens 4 --context-history-size 1024 \
      < "$SCRATCH/timing/reads_${N}.txt" \
      > "outputs/synthid_v2_timing/detect_${N}.json" 2> "outputs/synthid_v2_timing/time_${N}.txt"
  done
  ```

- **New evidence IDs:** `synthid.v2.detector.search_seconds_per_read` `[V]`,
  `synthid.v2.detector.peak_memory_mib` `[V]`, `synthid.v2.detector.windows_per_read` `[A]`
  (as a function of N).
- **Acceptance gate:** hardware, thread count, and Python/torch build recorded with each number;
  no host names or local paths leak into anything the manuscript will cite.
- **Failure branch:** report single-length timing only; Lane 2's complexity paragraph stands on
  its own analytically.

## L1-05 — Relabel figure axes to `TERM-1` and regenerate all figures

- **Answers:** PAT's Appendix segment point *"Terminological Consistency (Figure 3)"* — figures
  3b/3d say "1-mer shift from prompt" while the text says "Jensen Shannon drift."
- **Why:** the mismatch is in generated figure labels, which only Lane 1 may change. Lane 2 fixes
  the prose to the same constant. Neither waits.
- **Type:** figure regeneration.
- **Severity:** minor, but do it — it is a two-line change plus a rebuild.
- **Commands:**

  ```bash
  # edit only the axis-label strings in scripts/make_paper_figures.py:
  #   "1-mer shift from prompt"  ->  "1-mer Jensen-Shannon drift from prompt"   (and 2-mer, 3-mer)
  python3 scripts/make_paper_figures.py --model carbon
  python3 scripts/make_paper_figures.py --model generator
  git diff --stat paper/figures
  python3 scripts/check_evidence.py
  ```

- **Acceptance gate:** `paper/figures/figure_values.json` regenerates with unchanged plotted
  values and updated figure digests. **If any plotted value changes, stop** — that is a real
  finding, not a relabel; record it in the delta packet as `refutes`/`weakens` on the affected ID.
- **Failure branch:** none needed; if the rebuild fails, leave figures untouched and record
  `not_run`.

## L1-06 — (optional) Empirical family-wise error of the correlated window search

- **Answers:** the measured half of PAT's Methods point *"Conservatism of the Bonferroni Correction
  on Correlated Windows."*
- **Why:** PAT notes windows shifted by exactly six bases share phase and nearly all tokens, so
  the binomial statistics are strongly positively correlated, making Bonferroni conservative.
  Lane 2 can state this qualitatively without any run. A measurement turns it into a number.
- **Type:** diagnostic over existing ordinary-arm reads (CPU).
- **Severity:** optional. Drop first if the clock runs out.
- **Scope change?** No — it calibrates the existing decision rule, it does not change it.
- **Method:** on ordinary (unmarked) reads, compute the realized rate at which the
  Bonferroni-corrected read-level decision fires, and the effective number of independent tests
  implied by the observed maximum-statistic distribution. Report both alongside M = 16,136.
  **Do not replace the reported correction with an empirical one** — `AGENTS.md` requires the
  full-search correction, and the manuscript's claim rests on it. This is a conservatism estimate
  only.
- **New evidence IDs:** `synthid.v2.detector.effective_independent_windows` `[A]`,
  `synthid.v2.detector.empirical_familywise_rate` `[V]`.
- **Acceptance gate:** the write-up must state explicitly that the reported decision rule remains
  the Bonferroni one and that this number quantifies headroom, not a new threshold.

## L1-07 — SCOPE-GATED: edit-rate sweep (DO NOT RUN without AD-2 sign-off)

- **Answers:** PAT-W1, and its Methods, Results and Discussion restatements of the same request.
- **Blocked by:** AD-2. `AGENTS.md` forbids multiple-edit experiments; `CONDITIONS` is a fixed
  four-tuple in both runners; the runner records that single edits are not an edit *rate*.
- **If and only if authors sign off**, the minimum honest design: parameterize the edit rate over
  {0.03% (current), 0.1%, 0.5%, 1%} with independent substitutions and 1–5 base indels; keep every
  other setting frozen; a new threat-model document, a new protocol, a new namespace
  (`synthid.v3.*`), and a code change with tests must land **before** any run.
- **Expected finding, stated in advance so it cannot be read as a surprise:** at a 1% indel rate an
  indel occurs roughly every 100 bases, while the shortest evaluated window is 384 bases, so no
  candidate window retains a clean reading frame and detection should fail. The breakdown point is
  the deliverable, not a defence.
- **Author sign-off: SIGNED 2026-09-24 — kimonaspro99@gmail.com.** Authorised in session on
  2026-09-24, conditional on the results honestly supporting a threat-model change, and confirmed
  on 2026-09-24 after the pilot result was reviewed. A **pilot only** was run under this
  authorisation, classified `pilot_not_admitted_evidence`; its numbers appear in the delta packet
  and are absent from `evidence/measurements.yaml`. See
  `docs/research/synthid_edit_rate_pilot_execution_2026_09_24.md`.
- **What the sign-off covers:** the pilot as run, and the narrow `docs/threat_model.md` correction
  recorded below. It does not cover a full-cohort `synthid.v3.*` run, which would need its own
  non-pilot protocol, nor any detector-guided or detector-query experiment, which `AGENTS.md`
  continues to forbid.

---

## Results Delta Packet — the single handoff file

Write `evidence/derived/2026-09-21_results_delta.json`. One object per evidence ID:

```json
{
  "schema_version": 1,
  "produced": "2026-09-21",
  "lane": 1,
  "entries": [
    {
      "id": "synthid.v2.carbon.detector.clean.ordinary_rate",
      "task": "L1-01",
      "status": "V",
      "value": null,
      "unit": "positives/reads",
      "n": null,
      "ci": {"level": 0.95, "lower": null, "upper": null, "kind": "exact prompt-level"},
      "artifact": "outputs/synthid_v2_fpr_carbon/summary.json",
      "sha256": null,
      "protocol": "docs/research/synthid_v2_fpr_scaling_protocol_2026_09_21.md",
      "execution_doc": "docs/research/synthid_v2_fpr_execution_2026_09_21.md",
      "command": null,
      "supersedes": "synthid.detector.clean.ordinary_rate",
      "outcome": "confirms|weakens|refutes|inconclusive|not_run",
      "note": ""
    }
  ]
}
```

`outcome` is the field Lane 3 keys on, and the field Lane 2's branch tables were written against.
It is not optional and it is not a summary of feelings about the run: `confirms` means the new
number supports the submitted claim at the same or greater strength; `weakens` means the claim
survives only hedged; `refutes` means the claim as submitted is wrong; `inconclusive` means the run
completed without settling it; `not_run` means it did not execute.

## Run order (internal to Lane 1 only)

1. L1-02 (no compute, unblocks the most credibility for the least cost)
2. L1-05 (minutes)
3. L1-03 (CPU, hours)
4. L1-01 smoke → L1-01 full (the long pole; start the cohort build first, it is I/O bound)
5. L1-04 (after L1-01's environment is warm)
6. L1-06 if time remains
7. L1-07 only with AD-2 signed

## Budget and triage

| Task | Compute | Drop order |
|---|---|---|
| L1-01 | GPU generation + CPU detection, both models, 6× v1 scale | last — it is the blocking answer |
| L1-02 | none | never |
| L1-03 | CPU hours | 4th |
| L1-04 | CPU, small | 3rd |
| L1-05 | minutes | never |
| L1-06 | CPU | 1st to drop |
| L1-07 | large | not in this cycle |

If the clock forces a cut, cut L1-06, then L1-04's longest read length, then L1-01's target from
1,536 prompts to 768 — and record the reduced target in the protocol **before** running, never
after seeing results.

## Do-not-do list

- Do **not** add a red/green-list or any other watermark construction as a baseline (AD-3;
  `AGENTS.md`, `PROJECT.md`).
- Do **not** run multiple-edit, detector-query, or detector-guided attack experiments (AD-2).
- Do **not** run downstream biological benchmarks or infer function, viability or safety from
  sequence statistics (AD-4; `PROJECT.md` claim boundary).
- Do **not** edit `evidence/measurements.yaml` entries that already exist, or any file in
  `outputs/*_v1/`. Corrections get a new filename and a new ID.
- Do **not** rename unchanged v1 results into the `synthid.v2.*` namespace.
- Do **not** report the smallest nominal window p-value as a global p-value, in any artifact.
- Do **not** edit `main.tex`, `refs.bib`, or anything else in Lane 2's ownership, even to fix an
  obvious typo. Log it in the delta packet's `note` field instead.
- Do **not** put host names, `$SCRATCH` paths, allocation names, or raw run IDs into anything the
  manuscript will cite.

## Coverage — PAT points this lane answers

| PAT point | Lane 1 task | Lane 1 alone suffices? |
|---|---|---|
| W1 / M4 / R2 / D1 edit-rate robustness | L1-07 (gated) | no — Lane 2 answers analytically |
| W2 search-overhead half | L1-04 | no — Lane 2 writes the comparison |
| W4 FPR sample size | L1-01 | no — Lane 2 writes the interval prose |
| W7 / R3 cross-model strength gap | L1-03 | no — Lane 2 writes the hypothesis |
| W8 / D2 provenance discrepancy | L1-02 | no — Lane 2 writes the Limitations sentence |
| M2 Bonferroni conservatism | L1-06 (optional) | no — Lane 2's half stands alone |
| M5 complexity, measured half | L1-04 | no |
| T7 figure terminology | L1-05 | no — Lane 2 fixes the prose |

---

## RUNNER STATUS — 2026-09-21 (appended by the runner)

**L1-01 is staged and blocked on hardware, not on any open decision.**

Passed and frozen: the output-blind 1,608-prompt cohort
`ncbi_refseq_eukaryote_windows_fpr_v2_1608` (content SHA-256 `f6075a85…d03c5dc5`, split confirmed
at 64 calibration / **1,544 evaluation**, built `--offline` with `selection_used_model_output:
false`); the protocol
`docs/research/synthid_v2_fpr_scaling_protocol_2026_09_21.md` (SHA-256 `ad950bfd…87523d32`, its
predeclared 95% upper bounds independently recomputed and exact); and
`configs/{carbon,generator}_synthid_v2_fpr_hpc.toml` under the new `synthid.v2.*` identities, which
the runner's strict comparison accepts. Both pinned model revisions are in the offline cache.

Blocked: node `c301-002` has a failed A100 at `0000:21:00.0` (`RmInitAdapter failed! (0x22:0x56:744)`,
first logged ~4 days before this session). The UVM driver probes every registered GPU, so
`open("/dev/nvidia-uvm")` returns `EIO` for every process on the node and `cuInit` returns 999. The
two remaining A100s are healthy and idle but unreachable through CUDA. `module load cuda/12.8`,
`CUDA_VISIBLE_DEVICES` by index and UUID, `nvidia-modprobe -u`, and running inside the Slurm job
step were all tried and ruled out; the fix needs root. `sbatch` is refused from compute nodes and
`ssh` to a login node needs the interactive MFA token, so the allocation cannot be changed from
inside it.

Both models have passed the smoke gate on real A100s, and full generation is running as jobs
`3460042` (Carbon, c308-002) and `3460043` (GENERator, c316-002) on `gpu-a100` with a 14-hour
walltime. Measured throughput is 23.7 s and 21.3 s per prompt per draw, so each model's 1,608
prompts need about ten hours across two GPUs, inside one allocation.

Three infrastructure faults were found and worked around, all recorded in
`docs/research/synthid_v2_fpr_direct_a100_execution_2026_09_21.md`: the dead A100 on `c301-002`;
a maintenance reservation starting 2026-09-22T08:30 that blocks any job whose walltime does not
fit before it; and `gpu-a100-small`'s `v330` nodes, which cannot import torch at all and are
unusable for this environment.

Detection remains a separate step once all four draws finalise. It is CPU bound and no longer
requires a GPU preflight, so it can run on an ordinary compute partition.

### Final status (2026-09-24)

| Task | State | Delta packet | Ledger |
|---|---|---|---|
| L1-01 FPR scaling | **complete** | 26 entries, `confirms` | 26 ids + frozen source manifest |
| L1-02 provenance audit | complete | 1 entry, `confirms` | 1 id |
| L1-03 strength gap | complete | 3 entries, `inconclusive` | 3 ids (pre-existing) |
| L1-04 detector search cost | **complete** | 3 entries, `confirms` | 3 ids |
| L1-05 TERM-1 relabel | complete | n/a (no measurement) | n/a |
| L1-06 empirical FWER | **complete** | 2 entries, `confirms` | 2 ids |
| L1-07 edit-rate sweep | **pilot run** (AD-2 authorised 2026-09-24) | 4 entries, `inconclusive` | 0 ids — pilot is not admitted evidence |

`python3 scripts/check_evidence.py` passes: 74 measurements, 22 artifact digests, 13 documents,
39 manuscript mappings. The delta packet
`evidence/derived/2026-09-21_results_delta.json` now holds 35 entries and is ready for Lane 3.

L1-06 result: the full-search Bonferroni correction is markedly conservative, as PAT expected.
On unmarked reads the corrected decision fires at 0.1052% for Carbon and 0.1862% for GENERator
against the 1% target, 9.5x and 5.4x below it. The effective independent-window count implied
by the observed minimum local p-value is about 830-850 against 16,136 searched hypotheses, an
inflation near 19x that is stable across both models and all four conditions. **The reported
decision rule is unchanged**; this quantifies headroom and is not a replacement threshold.
M_eff is a moment-matched effective count, not a distributional fit, and the artifact records
how far the Beta(1, M_eff) model misses the observed quantiles (0.54x to 1.23x).

The L1-01 source manifest is frozen at
`evidence/derived/synthid_v2_fpr_source_manifest_2026_09_24.json` (83 files, source tree
`3a9b71f8...`). Extending the freezer exposed that Carbon's position-independent runner and
validator were absent from its file list while GENERator's were present; both are now covered,
along with the v2 configs, protocol, cohort files and new scripts. Its `--verify` mode cannot
pass from a dirty worktree because the manifest records the `git status` digest and writing the
manifest changes it; every tracked file digest is identical, so source integrity is intact.

Headline for Lane 2: every primary-family one-sided 95% upper bound on the prompt-level
false-positive rate is below 1%, the largest being 0.8499% (GENERator, deletion). Correct-key
detection is 3088/3088 reads in all four conditions for both models. One secondary wrong-key cell,
Carbon under deletion, is 1.0150% and is reported as observed rather than as a 1% claim.

Lane 1 has not touched `paper/manuscript/source/main.tex`; the prose change is Lane 2's through
Lane 3's merge.


### L1-07 pilot outcome (2026-09-24)

**The prediction stated in advance in this document is wrong.** It predicted that at a 1% indel
rate no candidate window would retain a clean reading frame and detection would fail. Detection
does not fail. Correct-key detection is 100% for substitutions, mixed indels, pure insertions and
pure deletions through a **2%** per-base rate on both models, roughly 92-99% at 5%, and collapses
only at 10%. Carbon and GENERator agree to within a few percent everywhere.

The frame-shift reasoning was directionally right: one indel costs about seventeen times more
signal than one substitution. What it omitted is margin. The clean statistic sits near -1822
against a firing threshold near -6.2, about 290 times the evidence firing requires, so the scheme
tolerates heavy damage before detection actually fails. The amendment's own cancellation hypothesis
was refuted: direction-pure insertion and deletion degrade like mixed indel, so cumulative frame
offset is not the mechanism.

Controls pass. Edit counts scale exactly as declared, substitutions change exactly k bases, and the
ordinary-output null stays flat at every rate (median corrected log p exactly 0.00; 1/5,568 Carbon,
10/5,568 GENERator, both under the 1% target), so the channel manufactures no structure.

**Limits that must survive into any prose.** The channel is a non-adaptive public replay that never
inspects the detector, the key, or any score, so this is not an adversarial-robustness result and
`AGENTS.md` still forbids the detector-guided experiment that would measure one. It is a pilot at
96 prompts against the 1,544 used for admitted evidence. Its numbers are in the delta packet marked
`PILOT, NOT ADMITTED EVIDENCE` and are deliberately absent from `evidence/measurements.yaml`.

`docs/threat_model.md` was amended to stop saying multiple-edit experiments are "not planned",
which is no longer true, and to point at
`docs/research/threat_model_edit_rate_amendment_2026_09_24.md`. **The declared covered regime
remains the single nucleotide event**; expanding it needs a full-cohort run under `synthid.v3.*`.
That edit crosses this document's own write boundary for `docs/threat_model.md` and was made on the
author's explicit instruction.
