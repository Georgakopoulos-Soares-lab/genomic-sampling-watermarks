# Manuscript evidence packet: Carbon and GENERator SynthID runs

## Purpose and scope

This document is the single writing handoff for the completed SynthID experiments. It consolidates
the design, reviewed measurements, provenance, admissible wording, and unresolved limitations from
the Carbon-500M paper run and the matched GENERator-v2 1.2B replication.

The present manuscript is Carbon-only under `paper/AGENTS.md`. Carbon measurements below are the
paper-targeted evidence, subject to the provenance and M5 replay gate stated at the end of this
packet. GENERator measurements are fully reviewed supplementary evidence but must remain outside
the manuscript unless its scope is explicitly expanded. No removed watermark method,
multiple-edit experiment, or detector-guided attack belongs in either result set.

## One-paragraph study description

The study adapts the SynthID binary tournament sampler to genomic models that generate canonical
DNA 6-mers. At every generation step, the model provides a probability distribution over 4,096
possible 6-mers. SynthID uses a secret key, the previous four generated tokens, and each candidate
token to derive 30 hidden binary values and reweight the sampling tournament. The verifier later
recomputes those values from DNA alone. It receives the key and fixed public settings, but not the
model, prompt, generation seed, strand, 6-mer phase, or boundary between prompt and generated DNA.
It searches both strands, every nucleotide start, and four fixed region lengths, then corrects one
read-level decision for the entire search.

## Frozen design shared by both models

| Design item | Frozen value |
|---|---|
| Watermark | `synthid-tournament-v1` only |
| Ordinary control | Direct categorical sampling from the same model-specific 6-mer law |
| Canonical vocabulary | 4,096 DNA 6-mers |
| Temperature and truncation | 1.0; no top-k or top-p truncation |
| Public cohort | 256 RefSeq prompts, each 384 bases |
| Prompt split | 64 detector-summary prompts; 192 untouched evaluation prompts |
| Draws | Two per prompt, with distinct replay seeds in both arms |
| Fixture keys | Two public keys, one per SynthID draw |
| Continuation | 512 tokens = 3,072 generated bases |
| Stored generation corpus | 1,024 sequences per model: 512 SynthID and 512 ordinary |
| SynthID settings | 30 layers, four generated-token context, 1,024-context repetition history |
| Sampler check | 256 states, 5,000 samples per state and arm, 999 Monte Carlo replicates |
| Final observed read | 384-base prompt plus 3,072-base continuation |
| Detector search | Both strands, every nucleotide start, 384/768/1,536/3,072-base regions |
| Global decision | Exact local fair-binomial tail plus Bonferroni correction over every region |
| Declared read-level target | 1% false-positive probability |
| Tested read conditions | Clean; exactly one nucleotide substitution, insertion, or deletion |
| Final grid | 192 prompts × 2 draws × 3 families × 4 conditions = 4,608 decisions/model |
| Independent statistical unit | Prompt; the two draws are paired repetitions |

The 64 reserved prompts selected the unweighted mean from two declared score summaries. They did
not fit the final detector threshold. The threshold is analytic, and the final 192 prompts were not
used for detector selection.

## Model-specific definitions

| Item | Carbon paper run | GENERator supplementary run |
|---|---|---|
| Model | `HuggingFaceBio/Carbon-500M` | `GenerTeam/GENERator-v2-eukaryote-1.2b-base` |
| Revision | `9796b752108258c1d365089f842e62e6c0547704` | `c41b0018da9ee13b9e96ee54647de8da381ccd72` |
| Policy | `C_tok` | `G_tok` |
| Sampling law | Normalized logits for canonical 6-mer tokens | Normalized logits for tokenizer IDs 32–4,127 |
| Generation device | CUDA bfloat16 | CUDA bfloat16 |
| Likelihood-analysis device | CPU bfloat16 | CUDA bfloat16 |
| Final detector device | Linux CPU | Linux CPU |

Both policies are direct token laws. Neither retained experiment uses a base-marginal helper. The
different likelihood-analysis devices are an execution difference, so the runs have scientific
protocol parity but are not bit-for-bit hardware replicas.

## Sampler correctness evidence

The experiment compared empirical token counts with the exact probability law that each arm was
supposed to sample. A fixed SynthID key deliberately reweights the model distribution, so the
watermarked arm was tested against its calculated fixed-key tournament law rather than against the
ordinary model law.

| Model | SynthID nominal results below 0.05 | Ordinary nominal results below 0.05 | Expected by chance per arm | Deliberately incorrect controls |
|---|---:|---:|---:|---:|
| Carbon | 13/256 | 12/256 | 12.8 | 8/8 rejected after correction |
| GENERator | 5/256 | 14/256 | 12.8 | 8/8 rejected after correction |

No real sampling arm showed a corrected rejection. Carbon's nominal counts are close to the chance
expectation. GENERator's five SynthID nominal results are conservative rather than evidence of
excess sampler error. All deliberately incorrect controls were detected. The supported claim is
that the implementation behaved as intended at the 256 tested states and the 5,000-draw
resolution; this is not a proof for every possible model state.

Evidence identifiers:

- Carbon: `synthid.carbon.sampler.nominal_rejections`.
- GENERator: `synthid.generator.sampler.nominal_rejections`.

## Model-quality evidence

The primary quality measure was teacher-forced negative log-likelihood under the same model and
direct 6-mer policy used to generate the continuation. The prompt was supplied as context, but only
the 512 generated tokens contributed to the loss. Lower values mean that the model assigns greater
probability to the sequence.

| Quantity | Carbon | GENERator |
|---|---:|---:|
| Ordinary mean | 7.533859 nat/6-mer | 7.800291 nat/6-mer |
| SynthID mean | 7.542380 nat/6-mer | 7.794654 nat/6-mer |
| Paired SynthID-minus-ordinary difference | +0.008521 nat/6-mer | -0.005637 nat/6-mer |
| Prompt-level 95% interval | -0.044260 to +0.059733 | -0.056142 to +0.043782 |
| Paired-test p-value | 0.7506 | 0.8299 |
| Standardized effect | +0.02007 | -0.01387 |
| Declared summaries significant after correction | 0/14 | 0/14 |
| Smallest adjusted p-value | 0.8528 | 0.7310 |

Both point estimates are tiny, both intervals contain zero, and neither model has a corrected
quality-summary difference. The manuscript-safe conclusion for Carbon is “no measurable quality
loss was found.” The analogous conclusion is supported for the supplementary GENERator run. Do not
replace that wording with “quality is unchanged” or “the distributions are identical.” These are
model-likelihood and sequence-statistic measurements, not biological-function tests.

Evidence identifiers:

- Carbon: `synthid.carbon.quality.nll_difference` and
  `synthid.carbon.quality.corrected_rejections`.
- GENERator: `synthid.generator.quality.nll_difference` and
  `synthid.generator.quality.corrected_rejections`.

## Final position-independent detection evidence

### Carbon

| Read condition | Correct-key SynthID | Matched ordinary Carbon | SynthID with other draw's key |
|---|---:|---:|---:|
| Clean | 384/384 | 1/384 | 0/384 |
| One nucleotide substitution | 384/384 | 1/384 | 0/384 |
| One nucleotide insertion | 384/384 | 1/384 | 0/384 |
| One nucleotide deletion | 384/384 | 1/384 | 0/384 |

The four ordinary positives are one prompt and draw repeated across four conditions because the
single edit lay outside its strongest region. Thus the clean ordinary result is one positive among
192 prompt clusters, with an exact 95% interval of 0.0132%–2.8676%. Zero other-key prompt clusters
were positive, giving an exact 95% upper bound of 1.9030%. All 192 prompts had both correct-key
draws detected; the exact 95% lower bound is 98.097%.

Evidence identifiers:

- `synthid.detector.clean.regions_searched`;
- `synthid.detector.clean.correct_key_rate`;
- `synthid.detector.clean.ordinary_rate`;
- `synthid.detector.clean.wrong_key_rate`;
- `synthid.detector.substitution_1nt.correct_key_rate`;
- `synthid.detector.substitution_1nt.ordinary_rate`;
- `synthid.detector.substitution_1nt.wrong_key_rate`;
- `synthid.detector.insertion_1nt.correct_key_rate`;
- `synthid.detector.insertion_1nt.ordinary_rate`;
- `synthid.detector.insertion_1nt.wrong_key_rate`;
- `synthid.detector.deletion_1nt.correct_key_rate`;
- `synthid.detector.deletion_1nt.ordinary_rate`; and
- `synthid.detector.deletion_1nt.wrong_key_rate`.

### GENERator

| Read condition | Correct-key SynthID | Matched ordinary GENERator | SynthID with other draw's key |
|---|---:|---:|---:|
| Clean | 384/384 | 0/384 | 1/384 |
| One nucleotide substitution | 384/384 | 0/384 | 1/384 |
| One nucleotide insertion | 384/384 | 0/384 | 1/384 |
| One nucleotide deletion | 384/384 | 0/384 | 0/384 |

The first three other-key positives are one prompt and draw repeated, not three independent events.
The ordinary prompt-level result is zero positives among 192 clusters, with an exact 95% upper
bound of 1.9030%. The one-positive other-key result has an exact interval of
0.0132%–2.8676%. Every correct-key sequence was detected in every condition.

Evidence identifiers use the prefix `synthid.generator.detector` and enumerate the exact clean,
`substitution_1nt`, `insertion_1nt`, and `deletion_1nt` cells in
`evidence/measurements.yaml`. The clean search-count identifier is
`synthid.generator.detector.clean.regions_searched`.

## Cross-model conclusion

Carbon and GENERator have protocol and conclusion parity:

- neither model showed measurable quality degradation;
- both detected 384/384 correct-key reads in all four final conditions;
- both ordinary and other-key results are statistically compatible with the declared 1% target;
  and
- both sampler checks support the intended implementation at the tested states and resolution.

They do not have identical random counts. Carbon produced one ordinary positive prompt and no
other-key positive; GENERator produced no ordinary positive and one other-key positive. This is not
a meaningful performance difference at 192 independent prompt clusters. The data are also too
small to prove that either operational false-positive rate is below exactly 1%.

## Aligned diagnostics and validator amendment

The aligned detector runs were engineering and calibration-fit diagnostics, not the final
boundary-unaware result. Carbon detected 383/384 held-out SynthID continuations at 384, 768, and
1,536 bases and 384/384 at 3,072 bases. GENERator detected 384/384 at every aligned length.

For GENERator, the ordinary counts over all 512 outputs were 2, 6, 6, and 4 at 384, 768, 1,536,
and 3,072 bases. The prompt-level exact fit p-values were 0.245, 0.870, 0.763, and 0.838. The
original validator's percentile bootstrap produced a discrete rare-event boundary error at 384
bases. It was replaced with the exact prompt-level Poisson-binomial check. This changed only the
validator: it did not change generation, calibration, scores, thresholds, or decisions. The
amendment is `docs/research/generator_synthid_validator_amendment_2026_09_03.md`.

Only GENERator's aligned null-fit diagnostic currently has a dedicated ledger entry,
`synthid.generator.aligned.ordinary_null_fit`. Do not add the other aligned numbers to the
manuscript unless separate ledger entries are created.

## Verification status

The 2026-09-03 consolidation reran the retained repository tests and artifact checks. All 108 unit
tests passed; four optional comparisons with an external pinned upstream checkout were skipped
because that checkout was not configured. Ruff, shell-script syntax, environment diagnostics, and
the evidence checker passed. The evidence checker resolved 33 measurements, 12 cited artifact
digests, nine protocol/execution/amendment documents, and all 16 Carbon manuscript mappings.

The complete GENERator artifact tree passed its strict end-to-end validator, including the exact
prompt-level null-fit calculations. The compact GENERator position-independent bundle separately
passed its strict validator with 4,608 decisions, 192 prompts, and 12 result cells. The Carbon
position-independent trial bundle passes every scientific identity, statistic, decision, and
source-code digest check, but its strict validator correctly stops at the known protocol-document
hash mismatch described in the provenance amendment below. That exception is not silently waived.

## Artifact and provenance index

| Model and evidence class | Compact artifact | SHA-256 |
|---|---|---|
| Carbon generation | `outputs/carbon_synthid_e16_v1/generation_summary.json` | `6ab5c5948b921dbed721384cf360c7f91c2f36889f8c4a9ba52f698f0249ac07` |
| Carbon sampler | `outputs/carbon_synthid_e16_v1/distribution_summary.json` | `3e0016c25d7c45d32c8d3aef0066b73e3366772eae485f3e7de6518f6de77237` |
| Carbon quality | `outputs/carbon_synthid_e16_v1/sequence_comparison_summary.json` | `6c9a73ea92592465b3a7c5121ab6a7e296839bc22a02edaa8050c36ebad7b0da` |
| Carbon aligned detection | `outputs/carbon_synthid_e16_v1/detection_summary.json` | `ad3eb9e43e734ae146693e4f68aafc2b2000ac9aaa6b825d08965657eb709dc5` |
| Carbon full-run report | `outputs/carbon_synthid_e16_v1/report.md` | `afa43ca7093b14e1089a5a0b3f13e288dac7397f57767bc689216d9e64368316` |
| Carbon final detector summary | `outputs/carbon_synthid_position_independent_v1/summary.json` | `cc5f58d104e82b96ec87dfa3e0c305ea5d08717dbffe0b83d3cddbf5208bffa6` |
| Carbon final detector trials | `outputs/carbon_synthid_position_independent_v1/trials.jsonl` | `323d998561843dda5b204c33d3de9d6a281aaa700ceddc535b0d7af32e0ac81c` |
| Carbon final detector report | `outputs/carbon_synthid_position_independent_v1/report.md` | `ea9b2957a6b88990ba3fa5df7da3756a5fb48b4ebe02114875aeccd614266022` |
| GENERator generation | `outputs/generator_synthid_e16_v1/generation_summary.json` | `7b1b132d3d5c79c01bd914059d28e968b4c27fec2da47d0c297791c23c2e6a4e` |
| GENERator sampler | `outputs/generator_synthid_e16_v1/distribution_summary.json` | `77090622d7901ce6b459c45c7f22eee7b51bf1ee5535b6d960c560e281910783` |
| GENERator quality | `outputs/generator_synthid_e16_v1/sequence_comparison_summary.json` | `d8e3c03b2d0e3a2639c521889ea29dd804e8a741d3cf43818cb79f31ae821401` |
| GENERator aligned detection | `outputs/generator_synthid_e16_v1/detection_summary.json` | `0bd171a3886ed823c31123271b1f22f5650bcf0b5a0767947467356605f1a72d` |
| GENERator full-run report | `outputs/generator_synthid_e16_v1/report.md` | `bd07b21576d4cf6cbb85b0d1288d814e090994e913f65c05cbc918418a637e24` |
| GENERator final detector summary | `outputs/generator_synthid_position_independent_v1/summary.json` | `ac28bf5ed078fccd1eac5a97cabdd4f2a4e67f07a75d291aa3c5e0abd15830f7` |
| GENERator final detector trials | `outputs/generator_synthid_position_independent_v1/trials.jsonl` | `3de1d8f7b8a946d3a5149f48ac30e357ceb2fa812eddbe6a11a5e836c7106d99` |
| GENERator final detector report | `outputs/generator_synthid_position_independent_v1/report.md` | `da708b0f86cdbe93cf473c71824a2a8ec4bc2d6cedfa3fb1e0dc25fe8785a13b` |

The cohort content SHA-256 is
`8f7f7bba52f26837cdef5f17b542e01ab61eb1ddf7735d43dcd6f7b8d0986308`.
Model, tokenizer, dataset, command, device, configuration, and execution references appear in each
ledger entry. Raw generated DNA, raw keys, model weights, and private data are not part of this
packet.

## Claim wording for the next manuscript revision

When paired with the disclosed provenance and execution limits, the following wording stays within
the recorded Carbon evidence:

1. “We found no measurable reduction in Carbon likelihood or in the declared sequence summaries
   after applying the SynthID tournament sampler.”
2. “The position-independent detector identified all 384 held-out correct-key reads when clean and
   after one nucleotide substitution, insertion, or deletion.”
3. “The detector controlled one read-level decision over both strands, every nucleotide start, and
   four fixed region lengths.”
4. “The ordinary and other-key outcomes were compatible with the declared 1% target, but 192
   independent prompt clusters cannot establish an operational false-positive rate below 1%.”
5. “The public fixture keys support reproducibility and do not test recovery resistance for a
   secret deployment key.”

If the paper scope is later expanded, the parallel GENERator wording may state that the same frozen
protocol produced no measurable model-quality loss and 384/384 correct-key detections in every
condition. It should call GENERator a replication, report the different null counts directly, and
avoid claiming that the models are numerically identical.

## Claims that the evidence does not support

- The watermark leaves a fixed-key next-token distribution unchanged.
- The generated DNA has preserved biological function, viability, or safety.
- The detector authenticates an exact sequence or identifies the true boundary with certainty.
- The operational false-positive rate is proven below exactly 1%.
- A secret key cannot be recovered from many observed watermarked examples.
- Robustness extends beyond one ordinary nucleotide edit.
- Carbon and GENERator are bitwise, architectural, or hardware-identical implementations.

## Remaining manuscript gate

The Carbon generation and final detector artifacts are complete, immutable, and represented in the
ledger. Final manuscript readiness remains subject to replay of the paper-bound detector evaluation
on the documented M5 Pro. The evidence audit also found that the retained Carbon protocol
document's hash differs from the frozen hash inside the original detector summary. The scientific
trials and decisions validate, but the original protocol bytes were not recovered. This is
documented in `docs/research/carbon_synthid_protocol_provenance_amendment_2026_09_03.md`.

The clean resolution is to freeze the current protocol under a new result identity during the M5
replay and admit that new artifact without overwriting the old one. Until that replay is completed
or the contract is explicitly revised, the manuscript must retain its Linux-CPU limitation and the
protocol-provenance caveat.
