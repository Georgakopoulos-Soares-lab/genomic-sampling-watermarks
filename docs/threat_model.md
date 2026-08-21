# Threat model

## Roles

- **Generator**: has model access and a secret key, embeds a zero-bit provenance signal during sampling, and emits DNA.
- **Verifier**: has only the DNA, secret key, and public algorithm/configuration.
- **Observer**: sees one or more outputs but has no key and tries to distinguish watermarked from ordinary generation.
- **Editor**: may substitute, insert, delete, crop, reverse-complement, or query a detector to remove the watermark while retaining a chosen utility proxy.
- **Spoofer**: tries to cause unrelated or edited DNA to be attributed to the key holder.

## Security and statistical goals

1. Correct-key detection has useful power at a declared globally calibrated false-positive rate.
2. Wrong-key, unwatermarked-model, and public-sequence nulls satisfy that false-positive rate after the complete hypothesis search.
3. A one-output unkeyed classifier should not reliably distinguish exact-marginal outputs under matched conditions.
4. Key reuse, correlated queries, and many-output attacks are evaluated separately; one-output marginal preservation does not imply adaptive undetectability.
5. Detector-query removal reports success as a function of query count and edit budget.

## Key handling

- Root keys are supplied only at runtime and never written to logs or result records.
- Domain-separated derivations are used for partitions, target bits, generation nonces, detector offsets, and experiment fixtures.
- Evidence stores a non-reversible experiment key label, not a hash that invites offline key checking.
- Reusing a root key across experiments requires distinct public nonces and domain labels.

## Detector search

The declared detector may search:

- forward and reverse-complement orientation;
- phases 0 through 5;
- configured window locations and lengths;
- configured key-stream offsets;
- configured synchronization states.

Calibration samples the maximum statistic from this complete procedure. Any data-dependent search added later changes the detector and requires new null calibration.

## Out of scope

- Secret or patient genomic input.
- Wet-lab synthesis or biological deployment.
- Claims that proxy-preserving edits preserve biological function or safety.
- Public-key attribution in the first implementation.
- Protection against an adversary with the secret key or arbitrary replacement of the sequence.
