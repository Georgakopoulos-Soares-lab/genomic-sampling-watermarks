# GENERator-v2 1.2B `G_tok` SynthID validation protocol

Frozen on 2026-09-02 before model-backed benchmark or generation results were inspected. This is a
second-model replication of the Carbon SynthID experiment. It uses only
`synthid-tournament-v1` and its matched ordinary categorical control; no removed watermark method
or multi-edit experiment is included.

## Model and sampling law

The model is `GenerTeam/GENERator-v2-eukaryote-1.2b-base` revision
`c41b0018da9ee13b9e96ee54647de8da381ccd72`. The tokenizer has 32 special tokens followed by all
4,096 canonical DNA 6-mers. Policy `G_tok` restricts each next-token decision to those 4,096 model
logits and normalizes them once. Temperature is 1.0, with no top-k or top-p truncation.

This direct-token policy is intentional: it makes the probability supplied to SynthID exactly the
same kind of 4,096-way categorical law used in the Carbon experiment. It is not GENERator's
released base-marginal helper, which would define a different sampling law and therefore would not
be the same experiment.

## Frozen corpus and generation

The experiment reuses the identical 256 public RefSeq prompts, each 384 bases. It also reuses the
same deterministic 64-prompt detector-check and 192-prompt evaluation split so model comparisons
are not confounded by different prompts. For each prompt there are two draws. Each draw contains:

- one 512-token (3,072-base) SynthID continuation;
- one matched 512-token ordinary continuation;
- a draw-specific public replay seed in each arm; and
- one of two public fixture keys in the SynthID arm.

The complete corpus is 1,024 sequences and 3,145,728 generated bases. The key material is public
only for reproducibility and is not evidence about deployment-key recovery.

## SynthID construction

The unchanged implementation applies 30 binary tournament updates. Candidate bits are derived by
domain-separated HMAC-SHA-256 from the previous four generated 6-mers and the candidate token. The
first four generated tokens are ordinary samples. Repeated four-token contexts are sampled
ordinarily and omitted from detection.

For a fixed key and context, the tournament deliberately reweights the model probabilities. The
preservation statement is an expectation over fresh keyed functions, not equality between one
fixed-key distribution and `G_tok`.

## Required experiments

1. At the state after 64 ordinary tokens for each prompt, draw 5,000 samples from the calculated
   fixed-key tournament law and 5,000 from `G_tok`. Use the same 999-replicate goodness-of-fit test,
   64-key finite average, and eight deliberately wrong negative-control states as Carbon.
2. Generate the complete matched two-draw corpus and verify recomputed keyed scores, lengths,
   checksums, unique identities, and distinct replay streams.
3. Teacher-force every continuation under normalized `G_tok`, scoring the 512 generated tokens but
   using the prompt as context. Compare SynthID minus ordinary within each prompt and draw. Use
   prompt-cluster bootstrap intervals and prompt-level sign flips, plus the same declared sequence
   summaries and multiple-test correction.
4. On the common 64-prompt check split, compare the unweighted mean score with the released default
   weighted mean. This is a replication check only: the already frozen position-independent
   detector remains the unweighted mean regardless of which number is larger.
5. Run clean aligned detection at 384, 768, 1,536, and 3,072 generated bases as a diagnostic. Use
   the unchanged analytic one-sided threshold and keep correct-key, matched ordinary, wrong-key,
   independent-key ordinary, and public-RefSeq families separate.
6. Run the separately frozen position-independent protocol on only the 192 evaluation prompts.

The primary quality statement is the paired difference in GENERator negative log-likelihood per
6-mer, with its 95% prompt-cluster interval. “No measured quality loss” is allowed only if the
estimate is small, its interval is compatible with zero, and the declared sequence summaries show
no corrected difference. These are model and sequence proxies, not biological-function tests.

## Execution and evidence gates

`configs/generator_synthid_validation_v1.toml` is the required MPS/CPU-capable profile and uses
float32 for the model's declared checkpoint precision. The optional CUDA profile may accelerate
the identical code path and must record its dtype and environment. Before the full run, a small
checkpoint/tokenizer/likelihood benchmark must pass. Then the full artifact validator, the
position-independent validator, all unit tests, lint, and the evidence checker must pass before any
number is admitted to the manuscript or evidence ledger.

Raw model weights, generated sequences, and keys remain outside Git. Final result files are never
silently overwritten; corrections create a new artifact and measurement ID.

