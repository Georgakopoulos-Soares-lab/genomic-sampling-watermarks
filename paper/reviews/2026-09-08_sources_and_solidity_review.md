# Review note — 2026-09-08 — source verification, carried across the restructure

## What this note is, and what happened to it

This began as the `paper-sources` pass that `2026-08-24_first_full_draft.md` left open: live
verification of every citation and every external model claim in the E-series partition-coupling
manuscript, against primary sources.

While that pass was running, the `Full restructure` commit landed. It deleted the sectioned manuscript
(`sections/*.tex`, `generated/*`, `make_tables.py`, `make_figures.py`, the ten ledger-driven figures,
`figures/manifest.json`), gutted the 103-measurement ledger, and replaced all of it with the
single-file Carbon SynthID validation draft and `paper/context/evidence_map.md`.

**Most of the manuscript-level work in this pass was therefore discarded rather than applied**, because
its targets no longer exist. What survives is recorded below: facts about external sources, which do
not depend on which manuscript cites them, plus the merged bibliography.

The discarded edits are recoverable — they are in `stash@{0}` and were also saved as a patch outside
the repository during the merge. They fixed the abstract's uncaveated "complete from 96 bases", an
overstated key-reuse calibration sentence, a proxy-cost figure that quoted the full shuffle where
bounded shuffles shift further, two orphan figure floats, and a `targetFPR` that was typed rather than
read from the ledger. **If any of the E-series material is ever revived, read that patch first** — several
of those defects were claim-strength problems, not typos, and they will come back with the prose.

## Applied: the bibliography

`paper/manuscript/source/refs.bib` now holds 30 entries. The 13 that came with the restructure are
kept, with two upgraded from this pass's verification:

- **`carbon2026`** — full 14-author list from the bioRxiv landing page, replacing `and others`.
- **`zhang2025securing`** — confirmed accepted at NeurIPS 2025; had been cited as a bare preprint.

`kuditipudi2024robust` was independently confirmed as TMLR 2024 through the OpenReview API record
(ISSN 2835-8856, published 2024-06-02), which matches what the restructure already had; ISSN and a
stable URL were added.

Seventeen entries were added and are **not yet cited** from `main.tex`. Each was added against a
specific gap in the current draft's Background or Discussion:

| Gap in the current draft | Entries that serve it |
|---|---|
| §Watermarking what a language model writes describes distortion-free sampling but not its source or its reweighting siblings | `aaronson2022watermark`, `hu2024unbiased`, `wu2024dipmark` |
| §Marks written into DNA before models wrote DNA cites the synthetic cell and DNA-Crypt, but not watermarks embedded in synthetic genes | `liss2012watermarks` |
| Robustness claims lean on `zhang2024sand` alone; the attack literature is otherwise absent | `jovanovic2024stealing`, `reynolds2025breaking`, `wu2024collisions`, `gloaguen2025spoofing`, `diaa2025adaptive`, `sadasivan2025reliably` |
| The edit-budget discussion has no coding-theoretic reference point | `christ2024prc`, `haeupler2017synchronization` |
| Nothing distinguishes position-indexed marks from content-binding ones | `fairoze2025publicly` |
| §216 cites DNAMark for designed sequences but not the closest local-verification biosecurity precedent | `chen2025protein` |
| Released code is what was actually run, and it differs from the papers | `carbon500m`, `generatorv2checkpoint`, `generatorv22026` |

`reynolds2025breaking` and `wu2024collisions` deserve attention from whoever writes the next
Background pass. The first spoofs the Kuditipudi distortion-free family by recovering its key sequence;
the second shows key collision undermining the distortion-free property itself. A draft about a keyed
sampling watermark that cites neither will read as unaware of them.

## Verified against primary sources, and still true after the restructure

Nothing below came from the repository's own notes.

- **`Carbon-500M` has both audited branches.** The model card confirms a 500M decoder-only Llama-style
  DNA model, a hybrid 6-mer plus Qwen3-BPE tokenizer, a `main` branch that is a standard causal LM, and
  an `fns` branch adding base-pair-level generation and scoring. This is the checkpoint the current
  draft generates from.
- **`_BPLogitsProcessor` is real, and the preprint does not describe it.** `modeling_generator.py` in
  the pinned GENERator-v2 checkpoint defines it, overrides `generate()`, marginalizes the 4,096-way
  distribution to per-base probabilities, samples each base independently, and reassembles a token id.
  A direct read of the GENERator-v2 full text found the word "sampling" zero times: its marginalization
  is presented as a training objective, and its only inference-time use there is single-position
  variant-effect scoring. **The released generation path is not the one the paper describes.**
- **That divergence is the training objective's dual, not a bug.** The same preprint proves factorised
  nucleotide supervision equivalent to maximum-likelihood training of a predictor emitting $k$
  single-nucleotide tokens per step under conditional independence given the shared hidden state. The
  released sampler is exactly that predictor. This is the strongest available argument for pinning
  checkpoints rather than citing papers for generation behaviour.
- **The GENERator-v2 authors state 6-mer phase sensitivity themselves**, noting that shifting the
  tokenization offset by one nucleotide yields an entirely different tokenization. Any fixed-block
  alignment argument can cite the model's own paper for the premise.
- **Factorised nucleotide supervision is legitimately attributable to both families.** GENERator-v2
  introduces it; the Carbon-500M card independently uses the term for its `fns` branch.
- **The Carbon bioRxiv DOI prefix `10.64898` is correct**, not a corrupted `10.1101`.

## Corrected in the repository, then superseded

Two documentation defects were found and fixed during this pass, and the restructure then removed the
text they lived in. Recording them so they are not reintroduced:

- `docs/research/literature_map.md` listed two attack papers under titles that do not match their
  primary sources, and linked a withdrawn OpenReview id for a third. The correct titles are
  *Discovering Spoofing Attempts on Language Model Watermarks*, *Optimizing Adaptive Attacks against
  Watermarks for Language Models*, and *Breaking Distortion-free Watermarks in Large Language Models*.
- `CLAUDE.md` stated the indel gap as "50 to 150 times" and the windowed recovery as "five- to
  tenfold". Recomputed from the then-current ledger, the true ratios were 75x to 200x and two- to
  tenfold. Both numbers were wrong in the charter for as long as it stood.

## One thing the restructure gave up, flagged rather than fixed

The old manuscript enforced "every paper number resolves to the ledger" *mechanically*: prose cited
`\newcommand` macros generated from `evidence/measurements.yaml`, tables were generated whole, and
`make_tables.py` raised on a missing measurement. No empirical number could be typed into prose, so it
could not drift.

The restructure deleted that generator. `paper/context/evidence_map.md` now carries the same rule as a
hand-maintained table mapping claims to `synthid.*` identifiers, and numbers are typed directly into
`main.tex`. Figures are still generated, from `figures/figure_values.json` via
`scripts/make_paper_figures.py`, so the figure side keeps its guarantee. The prose side does not:
`scripts/check_evidence.py` validates evidence artifacts, not the numbers printed in the manuscript.

That is a real loss of a guarantee this project built deliberately, and it is worth stating plainly
because the failure mode is silent — a number edited in prose now stays wrong until a human compares it
against the map. Rebuilding a macro generator against the `synthid.*` identifiers would restore it.
Whether that is worth doing now is a call for whoever owns the new draft; it was not attempted here
because it is a build-system change, not a review finding.

Note also that `scripts/check_evidence.py` currently fails on this machine with five missing artifacts
under `outputs/carbon_synthid_e16_v1/` and `outputs/carbon_synthid_position_independent_v1/`. Those
paths are gitignored run outputs, so this is an environment gap rather than a defect — but it means the
validator cannot be used as a green light here, and nobody should read a clean local run as evidence
that it passed.

## Addendum, same day — first pass over the current Carbon SynthID draft

Done after the merge, so this note now covers the live manuscript as well as the deleted one.

### Checked mechanically, all sound

- **The search count reproduces exactly.** $M = 2\sum_L (N-L+1)$ with $N = 3{,}456$ and
  $L \in \{384, 768, 1{,}536, 3{,}072\}$ gives $2 \times 8{,}068 = 16{,}136$, and
  $\log_{10}(M/\alpha) = 6.2078$, which is the stated 6.21.
- **Equation 1 is the correct tournament update, derived independently.** For two i.i.d. entrants
  from $p$ with ties broken uniformly, the winner's law is $p(x)\,(1 + g(x) - G)$ where
  $G = \sum_y p(y) g(y)$ — exactly the printed equation. It sums to one and is non-negative for all
  $G \in [0,1]$, and layer-wise application is genuinely equivalent to the $2^m$-leaf tournament.
- **The mean-preservation identity holds for all $m$**, not just one layer: $E_{g}[1 + g(x) - G] = 1$
  for fresh independent bits, so $E[p_m] = p$ by induction. The manuscript's separation of this
  identity from fixed-key behaviour, and its decision to test the sampler against $p_k$ rather than
  $p$, is the right call and is stated precisely.
- **Bonferroni over $M$ windows is valid under arbitrary dependence**, so the heavy overlap between
  windows makes the correction conservative rather than wrong. The manuscript says it pays for
  overlapping windows; it could also say the resulting test is conservative, which would strengthen
  the claim rather than weaken it. Consistent with observing one ordinary positive where $\alpha =
  0.01$ over 384 reads would predict about four.
- All six floats are referenced; no orphans. No host names, local paths, run ids, or key material.
  Builds clean at 12 pages with no undefined citations after the bibliography merge.
- **Nine prose numbers spot-checked against `context/evidence_map.md` and all match** exactly:
  13/256 and 12.8 expected, 7.53386 and 7.54238 nats, $+0.00852$, 0.084 s.d., 16,136, 124.8, 181,
  203. The manual map is holding today.

### Compliance with `paper/AGENTS.md`

Every applicable rule is satisfied. In particular the required statement that the SynthID identity is
an expectation over fresh keyed functions while fixed-key sampling follows its calculated reweighted
law is present and unusually well done; detector false-positive behaviour is reported only after the
full orientation, start, and length correction; and no biological, cryptographic, or authenticity
claim exceeds its evidence class.

### Defect: the compensating disclosure is missing

`paper/README.md`, `paper/context/evidence_map.md`, and
`paper/reviews/2026-09-03_manuscript_restructure.md` all state that the two open execution gates — the
Linux-CPU execution awaiting M5 Pro replay, and the protocol-document hash mismatch — are deliberately
not printed **because the manuscript instead carries the scientific statement that follows from them**:
that this is one implementation on one model and one corpus whose confirmatory replication is
outstanding.

**No such statement is in `main.tex`.** Searching it for replication, confirmatory, or outstanding
returns only unrelated hits. The Discussion's scope paragraph limits generality to one model, one
watermark, and one verifier, which is a different claim: it says nothing about the replication of
*these runs* being outstanding.

So the manuscript currently discloses neither the gates nor the substitute that justified removing
them. The restructure note already flags the removal as "a deliberate departure from the instruction
in `paper/AGENTS.md` ... it must be revisited before submission"; that departure is now unbalanced,
and the balance was the stated reason it was acceptable. This is the highest-priority item in `paper/`.

Fixing it is one sentence in the Discussion's scope paragraph. It is left to the authors rather than
applied here, because the removal was made at the authors' direction and re-deciding it silently
would be the wrong move.

### Defect: two review notes from the same day contradict each other

`2026-09-03_manuscript_rewrite.md` states the gates "are now written into the manuscript's discussion
rather than held only in review notes." `2026-09-03_manuscript_restructure.md` states that "at the
authors' direction they are no longer printed in the manuscript." Both stand unreconciled in the review
history, and a reader of the first alone would believe the manuscript discloses the gates. `AGENTS.md`
forbids overwriting review history, so this wants a dated addendum on the earlier note, not an edit.

### Defect: keys are described two ways

Section *Prompts and generation* says "Both keys are published with this study so the runs can be
reproduced." *Data and code availability* says the keys, sequences, prompts, verifier outputs, and code
are "available from the authors on request." Published and on-request are different claims, and the
paper makes both about the same artifacts. Separately, on-request availability is weak for a provenance
result and is refused outright by some venues.

### Citation gaps the merged bibliography now covers

Each of these is a sentence in the current draft that names something it does not cite:

- *Background* names "inverse-transform or exponential-minimum sampling" but cites only
  `kuditipudi2024robust`; exponential-minimum sampling's usual source is uncited → `aaronson2022watermark`.
- Equation 1 **is** a distribution-reweighting rule, yet the reweighting branch of the
  distortion-free family is absent → `hu2024unbiased`, `wu2024dipmark`.
- The *Discussion* names key recovery from many observed outputs as an untested limitation and cites
  nothing for it. `reynolds2025breaking` attacks precisely the distortion-free family the Background
  describes, `wu2024collisions` shows key reuse undermining distortion-freeness, and
  `jovanovic2024stealing` recovers keys by querying. **A reviewer will ask why the threat is named
  without them.**
- The frame-shift result — the paper's most structural contribution — has no coding-theoretic anchor
  → `christ2024prc` (robust to substitutions and deletions), `haeupler2017synchronization`.

### One analysis worth doing, at no experimental cost

The Discussion names "the length at which position-independent detection stops working" as a real
quantity the study does not measure. The ingredients to bound it analytically are already reported:
median best-window strength 790.6 at 3,072 written bases, the threshold $\log_{10}(M(N)/\alpha)$, and
the fact that strength grows roughly linearly in scored bits while the correction grows only
logarithmically in read length. An analytic estimate would convert a stated open question into a
result without generating a single new sequence. Not attempted here because it is a new claim and
belongs to whoever owns the draft.

### Posture

The manuscript is markedly better than the one it replaced — plain prose, one word per idea enforced
by Table 1, claim classes kept apart, and limits stated without hedging. It is also **legacy**:
`paper/AGENTS.md` and `CLAUDE.md` both declare the Carbon-only draft development material whose
numbers must not be reused, and the declared target is `synthid_dual_model_confirmatory_v2` — both
models, 1,024 new prompts, new M5 Pro runs, a `synthid.v2.*` namespace, and a false-positive target
tightened from 0.01 to 0.001.

Two consequences follow. First, prose polishing on this draft has limited return, because its numbers
cannot survive into the rebuild; what does carry forward is the bibliography, the Background, the
vocabulary discipline, the method exposition, and the structural argument, all reusable as they stand.
Second, the rebuild is closer than the plan implies, because the GENERator-v2 1.2B replication already
exists as reviewed evidence and is fenced out only pending an explicit scope decision. Making that
decision is the highest-value move available in `paper/`; the missing disclosure sentence is the
cheapest.

## Addendum 2 — the consistency pass, applied

Every `paper/` claim was checked against the repository document that governs it, and the mismatches
were fixed rather than only reported.

### Verified consistent, no change needed

- **`context/evidence_map.md` closes against the ledger.** All 19 `synthid.*` identifiers it
  references exist in `evidence/measurements.yaml`. The 17 `synthid.generator.*` measurements in the
  ledger are correctly absent from it, matching the declared fence around the GENERator replication.
- **Prose numbers match the map**, on all nine values spot-checked.
- No host names, local paths, run ids, or key material anywhere in the manuscript source.

### Fixed in the manuscript

1. **The missing scope statement, now present.** `README.md`, `context/evidence_map.md`, and
   `2026-09-03_manuscript_restructure.md` all assert the manuscript states that this is one
   implementation on one corpus whose confirmatory replication is outstanding. It did not. The
   Discussion's scope paragraph now says it, which restores the balance the gate removal depended on.
2. **The reference implementation is now credited.** `sources.yaml` pins
   `synthid_text_code` — google-deepmind/synthid-text at `addb4a15`, Apache-2.0 — with
   `use: tournament formula, default depth, context width, and repeated-context masking`. The
   manuscript described exactly those four things and cited only the Nature paper. It now cites the
   pinned implementation as well, in *Writing the mark*. This was an attribution gap on
   Apache-2.0 licensed work, not only a bibliographic one. The manuscript's stated values are
   consistent with that implementation's defaults: 30 layers, four-token context, 1,024-context
   repetition history.
3. **The keys are described one way.** *Prompts and generation* said the two keys are published;
   *Data and code availability* listed them among artifacts "available from the authors on request".
   The ledger settles it — `fixture_keys: public reproducibility material`, and its header states the
   keys are not deployment secrets and do not constitute a key-recovery test. The availability
   section now says that, and no longer implies the keys are withheld.

### Fixed in the governing documents

4. **`paper/AGENTS.md` said "There are no retained result figures."** The manuscript has four, and
   `README.md` documents how they are built. The rule now states what is actually enforced: figures
   carry only admitted evidence, are generated by `../scripts/make_paper_figures.py` with per-artifact
   SHA-256 verification and every plotted value recorded in `figures/figure_values.json`, none is
   hand-drawn, and none from a removed watermark method is retained.
5. **`paper/README.md` gave an ambiguous regenerate command.** Its prose names
   `../scripts/make_paper_figures.py` while its command block ran `scripts/make_paper_figures.py`;
   only the second is correct, and only from the repository root, which the block now says.
6. **The contradicting review notes are reconciled.** A dated addendum on
   `2026-09-03_manuscript_rewrite.md` marks its open-gates section superseded and points to the
   restructure note as authoritative. The earlier text is left unedited, per the rule against
   overwriting review history.

### Removed

7. **`paper/figures/fig08_baseline_signal_per_token.{pdf,png}`** — the one figure of the deleted
   E-series manuscript that its removal missed, left behind as an untracked, gitignored orphan next to
   the four live figures. Also `paper/scripts/__pycache__/`, bytecode for `make_tables.py` and
   `make_figures.py`, which no longer exist.

### After the pass

`paper/` builds clean at 12 pages with no undefined references or citations, 31 bibliography entries
with 14 cited and 17 deliberately uncited, every line within the file's wrapping convention, and no
remaining disagreement between the manuscript, `README.md`, `AGENTS.md`, `context/evidence_map.md`,
`sources.yaml`, `evidence/measurements.yaml`, and the review history.

What remains open is not inconsistency. The two execution gates are still open, the manuscript is
still legacy Carbon-only material by its own governing rules, and the dual-model scope decision is
still unmade.

## Not done

- No review of the current Carbon SynthID draft. This pass never read `main.tex` as a manuscript;
  it was verifying the previous one. **The new draft has not had a sources pass**, and the added
  entries above are an input to that pass, not a substitute for it.
- No security or biological-proxy review of the current draft.
- The added bibliography entries are uncited, so they do not appear in the rendered document. That is
  intentional: citing them means writing prose, which is the next pass's job.
