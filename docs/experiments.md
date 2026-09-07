# Experiments actually performed

> The runs below are version-one development history. Their numbers are not confirmatory evidence
> for the planned dual-model paper. The new study has not run yet; its design is in
> `docs/research/dual_model_synthid_paper_rebuild_plan.md`.

This document describes completed SynthID work only. Sections 1–7 report the Carbon paper
experiment. Section 8 reports the separately labeled GENERator replication. Counts that refer to
prompts treat the prompt as the independent unit; the two draws from one prompt are paired
repetitions, not two independent biological samples.

## 1. Public prompt cohort

The frozen cohort contains 256 public RefSeq prompts, each 384 bases long. A deterministic split
reserved 64 prompts for detector selection and 192 prompts for final evaluation. The same split was
used throughout. No private or patient DNA was used.

## 2. Generation

For every prompt, Carbon generated two 3,072-base SynthID continuations and two matched ordinary
continuations. The two draws used different public replay seeds. The SynthID draws also used two
different public fixture keys. Temperature was 1.0, with no top-k or top-p truncation.

This produced 1,024 stored sequences: 256 prompts × two draws × two arms. Prompt bases were not
counted as generated output.

## 3. Sampler check

At one frozen Carbon state per prompt, the exact fixed-key SynthID distribution was calculated.
The experiment then drew 5,000 tokens from that distribution and compared the observed counts with
the calculated probabilities. The ordinary arm was checked against the ordinary Carbon
distribution. A deliberately incorrect sampler was included to ensure the test could detect a real
error.

Across 256 SynthID states, 13 nominal tests fell below 0.05, compared with 12.8 expected by chance.
The ordinary arm had 12. All eight deliberately incorrect controls were rejected after correction.
This supports implementation correctness at the tested states and test resolution. It is not a
formal proof of the method.

## 4. Model-quality comparison

Carbon scored every stored continuation token while being shown the true preceding sequence. The
primary measure was negative log-likelihood: lower means Carbon considers the sequence more
probable. The paired SynthID-minus-ordinary difference was 0.00852 nat per token, with a 95%
prompt-level interval from -0.04426 to 0.05973 and p=0.751. The SynthID and ordinary means were
7.54238 and 7.53386 nat per token.

Several sequence summaries, including composition and repetition measures, were also compared.
None differed after correcting for the number of summaries tested. The correct academic
interpretation is that this experiment found no measurable quality loss. It does not prove that
the two generators are identical, and these measurements are not tests of biological function.

## 5. Detector selection

The 64 reserved prompts were used only to choose between two predeclared SynthID score summaries.
The simple unweighted mean separated SynthID and ordinary outputs better and was frozen. The final
position-independent detector does not estimate its false-positive threshold from these prompts.

## 6. Position-independent detector

For each of the 192 held-out prompts and two draws, the stored 384-base prompt was prepended to the
stored 3,072-base continuation. The detector received the complete 3,456-base read but not the
boundary at base 384. It searched:

- the supplied strand and its reverse complement;
- every possible nucleotide start;
- 384-, 768-, 1,536-, and 3,072-base regions; and
- the same 30 layers, four-token context, and repetition rule used during generation.

For each tested region, the detector calculated the exact probability of seeing at least that many
keyed one-bits under a fair coin. It then multiplied the smallest region probability by the total
number of regions searched. This creates one false-positive-controlled decision for the entire
read. No prompt was used to fit this threshold, and no new calibration was run.

Three families were kept separate: SynthID with its correct draw key, matched ordinary Carbon with
that key, and SynthID with the other draw's key. The experiment was repeated on the clean read and
after exactly one nucleotide substitution, insertion, or deletion. The complete design contained
4,608 decisions.

## 7. Final detection results

| Read condition | Correct-key true positives | Ordinary false positives | Wrong-key false positives |
|---|---:|---:|---:|
| Clean | 384/384 | 1/384 | 0/384 |
| One substitution | 384/384 | 1/384 | 0/384 |
| One insertion | 384/384 | 1/384 | 0/384 |
| One deletion | 384/384 | 1/384 | 0/384 |

All 192 prompts had both correct-key draws detected in all four conditions. The exact 95% lower
bound for an all-success prompt-level result is 98.097%. The only ordinary positive was one prompt
and one draw; it repeats across edit rows because each edit fell outside its strongest 384-base
region. The clean prompt-level false-positive estimate is 1/192, with an exact 95% interval of
0.0132% to 2.8676%. Zero of 192 prompt clusters passed with the wrong key, giving a 95% upper bound
of 1.9030%.

The result shows a strong detector signal in this corpus, including after each tested single-base
event. The available number of independent prompts is not sufficient to prove an operational
false-positive rate below exactly 1%.

## 8. Supplementary GENERator replication

The full process above was repeated with `GenerTeam/GENERator-v2-eukaryote-1.2b-base` revision
`c41b0018da9ee13b9e96ee54647de8da381ccd72`. Its `G_tok` policy samples directly from the model's
4,096 canonical 6-mer tokens. The released base-marginal helper was not used. Temperature remained
1.0, with no top-k or top-p truncation.

### 8.1 Generation and sampler check

The identical 256 prompts, two draws, two arms, and 3,072-base continuation length produced 1,024
unique GENERator sequences. The two ordinary draws differed through their replay seeds; the two
SynthID draws additionally used two public fixture keys.

At the 256 tested fixed states, 5 SynthID sampler checks fell below the nominal 0.05 level, compared
with 12.8 expected by chance. The ordinary arm had 14. Neither real arm had a rejection after
multiple-test correction. All eight deliberately incorrect controls were rejected even after the
strict correction. The low SynthID nominal count is conservative: it does not indicate excess
departures from the intended distribution.

### 8.2 Model quality

The paired SynthID-minus-ordinary difference in GENERator negative log-likelihood was -0.005637 nat
per generated 6-mer. The 95% prompt-level interval was -0.056142 to 0.043782, p=0.8299, and the
standardized effect was -0.01387. The ordinary and SynthID means were 7.800291 and 7.794654 nat per
6-mer. None of the 14 declared likelihood and sequence summaries differed after multiple-test
correction; the smallest adjusted probability was 0.7310. This supports no measured GENERator
quality loss, not biological equivalence or function.

### 8.3 Aligned diagnostic and final detector

The aligned correct-key diagnostic detected all 384 held-out SynthID continuations at 384, 768,
1,536, and 3,072 bases. Across 512 ordinary outputs, the positive counts at these lengths were 2,
6, 6, and 4. Exact prompt-level goodness-of-fit probabilities were 0.245, 0.870, 0.763, and 0.838,
so the observed ordinary counts were compatible with their analytic expectations at every length.

The final detector then searched the complete prompt-plus-continuation reads without knowing the
boundary:

| Read condition | Correct-key true positives | Ordinary false positives | Other-key false positives |
|---|---:|---:|---:|
| Clean | 384/384 | 0/384 | 1/384 |
| One substitution | 384/384 | 0/384 | 1/384 |
| One insertion | 384/384 | 0/384 | 1/384 |
| One deletion | 384/384 | 0/384 | 0/384 |

All 192 prompts had both correct-key draws detected in all four conditions, with an exact 95% lower
bound of 98.097%. The ordinary result, zero positive prompt clusters out of 192, has an exact 95%
upper bound of 1.903%. The other-key positives in the first three rows are one repeating prompt and
draw; 1/192 prompt clusters gives an exact 95% interval from 0.0132% to 2.8676%.

GENERator therefore passes the same predeclared gates as Carbon: no measured likelihood loss, 100%
clean and single-edit detection in this corpus, and null results statistically compatible with the
1% target. The two models need not have identical false-positive counts. The full execution and
validator amendment are recorded in
`docs/research/generator_synthid_execution_2026_09_03.md` and
`docs/research/generator_synthid_validator_amendment_2026_09_03.md`.

## 9. Evidence and manuscript handoff

All reviewed numerical results are in `evidence/measurements.yaml`. The complete writing summary,
including the shared design, cross-model comparison, artifact hashes, permitted wording, and claim
limits, is `docs/research/manuscript_evidence_packet.md`.

The current Carbon-only manuscript uses the exact identifiers listed in
`paper/context/evidence_map.md`. The GENERator measurements are reviewed supplementary evidence and
are not inserted into that manuscript without a separate scope decision. Frozen protocol files and
immutable result summaries are not rewritten to make later documentation appear predeclared.
