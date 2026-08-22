# Claims and limits

## Claim classes

| Class | Required support |
|---|---|
| Mathematical | Definition, proposition, proof, and executable edge-case tests |
| Cryptographic | Explicit security game, assumptions, reduction or clearly labeled heuristic status |
| Statistical | Sampling unit, calibration protocol, uncertainty, multiplicity, and reproducible evidence |
| Biological proxy | Exact metric, reference cohort, limitations, and no functional inference |

## Forbidden shortcuts

- Nominal 4,096-token vocabulary does not establish usable entropy or watermark capacity.
- One sampled output having the correct marginal does not establish security under key reuse or adaptive queries.
- A minimum p-value across detector hypotheses is not a valid global p-value without calibration.
- Low proxy distance does not establish biological equivalence.
- Training with FNS does not imply that the released Carbon checkpoint uses base-marginal sampling.
- Robustness to random edits does not establish robustness to adaptive removal.
- Failure of cheap unkeyed distinguishers does not establish undetectability, and no interval is
  valid beyond the exchangeability it assumes: resample the unit that actually varies.

## Required qualifiers

- Name the model policy (`C_tok`, `C_bp`, `G_tok`, or `G_bp`).
- Name the sequence length, edit channel, and globally calibrated FPR.
- State whether evidence is synthetic, real-logit, generated-sequence, or public-sequence.
- State whether the setting is single-output, many-output, wrong-key, or adaptive-query.

