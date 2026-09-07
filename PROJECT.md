# Project charter

## Research question

Can the SynthID tournament watermark be added while two genomic language models generate DNA,
without exceeding a pre-specified model-quality loss bound, and can a verifier find the watermark
when it does not know where the generated part begins? The rebuilt paper will answer this jointly
for Carbon-500M and GENERator-v2 1.2B under one new confirmatory study identity.

## Retained scope

This repository contains one watermark method: `synthid-tournament-v1`. The two paper models are
Carbon-500M revision `9796b752108258c1d365089f842e62e6c0547704`, restricted to its 4,096
canonical DNA 6-mer tokens, and
`GenerTeam/GENERator-v2-eukaryote-1.2b-base` revision
`c41b0018da9ee13b9e96ee54647de8da381ccd72` and its direct 4,096-token canonical policy `G_tok`.
Neither model uses an alternate base-marginal policy in the retained experiments. Ordinary
categorical sampling from the model-specific distribution is the only generation control.

The retained detector is `synthid-position-independent-detector-v1`. It receives DNA, a secret key,
the public generation domain, and fixed public settings. It does not receive the prompt, model,
model probabilities, random generation seed, strand, 6-mer phase, or generation boundary.

## Evidence status

Existing version-one Carbon and GENERator measurements are retained only as development history.
They may inform runtime and blinded power planning, but they are not confirmatory evidence for the
rebuilt paper. New paper-bound evidence requires a fresh prompt cohort, a new protocol and evidence
identity, and complete M5 Pro runs for both models. The active design and gates are in
`docs/research/dual_model_synthid_paper_rebuild_plan.md`.

## Claim boundary

The study measures statistical watermark detection and model-based sequence-quality proxies. It
does not establish biological function, viability, safety, sequence authenticity, or formal
secret-key security. The operational attacker is assumed not to know the key and not to see or
query the detector score. Multiple-edit and detector-guided attack experiments are outside this
study.

The previous detector runs used Linux CPU and the previous generations used CUDA. The new paper
does not inherit those results. Every paper-bound stage for both models must run through the
documented Apple M5 Pro path unless the hardware contract is explicitly revised before the new
protocol is frozen.
