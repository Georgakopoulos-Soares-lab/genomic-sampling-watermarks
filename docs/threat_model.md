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
behavior. Multiple edits and detector-guided editing are outside this threat model and are not
planned experiments for this study.

This boundary follows from the search geometry, not from convenience. Detection requires a
contiguous region whose 6-mer alignment survives and that carries enough scored tokens to clear
the corrected threshold: at `alpha = 0.01` and `M = 16,136` windows, a window needs at least 21
scored tokens even if every mark bit is positive, and the shortest evaluated window spans 384
bases. Independent indels arriving at rate `r` leave expected clean stretches near `1/r` bases,
so raising the rate shortens the surviving region faster than it weakens the mark. Measuring the
breakdown point would therefore require a shorter-window search with a correspondingly larger
correction. That is a different verifier and a different study, and it is why the higher-rate
sweep is declined here rather than deferred.

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
