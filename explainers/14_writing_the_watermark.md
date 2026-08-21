# 14 — Writing the watermark into real DNA

## What changed

Until now the project measured a *possibility*: how much watermark information the model
distributions could carry. It did not actually watermark anything. Now it does. The generator can
produce a watermarked DNA sequence from a real model, and a verifier holding only the DNA and the
key can recover the signal.

## The loop, one token at a time

At token position `i`, with the model's next-token distribution `p` over the 4,096 canonical 6-mers:

```text
1. derive partition P_i  = split the 4,096 tokens into two equal halves, using key + position
2. derive latent bit c_i = one keyed coin flip, using key + position
3. q  = total probability p assigns to group 1 under P_i
4. G  = maximal coupling of c_i to a Bernoulli(q) draw       ← which half we will sample from
5. token = draw from p restricted and renormalized to group G
6. append token to the context, go to i+1
```

Steps 3-5 are what keep the distribution honest. The half is chosen with exactly probability `q`,
and inside the half the token is chosen with exactly the model's conditional probabilities. Multiply
those and you get back the model's original probability for that token. Nothing is biased.

Step 4 is what puts the signal in. Maximal coupling makes the sampled group agree with the keyed
coin as often as the mass allows: the agreement probability is `1 - |q - 1/2|`. When the partition
splits the mass evenly, `q = 1/2` and the group *always* equals the coin. When the model is nearly
certain of one token, `q` is near 0 or 1 and the group is nearly independent of the coin — no signal.
That is the same quantity explainer 11 measured as capacity, seen from the other side.

## Why the partition changes every position

A single fixed partition would let anyone who collects enough outputs learn it by counting. Deriving
`P_i` and `c_i` from `HMAC(key, purpose ‖ domain ‖ i)` means each position is its own puzzle, with
separate derivations for the partition and the bit, and a domain label that keeps different
experiments from colliding.

The important consequence: **the partition depends on the position and the key, never on the token
that was emitted.** That is why the verifier can recompute it later from the DNA alone, and why the
detector can cache one partition per position and reuse it across every alignment hypothesis it
tries.

## The key never touches a file

The generator reads the key from the environment at run time. Reports store a human-chosen
experiment label — not the key, not a hash of the key. A hash would be worse than useless: it would
let anyone test key guesses offline.

For the experiments in this repository we use a *published, deliberately non-secret* fixture key and
label it as such in every artifact. That is a reproducibility choice, not a security claim. Detection
power is a property of the construction, not of one key, and the wrong-key null trials use different
keys, so the calibration still means something. The runtime-secret path is implemented and tested; it
just is not what a reproducible pilot should use.

## Did it work?

Two smoke runs on real weights, `C_tok` and `G_bp`, then the real experiment. In every case the
verifier — given only the emitted DNA, the public 4,096-mer list, and the key — reproduced the
generator's agreement pattern exactly, position for position. The watermarked arm agreed with the
keyed coin 31 times out of 32; the matched ordinary arm agreed 16 times out of 32, which is exactly
chance.

The verifier used only the public canonical 6-mer list, never the model. That is the property the
whole paper depends on.

## Proving the distribution is untouched

An argument on paper is not enough; the implementation could still be wrong. So each policy was
tested at four real model states, 8,000 watermarked draws and 8,000 ordinary draws per state, against
the declared model law.

The test is a likelihood-ratio (`G`) goodness-of-fit test with a **simulated** reference
distribution rather than the textbook chi-square one. With 4,096 categories and only a few thousand
draws, most categories are empty or nearly so, and the chi-square approximation is simply wrong at
that sparsity. Resampling counts from the declared law 999 times gives a reference with the correct
size.

Result: across 12 watermarked tests, nothing was rejected after correcting for multiple testing, and
exactly one test fell below the uncorrected 0.05 line. The matched ordinary arm — which *is* the
declared law, and therefore acts as a check that the test itself is calibrated — also had exactly
one. The two arms are indistinguishable, which is what an exact-marginal construction predicts.

A guard against self-congratulation: the test suite includes a deliberately broken sampler that picks
uniformly inside the chosen half instead of using the conditional law. The test rejects it. So the
gate has real power; it is not passing because it cannot fail.

## The sequence-level check, and what one key can hide

Correct per-token distributions are the strong claim. There is a weaker, more suspicious question
behind them: does a watermarked *sequence* look different in bulk? So the matched arms were compared
on nine composition and complexity proxies — GC and purine and CpG fraction, base/dinucleotide/
trinucleotide entropy, distinct-hexamer fraction, and homopolymer run statistics — paired per
prompt, with an exact permutation test that enumerates all 256 sign flips of the eight paired
differences.

No metric was rejected after correcting for the nine tests, for any policy. But `C_tok` deserves to
be stated rather than rounded off: two of its nine metrics cross the uncorrected 0.05 line (CpG
fraction, distinct-hexamer fraction), and the other seven lean the same way — slightly higher
entropy, slightly shorter homopolymer runs. That is a coherent direction, not obviously noise.

Here is the interesting part, and it is a reasoning trap worth internalizing. It *cannot* be a
marginal-preservation failure. If every step samples the exact conditional law given the prefix,
then by induction the joint law of the whole sequence is exactly the model's joint law — provided
the key is unknown or random. But this experiment used **one fixed key** for every watermarked
sequence. A single key's realization can drift systematically in bulk statistics even when the
construction is exact in expectation over keys, and eight prompts nowhere near average that away.

So the honest reading is: no gross sequence-level artifact, and one unresolved fixed-key directional
pattern. The fix is not a better argument, it is a better experiment — regenerate the watermarked arm
under several independent keys and test the key-averaged difference. That costs another generation
pass per key per policy, so it is written down as owed rather than quietly skipped.

## What this does not show

- **Not sequence-level indistinguishability.** Every single token has the right distribution. That
  does not prove a long watermarked sequence is statistically identical to an unwatermarked one; the
  positions share a key. Testing that is a separate experiment.
- **Not security.** One output having the correct marginal says nothing about what an adversary
  learns from many outputs, from reusing a key, or from querying a detector.
- **Not detection.** Agreement rates measured by the generator, which knows the key and the model,
  are not detector results. Explainer 15 covers what the detector can actually do.

Return to the [explainer index](README.md).
