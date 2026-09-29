# Threat model

## Parties and information

The generator has a genomic language model and a secret key. The rebuilt paper evaluates
Carbon-500M and GENERator-v2 1.2B as two model applications of the same SynthID implementation. The
generator adds the SynthID signal while sampling DNA. The verifier has the observed DNA, the same
secret key, the public generation domain, and fixed public detector settings. The verifier does not
need the prompt or model.

The outside observer may see watermarked outputs and knows the published method. The observer does
not know the secret key and cannot obtain, query, or optimize against the detector score.

## Edit model

The retained experiment covers an unchanged read and exactly one ordinary nucleotide event inside
the generated continuation: one substitution, one insertion, or one deletion. The event location
and affected base are selected by a frozen public random procedure, not by inspecting detector
behavior.

Editing at higher rates has since been measured rather than argued. A full-cohort run over 1,544
evaluation prompts per model, both draws, applied independent public-replay edits at per-base
rates of 0.0003, 0.001, 0.005, 0.01, 0.02, 0.05 and 0.10, as substitutions, mixed indels, and
direction-pure insertions and deletions. Correct-key detection recovered every read for all four
edit kinds through a 2% per-base rate on Carbon and a 1% rate on GENERator; at 2% GENERator still
recovered every read under substitution and under direction-pure insertion and deletion, and
missed one read in 3,088 under mixed indels. Detection fell to about 93% for indels at 5%, where
substitutions recovered every Carbon read and all but one GENERator read, and collapsed by 10%.
Ordinary output under the
corresponding key stayed at or below the 0.01 target at every rate and kind. The detector was
unchanged throughout: same window set, same orientations, same correction. Results are admitted
under `synthid.v3.*`; the protocol is
`docs/research/synthid_v3_edit_rate_protocol_2026_09_24.md` and the execution record is
`docs/research/synthid_v3_edit_rate_execution_2026_09_24.md`.

This measurement is admitted as evidence under an explicit author sign-off recorded in
`docs/research/threat_model_edit_rate_v3_admission_2026_09_29.md`, which authorizes the
full-cohort run beyond the pilot covered by the 2026-09-24 amendment. **The declared covered
regime is widened accordingly**: in addition to the primary single-event condition, this study's
claims now cover non-adaptive public-replay editing up to the measured full-recovery ceiling of
each model — a 2% per-base rate on Carbon and a 1% rate on GENERator — and, as characterized
degradation and collapse rather than recovery, up to 10%. The regime remains strictly
non-adaptive: it does not include, and does not by itself support any claim about, an adversary
who inspects the detector, the key, or any score.

The edit channel is a non-adaptive public replay that never inspects the detector, the key, or any
score. Detector-guided and detector-query editing remain outside this threat model, and no
adversarial-robustness claim follows from these measurements: an adaptive editor placing edits
where they hurt most has not been measured.

## Detection goal

With the correct key, a watermarked read should pass the declared sequence-level threshold. An
ordinary model output and a watermarked read checked with the other draw's key should pass only at
the declared false-positive frequency. The position-independent detector must make this decision
without knowing the prompt boundary, strand, or 6-mer alignment.

## Key assumptions

The implementation uses HMAC-SHA-256 to derive keyed binary values from local token context. The
statistical test assumes that, without the correct key, these values behave like independent fair
bits. This is a standard cryptographic modeling assumption, not a security proof.

The experiments use public fixture keys for reproducibility. Consequently, they test statistical
generation and detection, not resistance to recovering a real deployment key from many examples.
A deployment key must be secret, randomly generated, and kept out of output files and logs.

## Claims not made

The tests do not establish biological function, viability, safety, sequence authenticity, formal
key-recovery resistance, or public-key attribution. They also do not show that a detected local
region is the exact generation boundary; the detector reports the strongest tested region.
