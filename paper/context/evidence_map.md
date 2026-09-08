# Carbon manuscript evidence map

> This map belongs to the Carbon-only draft. None of these identifiers may be used in the planned
> dual-model paper, which will carry its own `synthid.v2.*` map after fresh Carbon and GENERator
> evidence passes every frozen gate.

This is the complete empirical source map for `paper/manuscript/source/main.tex`. Every number
printed in the manuscript, and every value plotted in a figure, must resolve to one of the exact
identifiers below. Wildcard identifiers are intentionally not used.

## Sampler and sequence quality

| Manuscript claim | Evidence identifier | Reviewed value |
|---|---|---:|
| Fixed-state marked-arm nominal rejection count | `synthid.carbon.sampler.nominal_rejections` | 13/256; 12.8 expected |
| Paired marked-minus-ordinary Carbon model score | `synthid.carbon.quality.nll_difference` | 0.00852 nat/6-mer |
| Declared quality summaries significant after correction | `synthid.carbon.quality.corrected_rejections` | 0/14 |
| Largest absolute standardized effect among the 14 summaries | `synthid.carbon.quality.metric_family_effects` | 0.0837 s.d. |

The model-score entry also carries the arm means, prompt-level 95% interval, p-value, standardized
effect, 256 prompt clusters, and 512 matched pairs. Those fields are uncertainty and scope on the
same measured quantity and need no separate identifiers.

## Position-independent detection

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

- Sampler and quality claims resolve to compact files in `outputs/carbon_synthid_e16_v1/`.
- Detection claims resolve to `outputs/carbon_synthid_position_independent_v1/summary.json` and
  `trials.jsonl`.
- Exact artifact hashes, commands, model revision, cohort, devices, and protocol references are in
  `evidence/measurements.yaml`.
- The completed run narratives are
  `docs/research/carbon_synthid_e16_execution_2026_08_29.md` and
  `docs/research/carbon_synthid_position_independent_execution_2026_09_02.md`.
- The detection result's protocol-file hash mismatch is disclosed in
  `docs/research/carbon_synthid_protocol_provenance_amendment_2026_09_03.md`.

## Writing boundaries

The manuscript may say that no measurable Carbon quality loss was found and that every marked read
in the tested corpus was found. It may say that the control counts are consistent with the declared
1% target. It must not say that quality is mathematically unchanged, that the operational
false-positive rate is proven below 1%, or that biological function, viability, safety, sequence
authenticity, or resistance to key recovery was shown.

Two execution gates remain open and are tracked here rather than in the manuscript, at the authors'
direction: the detection run was executed on Linux CPU and still requires replay on the documented
Apple M5 Pro, and the protocol file recorded inside that result does not match the bytes of the
retained protocol document (see
`docs/research/carbon_synthid_protocol_provenance_amendment_2026_09_03.md`). Neither is resolved.
The manuscript instead states the scientific scope limit that follows from them: this is a single
implementation on one model and one corpus, whose confirmatory replication is outstanding. Both
gates must be closed before submission.

The completed GENERator-v2 1.2B replication is fully reviewed in `evidence/measurements.yaml` and
collected in `docs/research/manuscript_evidence_packet.md`. GENERator-v2 is a co-primary model of the
rebuilt dual-model paper, so it is not supplementary work; its version-one identifiers are legacy
development history, exactly like the Carbon identifiers in this map, and no legacy identifier from
either model may enter the rebuilt paper.
