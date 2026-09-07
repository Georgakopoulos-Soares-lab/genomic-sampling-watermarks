# GENERator SynthID replication: completed execution

## Status

The frozen GENERator replication is complete and passes the same declared model-quality and
position-independent detection gates as the Carbon experiment. This is supplementary evidence. It
does not change the Carbon-only scope of the manuscript.

The model was `GenerTeam/GENERator-v2-eukaryote-1.2b-base` revision
`c41b0018da9ee13b9e96ee54647de8da381ccd72`. Generation used policy `G_tok`: the model's next-token
probabilities were restricted to its 4,096 canonical DNA 6-mers and normalized. The only two arms
were SynthID tournament sampling and ordinary categorical sampling from this same distribution.

## What was run

1. The already frozen public cohort supplied 256 prompts of 384 bases. The same fixed split as the
   Carbon experiment reserved 64 prompts for the detector-summary comparison and 192 for final
   evaluation.
2. For every prompt, GENERator produced two 3,072-base SynthID continuations and two matched
   ordinary continuations. Draw zero and draw one used distinct public replay seeds. The two
   SynthID draws also used different public fixture keys; ordinary sampling has no key. Temperature
   was 1.0 and neither top-k nor top-p truncation was used.
3. This produced 1,024 unique sequences: 256 prompts times two draws times two arms. Each
   continuation contained 512 generated 6-mer tokens. Prompt bases were not counted as generated
   output.
4. At one fixed model state per prompt, 5,000 SynthID samples were compared with the exact
   fixed-key tournament probabilities and 5,000 ordinary samples were compared with the ordinary
   `G_tok` probabilities. Eight deliberately incorrect controls checked that the test could find a
   real implementation error.
5. GENERator then scored every generated token while seeing its true preceding prompt and
   continuation. SynthID and ordinary results were paired within the same prompt and draw. Fourteen
   predeclared likelihood and sequence summaries were tested, with correction for examining
   several summaries.
6. An aligned detector diagnostic checked generated prefixes of 384, 768, 1,536, and 3,072 bases.
   The 64 reserved prompts were used only to compare two declared score summaries; the unweighted
   mean remained frozen for the final detector.
7. The final detector received each complete 3,456-base prompt-plus-continuation read without the
   prompt boundary. For every read it searched both strands, every nucleotide start, and all four
   region lengths in one globally corrected decision. The same test was repeated after exactly one
   nucleotide substitution, insertion, or deletion. These were base-level edits, not 6-mer edits.
   With 192 prompts, two draws, three result families, and four conditions, this made 4,608 final
   decisions.

## Sampler correctness

| Arm or check | Nominal results below 0.05 | Chance expectation | Corrected rejections |
|---|---:|---:|---:|
| Exact fixed-key SynthID law | 5/256 | 12.8 | 0 |
| Ordinary `G_tok` law | 14/256 | 12.8 | 0 |
| Deliberately incorrect control | 8/8 | 0.4 | 8/8 |

The ordinary count is close to chance. The SynthID count is lower than the chance average, which
is conservative rather than evidence of excess error. No state in either real sampling arm was
rejected after correction, while every deliberately incorrect control was found. This supports
correct sampling at the 256 tested states and at the available 5,000-draw resolution; it is not a
formal proof for every possible model state.

For a fixed key and context, SynthID intentionally changes the next-token distribution. Its
preservation identity concerns an expectation over fresh keyed functions. The finite public-key
average in the diagnostic is not a security test and should not be interpreted as equality for a
particular key.

## Model-quality result

The primary difference was SynthID minus ordinary negative log-likelihood under GENERator. Lower
negative log-likelihood means that the model assigns greater probability to the sequence.

| Quantity | Result |
|---|---:|
| Ordinary mean | 7.800291 nat per 6-mer |
| SynthID mean | 7.794654 nat per 6-mer |
| Paired difference | -0.005637 nat per 6-mer |
| 95% prompt-level interval | -0.056142 to 0.043782 |
| Paired-test probability | 0.8299 |
| Standardized effect | -0.01387 |

The point estimate is very small and slightly favors SynthID, while the interval contains zero.
None of the 14 declared likelihood or sequence summaries differed after multiple-test correction;
the smallest adjusted probability was 0.7310. The supported conclusion is therefore **no measured
quality loss under GENERator**. This result does not establish biological function, viability,
safety, or exact equality of the two generation distributions.

## Aligned detector diagnostic

The correct key detected all 384 held-out SynthID continuations at every tested length. Across all
512 ordinary outputs used for the analytic-null fit check, the positive counts were 2, 6, 6, and 4
at 384, 768, 1,536, and 3,072 bases. The corresponding exact expected counts were approximately
5.02, 5.32, 5.01, and 5.14. Prompt-level exact fit probabilities were 0.245, 0.870, 0.763, and
0.838, so no length showed evidence that the analytic false-positive calculation was miscalibrated.

The validator originally used a percentile bootstrap for this rare-event check. At 384 bases its
upper endpoint was 5/512 while the exact expected value was 5.0199/512, causing a numerical false
failure even though the observed count was only 2/512. The validator was corrected to use the
pre-existing prompt grouping and the exact Poisson-binomial distribution. Generation, calibration,
detector scores, thresholds, and decisions were not changed or rerun. The amendment is recorded in
`generator_synthid_validator_amendment_2026_09_03.md`.

## Position-independent detector result

| Read condition | Correct-key SynthID | Ordinary output | SynthID checked with other key |
|---|---:|---:|---:|
| Clean | 384/384 | 0/384 | 1/384 |
| One nucleotide substitution | 384/384 | 0/384 | 1/384 |
| One nucleotide insertion | 384/384 | 0/384 | 1/384 |
| One nucleotide deletion | 384/384 | 0/384 | 0/384 |

All 192 prompt clusters had both correct-key draws detected in all four conditions. The exact 95%
lower bound for this all-success prompt-level result is 98.097%. No ordinary prompt cluster was
positive, giving an exact 95% interval from 0% to 1.903%. The first three other-key rows contain the
same single prompt and draw, not three independent events; their exact prompt-level interval is
0.0132% to 2.8676%. The deletion removed that chance signal.

The weakest correct-key corrected probabilities were approximately 3.92e-16 for the clean read,
1.62e-15 after substitution, 8.14e-7 after insertion, and 7.89e-8 after deletion. Even the weakest
was far below the 0.01 decision threshold. The insertion and deletion margins are smaller than the
clean margin, which is an expected warning sign when a one-base shift disrupts the 6-mer alignment,
but no true positive was lost in this corpus.

The 192 independent prompt clusters are enough to show strong detection and compatibility with a
1% false-positive target. They are not enough to prove that the true operational false-positive
rate is below exactly 1%. Public fixture keys permit replay but do not test whether a real secret
deployment key can be recovered from many examples.

## Comparison with Carbon and decision

Both models had 384/384 correct-key detections in every condition and no measured loss in their own
model likelihood. Carbon had one ordinary false-positive prompt and no other-key positive;
GENERator had no ordinary positive and one other-key positive. These small null-count differences
are ordinary sampling variation and both exact intervals contain the declared 1% target.

Accordingly, GENERator matches Carbon at the level defined before the run: no detected quality
degradation, clean true-positive rate at least 95%, each single-edit true-positive rate at least
90%, and null results statistically compatible with the 1% target. Matching does not mean that
every raw count or signal margin must be numerically identical.

## Execution and validation record

The optional accelerated execution used two A100 GPUs for the two generation draws and model-backed
analyses, followed by CPU detection. The generation stage reached its two-hour queue limit after
all 1,024 sequences and both quality results were safely finalized; the last nine sampler-state
checks were resumed without regenerating sequences. A first post-processing attempt stopped on the
rare-event validator issue described above. The position-independent run and both corrected strict
validators then completed successfully.

The run used Python 3.12.14, PyTorch 2.11.0+cu128, Transformers 5.15.1, NumPy 2.5.2, and SciPy
1.18.0. The frozen source-tree SHA-256 was
`96f8418f13cfec283cdfa2d4ea7c228a6c96ce99569b029dbda91c9efeb1a989`.

Reviewed compact artifacts:

- generation summary: `7b1b132d3d5c79c01bd914059d28e968b4c27fec2da47d0c297791c23c2e6a4e`;
- sampler summary: `77090622d7901ce6b459c45c7f22eee7b51bf1ee5535b6d960c560e281910783`;
- sequence comparison: `d8e3c03b2d0e3a2639c521889ea29dd804e8a741d3cf43818cb79f31ae821401`;
- aligned detection: `0bd171a3886ed823c31123271b1f22f5650bcf0b5a0767947467356605f1a72d`;
- final position-independent summary:
  `ac28bf5ed078fccd1eac5a97cabdd4f2a4e67f07a75d291aa3c5e0abd15830f7`;
- final position-independent trials:
  `3de1d8f7b8a946d3a5149f48ac30e357ceb2fa812eddbe6a11a5e836c7106d99`;
- corrected full-validator digest:
  `fa4fc9a6e36644c6d3b973f7dbd60810220bc0b2a167501ca9ebfa3a164edfeb`.

Final verification comprised both strict artifact validators, 108 passing unit tests with four
optional upstream-parity tests skipped, the complete Ruff check, the evidence-ledger check, shell
syntax validation for the resume path, and the environment doctor. The required MPS/CPU-compatible
path remains in the repository; this optional accelerated execution does not make CUDA part of the
required protocol.
