# Contribution frame

## One-sentence contribution

We formulate and evaluate secret-key exact-marginal sampling as a model-free provenance channel for fixed 6-mer genomic language models, with source-accurate generation baselines and globally calibrated robustness to DNA synchronization errors.

## What may be novel

- Cross-model evidence on the realized watermark channel of Carbon and GENERator-v2 rather than an argument from nominal vocabulary size.
- Explicit separation of direct-token and base-marginal generation policies.
- Translation from nucleotide edits to a fixed-6-mer synchronization channel, with the full detector search included in calibration.
- A laptop-reproducible evidence pipeline for genomic sampling watermarks.

## What is not claimed as novel

- Inverse-transform or exponential/Gumbel watermark sampling.
- The general idea of unbiased/distribution-preserving language-model watermarks.
- Existing PRC or synchronization-string constructions.
- DNA watermarking in general.

## Publication outcomes

1. Positive cross-model result with usable clean and edited detection.
2. Positive clean channel but synchronization-limited result focused on indels.
3. Evidence that a generic text-watermark construction transfers without a new sampler.
4. Negative result showing insufficient realized channel capacity on these policies.

All four are legitimate outcomes if supported by the frozen protocol.

## Which outcome the evidence now supports, as of 2026-08-23

**Outcome 3, together with outcome 2.**

E8/E9 measured all three constructions on the same policies, prompts, and detector search, each
calibrated on its own nulls. The exponential construction carries about 7.5 times partition
coupling's standardized signal per 6-mer token, and inverse transform about 1.4 times. Partition
coupling is at its structural ceiling rather than below it: it couples one bit per token, so its
per-token signal cannot exceed 1.0, and the measured 0.96 to 1.00 is the maximal-coupling loss away
from that cap.

So the paper must not claim partition coupling as the better construction. What it can claim:

- a generic text-watermark construction does transfer to fixed 6-mer genomic policies without a new
  sampler, and that transfer was measured rather than assumed (outcome 3);
- the clean channel is strong for all three constructions and the binding limit is synchronization,
  not capacity — E7's indel wall stands two orders of magnitude below the substitution tolerance
  (outcome 2);
- the realized channel per policy, the exact-marginal preservation, and the global calibration over
  the complete declared search are measured on released models.

## The security result, and it is negative

E11/E12 measured what key reuse buys an attacker who never sees the key. A **spliced forgery** —
assembled position by position from two watermarked outputs under the same key — is accepted at rate
**1.000** at every length on every policy, with a statistic indistinguishable from genuine output
(3,072 bases: genuine 21.91 against forged 21.87, 21.79, 21.93 on `C_tok`).

This is not a tuning failure. The detector's decision at read position `i` depends only on which half
of the keyed partition at index `i` the observed token falls into, and that partition is a function of
the key, the domain, and `i` alone. The statistic is a sum of per-position, **content-blind**
indicators, so nothing binds position `i` to position `j`, and nothing binds the sequence to a nonce,
a length, or a payload. **The construction authenticates a distribution, not a sequence.** Closing the
gap requires a different construction, and this project has not built one.

Removal also works. A full positional shuffle drops detection to 0.000 at every length and policy, and
a bounded block shuffle removes the mark once the block is wide enough — width 8 to 16 at the lengths
measured, and wider for longer sequences, because a longer sequence carries more signal to destroy.

The utility column has to be read carefully, and the paper must say why: the removal attacks permute
whole 6-mers, so they preserve the 6-mer multiset exactly, and the nine admitted proxies are
composition and complexity statistics that are nearly blind to them by construction. The measured cost
of removal is small mainly because the instruments cannot see it. The ORF and
independent-model-likelihood proxies declared in `../../docs/baseline_definition.md` are what would
price the long-range structure a rearrangement destroys, and E12 is the strongest argument for
building them.

So the paper's claim about security is bounded and stated plainly: this construction gives
**distribution-preserving, model-free provenance detection that survives realistic substitution and
cropping**, and it gives **no protection against an adversary who holds two outputs under one key**.
That is a real result about a real construction, and it is more useful stated than hedged.

Two framing rules follow, and they are the kind of thing that gets lost in drafting:

1. **Detection rate is not the baseline-comparison result.** It is 1.000 in every method-length-policy
   cell down to the detector's 96-base floor. Presenting that as the comparison would report a null
   result as an agreement. The comparison result is the per-token signal.
2. **The per-token ordering is not a robustness ordering.** Nothing measured says how `its` or `exp`
   degrade under substitutions or indels, and the clean-channel gap must not be read as predicting
   that.
3. **The spoofing detection rate of 1.000 is a vulnerability**, and it is the only inverted-sign
   detection rate in the ledger. It may not share an axis, a table column, or a sentence pattern with
   the intended-detection rates, and it may never be averaged with them.
4. **The spoofing result is not specific to partition coupling.** Inverse transform and the
   exponential construction are also position-indexed and content-blind, so the same splice applies
   to them in principle. It was measured only on partition coupling, so the paper says "measured on
   ours, and the argument extends to any position-indexed keyed statistic" — and says which half of
   that is measurement and which is argument.

