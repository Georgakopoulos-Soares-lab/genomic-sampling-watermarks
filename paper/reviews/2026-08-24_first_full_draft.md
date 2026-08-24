# Review note — 2026-08-24 — first evidence-complete draft

## What changed

The manuscript moved from a protocol scaffold to a full draft. Abstract, introduction with
contribution bullets, methods, experimental design, results, discussion, and limitations are written;
nine figures and six tables are generated from the ledger; the document builds.

Evidence state at the time of this draft: **97 admitted measurements** across eleven experiment
families, plus five records of superseded results and why. Waves 1, 2, and 3 of
`context/05_drafting_readiness_plan.md` are all unblocked on evidence, so nothing in this draft is
written from an expected result.

## What was checked, mechanically

| Check | Result |
|---|---|
| Every empirical number resolves to the ledger | **enforced by construction.** Prose cites `\newcommand` macros generated from the ledger; tables are generated whole. No empirical number is typed into prose. |
| Figures generated, not hand-edited | 9 figures from `paper/scripts/make_figures.py`, 57 measurements; `scripts/check_figures.py` passes |
| Figure manifest matches the ledger | passes: every cited id exists, every figure file exists, every figure declares a caption claim and an axis direction |
| Manuscript builds | passes, no undefined references |
| Generated prose has no lost spaces | passes; `scripts/check_generated_prose.py` added after this defect reached a rendered PDF |
| Test suite, lint, format, ledger | 290 tests, ruff clean, ledger OK |

## Defects found and fixed while drafting

1. **Ten captions rendered glued words** (`perbase`, `everylength`, `rateafter`, `tentimes`, and six
   more), because a string literal split across source lines lost its trailing space. Invisible in a
   source diff, survives every test, and reached a rendered PDF. Fixed, and
   `scripts/check_generated_prose.py` now parses the generator sources and fails on any implicit
   concatenation whose literals do not carry their own space. A dictionary-based heuristic was tried
   first and abandoned: it produced dozens of false positives on ordinary inflected words, while the
   exact source-level check produced exactly the ten real defects and nothing else.

2. **The E7 figure referenced a length E7 never measured.** The indel figure initially asked for 3,072
   bases; the indel experiments stop at 1,536. The figure script raised rather than plotting a
   default, which is the behaviour that caught it, and the figure and its substitution overlay are now
   both drawn at 1,536.

3. **Two figures were unreadable as first drawn.** The baseline-comparison bands were invisible on a
   log axis and the clean-detection panel was a flat line at 1.000 carrying no information. Both were
   redesigned: the first as a range-bar point plot, the second with a second panel showing the
   separation margin, which is where the length dependence actually lives.

4. **Log axes collided with their own minor ticks**, rendering length labels as an unreadable smear.
   Fixed with an explicit null minor locator.

## Judgement calls a reviewer should check

- **The crop figure shows all three policies agreeing exactly.** That looks like a plotting bug and is
  not: every failing condition is one whose required key-stream offset lies outside the declared
  search, which is policy-independent. The figure script asserts the condition lists match rather than
  assuming it, and the caption states the reason.

- **Two results are reported with inverted sign.** `e11.spoofing.*` reports a detection rate of 1.000
  that is a vulnerability, and `e12.removal.*` reports 0.000 that is a successful attack. They are kept
  off the axes of the intended-detection figures, marked with a distinct colour and marker, and both
  the figure caption and the table caption state which direction is which. This is the single easiest
  thing for a later edit to break.

- **The baseline comparison deliberately does not plot detection rate.** It is 1.000 in every
  method-length-policy cell, so plotting it would present a null result as agreement. The per-token
  signal is plotted instead, in each method's own null units, and the caption says why.

- **The paper states that our own construction is the weaker one.** That is what the measurement says,
  and the contribution is reframed around the measurement rather than the construction.

## Still open before submission

Not evidence gaps — these are the remaining pre-submission steps.

1. `paper-sources` over every citation against a primary source. Related work currently cites four
   references and has not been checked live.
2. `security-review` over every cryptographic and adversarial sentence, especially the claim that the
   splice argument extends to any position-indexed content-blind statistic, which is reasoning rather
   than measurement and is labelled as such.
3. `biological-proxies` over every sequence-statistic sentence, especially the removal utility claim.
4. `paper-structure`, then `paper-style`.
5. Confirm no host names, local paths, run ids, or key material appear anywhere in the source.
6. Two desirable but non-gating experiments: additional `G_bp` draws to resolve two nominal
   distinguisher rejections (needs mains power), and the ORF and independent-model-likelihood proxies
   that would price the removal attack.

---

## Addendum, same day — E15 added, and it made a limitation worse

After this draft was first written, the two order-sensitive proxies that
`docs/baseline_definition.md` had declared and never implemented were built and run: open reading frame
summaries and a score under a Markov reference fitted on held-out cohort prompts. The point was to
price the E12 removal attack, which the nine composition proxies cannot see.

**Neither instrument prices it.** The ledger grew to **103 measurements**, a tenth figure was added, and
three manuscript sections were rewritten — but in the direction of a stronger limitation, not a weaker
one.

The way the reading-frame measure failed is the part worth reviewing carefully, because it nearly went
the other way. Its relative shift is 0.07 to 0.43, larger than any composition shift on most cells, and
that number alone reads as an instrument that works. The exact paired sign-flip test over the eight
prompts shows the direction is absent: under every bounded shuffle the longest reading frame rises
about as often as it falls. On high-entropy DNA a long reading frame is a chance extreme-value
statistic, so permuting the sequence re-rolls it rather than destroying a structure, and a relative
shift built from absolute differences records the re-roll.

Had the shift been admitted without the paired test, this project would have published a claim that the
removal attack costs a measurable amount of sequence structure. It does not, as far as we can measure.

Consequences for review:

- `fig10_unpriced_removal` exists specifically to make this visible: magnitude on the left, p-value on
  the right, with the 0.05 line drawn. Its declared sign says a left-panel value is not evidence unless
  the right panel is below the line. **Do not let a later edit present the left panel alone.**
- `src/genomic_watermarks/structure_report.py` recomputes the sign-flip p-value from the stored rows
  during validation rather than trusting it, because the p-value *is* the result here.
- The validator also rejects a reference model fitted on any scored prompt, checked by prompt id. An
  independent-model score fitted on the sequences it scores would be circular, and the check is
  structural rather than a note.
- The E15 protocol discloses that an exploratory run on one policy preceded the frozen shape, so its
  predictions are informed rather than blind. That disclosure is deliberate.

This was the seventh instance in the project of an unsigned magnitude masquerading as an effect. The
standing rule in `CLAUDE.md` now states it directly: never report an unsigned magnitude as an effect;
the paired test decides.
