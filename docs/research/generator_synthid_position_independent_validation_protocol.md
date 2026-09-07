# GENERator SynthID position-independent detector validation protocol

Frozen on 2026-09-02 before GENERator generation or detector results were inspected. This protocol
uses only `synthid-tournament-v1` and `synthid-position-independent-detector-v1`.

## Objective and held-out data

After the model-quality and aligned checks finish, reuse their immutable GENERator generation
files. Prepend each stored 384-base public prompt to its 3,072-base continuation, but do not give
the detector the prompt length or generation boundary. Evaluate only the 192 prompts in the common
frozen evaluation split, with two draws per prompt. The 64 detector-check prompts remain excluded.

The model is GENERator-v2 1.2B revision
`c41b0018da9ee13b9e96ee54647de8da381ccd72`, using direct canonical policy `G_tok`. No model
inference, new generation, empirical threshold fitting, or detector-setting selection occurs in
this stage.

## Complete search and correction

For every read, search both orientations, every nucleotide start, and 384-, 768-, 1,536-, and
3,072-base windows. Use 30 layers, four local context tokens, the 1,024-context repetition rule,
and exact fair-binomial local upper tails. Multiply the smallest local probability by the complete
number of orientation × start × length hypotheses and cap it at one. Detect when this single global
probability is at most 0.01.

The complete search has 16,136 hypotheses for a 3,456-base clean or substituted read, 16,144 after
one insertion, and 16,128 after one deletion. A different search count invalidates the trial.

## Families and conditions

Keep three result families separate:

1. SynthID continuation checked with its draw's correct fixture key;
2. matched ordinary GENERator continuation checked with that key; and
3. SynthID continuation checked with the other draw's key.

Evaluate the clean read and exactly one deterministic nucleotide substitution, insertion, or
deletion inside the continuation. The same edit identity is applied to matched arms. These are
single nucleotide events, not 6-mer edits, multi-edit attacks, or detector-guided attacks.

The full design is 192 prompts × two draws × three families × four conditions = 4,608 final
sequence decisions. For each cell, report the count out of 384, prompt-cluster uncertainty, and
prompt-level “either draw” and “both draws” exact intervals. Also report winning orientation,
window length, corrected probability range, and the weakest correct-key case.

## Interpretation gates

- Clean correct-key detection below 95% is a failure for this corpus.
- Any single-edit correct-key detection below 90% is a warning.
- Ordinary and wrong-key rates must be interpreted using 192 prompt clusters, not as 384 fully
  independent observations.
- Passing does not prove an operational false-positive rate below exactly 1%, biological function,
  viability, authenticity against an adversary, or formal secret-key security.

The strict validator must reject incomplete grids, wrong model or policy provenance, incorrect key
mapping, wrong read/search sizes, invalid coordinate mapping, inconsistent exact/log probabilities,
or decisions inconsistent with the global 0.01 rule. Final trial artifacts contain neither raw DNA
nor raw keys.
