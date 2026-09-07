# Generation and control definitions

## Carbon generation policy

The experiment uses Carbon-500M revision
`9796b752108258c1d365089f842e62e6c0547704`. At each generation step, the model probabilities are
restricted to the 4,096 canonical DNA 6-mers and normalized to sum to one. Temperature is 1.0 and
no top-k or top-p truncation is applied.

## GENERator generation policy

The rebuilt paper's second model uses `GenerTeam/GENERator-v2-eukaryote-1.2b-base` revision
`c41b0018da9ee13b9e96ee54647de8da381ccd72`. Policy `G_tok` gathers the logits for its 4,096
canonical DNA 6-mer tokens, whose tokenizer IDs are 32 through 4,127, and normalizes those logits
once. Temperature is 1.0 and no top-k or top-p truncation is applied. This is the direct token
distribution, not the released base-marginal helper.

## SynthID arm

`synthid-tournament-v1` applies 30 keyed tournament layers to the current model probability
distribution. Its keyed values depend on the preceding four generated 6-mers and each candidate
6-mer. The first four generated tokens are ordinary samples so that the detector can reconstruct
all later contexts from the output alone. A repeated four-token context is sampled ordinarily and
excluded from the detector score, matching the reference design.

## Ordinary arm

`ordinary-categorical-v1` samples directly from the same model-specific probability distribution,
with the same prompt, temperature, output length, model revision, and token restriction. It has no
key.

The two ordinary draws for a prompt are made independently reproducible by distinct public replay
seeds. Sampling uses a random draw from the model distribution at every step; it is not greedy
generation. Because each sampled token changes the next model context, an early difference usually
causes the two continuations to diverge further. The watermark key is neither needed nor used to
create ordinary variation.

## Keys and draws

Each prompt has two stored draws. Draw zero and draw one use two different public fixture keys in
the SynthID arm and two different public replay seeds in both arms. These keys are deliberately
public so another researcher can reproduce the study. A real deployment must use an independently
generated secret key that is never written to results.
