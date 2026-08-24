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
14. [Writing the watermark into real DNA](14_writing_the_watermark.md) — the generation loop, why the distribution stays honest, and what a single fixed key can still hide.
15. [The detector, and what an honest threshold costs](15_the_detector_and_honest_thresholds.md) — a model-free verifier searching 96 alignments, and why calibrating the maximum is the whole problem.
16. [How much damage it survives](16_how_much_damage_it_survives.md) — substitution robustness, crops and the other strand, what a wider search costs, and a correction worth reading.
17. [The synchronization wall](17_the_synchronization_wall.md) — why one deleted base breaks everything after it, two predictions that were wrong in useful ways, and the wall that a windowed detector moves but cannot remove.
18. [Measuring against the alternatives](18_measuring_against_the_alternatives.md) — how a comparison between watermark constructions can be rigged without meaning to, why our method loses on clean sequences and why that is structural, and a threshold that does not transfer to real genomes.
19. [What two outputs buy an attacker](19_what_two_outputs_buy_an_attacker.md) — why anyone holding two watermarked sequences can mint a third the verifier accepts, why that is structural rather than a bug, and why both of the instruments we built to price the removal attack turned out to be blind to it.

The short version is this: the model assigns probabilities to possible next DNA blocks. A secret
key changes *how we draw* from those probabilities, not what the probabilities are on average. The
detector later looks for a key-dependent pattern using only the DNA, the key, and public settings.

No result enters the paper automatically. The foundation, the real tokenizer audits, the sequential
capacity gate, the watermarked generation path, the distribution-preservation gate, calibrated clean
detection, substitution and crop and strand robustness, the insertion and deletion synchronization
result, the unkeyed-distinguisher checks, and the matched comparison against the two published
alternatives have all been completed and reviewed. **85 numbers are admitted to the evidence ledger**,
with five records of results that were superseded and why.

Two findings are worth carrying away. The binding limit is **synchronization**, not capacity: a
deleted base pushes everything after it off the reading grid, and the detector tolerates indel rates
one to two orders of magnitude below its substitution tolerance. And on clean sequences our own
construction is **not** the strongest of the three measured — the exponential method is about 7.5
times louder per token, because ours hides one bit per token by design and is already at that ceiling.

The adversarial end is now measured too, and it is negative: anyone holding **two** outputs from one
key can splice them into a third sequence that the verifier accepts every time, because the detector's
per-position checks are blind to the DNA content. The construction authenticates a *distribution*, not
a *sequence*. **103 numbers are admitted to the evidence ledger.**

Those two instruments now exist, and the honest result is that neither prices the removal attack: the
independent-model score barely moves, and the reading-frame measure moves a lot without moving in a
consistent direction, because a long reading frame in high-entropy DNA is mostly a chance event that
shuffling re-rolls. The attack is unpriced and we say so rather than quoting the small numbers our
blind instruments produce.

A first full draft of the paper exists and builds, with every number drawn from the ledger and every
figure generated from it. What remains is checking rather than measuring.
