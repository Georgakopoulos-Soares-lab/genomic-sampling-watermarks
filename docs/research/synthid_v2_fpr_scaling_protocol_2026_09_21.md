# SynthID v2 false-positive-rate scaling protocol

This protocol is frozen before the first v2 model generation. It governs the new Carbon-500M and
GENERator-v2 1.2B runs only; the version-one artifacts remain immutable.

## Question and outcome

Estimate the prompt-level false-positive frequency of the existing position-independent detector
at its declared read-level threshold of 0.01. The ordinary corresponding-key family is primary;
the watermarked wrong-key family is reported separately. Correct-key detection and the three
single-nucleotide conditions are retained as checks. The prompt is the independent unit: either
positive draw makes a prompt positive. Exact one-sided 95% binomial upper bounds use
`Beta^{-1}(0.95; positives + 1, prompts - positives)`, with an upper bound of 1 when all prompts
are positive. At 1,544 evaluation prompts, 0, 8, and 15 positive prompt clusters imply upper
bounds of 0.19384%, 0.93294%, and 1.49200%, respectively. Thus a larger sample sharpens the
estimate, but a bound below 1% is contingent on at most eight observed positives.

## Cohort and split

- Source spec: `data/public_prompt_cohort_fpr_v2_sources.yaml`, frozen before fetching output.
- Frozen candidate manifest: `data/public_prompt_cohort_fpr_v2_1608.yaml`.
- Processed prompts: `data/processed/ncbi_refseq_eukaryote_windows_fpr_v2_1608/prompts.jsonl`.
- Cohort identifier: `ncbi_refseq_eukaryote_windows_fpr_v2_1608`.
- Cohort content SHA-256: `f6075a85bc056f5159952031618c544fb3a82864ed9029c913e7f5a7d03c5dc5`
  (the ordered per-case digest the runner recomputes from `prompts.jsonl` and pins into every
  generation and detection shard).
- Source specification SHA-256: `8ecdbdf10eda6ebbefad90031552914e62671d16039b209b2025d5210fd53b1d`.
- Frozen candidate manifest SHA-256: `7adad76712848a0d0b19e9660c24197293d751610a98ecb8db1bda35534b5c55`.
- Processed `prompts.jsonl` SHA-256: `cb19e90662fcb25f774b0840e2e696132e2dc9c54439d97597bd186d4948f775`.
- Public-null cohort SHA-256: `b949530f16ea5b4b19ef9c43170bafac3ac9a1d43b355efb92ec8a5ffeaba0c5`.
- Cohort frozen and processed offline on 2026-09-21; the processed build ran with `--offline`,
  so no prompt could be reselected after any model output existed.
- Twelve accession-versioned non-human RefSeq chromosomes contribute 134 output-blind,
  non-overlapping 3,072-base source spans each. Each source span has a 384-base prompt.
- Use the existing deterministic SHA-256 prompt split with 64 calibration prompts and 1,544
  evaluation prompts. Calibration prompts are excluded from the final detector rates. The
  detector threshold is analytic and is not fitted to this cohort.

## Generation

For each model, generate two independent draws and two arms per prompt. Carbon-500M revision
`9796b752108258c1d365089f842e62e6c0547704` uses `C_tok`; GENERator-v2 1.2B revision
`c41b0018da9ee13b9e96ee54647de8da381ccd72` uses `G_tok`. Each policy normalizes over its
4,096 canonical DNA 6-mers, uses temperature 1 and no top-k or top-p truncation, and generates
512 tokens (3,072 bases). The ordinary arm is categorical sampling from that same policy. The
SynthID arm uses a 30-layer binary tournament, four preceding token context, and 1,024-context
repetition history. The first four generated tokens and repeated contexts are sampled ordinarily;
repeated contexts are excluded from detector scoring. Draws use the two established public
fixture-key indices and distinct public replay seeds. No raw key appears in an artifact.

New domain labels `carbon-synthid-fpr-v2` and `generator-synthid-fpr-v2` enter the existing
`experiment_label/cohort_id/policy_id` domain rule. This deliberately produces new keyed
functions for the new evidence identity; the tournament and sampling laws are unchanged.

## Position-independent detector

Prepend each stored 384-base prompt to its generated continuation. For
each clean read and each read with one deterministic substitution, insertion, or deletion inside
the continuation, search both orientations, every base start, and window lengths 384, 768, 1,536,
and 3,072 bases. Apply the same 30 layers, four-token context, and repetition mask. The exact
fair-binomial upper tail is multiplied by the number of searched orientation × start × length
hypotheses, capped at one, and compared with 0.01. This correction covers the complete searched
family; the smallest nominal window p-value is not a read-level p-value. Expected hypothesis
counts are 16,136 for clean/substitution, 16,144 for insertion, and 16,128 for deletion.

Report three distinct families per condition: watermarked correct key, ordinary corresponding
key, and watermarked other draw's key. The design has 1,544 prompts × 2 draws × 3 families × 4
conditions = 37,056 read-level decisions per model. Each family/condition reports read counts,
prompt-cluster counts, exact prompt-level intervals, and the one-sided upper bound.

## Gates and interpretation

Run a four-prompt, 64-token direct-A100 smoke for each model and validate complete per-draw shards
before starting the full 512-token runs. For full generation, verify every shard's cohort, prompt
digest, policy, label, draw, and sequence checksum before finalization. Detection starts only after
both full draw files and the fixed prompt split are complete. Per-prompt generation and detection
shards are immutable checkpoints; rerunning the same command validates and skips completed shards.
Keep separate smoke and full roots. Record environment, exact command, git/source manifest,
config hash, protocol hash, model revisions, cohort hash, runtime, artifact hashes, and validation
status in the execution document. A result may enter `evidence/measurements.yaml` only after the
strict validators pass and all artifact/protocol hashes agree.

Predeclared interpretation: clean correct-key rate below 0.95 is a failure; any single-edit
correct-key rate below 0.90 is a robustness warning. An observed control rate or upper bound above
1% is reported as such, with no claim that the 1% operational rate was established. This is a
statistical watermark and model-proxy study, not evidence of biological function or key secrecy.
