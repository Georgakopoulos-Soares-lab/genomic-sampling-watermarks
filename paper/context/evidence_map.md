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
| 2a | paired marked-minus-ordinary model score with its interval | `synthid.carbon.quality.nll_difference` |
| 2b | all 14 declared summaries as standardized effects with intervals | `synthid.carbon.quality.metric_family_effects`, `synthid.carbon.quality.corrected_rejections` |
| 3a | window strength per unedited read, by family, against the threshold | `synthid.detector.strength_separation`, `synthid.detector.clean.regions_searched` |
| 3b | prompt-level detection rate with exact intervals, by family and condition | the twelve `synthid.detector.*_rate` entries |
| 4a | window strength per marked read, by read condition | `synthid.detector.strength_separation` |
| 4b | length of the strongest window, by read condition | `synthid.detector.strongest_window_length` |

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

## Writing boundaries

The manuscript may say that no measurable quality loss was found in either model and that every
marked read in the tested corpus was found in both. It may say that the control counts are consistent
with the declared 1% target. It may say that the same implementation carried across two models, which
is portability of the implementation. It must not say that quality is mathematically unchanged, that
the operational false-positive rate is proven below 1%, that the two models are equivalent in any
respect, or that biological function, viability, safety, sequence authenticity, or resistance to key
recovery was shown.

Claims that rest on one model only must name that model. Window-strength separation, the largest
standardized effect among the 14 measures, the edit-by-edit strengths, and the winning window length
are Carbon. The aligned-detector ordinary null fit is GENERator. All four figures are Carbon.

Two execution gates remain open and are now disclosed in the manuscript's Limitations section rather
than tracked only here, because the numbers they qualify are paper-bound under
`docs/research/dual_model_v1_admission_amendment_2026_09_09.md`: generation ran on GPU hardware and
detection on x86-64 CPUs without independent replication across platforms, and the protocol file recorded
inside the Carbon detection result does not match the bytes of the retained protocol document (see
`docs/research/carbon_synthid_protocol_provenance_amendment_2026_09_03.md`). Neither is resolved. The
manuscript also states the scope limit that follows: one execution per model on one shared corpus,
whose confirmatory replication is outstanding. The M5 Pro replication remains the intended next step,
and the gates must be closed before the result is described as settled rather than as executed once.

The 2026-09-11 editorial revision removes references to pinned model revisions and a prescribed
replication machine from the manuscript at the user's request. Exact revisions and execution
environments remain in the evidence trail; the hardware requirements for future runs are unchanged.
