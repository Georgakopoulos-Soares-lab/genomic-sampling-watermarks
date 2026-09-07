# GENERator aligned-null validator amendment

## Reason for the amendment

The frozen protocol requires the analytic 1% detector threshold to be checked against ordinary
outputs, with the prompt as the independent unit. The original validator tried to enforce this by
asking whether the exact expected rate lay inside a percentile bootstrap interval for the observed
rare-event rate.

At 384 bases the run observed 2 positives among 512 ordinary sequences. The exact expected count
was 5.0198758. Because bootstrap resamples cannot create fractional events, the upper bootstrap
endpoint was exactly 5/512, or 0.9765625%, while the expected rate was 0.9804445%. The resulting
gap was only 0.003882 percentage points. Treating this discretization artifact as a scientific
failure would be incorrect.

## Corrected validation rule

The validator now groups the two draws belonging to each prompt and computes the exact distribution
of the number of prompts with at least one positive. It allows each draw to retain its declared
analytic probability, so the resulting prompt probabilities need not be identical. The observed
prompt count is compared with this Poisson-binomial distribution using an equal-tailed two-sided
test. A probability below 0.05 fails validation.

| Generated bases | Observed positive prompts | Expected positive prompts | Exact two-sided probability |
|---:|---:|---:|---:|
| 384 | 2/256 | 4.9953 | 0.2451 |
| 768 | 6/256 | 5.2877 | 0.8698 |
| 1,536 | 6/256 | 4.9844 | 0.7625 |
| 3,072 | 4/256 | 5.1136 | 0.8377 |

All four checks pass. The correction changed only the evidence validator. It did not alter the
frozen protocol's target rate, the prompt split, generated sequences, keys, sampler, score,
threshold, or any detection decision. The original failed validation attempt remains part of the
execution history. The same validator correction was applied to the Carbon validation script so
future replays use the same statistically appropriate rule.
