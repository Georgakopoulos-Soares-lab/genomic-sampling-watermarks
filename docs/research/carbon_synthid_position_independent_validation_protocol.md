# Carbon SynthID position-independent detector validation protocol

Frozen before execution. This validation applies only to `synthid-tournament-v1` and
`synthid-position-independent-detector-v1`. It does not use partition coupling, ITS, EXP, or any
other watermark implementation.

## Objective

Check that the final detector can identify the existing Carbon SynthID watermark when it is given
only an observed DNA read, the secret-key fixture, the public generation domain, and fixed public
settings. In particular, it receives no prompt length, generation boundary, 6-mer phase, strand,
or position offset.

The generation algorithm is not changed or rerun. Consequently this experiment tests detection,
not model quality. Existing matched generation artifacts and their checksums are reused so the
sequence-quality conclusions from the frozen Carbon validation remain unchanged.

## Frozen data and split

- model and policy: Carbon-500M `C_tok`, revision
  `9796b752108258c1d365089f842e62e6c0547704`;
- source corpus: the immutable `carbon_synthid_validation_hpc_v4` generation bundle;
- split: only the 192 frozen evaluation prompts, never the 64 detector-selection prompts;
- trials: two independent stored draws per prompt, giving 384 sequence trials per result cell;
- prompt: the stored 384-base public prompt is prepended to each continuation;
- continuation: the stored 3,072-base SynthID or matched ordinary Carbon output.

No model inference, continuation generation, empirical threshold calibration, or detector-setting
selection is permitted during this validation.

## Detector configuration

Every read is evaluated once with the complete default configuration:

- both supplied and reverse-complement orientations;
- every nucleotide start position;
- 384, 768, 1,536, and 3,072-base candidate windows jointly;
- 30 tournament layers;
- four local context tokens;
- 1,024-context repetition history; and
- one sequence-level target false-positive rate of 0.01.

The local score uses the exact fair-binomial upper tail. The final probability is the smallest
local probability multiplied by the total number of searched orientation × start × length
hypotheses and capped at one. The implementation retains the same calculation in log space to
avoid numerical underflow.

For clean and one-substitution reads, the read has 3,456 bases and the complete search contains
16,136 hypotheses. A one-base insertion gives 3,457 bases and 16,144 hypotheses. A one-base
deletion gives 3,455 bases and 16,128 hypotheses. These counts include both orientations and all
four lengths. Any other count invalidates the corresponding trial.

## Families

Each prompt and draw contributes three separate detector trials:

1. `watermarked_correct_key`: SynthID continuation checked with the fixture key used to generate
   that draw;
2. `ordinary_corresponding_key`: matched ordinary Carbon continuation checked with that same key;
3. `watermarked_wrong_key`: the SynthID continuation checked with the other draw's fixture key.

The ordinary and wrong-key families are not pooled. Fixture keys are public reproducibility
material, not deployment secrets and not evidence of cryptographic key security.

## Conditions

The primary condition is the clean prompt-plus-continuation read. Three robustness conditions are
reported separately after exactly one deterministic nucleotide event inside the continuation:

- one substitution;
- one insertion; and
- one deletion.

The edit position and inserted or replacement base use the already frozen public replay procedure
in `synthid_boundary.py`. The same edit identity is used for the matched SynthID and ordinary arm.
These are single-event tests, not 1% edit-rate or adversarial-edit tests.

The full design therefore contains 192 prompts × two draws × three families × four conditions =
4,608 sequence-level decisions.

## Required checks and reporting

Before interpreting the corpus run:

- exact binomial tails must agree with literal enumeration on small cases;
- cached every-start scoring must agree with literal substring scoring;
- the detector must recover synthetic watermarks under two different prefix lengths, reverse
  complementation, and each single-base edit;
- the full repository unit suite and lint must pass; and
- the evidence ledger checker must pass.

For each condition and family, report detections out of 384, the sequence rate, a prompt-cluster
bootstrap interval, and prompt-level exact intervals after collapsing the two draws by “either
draw” and “both draws.” Also report winning orientation and window-length distributions, the range
of corrected probabilities, and the weakest correct-key result.

The strict validator must reject incomplete prompt/draw/family/condition grids, incorrect key
mapping, incorrect read or search sizes, invalid coordinates, mismatched exact and log
probabilities, or a decision inconsistent with the fixed 0.01 rule. Result artifacts contain no raw
key or DNA sequence.

## Interpretation gates and limits

- Clean correct-key detection below 0.95 is a failure of the implemented position-independent
  protocol for this corpus.
- Each single-edit correct-key rate below 0.90 is a robustness warning.
- Every ordinary and wrong-key rate is interpreted with its prompt-level confidence interval; 384
  correlated sequence draws cannot tightly establish a 1% operational ceiling.
- The analytic correction controls the declared finite search under the keyed-PRF idealization.
  An undeclared larger search must receive a new multiplicity correction.
- A passing result establishes neither biological function nor viability, authenticity against an
  adversary, key security from many observations, nor robustness to multiple or adversarial edits.
