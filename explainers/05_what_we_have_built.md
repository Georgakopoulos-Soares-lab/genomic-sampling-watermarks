# 05 — What we have built

## The repository is both code and paper workspace

The project has one package, one manuscript, and one deliberately small evidence ledger. It does
not create a directory or manifest system for every planned experiment.

```text
src/genomic_watermarks/  tested implementation
tests/                   offline correctness tests
scripts/                 audits, checks, collectors, and analysis commands
configs/                 laptop and smoke settings
docs/                    formal research definitions
explainers/               beginner-friendly learning path
evidence/                 paper-printable measurements only
paper/                    one combined manuscript
.claude/                  project instructions and narrow agent roles
```

## Implemented now

### DNA handling

- uppercase normalization and rejection of noncanonical bases;
- reverse complements;
- fixed 6-mer tokenization;
- all 12 strand-and-phase hypotheses: two orientations times six phases.

Example:

```text
forward:            ATCGGC
reverse complement: GCCGAT
```

### Reference watermark sampler

- deterministic keyed partitions using HMAC-SHA-256;
- equal group cardinality;
- maximal coupling for balanced or unbalanced probability mass;
- conditional token sampling that preserves the declared marginal;
- deterministic fixtures for tests.

The deterministic test random generator is for reproducibility. It is not presented as a
production cryptographic random generator.

### Model integration foundation

- exact revisions for Carbon, GENERator, and reference implementations;
- Carbon and GENERator prompt formatting;
- canonical 6-mer ID extraction;
- direct-token and base-product probability transforms;
- revision-pinned Carbon and GENERator tokenizer loading;
- an enforced pin for Carbon's transitive Qwen tokenizer;
- MPS-first runtime selection with CPU fallback;
- a one-forward-pass model probe that reports probabilities, timing, and memory without saving DNA.
- a completed eight-context Carbon-500M `C_tok` synthetic capacity pilot with a four-context CPU
  comparison.
- a frozen 12-window public RefSeq prompt cohort and a full Carbon MPS/CPU engineering pilot over
  it.
- completed GENERator-v2 `G_tok` and `G_bp` pilots on the same cohort, with an enforced revision
  boundary for the model's internal tokenizer reload.
- an unwatermarked sequential collector that grows each context by one sampled 6-mer, measures 32
  public partitions without extra model passes, and stores no raw generated DNA.
- a strict report validator, prompt-cluster bootstrap, frozen 24-prompt expansion, and complete
  three-policy E2 capacity runs.

### Edit and detector fixtures

- substitution, insertion, deletion, and crop operations;
- keyed partition-agreement scoring;
- explicit forward/reverse-complement and phase search.

These are foundations for later robustness experiments, not a complete calibrated detector.

### Research controls

- one combined paper charter;
- clear model-policy IDs;
- a threat model and claim boundaries;
- an M5 Pro hardware contract;
- a minimal evidence ledger;
- a manuscript skeleton;
- project-specific `CLAUDE.md` and `.claude/agents/` roles.

## What the tests currently prove

The offline suite checks 59 behaviors, including:

- the 4,096-token canonical vocabulary;
- tokenizer mapping edge cases with local fakes;
- Carbon's transitive revision injection and loader restoration;
- stable normalization of model scores;
- the difference between direct and base-product distributions;
- exact-marginal behavior on fixed toy distributions;
- DNA edits and detector hypothesis enumeration;
- invalid-input failures.

Separate real-tokenizer audits have also checked the pinned upstream tokenizers. These audits do not
load checkpoint weights.

## Not implemented yet

- the full generation loop that applies a watermark at every model step;
- evidence admission for the now-complete prompt-cluster E2 runs;
- inverse-transform and exponential/Gumbel samplers;
- a globally calibrated detector;
- paper-scale public cohorts and biological proxy measurements;
- attack experiments and paper results;
- ECC or pseudorandom-code experiments.

The evidence ledger correctly contains zero measurements today. Passing unit tests validates code
properties; it does not create empirical model results.

Next: [Detection and DNA edits](06_detection_and_edits.md).
