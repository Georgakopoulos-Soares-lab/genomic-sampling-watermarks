# GENERATOR SynthID position-independent detector validation

The detector received no prompt boundary, phase, strand, or offset. It searched both
orientations, every nucleotide start, and all four declared lengths in one globally
corrected decision. Generation and calibration were not rerun.

## Sequence-level detection

| Condition | Family | Detections | Rate | Prompt-cluster 95% interval |
|---|---|---:|---:|---:|
| clean | watermarked_correct_key | 384/384 | 100.0000% | 100.0000%–100.0000% |
| clean | ordinary_corresponding_key | 0/384 | 0.0000% | 0.0000%–0.0000% |
| clean | watermarked_wrong_key | 1/384 | 0.2604% | 0.0000%–0.7812% |
| substitution_1nt | watermarked_correct_key | 384/384 | 100.0000% | 100.0000%–100.0000% |
| substitution_1nt | ordinary_corresponding_key | 0/384 | 0.0000% | 0.0000%–0.0000% |
| substitution_1nt | watermarked_wrong_key | 1/384 | 0.2604% | 0.0000%–0.7812% |
| insertion_1nt | watermarked_correct_key | 384/384 | 100.0000% | 100.0000%–100.0000% |
| insertion_1nt | ordinary_corresponding_key | 0/384 | 0.0000% | 0.0000%–0.0000% |
| insertion_1nt | watermarked_wrong_key | 1/384 | 0.2604% | 0.0000%–0.7812% |
| deletion_1nt | watermarked_correct_key | 384/384 | 100.0000% | 100.0000%–100.0000% |
| deletion_1nt | ordinary_corresponding_key | 0/384 | 0.0000% | 0.0000%–0.0000% |
| deletion_1nt | watermarked_wrong_key | 0/384 | 0.0000% | 0.0000%–0.0000% |

## Protocol facts

- Evaluation prompts: 192
- Draws per prompt: 2
- Total decisions: 4608
- Search: both orientations × every nucleotide start × 384/768/1,536/3,072 bases
- Decision: exact local fair-binomial tail with one global Bonferroni correction
- Calibration rerun: no
- Generation rerun: no

This is a detector validation only. It does not establish biological function,
viability, adversarial authenticity, or secret-key security from many observations.
