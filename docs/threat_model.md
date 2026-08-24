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

## Measured outcomes against these goals, 2026-08-23

Recorded here so the goals above are not read as achievements.

| Goal | Outcome |
|---|---|
| 1. Correct-key power at a calibrated FPR | **met.** Detection rate 1.000 from 96 bases on all three policies at a 0.01 target calibrated over the complete search. |
| 2. Wrong-key, unwatermarked, and public-sequence nulls satisfy the FPR | **met for wrong-key and unwatermarked; qualified for public sequences.** Natural public DNA under a wrong key exceeds thresholds calibrated on model-generated nulls above the 0.01 target at some lengths, worst for the two baseline constructions. Public-sequence trials are reported separately and are never pooled into a threshold, which is why this was visible. |
| 3. One-output unkeyed classifier should not distinguish | **met for `C_tok` and `G_tok`. Unresolved for `G_bp`**, which has two nominal permutation rejections that do not clear Bonferroni across nine tests. |
| 4. Key reuse and many-output attacks evaluated separately | **evaluated, and the result is negative.** See below. |
| 5. Detector-query removal reports success against query count and edit budget | **partly met.** Removal by rearrangement is measured against block width and sequence length, with a utility column. No detector-query loop was run: the attacks here need no detector queries at all, which is a stronger attacker result than the goal anticipated. |

### The spoofer goal is not met, and cannot be met by this construction

An attacker holding **two** watermarked outputs under one key can splice them position by position into
a sequence the generator never produced, and the verifier accepts it at rate **1.000** at every length
on every policy, with a statistic indistinguishable from genuine output.

The reason is structural. The detector's decision at read position `i` depends only on which half of
the keyed partition at stream index `i` the observed token falls into, and that partition is a function
of the key, the domain, and `i` — never of the observed DNA. The statistic is therefore a sum of
per-position, content-blind indicators. Nothing binds position `i` to position `j`, and nothing binds
the sequence to a nonce, a length, or a payload.

So the construction as specified **authenticates a distribution, not a sequence**. Any defence is a
different construction — content-binding, a per-sequence nonce carried in the sequence, or a coding
layer — and none of those is built or evaluated here.

The argument extends to any position-indexed, content-blind keyed statistic, which includes the
inverse-transform and exponential baselines. That extension is reasoning, not measurement: only
partition coupling was attacked.

### What the key-handling rules do and do not buy

The domain separation and per-experiment nonces in the section above prevent one experiment's key
stream from colliding with another's. They do **not** prevent this attack, because the attacker works
entirely inside one domain and one nonce — the very domain the verifier is checking. Domain separation
is hygiene, not a defence against reuse within a domain.

## Out of scope

- Secret or patient genomic input.
- Wet-lab synthesis or biological deployment.
- Claims that proxy-preserving edits preserve biological function or safety.
- Public-key attribution in the first implementation.
- Protection against an adversary with the secret key or arbitrary replacement of the sequence.
- Protection against a spoofer holding two or more outputs under one key: measured, not achieved, and
  out of reach for this construction rather than merely unimplemented.
- Any claim that a coding layer, content binding, or a per-sequence nonce would close the spoofing gap.
  Those are untested constructions.
