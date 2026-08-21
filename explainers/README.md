# Project explainers

These notes explain the project for someone seeing genomic language models and sampling
watermarks for the first time. They are a learning path, not a second research plan.

Read them in order:

1. [The question](01_the_question.md) — what the paper is trying to establish.
2. [How the models generate DNA](02_how_genomic_models_generate.md) — 6-mers, probabilities, and phases.
3. [How the watermark works](03_how_the_watermark_works.md) — a complete four-token example.
4. [Why model policies matter](04_model_policies.md) — `C_tok`, `C_bp`, `G_tok`, and `G_bp`.
5. [What we have built](05_what_we_have_built.md) — the repository as it exists today.
6. [Detection and DNA edits](06_detection_and_edits.md) — strand, phase, crops, substitutions, and indels.
7. [Running it on the MacBook](07_running_and_next_steps.md) — commands, outputs, and the next gate.
8. [The first real DNA prompt cohort](08_public_cohort_and_carbon_pilot.md) — reproducible public windows and what the Carbon pilot taught us.
9. [GENERATOR policies and numerical precision](09_generator_policies_and_precision.md) — why `G_tok` differs from `G_bp` and why this model uses float32.
10. [From engineering pilot to evidence](10_from_pilot_to_evidence.md) — why 24 prompts can produce 3,072 states without pretending they are independent.
11. [What the first full capacity result taught us](11_first_full_capacity_result.md) — why one unusual prompt caused a fair, output-blind cohort expansion.
12. [From capacity to detection](12_from_capacity_to_detection.md) — why a promising channel estimate still needs generated sequences and a calibrated standalone detector.
13. [What "admitted evidence" means](13_what_admitted_evidence_means.md) — how a validated result becomes a citable number, and what the capacity numbers still do not claim.

The short version is this: the model assigns probabilities to possible next DNA blocks. A secret
key changes *how we draw* from those probabilities, not what the probabilities are on average. The
detector later looks for a key-dependent pattern using only the DNA, the key, and public settings.

No result enters the paper automatically. We have implemented and tested the foundation, audited
the real tokenizers, completed the sequential capacity gate for Carbon and both GENERator-v2
policies, and admitted exactly three numbers from it to the evidence ledger. The next gate is
watermarked generation, distribution preservation, and converting capacity into actual
standalone-detector performance.
