# Cross-model clean-read strength analysis — 2026-09-21

This is a CPU derivation from the admitted version-one Carbon and GENERator artifacts, not a new
generation or detector run. The script verifies the SHA-256 of both retained trial files and both
sequence-comparison summaries, checks the complete 192-prompt × two-draw clean correct-key grid,
and recomputes each selected window's exact local binomial tail. The numerical output and code
hash are in `evidence/derived/cross_model_strength_2026_09_21.json`.

| Clean correct-key quantity, 384 reads/model | Carbon | GENERator |
|---|---:|---:|
| Minimum local strength, −log10 local p | 124.78 | 19.61 |
| Median local strength | 790.62 | 798.78 |
| Median scored tokens in winning window | 508 | 508 |
| Minimum scored tokens in winning window | 252 | 124 |
| Fraction of potential winning-window tokens excluded as repeated contexts | 0.177% | 0.131% |
| Median positive mark-bit fraction | 0.7392 | 0.7403 |
| Pearson correlation, local strength vs. scored-token count | 0.412 | 0.767 |

The weakest GENERator window is 3,072 bases long, with 334 scored tokens and 174 excluded repeated
contexts; its positive mark-bit fraction is 0.5458. The weakest Carbon window has 508 scored tokens,
zero repeated-context exclusions, and a fraction of 0.5961. Holding the GENERator fraction fixed and
restoring all 508 potential scored tokens raises its calculated local strength from 19.61 to 29.22.
That 9.61-unit arithmetic sensitivity is 9.1% of the 105.16-unit gap between the two weakest
reads. It is not a causal attribution: the fraction could change if different contexts were scored,
and the detector might select another window. Both models have full-window scoring at the median;
GENERator has fewer repeated-context exclusions overall. The dramatic minimum gap is an outlier
comparison, not a typical cross-model difference.

The ordinary-arm teacher-forced mean negative log-likelihood on each model's own samples is 7.534
nat per 6-mer for Carbon and 7.800 for GENERator. This is consistent with different average model
uncertainty on sampled trajectories, but the quality summary covers 256 prompts and stores only
cohort-level means. The detector table covers 192 evaluation prompts. Neither source links
per-read model uncertainty to detector strength. The base and dinucleotide entropy summaries are
properties of the generated sequences, not measurements of conditional predictive entropy.
The predictive-entropy explanation therefore remains a hypothesis.

All strengths here are local winning-window statistics. The read-level detector applies the full
search correction before making a decision. The correlation is descriptive because the two draws
within a prompt are paired and the winning windows were selected by the detector; no independent
read-level significance test is claimed.

Reproduce from the repository root:

```bash
python3 scripts/derive_cross_model_strength_analysis.py --check
PYTHONPATH=src python3 -m unittest tests.test_cross_model_strength -v
```
