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

The sampler counts above come from a test that draws from the computed fixed-key and model
distributions and compares the draws with those same distributions. The manuscript therefore
treats them as a check of the sampling step and of the test. The correctness of the fixed-key
computation rests on implementation tests, not on ledger measurements:

- `tests/test_synthid_upstream_parity.py`, against SynthID-Text commit `addb4a15`, which needs
  `GSW_SYNTHID_UPSTREAM`;
- `tests/test_sampler_fidelity_v4.py`, which checks the NumPy path against the reference, and
  draw-for-draw identity with `_tournament_step`.

Both passed on 2026-10-01.

The model-score entry also carries the arm means, prompt-level 95% interval, p-value, standardized
effect, 256 prompt clusters, and 512 matched pairs. Those fields are uncertainty and scope on the
same measured quantity and need no separate identifiers.

## Position-independent detection, Carbon

| Read condition | Result family | Evidence identifier | Reviewed count |
|---|---|---|---:|
| Clean | windows in one decision | `synthid.detector.clean.regions_searched` | 16,136 |
| Clean | marked, correct key | `synthid.detector.clean.correct_key_rate` | 384/384 |
| Clean | ordinary | `synthid.detector.clean.ordinary_rate` | 1/384 |
| Clean | marked, wrong key | `synthid.detector.clean.wrong_key_rate` | 0/384 |
| One substitution | marked, correct key | `synthid.detector.substitution_1nt.correct_key_rate` | 384/384 |
| One substitution | ordinary | `synthid.detector.substitution_1nt.ordinary_rate` | 1/384 |
| One substitution | marked, wrong key | `synthid.detector.substitution_1nt.wrong_key_rate` | 0/384 |
| One insertion | marked, correct key | `synthid.detector.insertion_1nt.correct_key_rate` | 384/384 |
| One insertion | ordinary | `synthid.detector.insertion_1nt.ordinary_rate` | 1/384 |
| One insertion | marked, wrong key | `synthid.detector.insertion_1nt.wrong_key_rate` | 0/384 |
| One deletion | marked, correct key | `synthid.detector.deletion_1nt.correct_key_rate` | 384/384 |
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
| Clean | marked, correct key | `synthid.generator.detector.clean.correct_key_rate` | 384/384 |
| Clean | ordinary | `synthid.generator.detector.clean.ordinary_rate` | 0/384 |
| Clean | marked, wrong key | `synthid.generator.detector.clean.other_key_rate` | 1/384 |
| One substitution | marked, correct key | `synthid.generator.detector.substitution_1nt.correct_key_rate` | 384/384 |
| One substitution | ordinary | `synthid.generator.detector.substitution_1nt.ordinary_rate` | 0/384 |
| One substitution | marked, wrong key | `synthid.generator.detector.substitution_1nt.other_key_rate` | 1/384 |
| One insertion | marked, correct key | `synthid.generator.detector.insertion_1nt.correct_key_rate` | 384/384 |
| One insertion | ordinary | `synthid.generator.detector.insertion_1nt.ordinary_rate` | 0/384 |
| One insertion | marked, wrong key | `synthid.generator.detector.insertion_1nt.other_key_rate` | 1/384 |
| One deletion | marked, correct key | `synthid.generator.detector.deletion_1nt.correct_key_rate` | 384/384 |
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
artifact before plotting and writes every plotted summary value, with figure digests, to a
manifest: `paper/figures/figure_values.json` (Figures 1, 2, S1, S2),
`figure_values_v2.json` and `figure_values_generator_v2.json` (Figures 3 and 4), and
`figure_values_edit_rate.json` (Figure 5).

| Figure | What it shows | Evidence identifiers |
|---|---|---|
| 1a | one keyed layer applied to an illustrative distribution | none; illustration of the manuscript's layer equation, carries no measurement |
| 1b | read layout and the search the verifier performs | `synthid.detector.clean.regions_searched` |
| 2a,c | paired marked-minus-ordinary model score with its interval | `synthid.carbon.quality.nll_difference`, `synthid.generator.quality.nll_difference` |
| 2b,d | all 14 declared summaries as standardized effects with intervals | `synthid.carbon.quality.metric_family_effects`, `synthid.generator.quality.metric_family_effects`, and both corrected-rejection entries |
| S1a,c | primary cohort: window strength per unedited read, by family, against the threshold | Carbon and GENERator `detector.strength_separation` entries and their clean-region counts |
| S1b,d | primary cohort: prompt-level detection rate with exact intervals, by family and condition | the twelve Carbon and twelve GENERator `detector.*_rate` entries |
| S2a,c | primary cohort: window strength per marked read, by read condition | Carbon and GENERator `detector.strength_separation` entries |
| S2b,d | primary cohort: length of the strongest window, by read condition | Carbon and GENERator `detector.strongest_window_length` entries |

Figures 3 and 4 in the main text show the second cohort; see the second-cohort figure table below.

Supplementary Figure S1b plots the prompt-level rate. Its point estimates are the ledger fields
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

## Second cohort and edit-rate series (revised 2026-09-30)

These identifiers back the second cohort (Methods, Prompts and generation; Results, Second cohort),
Table 1, and Figures 3, 4, and 5. The manuscript cites them by number, as
with every version-one entry above. The 2026-09-29 reconciliation first admitted them; the
2026-09-30 revision (`paper/reviews/2026-09-30_post_lane_revision_plan.md`) moved them out of
Limitations into Methods and Results and added three derived entries.

| Manuscript claim | Evidence identifier | Reviewed value |
|---|---|---:|
| Second cohort: 1,608 prompts, 1,544 evaluated, 12 records | `synthid.v2.cohort.identity` | 1,608; 1,544 |
| Largest ordinary-output one-sided 95% bound | `synthid.v2.detector.fpr_upper_bound` | 0.850% (GENERator, deletion); eight-positive threshold |
| Wrong-key cell above 1% | `synthid.v2.carbon.detector.deletion_1nt.wrong_key_rate` | 9 positives; bound 1.015% |
| Corrected decision rate on unmarked reads | `synthid.v2.detector.empirical_familywise_rate` | 0.105% Carbon, 0.186% GENERator; 9.5x, 5.4x |
| Effective number of independent tests | `synthid.v2.detector.effective_independent_windows` | 827.7-852.4 against 16,136 |
| Median and weakest clean strength, both cohorts | `synthid.v2.strength_gap.cohort_strength_summary` | 790.6/798.8 and 124.8/19.6 primary; 792.9/799.7 and 237.6/123.8 second |
| Median mark-bit fraction, primary cohort | `synthid.v2.strength_gap.cohort_strength_summary` | 74% both models |
| Weakest GENERator read: 174 excluded, 334 scored, 54.6% ones, 9% of gap | `synthid.v2.strength_gap.explained_component` | 0.0914 |
| Scored-token median 508 in both models | `synthid.v2.strength_gap.scored_tokens_per_read` | 508, 508 |
| Median strength after one edit, second cohort | `synthid.v2.detector.correct_key_strength_by_condition` | Carbon 792.9, 777.6, 441.8, 437.7; GENERator 799.7, 783.8, 443.1, 438.5 |
| Carbon protocol audit, eight of nine settings recovered | `synthid.v2.carbon.provenance.audit` | `confined_to_document_text`; context history from code default |
| Search time and memory | `synthid.v2.detector.search_seconds_per_read`, `synthid.v2.detector.peak_memory_mib`, `synthid.v2.detector.windows_per_read` | 0.0956 s; 27.9-69.1 MiB; 16,136 |
| Edit-rate detection by rate and type, Carbon | `synthid.v3.carbon.detector.edit_rate_full_detection_ceiling` | per-cell rates in `uncertainty`; ceiling 0.02 |
| Edit-rate detection by rate and type, GENERator | `synthid.v3.generator.detector.edit_rate_full_detection_ceiling` | per-cell rates in `uncertainty`; 3,087/3,088 mixed at 2% |
| Ordinary outputs under editing | `synthid.v3.carbon.detector.edit_rate_null_rate`, `synthid.v3.generator.detector.edit_rate_null_rate` | 132 and 116 of 89,552; worst cells 0.227%, 0.291% |
| Models agree within one percentage point | `synthid.v3.detector.edit_rate_model_agreement` | 0.0097 (substitution, 10%) |

In the edit-rate series, each insertion or deletion event adds or removes 1–5 bases (`deterministic_multi_base_edit`, default `max_indel_bases=5`, unchanged by `scripts/run_synthid_edit_rate_pilot.py`); each substitution changes one base. The per-base rate therefore counts events, as the manuscript's Methods now state. The v3 ledger entries record events per read but not the span.

Table 1 cells (detection cohort), each carrying read and prompt counts, exact intervals, the one-sided bound, and the
winning-window length counts that the Results cite (3,087/3,085 full-window reads unedited;
1,724/1,732 after an insertion; 1,663/1,671 after a deletion):

| Model | Read condition | Family | Evidence identifier |
|---|---|---|---|
| Carbon | None | correct key, reads; winning-window lengths | `synthid.v2.carbon.detector.clean.correct_key_rate` |
| Carbon | None | ordinary, positives and one-sided bound | `synthid.v2.carbon.detector.clean.ordinary_rate` |
| Carbon | None | wrong key, positives and one-sided bound | `synthid.v2.carbon.detector.clean.wrong_key_rate` |
| Carbon | One substitution | correct key, reads; winning-window lengths | `synthid.v2.carbon.detector.substitution_1nt.correct_key_rate` |
| Carbon | One substitution | ordinary, positives and one-sided bound | `synthid.v2.carbon.detector.substitution_1nt.ordinary_rate` |
| Carbon | One substitution | wrong key, positives and one-sided bound | `synthid.v2.carbon.detector.substitution_1nt.wrong_key_rate` |
| Carbon | One insertion | correct key, reads; winning-window lengths | `synthid.v2.carbon.detector.insertion_1nt.correct_key_rate` |
| Carbon | One insertion | ordinary, positives and one-sided bound | `synthid.v2.carbon.detector.insertion_1nt.ordinary_rate` |
| Carbon | One insertion | wrong key, positives and one-sided bound | `synthid.v2.carbon.detector.insertion_1nt.wrong_key_rate` |
| Carbon | One deletion | correct key, reads; winning-window lengths | `synthid.v2.carbon.detector.deletion_1nt.correct_key_rate` |
| Carbon | One deletion | ordinary, positives and one-sided bound | `synthid.v2.carbon.detector.deletion_1nt.ordinary_rate` |
| Carbon | One deletion | wrong key, positives and one-sided bound | `synthid.v2.carbon.detector.deletion_1nt.wrong_key_rate` |
| GENERator | None | correct key, reads; winning-window lengths | `synthid.v2.generator.detector.clean.correct_key_rate` |
| GENERator | None | ordinary, positives and one-sided bound | `synthid.v2.generator.detector.clean.ordinary_rate` |
| GENERator | None | wrong key, positives and one-sided bound | `synthid.v2.generator.detector.clean.wrong_key_rate` |
| GENERator | One substitution | correct key, reads; winning-window lengths | `synthid.v2.generator.detector.substitution_1nt.correct_key_rate` |
| GENERator | One substitution | ordinary, positives and one-sided bound | `synthid.v2.generator.detector.substitution_1nt.ordinary_rate` |
| GENERator | One substitution | wrong key, positives and one-sided bound | `synthid.v2.generator.detector.substitution_1nt.wrong_key_rate` |
| GENERator | One insertion | correct key, reads; winning-window lengths | `synthid.v2.generator.detector.insertion_1nt.correct_key_rate` |
| GENERator | One insertion | ordinary, positives and one-sided bound | `synthid.v2.generator.detector.insertion_1nt.ordinary_rate` |
| GENERator | One insertion | wrong key, positives and one-sided bound | `synthid.v2.generator.detector.insertion_1nt.wrong_key_rate` |
| GENERator | One deletion | correct key, reads; winning-window lengths | `synthid.v2.generator.detector.deletion_1nt.correct_key_rate` |
| GENERator | One deletion | ordinary, positives and one-sided bound | `synthid.v2.generator.detector.deletion_1nt.ordinary_rate` |
| GENERator | One deletion | wrong key, positives and one-sided bound | `synthid.v2.generator.detector.deletion_1nt.wrong_key_rate` |

Figures for this section:

| Figure | What it shows | Evidence identifiers |
|---|---|---|
| 5a,b | correct-key detection by per-base edit rate and edit type | both `edit_rate_full_detection_ceiling` entries; values in `paper/figures/figure_values_edit_rate.json` |
| 5c | ordinary-output detection by rate, pooled over edit types | both `edit_rate_null_rate` entries |
| 3a-d | second-cohort strength per unedited read and prompt-level rates | the 24 Table 1 entries; values in `paper/figures/figure_values_v2.json` and `figure_values_generator_v2.json` |
| 4a-d, Table S2 | second-cohort strength and strongest-window length by edit | the 8 correct-key Table 1 entries and `synthid.v2.detector.correct_key_strength_by_condition` |

Five delta-packet results carry no ledger identity and no manuscript sentence: the four superseded
96-prompt pilot results (`synthid.pilot.*`), replaced by the full edit-rate series, and the two
figure-regeneration receipts `synthid.v2.{carbon,generator}.figures.detection_rebuilt`, which record
a relabelling with unchanged plotted values.

## Writing boundaries

The manuscript may say that no measurable quality loss was found in either model and that every
marked read in both tested cohorts was found in both models. It may state the one-sided 95% upper
confidence bounds on the ordinary-output rate, and that they lie below 1%, but not that the
false-positive rate is proven below 1%. It must report the wrong-key cell above 1%. It may say that
the same implementation carried across two models, which is portability of the implementation, and
that their edit-rate curves agree within one percentage point. It must not present the 2% versus 1%
full-detection ceilings as a difference in robustness, since one read separates them. It must not
say that quality is mathematically unchanged, that the two models are equivalent in any respect, or
that biological function, viability, safety, sequence authenticity, resistance to key recovery, or
robustness to an adaptive editor was shown.

Claims that rest on one model only must name that model. The aligned-detector ordinary null fit is
specific to GENERator, as are the weakest-read details. Figures 2-4 and S1-S2 display Carbon in
panels **a,b** and GENERator in panels **c,d**; Figure 5 shows Carbon in **a**, GENERator in **b**,
and both models in **c**. Figure 1 is illustrative except for its reported search count.

The Limitations section discloses the execution scope. The sampler and quality results come from
one execution per model on the primary cohort. The second cohort repeated generation and detection
in a separate environment with new keyed functions but is not an independent replication. The
protocol file recorded inside the Carbon primary detection result does not match the retained
protocol document (`docs/research/carbon_synthid_protocol_provenance_amendment_2026_09_03.md`). The
audit recorded as `synthid.v2.carbon.provenance.audit` recovers eight of the nine governed settings
from the result's own fields; the context-history size rests on the default of the hash-identified
detector code. The manuscript therefore says the mismatch gives no indication of changed results,
not that it is resolved.

The 2026-09-11 editorial revision removes references to pinned model revisions and a prescribed
replication machine from the manuscript at the user's request. Exact revisions and execution
environments remain in the evidence trail; future runs must document their actual environment.
