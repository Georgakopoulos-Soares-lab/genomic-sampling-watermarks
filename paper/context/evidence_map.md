# Dual-model manuscript evidence map

> This map belongs to the dual-model manuscript on Carbon-500M and GENERator-v2 1.2B. Both models'
> version-one identifiers are admitted as paper evidence by
> `docs/research/dual_model_v1_admission_amendment_2026_09_09.md`, which supersedes the earlier rule
> that manuscript numbers must come from a `synthid.v2.*` namespace. The execution caveats that rule
> was protecting against are disclosed in the manuscript's Limitations section instead.

This is the complete empirical source map for `paper/manuscript/source/main.tex`. Every number
printed in the manuscript, and every value plotted in a figure, must resolve to one of the exact
identifiers below. Wildcard identifiers are intentionally not used.

## Sampler and sequence quality, Carbon

| Manuscript claim | Evidence identifier | Reviewed value |
|---|---|---:|
| Fixed-state marked-arm nominal rejection count | `synthid.carbon.sampler.nominal_rejections` | 13/256; 12.8 expected |
| Paired marked-minus-ordinary Carbon model score | `synthid.carbon.quality.nll_difference` | 0.00852 nat/6-mer |
| Declared quality summaries significant after correction | `synthid.carbon.quality.corrected_rejections` | 0/14 |
| Largest absolute standardized effect among the 14 summaries | `synthid.carbon.quality.metric_family_effects` | 0.0837 s.d. |

The model-score entry also carries the arm means, prompt-level 95% interval, p-value, standardized
effect, 256 prompt clusters, and 512 matched pairs. Those fields are uncertainty and scope on the
same measured quantity and need no separate identifiers.

## Position-independent detection, Carbon

| Read condition | Result family | Evidence identifier | Reviewed count |
|---|---|---|---:|
| Clean | windows in one decision | `synthid.detector.clean.regions_searched` | 16,136 |
| Clean | marked, right key | `synthid.detector.clean.correct_key_rate` | 384/384 |
| Clean | ordinary | `synthid.detector.clean.ordinary_rate` | 1/384 |
| Clean | marked, wrong key | `synthid.detector.clean.wrong_key_rate` | 0/384 |
| One substitution | marked, right key | `synthid.detector.substitution_1nt.correct_key_rate` | 384/384 |
| One substitution | ordinary | `synthid.detector.substitution_1nt.ordinary_rate` | 1/384 |
| One substitution | marked, wrong key | `synthid.detector.substitution_1nt.wrong_key_rate` | 0/384 |
| One insertion | marked, right key | `synthid.detector.insertion_1nt.correct_key_rate` | 384/384 |
| One insertion | ordinary | `synthid.detector.insertion_1nt.ordinary_rate` | 1/384 |
| One insertion | marked, wrong key | `synthid.detector.insertion_1nt.wrong_key_rate` | 0/384 |
| One deletion | marked, right key | `synthid.detector.deletion_1nt.correct_key_rate` | 384/384 |
| One deletion | ordinary | `synthid.detector.deletion_1nt.ordinary_rate` | 1/384 |
| One deletion | marked, wrong key | `synthid.detector.deletion_1nt.wrong_key_rate` | 0/384 |
| All | window strength by family and condition | `synthid.detector.strength_separation` | weakest marked read 124.78 |
| All | length of the strongest window | `synthid.detector.strongest_window_length` | 181/384 shorter after an insertion |

The four displayed ordinary positives are the same prompt and draw under four read conditions. The
prompt-level interval for that one positive among 192 independent prompts is stored on the
ordinary-rate entries. The all-success marked interval and the zero-positive wrong-key upper bound
are stored on their respective entries.

## Sampler and sequence quality, GENERator

| Manuscript claim | Evidence identifier | Reviewed value |
|---|---|---:|
| Fixed-state marked-arm nominal rejection count | `synthid.generator.sampler.nominal_rejections` | 5/256; 12.8 expected; ordinary arm 14 |
| Paired marked-minus-ordinary GENERator model score | `synthid.generator.quality.nll_difference` | -0.00564 nat/token; arms 7.79465 and 7.80029 |
| Declared quality summaries significant after correction | `synthid.generator.quality.corrected_rejections` | 0/14; smallest adjusted P 0.73 |
| Aligned-detector ordinary null fit at four lengths | `synthid.generator.aligned.ordinary_null_fit` | pass; 2, 6, 6, 4 positive prompts against about 5 expected |

The retained GENERator analysis includes the full 14-measure effect summary, with the largest
absolute standardized effect reported as `synthid.generator.quality.metric_family_effects`.

## Position-independent detection, GENERator

| Read condition | Result family | Evidence identifier | Reviewed count |
|---|---|---|---:|
| Clean | windows in one decision | `synthid.generator.detector.clean.regions_searched` | 16,136 |
| Clean | marked, right key | `synthid.generator.detector.clean.correct_key_rate` | 384/384 |
| Clean | ordinary | `synthid.generator.detector.clean.ordinary_rate` | 0/384 |
| Clean | marked, wrong key | `synthid.generator.detector.clean.other_key_rate` | 1/384 |
| One substitution | marked, right key | `synthid.generator.detector.substitution_1nt.correct_key_rate` | 384/384 |
| One substitution | ordinary | `synthid.generator.detector.substitution_1nt.ordinary_rate` | 0/384 |
| One substitution | marked, wrong key | `synthid.generator.detector.substitution_1nt.other_key_rate` | 1/384 |
| One insertion | marked, right key | `synthid.generator.detector.insertion_1nt.correct_key_rate` | 384/384 |
| One insertion | ordinary | `synthid.generator.detector.insertion_1nt.ordinary_rate` | 0/384 |
| One insertion | marked, wrong key | `synthid.generator.detector.insertion_1nt.other_key_rate` | 1/384 |
| One deletion | marked, right key | `synthid.generator.detector.deletion_1nt.correct_key_rate` | 384/384 |
| One deletion | ordinary | `synthid.generator.detector.deletion_1nt.ordinary_rate` | 0/384 |
| One deletion | marked, wrong key | `synthid.generator.detector.deletion_1nt.other_key_rate` | 0/384 |

The retained GENERator analysis includes the corresponding window-strength margin,
read-condition-specific best-window strengths, and strongest-window-length counts under
`synthid.generator.detector.strength_separation` and `synthid.generator.detector.strongest_window_length`.
The manuscript uses the same definitions for both models; the ledger names the wrong-key family
`other_key_rate` for GENERator and `wrong_key_rate` for Carbon, even though the manuscript uses a
single phrase, "wrong key", for both.

## Figures

Figures are produced by `scripts/make_paper_figures.py`, which verifies the SHA-256 of each source
artifact before plotting and writes every plotted summary value, with figure digests, to
`paper/figures/figure_values.json`.

| Figure | What it shows | Evidence identifiers |
|---|---|---|
| 1a | one keyed layer applied to an illustrative distribution | none; illustration of the manuscript's layer equation, carries no measurement |
| 1b | read layout and the search the verifier performs | `synthid.detector.clean.regions_searched` |
| 2a,c | paired marked-minus-ordinary model score with its interval | `synthid.carbon.quality.nll_difference`, `synthid.generator.quality.nll_difference` |
| 2b,d | all 14 declared summaries as standardized effects with intervals | `synthid.carbon.quality.metric_family_effects`, `synthid.generator.quality.metric_family_effects`, and both corrected-rejection entries |
| 3a,c | window strength per unedited read, by family, against the threshold | Carbon and GENERator `detector.strength_separation` entries and their clean-region counts |
| 3b,d | prompt-level detection rate with exact intervals, by family and condition | the twelve Carbon and twelve GENERator `detector.*_rate` entries |
| 4a,c | window strength per marked read, by read condition | Carbon and GENERator `detector.strength_separation` entries |
| 4b,d | length of the strongest window, by read condition | Carbon and GENERator `detector.strongest_window_length` entries |

Figure 3b plots the prompt-level rate. Its point estimates are the ledger fields
`prompts_with_both_draws_detected` and `prompts_with_at_least_one_positive_draw` over
`prompt_clusters`; its error bars are the exact intervals stored on the same entries.

## Source bundles

- Carbon sampler and quality claims resolve to compact files in `outputs/carbon_synthid_e16_v1/`.
- Carbon detection claims resolve to `outputs/carbon_synthid_position_independent_v1/summary.json`
  and `trials.jsonl`. Both Carbon directories are gitignored run outputs and are absent from a fresh
  clone, which is why `scripts/check_evidence.py` cannot pass without them.
- GENERator sampler, quality, and null-fit claims resolve to `outputs/generator_synthid_e16_v1/`,
  and its detection claims to `outputs/generator_synthid_position_independent_v1/`. Both are present
  in the repository.
- Exact artifact hashes, commands, model revision, cohort, devices, and protocol references are in
  `evidence/measurements.yaml`.
- The completed run narratives are
  `docs/research/carbon_synthid_e16_execution_2026_08_29.md`,
  `docs/research/carbon_synthid_position_independent_execution_2026_09_02.md`, and
  `docs/research/generator_synthid_execution_2026_09_03.md`.
- The detection result's protocol-file hash mismatch is disclosed in
  `docs/research/carbon_synthid_protocol_provenance_amendment_2026_09_03.md`.

## Version-two and version-three confirmatory evidence (2026-09-29 reconciliation)

Lane 1 (`2026-09-21_lane1_hpc_runs.md`) reported 45 results in its delta packet
(`evidence/derived/2026-09-21_results_delta.json`) after the version-one manuscript numbers above
were already admitted. Forty of those are ledger entries — 35 under `synthid.v2.*` and 5 under
`synthid.v3.*`; the remaining five are accounted for below. Lane 3 reconciled the manuscript
against them on 2026-09-29; these rows are the ones the revised `main.tex` now cites, by number
rather than by literal identifier (as with every v1 entry above).

| Manuscript claim | Evidence identifier | Reviewed value |
|---|---|---:|
| Scaled cohort identity | `synthid.v2.cohort.identity` | 1,608 prompts; 1,544 evaluation |
| Correct-key detection, scaled cohort, both models, all 4 conditions | the 8 `synthid.v2.{carbon,generator}.detector.*.correct_key_rate` entries | 3,088/3,088 in every cell |
| Largest primary-family (ordinary-control) one-sided 95% upper bound | `synthid.v2.detector.fpr_upper_bound` | 0.8499% (GENERator, deletion) |
| Secondary wrong-key cell exceeding 1% | `synthid.v2.carbon.detector.deletion_1nt.wrong_key_rate` | observed one-sided upper 1.0150% |
| Carbon protocol-hash discrepancy, resolved verdict | `synthid.v2.carbon.provenance.audit` | `confined_to_document_text` |
| Detector search cost, measured | `synthid.v2.detector.search_seconds_per_read`, `synthid.v2.detector.peak_memory_mib` | 0.0956 s/read at N=3,456; 27.9 MiB |
| Bonferroni conservatism, measured | `synthid.v2.detector.empirical_familywise_rate`, `synthid.v2.detector.effective_independent_windows` | 0.105%/0.186% fired vs 1% target; M_eff ≈ 830–850 vs 16,136 |
| Full-cohort edit-rate ceiling, Carbon | `synthid.v3.carbon.detector.edit_rate_full_detection_ceiling` | full detection through 2%/base, collapse by 10% |
| Full-cohort edit-rate ceiling, GENERator | `synthid.v3.generator.detector.edit_rate_full_detection_ceiling` | full detection through 1%/base (3,087/3,088 indels at 2%), collapse by 10% |
| Full-cohort edit-rate null check | `synthid.v3.{carbon,generator}.detector.edit_rate_null_rate` | ≤0.15% pooled, at or below the 1% target throughout |

The `synthid.v3.*` entries are admitted under the sign-off recorded in
`docs/research/threat_model_edit_rate_v3_admission_2026_09_29.md` (see also
`paper/reviews/2026-09-29_lane3_reconciliation.md`, CONF-01).

Five delta-packet results are deliberately not ledger entries and are cited by no manuscript
sentence. Four are the superseded 96-prompt edit-rate pilot (`synthid.pilot.*`, outcome
`inconclusive`), replaced in full by the `synthid.v3.*` cohort above; the pilot's execution record
is retained at `docs/research/synthid_edit_rate_pilot_execution_2026_09_24.md`. The fifth pair of
delta rows, `synthid.v2.{carbon,generator}.figures.detection_rebuilt`, records that both models'
figure sets were regenerated with the corrected drift labels and that every previously plotted
numeric value is unchanged; it is a regeneration receipt against
`paper/figures/figure_values.json`, carries no measured quantity, and so states no claim requiring
a ledger identity.

The cross-model strength-gap entries (`synthid.v2.strength_gap.*`) are ledger entries but remain
`inconclusive`, and are intentionally not cited by number in the manuscript, matching the inconclusive branch already
in §4.3.

## Writing boundaries

The manuscript may say that no measurable quality loss was found in either model and that every
marked read in the tested corpus was found in both. It may say that the control counts are consistent
with the declared 1% target. It may say that the same implementation carried across two models, which
is portability of the implementation. It must not say that quality is mathematically unchanged, that
the operational false-positive rate is proven below 1%, that the two models are equivalent in any
respect, or that biological function, viability, safety, sequence authenticity, or resistance to key
recovery was shown.

Claims that rest on one model only must name that model. The aligned-detector ordinary null fit is
specific to GENERator. Figures 2--4 display Carbon in panels \textbf{a,b} and GENERator in panels
  extbf{c,d}; Figure 1 is illustrative except for its reported search count.

Two execution gates were open for the version-one result and are disclosed in the manuscript's
Limitations section rather than tracked only here, because the numbers they qualify are paper-bound
under `docs/research/dual_model_v1_admission_amendment_2026_09_09.md`. Generation ran on GPU
hardware and detection on x86-64 CPUs without independent replication across platforms **for the
primary 192-prompt cohort**; a second, independently documented execution environment (TACC
Lonestar6, A100 GPUs, Slurm) and a second, larger, independently frozen cohort (1,608 prompts) were
subsequently used for the false-positive-rate, timing, and conservatism measurements in the section
above, though the headline detection and quality numbers still come from the original
single-execution cohort. The protocol file recorded inside the Carbon detection result does not
match the bytes of the retained protocol document (see
`docs/research/carbon_synthid_protocol_provenance_amendment_2026_09_03.md`); this was **resolved**
by `synthid.v2.carbon.provenance.audit` (2026-09-21): every parameter the document governs is
independently recoverable from the result artifact and agrees with the reported analysis, so the
discrepancy is confined to the document's text and does not affect the generative distribution or
detection statistic. The manuscript still states the scope limit that follows from the primary
result: one execution per model on one shared corpus for the headline numbers, whose confirmatory
replication in a fully independent environment remains the intended next step.

The 2026-09-11 editorial revision removes references to pinned model revisions and a prescribed
replication machine from the manuscript at the user's request. Exact revisions and execution
environments remain in the evidence trail; future runs must document their actual environment.
