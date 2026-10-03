# Number register for `main.tex` (2026-10-01)

Part 1 of the condensation pass in `paper/context/condense_and_number_check_prompt.md`. Every
numeral in the Abstract, body, captions, and tables of `paper/manuscript/source/main.tex` was
extracted and grouped by the quantity it reports. Line numbers (`L###`) refer to `main.tex` as it
stood before this pass (kept outside the repository as `main_before_condense.tex`). Sources are
ledger identifiers in `evidence/measurements.yaml`, figure manifests in
`paper/figures/figure_values*.json`, or, for fixed design settings that are not measurements, the
cohort specifications in `data/` and the protocol documents named in the ledger.

All values below were recomputed or read back from their source with a script. Figure values were
compared with the manifests field by field (Figures 2-5 and S1-S2). The re-check after the rewrite
is at the end of this file.

## Discrepancies found and fixed

| # | Where | Printed | Ledger | Fix |
|---|---|---|---|---|
| 1 | Introduction, L146 | "A second cohort eight times larger" | `synthid.v2.cohort.identity`: 1,608 prompts, 1,544 held out; development cohort 256 prompts, 192 held out | The cohort is 6.3 times larger (1,608/256). The factor of eight holds only for held-out prompts (1,544/192 = 8.04) and reads (3,088/384). The rewrite drops the comparison from the Introduction; the factor is no longer printed anywhere, because every remaining use was in sentences that repeated table values. |

No other value disagreed with its source in value, rounding, unit, model, or cohort.

Found outside `main.tex` and not changed (the ledger is immutable under the evidence rules):

- `synthid.v2.detector.search_seconds_per_read` has a `notes` text saying "a 6.3x speed-up", but
  its own value fields give 0.0956 / 0.01665 = 5.74. The manuscript prints 5.7, which follows the
  value fields; the 2026-10-01 final evidence audit (fix 2) traced the 6.3 to an unledgered
  single-worker wall time. The ledger note should be corrected when the ledger is next amended.
- `evidence/measurements.yaml` does not parse under a strict YAML loader: L2222-2224 of the ledger
  (`synthid.v3.source_manifest`, `supersedes_manifest`) is a plain multi-line scalar containing
  "three files: two new batch wrappers", and the `: ` ends the scalar. `scripts/check_evidence.py`
  reads the ledger with regular expressions and is unaffected. This register loaded the ledger
  with that one phrase patched in memory.
- The known duplicate `notes:` key in `synthid.generator.detector.strongest_window_length`
  (2026-10-01 audit, item 12) is still present.

## A. Fixed design settings (not measurements)

| Quantity | Locations | Printed | Source | Source value |
|---|---|---|---|---|
| Canonical token vocabulary | L266, L297, L309, Fig. 1 caption L416, L490 | 4,096 | scope `policy` of every sampler, quality and detector entry | canonical 4096-way 6-mer distribution |
| Tournament depth | L321, L385, L390, Fig. 1 caption L418 | 30 | scope `depth` / `tournament_depth` | 30 |
| Context width | L310, L325-326, L346 (words) | four tokens | scope `context_tokens` | 4 |
| Repetition history | L329, Limitations L910 | 1,024 | scope `context_history_size`; `synthid.v2.carbon.provenance.audit` | 1024 |
| Window lengths | L344; 3,072 also L443, L461, L537, L703, L718, L754, L790, L801-802, L1071 | 384, 768, 1,536, 3,072 | scope `window_base_lengths` | [384, 768, 1536, 3072] |
| Read length | L355, L406, L408, Fig. 1 caption L422, L466 | 3,456 bases | `synthid.detector.clean.regions_searched` quantity | 3456 |
| Windows searched per read, M | L355, Fig. 1 caption L421, Fig. 3 caption L654, L747, Fig. S1 caption L1050 | 16,136 | `synthid.detector.clean.regions_searched`, `synthid.generator.detector.clean.regions_searched`, `synthid.v2.detector.windows_per_read`; manifests `windows_searched` | 16136 (recomputed: 2 x sum(3456-L+1)) |
| Target level alpha | L364; "1% target" L148, L530, L548, L634, L734, L740, L792, L814, L915, L918, L1054 | 0.01 / 1% | scope `target_sequence_false_positive_rate` | 0.01 |
| Strength threshold | L367, L614, L820 | 6.21 | `synthid.detector.strength_separation` `threshold_strength`; every Fig. 3/4 manifest `threshold_strength` | 6.2078 |
| Sampling temperature | L299 | 1.0 | `docs/research/carbon_synthid_validation_v1_protocol.md` L11 | temperature 1.0, no top-k/top-p |
| Prompt length | L431, L465 | 384 bases | `synthid.v2.cohort.identity` `prompt_bases`; development protocol | 384 |
| Source records and organisms | L431 (16, eight), L453 (12 of 16, six of eight), Limitations L888 (16) | 16 records, 8 organisms; 12 records, 6 organisms | `data/public_prompt_cohort_large_v1_sources.yaml` (`record_count: 16`, 8 organisms); `synthid.v2.cohort.identity` (`accessions: 12`, `organisms: 6`) | as printed; the 12 records are a subset of the 16 (mouse and budding yeast absent, as printed) |
| Windows per record, detection cohort | L452 | 134 | `data/public_prompt_cohort_fpr_v2_sources.yaml` `windows_per_record` | 134 (134 x 12 = 1,608) |
| Development cohort size and split | L438-440, L442, L557, L576, L598, L522, L666, L915, Fig. S1 caption L1051 | 256 prompts; 64 reserved; 192 held out | quality scope `prompts: 256`; detector scope `evaluation_prompts: 192`; `synthid.generator.aligned.ordinary_null_fit` command `--calibration-prompts 64` | 256; 64; 192 |
| Detection cohort size and split | Abstract L89, L452, L455, L526, Fig. 3 caption L655, L738, Table 2 caption L760 | 1,608 prompts; 64 set aside; 1,544 held out | `synthid.v2.cohort.identity` | 1608; 64; 1544 |
| Continuation length and arm sizes | L460-461 | 512 tokens, 3,072 bases; 512 marked and 512 ordinary per model | quality scope `generated_bases_per_sequence: 3072`, `sequences_per_arm: 512` | as printed |
| Matched pairs | L576, Fig. 2 caption L598 | 512 pairs from 256 prompts | `synthid.*.quality.nll_difference` `matched_pairs`, `prompt_clusters` | 512; 256 |
| Sampler check design | L488, L490, L492, L496, L570 | token index 64; 5,000 draws; 999 replicates; eight control states | `synthid.{carbon,generator}.sampler.nominal_rejections` (command `--state-token-index 64`; `samples_per_state`, `monte_carlo_replicates`, `deliberately_incorrect_control_states`) | 64; 5000; 999; 8 |
| Bootstrap and sign-flip replicates | L518-519 | 20,000; 100,000 | quality and sampler commands `--bootstrap-replicates 20000 --permutation-replicates 100000` | as printed |
| Sequence measures | L505-508 (Thirteen + model score), L576, Fig. 2 caption L599-600, Limitations L947 | 14 | `synthid.*.quality.corrected_rejections` `tested_metrics` | 14 |
| Jensen-Shannon k | L507-508 | k = 1, 2, 3 | metric names `js_divergence_from_prompt_k{1,2,3}_bits` | as printed |
| Edit-rate design | L537-538, L546 | r = 0.03, 0.1, 0.5, 1, 2, 5, 10%; 1, 3, 15, 31, 61, 154, 307 edits; 3,088 reads per cell | `synthid.v3.*.edit_rate_full_detection_ceiling` (`events_per_read_by_rate`, `reads_per_cell`); Fig. 5 manifest `edit_rates`, `edits_per_read` | as printed (recomputed round(3072 r)) |
| Indel span | L539-540, Fig. 5 caption L790 (words) | one to five bases | evidence map, edit-rate paragraph (`max_indel_bases=5`) | 1-5 |
| Hardware | L407 (AMD EPYC 7763), L473-474 (x86-64, A100) | as printed | `synthid.v2.detector.search_seconds_per_read` `hardware`; detector scope `detection_device`; `docs/research/synthid_v2_fpr_direct_a100_execution_2026_09_21.md` | as printed |

## B. Sampler check (development cohort)

| Quantity | Locations | Printed | Ledger identifier | Ledger value |
|---|---|---|---|---|
| Marked-sampler nominal rejections, Carbon | L557, L565 | 13 of 256 | `synthid.carbon.sampler.nominal_rejections` | 13; `tested_states` 256 |
| Marked-sampler nominal rejections, GENERator | L557 | 5 of 256 | `synthid.generator.sampler.nominal_rejections` | 5 |
| Expected under chance | L558, L566 | 12.8 | both entries `expected_rejections_under_null` | 12.8 |
| Ordinary-sampler nominal rejections | L558, L565 | 12 (Carbon), 14 (GENERator) | `ordinary_control_rejections` | 12; 14 |
| Benjamini-Hochberg rejections, GENERator, both samplers | L563-564 (words) | none | `synthid_rejections_after_benjamini_hochberg`, `ordinary_rejections_after_benjamini_hochberg` | 0; 0 |
| Benjamini-Hochberg rejections, Carbon | L564-565 | not retained | no field | as printed |
| Negative control | L567 (words) | all eight states, each model | `deliberately_incorrect_control_rejections` / `_states` | 8/8 each |
| Bonferroni level and Monte Carlo floor | L560-562 | 0.05; 0.05/256 = 1.95 x 10^-4; 10^-3 | derived from 256 states and 999 replicates | 1.953 x 10^-4; 1/1000 |
| Expected count per category | L491 | about 1.2 | derived: 5,000 / 4,096 | 1.22 |

## C. Sequence-quality proxies (development cohort)

| Quantity | Locations | Printed | Ledger identifier / manifest | Source value |
|---|---|---|---|---|
| Model-score difference, Carbon | L581-582 | +0.00852 nat/token; 95% interval -0.04426 to +0.05973; P = 0.75 | `synthid.carbon.quality.nll_difference`; `figure_values.json` `fig2_quality` | 0.008521; [-0.044260, 0.059733]; 0.7506 |
| Model-score difference, GENERator | L582-583 | -0.00564; -0.05614 to +0.04378; P = 0.83 | `synthid.generator.quality.nll_difference`; `fig2_quality_generator` | -0.005637; [-0.056142, 0.043782]; 0.8299 |
| Smallest adjusted P | L578 | 0.85 (Carbon), 0.73 (GENERator) | `synthid.{carbon,generator}.quality.corrected_rejections` `smallest_adjusted_p_value` | 0.8528; 0.7310 |
| Corrected rejections | L577-578, Fig. 2 caption L599-600 (words) | none of 14 | same entries, `value` | 0; 0 |
| Largest absolute standardized effect | L584-585 | 0.084 SD Carbon (longest single-base run); 0.111 SD GENERator (mean single-base run) | `synthid.{carbon,generator}.quality.metric_family_effects` | 0.08374 (`longest_homopolymer_run`); 0.11138 (`mean_homopolymer_run`) |

## D. Detection, development cohort (former Table 1, Figure S1)

| Quantity | Locations | Printed | Ledger identifier / manifest | Source value |
|---|---|---|---|---|
| Correct-key reads detected, both models, all four conditions | Abstract L86, L607, Table 1 L681-684, Conclusion L964 | 384/384 | `synthid.detector.{clean,substitution_1nt,insertion_1nt,deletion_1nt}.correct_key_rate`; `synthid.generator.detector.*.correct_key_rate` | 384/384 each |
| Ordinary positives, Carbon | L608-609, Table 1 | 1/384 every condition (same prompt and draw) | `synthid.detector.*.ordinary_rate` | 1/384 each |
| Wrong-key positives, Carbon | L609, Table 1 | 0/384 | `synthid.detector.*.wrong_key_rate` | 0/384 each |
| Ordinary positives, GENERator | L609, Table 1 | 0/384 | `synthid.generator.detector.*.ordinary_rate` | 0/384 each |
| Wrong-key positives, GENERator | L609-610, Table 1, Fig. S1 caption L1053 | 1/384 unedited, substitution, insertion; 0/384 deletion | `synthid.generator.detector.*.other_key_rate` | 1, 1, 1, 0 of 384 |
| "at most one positive read per model, control, and condition" | Abstract L87-88 | at most one | as above | max 1 |
| One positive as a percentage of reads | L611 | 0.26% | derived 1/384 | 0.2604% |
| Prompt-level counts | Table 1 L686 | 192/192, 1/192, 0/192 (Carbon); 192/192, 0/192, 1/192 (GENERator) | `prompts_with_both_draws_detected`, `prompts_with_at_least_one_positive_draw`; Fig. S1 manifests `positive_prompts` | as printed |
| Exact two-sided 95% intervals | L631-633, Table 1 L687, Limitations L916-917 | 98.10-100%; 0.013-2.868%; 0-1.903% | `exact_95_interval_for_both_draws`, `exact_95_interval`; Fig. S1 manifests | [0.98097, 1]; [0.000132, 0.028676]; [0, 0.019030] |
| Aligned-detector ordinary positives, GENERator | L638-639 | 2, 6, 6, 4 prompts; about five expected; P = 0.25-0.87 | `synthid.generator.aligned.ordinary_null_fit` | [2, 6, 6, 4]; [4.995, 5.288, 4.984, 5.114]; P [0.245, 0.870, 0.763, 0.838] |

## E. Window strength, both cohorts

| Quantity | Locations | Printed | Ledger identifier / manifest | Source value |
|---|---|---|---|---|
| Median unedited marked strength, development | L613 | 790.6 (Carbon), 798.8 (GENERator) | `synthid.v2.strength_gap.cohort_strength_summary` `primary_cohort`; `synthid.{,generator.}detector.strength_separation`; Fig. S1 manifests | 790.615; 798.780 |
| Weakest unedited marked strength, development | L616 | 124.8, 19.6 | same | 124.777; 19.615 |
| Weakest, detection cohort | L626-627 | 237.6, 123.8 | `cohort_strength_summary` `second_cohort`; Fig. 3 manifests `clean_strength_min` | 237.630; 123.775 |
| Median unedited, detection cohort | L751-752 | 792.9, 799.7 | `synthid.v2.detector.correct_key_strength_by_condition`; `cohort_strength_summary`; Fig. 3/4 manifests | 792.878; 799.691 |
| Median after one substitution, detection | L752 | 777.6, 783.8 | `correct_key_strength_by_condition`; Fig. 4 manifests | 777.561; 783.847 |
| Median after one insertion, detection | L753 | 441.8, 443.1 | same | 441.798; 443.110 |
| Median after one deletion, detection | L753 | 437.7, 438.5 | same | 437.655; 438.525 |
| Strength lost to one edit | L822-823 | about 2% (substitution), about 45% (insertion or deletion) | derived from the medians above | 1.93-1.98%; 44.3-45.2% |
| "starts near strength 800" | L820 | 800 | derived from medians 792.9, 799.7 | as printed |
| Weakest GENERator read: repeated contexts | L619 | 174 | `synthid.v2.strength_gap.explained_component` `generator_repeated_contexts` | 174 |
| Weakest GENERator read: scored tokens | L620 | 334 of a possible 508 | `generator_observed_scored_tokens`; `synthid.v2.strength_gap.scored_tokens_per_read` | 334; 508 (334 + 174 = 508) |
| Weakest GENERator read: fraction of 1s | L620 | 54.6% | `generator_observed_positive_fraction` | 0.5458 |
| Median fraction of 1s | L621 | 74%, both models | `cohort_strength_summary` `primary_cohort_median_mark_bit_positive_fraction` | 0.7392; 0.7403 |
| Share of the weakest-read gap closed by restoring tokens | L622 | 9% | `synthid.v2.strength_gap.explained_component` `value` | 0.0914 |
| Control strengths "near or below the threshold" | L614-616 (words) | qualitative | `clean_ordinary_maximum`, `clean_wrong_key_maximum` | 6.60 / 5.69 (Carbon); 5.58 / 6.85 (GENERator) |

## F. Length of the strongest window

| Quantity | Locations | Printed | Ledger identifier / manifest | Source value |
|---|---|---|---|---|
| Full window strongest, unedited, development | L718-719 | 383 of 384 (Carbon), 381 of 384 (GENERator) | `synthid.{,generator.}detector.strongest_window_length`; Fig. S2 manifests | 383; 381 |
| After one insertion, development | L719 | 203, 200 | same | 203; 200 |
| After one deletion, development | L720 | 232, 227 | same | 232; 227 |
| Full window strongest, unedited, detection | L754-755 | 3,087 (Carbon), 3,085 (GENERator) of 3,088 | `synthid.v2.{carbon,generator}.detector.clean.correct_key_rate` `winning_window_base_length_counts`; Fig. 4 manifests | 3087; 3085 |
| After one insertion, detection | L755 | 1,724, 1,732 | `*.insertion_1nt.correct_key_rate` | 1724; 1732 |
| After one deletion, detection | L755-756 | 1,663, 1,671 | `*.deletion_1nt.correct_key_rate` | 1663; 1671 |
| "almost half" shorter after an insertion or deletion | Fig. 4 caption L704 | words | same | 44-46% |

## G. Detection cohort: detection and false-positive bounds (former Table 2, Figure 3)

| Quantity | Locations | Printed | Ledger identifier / manifest | Source value |
|---|---|---|---|---|
| Correct-key reads detected, every model and condition | Abstract L90, L736, Table 2 L776-779, Fig. 3 caption, Conclusion L965 | 3,088/3,088 | `synthid.v2.{carbon,generator}.detector.*.correct_key_rate` `read_detections`/`read_trials` | 3088/3088 each |
| Two-sided 95% interval, prompt-level detection | L737 | 99.76-100% | same, `exact_two_sided_95_interval` | [0.99761, 1] |
| Ordinary positives and one-sided bounds, Carbon | Table 2; L737-738 ("three or four") | 3 (0.501), 3 (0.501), 3 (0.501), 4 (0.592) | `synthid.v2.carbon.detector.*.ordinary_rate` | 3, 3, 3, 4; 0.50141, 0.50141, 0.50141, 0.59186 |
| Ordinary positives and bounds, GENERator | Table 2; L738 ("five to seven"); L918 ("seven") | 5 (0.680), 5 (0.680), 6 (0.766), 7 (0.850) | `synthid.v2.generator.detector.*.ordinary_rate` | 5, 5, 6, 7; 0.67968, 0.67968, 0.76554, 0.84987 |
| Wrong-key positives and bounds, Carbon | Table 2; L741 ("five to nine") | 5 (0.680), 5 (0.680), 6 (0.766), 9 (1.015) | `synthid.v2.carbon.detector.*.wrong_key_rate` | 5, 5, 6, 9; 0.67968, 0.67968, 0.76554, 1.01497 |
| Wrong-key positives and bounds, GENERator | Table 2; L741 ("two or three") | 2 (0.407), 2, 2, 3 (0.501) | `synthid.v2.generator.detector.*.wrong_key_rate` | 2, 2, 2, 3; 0.40719 x3, 0.50141 |
| Largest ordinary bound | Abstract L92, L739, Limitations L918, Conclusion L967 | 0.850% (GENERator, deletion) | `synthid.v2.detector.fpr_upper_bound` | 0.0084987 |
| Wrong-key cell above 1% | Abstract L92-93, L742, Limitations L919, Table 2 | 1.015% (Carbon, deletion) | `synthid.v2.carbon.detector.deletion_1nt.wrong_key_rate` | 0.0101497 |
| Pre-declared threshold for a bound below 1% | L740 | at most eight positive prompts | `fpr_upper_bound` `predeclared_sub_one_percent_threshold_positives` | 8 |
| Reads per condition in Figure 3a | Fig. 3 caption L651-652 | 3,088 per family | `sequence_trials_per_cell` | 3088 |
| Each control positive from a different prompt | Table 2 caption L762 | words | `read_detections` = `prompt_positives` in every control cell | as printed |

## H. Conservatism of the correction (detection cohort)

| Quantity | Locations | Printed | Ledger identifier | Ledger value |
|---|---|---|---|---|
| Realized per-read rate on ordinary reads, pooled over four conditions | L744-745 | 0.105% (Carbon), 0.186% (GENERator) | `synthid.v2.detector.empirical_familywise_rate` | 0.0010525 (13/12,352); 0.0018620 (23/12,352) |
| Factor below alpha | L745 | 9.5, 5.4 | same, `conservatism_factor_vs_target` | 9.5015; 5.3704 |
| Effective number of independent tests | L746 | about 828-852 | `synthid.v2.detector.effective_independent_windows` | 827.7-852.4 over eight cells |
| Ratio to windows searched | L747 | about 19 times fewer than 16,136 | same, `inflation_range` | 18.9-19.5 |

## I. Edit-rate series (detection cohort)

| Quantity | Locations | Printed | Ledger identifier / manifest | Source value |
|---|---|---|---|---|
| Full-detection range | Abstract L96-97, Intro L149, L801-804, Conclusion L967 | complete or nearly complete through 2% (61 edits) | `synthid.v3.carbon.detector.edit_rate_full_detection_ceiling` (0.02); `synthid.v3.generator...` (0.01; one miss at 2%) | as printed |
| GENERator mixed series at 2% | L803-804, L808-809 | 3,087 of 3,088 | generator ceiling entry, `indel` 0.02 = 0.99968; Fig. 5 manifest `detected: 3087` | 3087 |
| Substitutions at 5% | L804-805 | 3,088 (Carbon), 3,087 (GENERator) | ceiling entries `substitution` 0.05 | 1.0; 0.99968 |
| Insertions and deletions at 5% | Abstract L97 ("about 93%"), L806 | 92.9-93.9% | ceiling entries `indel`, `insertion`, `deletion` at 0.05 | 93.26-93.59% (Carbon), 92.91-93.91% (GENERator) |
| Substitutions at 10% | L806 | 19.7% (Carbon), 18.7% (GENERator) | ceiling entries `substitution` 0.1 | 19.689%; 18.718% |
| Other edit types at 10% | L807 | 4.6-5.9% | ceiling entries | 5.44-5.86% (Carbon), 4.57-5.38% (GENERator) |
| "failed for most reads at 10%" | Conclusion L968 | words | as above | at most 19.7% detected |
| Agreement between models | L807-808 | within one percentage point | `synthid.v3.detector.edit_rate_model_agreement` | 0.0097 (substitution, 10%) |
| Ordinary reads, pooled | L812 | 132 of 89,552 (0.15%), 116 of 89,552 (0.13%) | `synthid.v3.{carbon,generator}.detector.edit_rate_null_rate` | 132/89552 = 0.1474%; 116/89552 = 0.1295% |
| Largest single ordinary cell | L813-814 | 0.29% (GENERator, mixed, 1%) | generator null entry `worst_cell` | indel 0.01, 0.29145% |
| Ordinary reads per point, Figure 5c | Fig. 5 caption L792 | 12,352 | Fig. 5 manifest `ordinary_pooled_over_edit_types` `reads` | 12352 (4 x 3,088) |
| Clean-stretch argument | L816-817 | about 100 bases at 1%, shorter than 384 | derived: 31 events per 3,072 bases | about 96-99 bases |

## J. Search cost

| Quantity | Locations | Printed | Ledger identifier | Ledger value |
|---|---|---|---|---|
| Median single-threaded time per read | L406-407 | 0.0956 s (3,456 bases); 0.245 s (6,912); 0.902 s (13,824) | `synthid.v2.detector.search_seconds_per_read` | 0.09561; 0.24482; 0.90222 |
| Peak memory per process | L408 | 27.9 MiB (3,456 bases); 69.1 MiB (13,824) | `synthid.v2.detector.peak_memory_mib` | 27.918; 69.078 |
| Parallel throughput | L408-410 | 16 workers; 0.0167 s per read; 5.7 times | `search_seconds_per_read` `wall_seconds_per_read_at_16_workers` | 0.016651; ratio 5.742 (see the ledger-note item above) |
| Twelve token frames | L400 (words) | two orientations by six phases | design | 12 |

## K. Window geometry (derived from design settings)

| Quantity | Locations | Printed | Derivation | Recomputed |
|---|---|---|---|---|
| Tokens in the shortest window | L386 | 64 | 384 / 6 | 64 |
| Scored tokens and mark bits, shortest window | L387-388 | at most 60; at most 1,800 | 64 - 4; 60 x 30 | 60; 1,800 |
| Ones needed at threshold | L388-389 | 1,004 of 1,800, about 56% | smallest S with Binomial(1800, 1/2) tail <= 0.01/16,136 | 1,004 (55.8%) |
| All-ones window that reaches the threshold | L389-390 | 21 mark bits | smallest n with 2^-n <= 0.01/16,136 | 21 |
| Mark bits per scored token | L385, L390 | 30 | tournament depth | 30 |

## L. Numerals that are not reported values

Model names (Carbon-500M, GENERator-v2 1.2B, GENERator-v2-eukaryote-1.2b-base); equation
constants (1 + g, Binomial(n, 1/2), 2^m, 10 in log10); "x86-64"; "A100"; "EPYC 7763";
"HMAC-SHA-256"; the grant number R35GM155468; and LaTeX layout lengths (0.15em, 0.35em, 1.08,
4pt, 12pt). These carry no measurement and need no ledger source.

## Checks

- **Same quantity, same value and precision everywhere.** Yes, apart from item 1. The largest
  ordinary bound is 0.850% in all five places; 1.015% in all four; 2.868% and 1.903% in all three;
  98.10-100% in both; 6.21 in all three; 16,136 in all five.
- **Text, tables, captions, and plotted values agree.** Every Table 1 and Table 2 cell matches the
  ledger. Every Figure 3, 4, S1, and S2 median, minimum, prompt count, interval, and window count
  matches its manifest and the ledger. Every Figure 5 cell matches both edit-rate entries. Figure 2
  model-score values match the ledger.
- **Counts and denominators.** 3,088 = 2 x 1,544; 384 = 2 x 192; 1,608 = 134 x 12 = 1,544 + 64;
  12,352 = 4 x 3,088; 89,552 = 29 x 3,088 (seven rates x four series, plus unedited reads);
  1/384 = 0.26%; 13/12,352 = 0.105%; 23/12,352 = 0.186%; 132/89,552 = 0.15%; 116/89,552 = 0.13%.
- **Ratios.** 9.5 and 5.4 follow from 0.01 / 0.105% and 0.01 / 0.186%; 19 times from
  16,136 / 827.7-852.4; 5.7 times from 0.0956 / 0.0167; 2% and 45% from the detection-cohort
  medians; "eight times as many held-out prompts" (L733) and "eight times as many reads" (L720)
  from 1,544/192 and 3,088/384. "Eight times larger" (L146) did not follow; see item 1.
- **Model and cohort.** Every value is attached to the right model and cohort. The GENERator-only
  values (aligned-detector diagnostic, weakest-read analysis, 3,087 at 2% mixed) name GENERator;
  the Carbon-only values (1.015%, 13 and 12 nominal rejections, protocol audit) name Carbon.
