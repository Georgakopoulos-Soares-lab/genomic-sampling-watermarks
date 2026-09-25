# GENERATOR SynthID position-independent detector validation

The detector received no prompt boundary, phase, strand, or offset. It searched both
orientations, every nucleotide start, and all four declared lengths in one globally
corrected decision. Generation and calibration were not rerun.

## Sequence-level detection

| Condition | Family | Detections | Rate | Prompt-cluster 95% interval |
|---|---|---:|---:|---:|
| clean | watermarked_correct_key | 3088/3088 | 100.0000% | 100.0000%–100.0000% |
| clean | ordinary_corresponding_key | 5/3088 | 0.1619% | 0.0324%–0.3238% |
| clean | watermarked_wrong_key | 2/3088 | 0.0648% | 0.0000%–0.1619% |
| substitution_1nt | watermarked_correct_key | 3088/3088 | 100.0000% | 100.0000%–100.0000% |
| substitution_1nt | ordinary_corresponding_key | 5/3088 | 0.1619% | 0.0324%–0.3238% |
| substitution_1nt | watermarked_wrong_key | 2/3088 | 0.0648% | 0.0000%–0.1619% |
| insertion_1nt | watermarked_correct_key | 3088/3088 | 100.0000% | 100.0000%–100.0000% |
| insertion_1nt | ordinary_corresponding_key | 6/3088 | 0.1943% | 0.0648%–0.3562% |
| insertion_1nt | watermarked_wrong_key | 2/3088 | 0.0648% | 0.0000%–0.1619% |
| deletion_1nt | watermarked_correct_key | 3088/3088 | 100.0000% | 100.0000%–100.0000% |
| deletion_1nt | ordinary_corresponding_key | 7/3088 | 0.2267% | 0.0648%–0.4210% |
| deletion_1nt | watermarked_wrong_key | 3/3088 | 0.0972% | 0.0000%–0.2267% |

## Protocol facts

- Evaluation prompts: 1544
- Draws per prompt: 2
- Total decisions: 37056
- Search: both orientations × every nucleotide start × 384/768/1,536/3,072 bases
- Decision: exact local fair-binomial tail with one global Bonferroni correction
- Calibration rerun: no
- Generation rerun: no

This is a detector validation only. It does not establish biological function,
viability, adversarial authenticity, or secret-key security from many observations.
