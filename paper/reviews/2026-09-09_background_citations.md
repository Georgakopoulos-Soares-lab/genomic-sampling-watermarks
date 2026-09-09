# Background citation pass: the 17 merged-but-uncited entries, verified and placed

Date: 2026-09-09
Scope: `paper/manuscript/source/main.tex` prose and citations. No empirical number, evidence tag,
scope word, table value, or figure changed. `refs.bib` untouched.

## Reason

`2026-09-08_sources_and_solidity_review.md` merged 30 bibliography entries, 17 of which were never
cited from `main.tex`. That note listed the draft sentences that name something they do not cite. All
17 are now cited, and the bibliography closes in both directions: every entry in `refs.bib` is cited
at least once, and every `\cite` key resolves to an entry.

## Verification, before placement

Every one of the 17 was checked against its primary source in this pass, not against the repository's
own notes:

| Entry | Verified against | What the source actually supports |
|---|---|---|
| `liss2012watermarks` | PLoS ONE article | 6-bit ASCII in synonymous codon rank parity; protein sequence unchanged; message "inseparably linked to the ORF"; watermarked HIV *gag* showed no mutation or reversion over 136 days |
| `aaronson2022watermark` | talk slides as cited | credited, hedged as "usually credited", matching the bib note |
| `hu2024unbiased` | arXiv:2310.10669 | watermarking "without affecting the output probability distribution" |
| `wu2024dipmark` | arXiv:2310.07710 | "distribution-preserving reweight function"; detectable without model API or prompt |
| `fairoze2025publicly` | IACR CiC 1(4) | publicly verifiable signature embedded by rejection sampling; unforgeable and distortion-free; error correction for low-entropy stretches |
| `christ2024prc` | IACR ePrint 2024/235 | "robust to substitution and deletion errors"; watermarking application tolerates cropping |
| `haeupler2017synchronization` | arXiv:1704.00807 | indexing with a synchronisation string converts k synchronisation errors into (1+e)k half-errors |
| `jovanovic2024stealing` | arXiv:2402.19361 | queries the watermarked **model's API** to reverse-engineer the scheme; enables spoofing and scrubbing |
| `reynolds2025breaking` | arXiv:2502.18608 | recovers the secret key sequence of the Kuditipudi distortion-free family by adaptive prompting |
| `wu2024collisions` | arXiv:2406.02603 | key collisions bias the watermarked distribution toward the original LM distribution |
| `gloaguen2025spoofing` | PMLR 267 | a **defence**: post-hoc statistical discrimination of spoofed from genuinely watermarked text |
| `diaa2025adaptive` | arXiv:2410.02440 | preference-optimised paraphrasers "evade detection against all surveyed watermarks" |
| `sadasivan2025reliably` | arXiv:2303.11156 | recursive paraphrasing lowers detection rates at slight quality cost; spoofing without white-box access |
| `chen2025protein` | Bioinformatics btaf141 | unbiased reweighting watermark for designed proteins; "privacy of designed sequences by local verification"; synthesiser verifies without logging to a server |
| `carbon500m` | model card | pinned revision `9796b752` is a standard causal LM |
| `generatorv2checkpoint` | pinned checkpoint `c41b0018` in the local cache | `modeling_generator.py:17` defines `_BPLogitsProcessor`, "Forces token selection to use per-base marginal probabilities", and overrides `generate()` to select each base from those marginals |
| `generatorv22026` | bioRxiv landing page | Factorized Nucleotide Supervision "reconciles efficient k-mer tokenization with single-nucleotide likelihoods through probability marginalization" |

## Three corrections to the earlier note's framing, applied

1. **`gloaguen2025spoofing` is a defence, not an attack.** The earlier note tabulates it under "the
   attack literature is otherwise absent". Its contribution is post-hoc discrimination of spoofed
   text, and its own conclusion is that "current spoofing attacks are less effective than previously
   thought". It is cited here as the answering move, not as another attack.
2. **`jovanovic2024stealing` queries the model, not the detector.** The earlier note says it "recovers
   keys by querying", which reads as detector-query. The attack queries the watermarked LLM's API.
   The distinction matters because this study's threat model excludes detector queries but not model
   outputs, so the sentence citing it says "querying a watermarked model".
3. **The GENERator-v2 6-mer phase-sensitivity claim was not used.** The earlier note reports that the
   GENERator-v2 authors state that shifting the tokenisation offset by one nucleotide yields an
   entirely different tokenisation, and suggests citing the model's own paper for that premise. That
   sentence could not be confirmed from the bioRxiv record in this pass, so `generatorv22026` is
   cited only for the marginalisation its abstract does state. The phase-sensitivity premise remains
   the manuscript's own argument, uncited, as before.

## Placements

- *Marks written into DNA*: `liss2012watermarks`, one sentence after DNA-Crypt, as the case where an
  inserted mark survives both software and replication. Strengthens the following paragraph's point
  that these schemes need a design step, rather than weakening it.
- *Watermarking what a language model writes*: `aaronson2022watermark` attributes the
  exponential-minimum rule the sentence already named; `hu2024unbiased` and `wu2024dipmark` add the
  reweighting branch, with an explicit statement that our construction belongs to it;
  `fairoze2025publicly` contrasts the publicly detectable design. A new closing passage carries the
  attack literature: `diaa2025adaptive`, `sadasivan2025reliably`, `jovanovic2024stealing`, then the
  key-directed `reynolds2025breaking` and `wu2024collisions`, then `gloaguen2025spoofing` as the
  answering move, ending by pointing at the Limitations rather than implying any of it was measured.
- *Genomic language models*: `generatorv22026` joins the six-base tokenisation citation;
  `generatorv2checkpoint` supports the new statement that what a model samples is a property of the
  code that was run rather than of the paper describing it. `chen2025protein` sits beside
  `zhang2025securing` as the local-verification biosecurity precedent.
- *Model and sampling*: `carbon500m`, so the generation model is pinned to a released revision and
  not only to its preprint.
- *Discussion*, indel paragraph: `haeupler2017synchronization` and `christ2024prc` give the frame-shift
  result its coding-theoretic anchor, followed by a statement that our verifier buys the same
  synchronisation by exhaustive search instead, paying in search size rather than in redundancy.
- *Limitations*, key-secrecy paragraph: `reynolds2025breaking` and `jovanovic2024stealing`, with the
  transfer question to a 4,096-token vocabulary stated as unasked, and the threat model restated.

## One number entered the manuscript

"136 days" in the `liss2012watermarks` sentence is a value from the cited literature, not a result of
this study, and it therefore has no `synthid.*` identifier. It is recorded here so an evidence audit
does not read it as an unmapped empirical claim. No other number was added, moved, or changed.

## Verification

- `./paper/scripts/build.sh` succeeds. Rebuilt with `--keep-logs`: **zero** undefined citations and
  zero undefined references in `main.log`; `main.blg` reports no BibTeX warnings. 15 pages, up from
  12 before today's two passes.
- Bibliography closes both ways: 31 entries, 31 cited, no `\cite` key missing from `refs.bib`.
- `uv run ruff check .` passes. `python3 -m unittest discover -s tests` reports 108 tests, zero
  failures, 8 skips. The skips are the documented upstream-parity and optional-dependency guards;
  reaching the audit's zero-skip result needs `GSW_SYNTHID_UPSTREAM` pointing at the pinned
  `synthid-text` clone.
- `python3 scripts/check_evidence.py` still fails on the same five gitignored Carbon version-one
  artifacts. Pre-existing environment gap, unchanged by this pass, and not a green light either way.

## Unchanged by this pass

The manuscript is still Carbon-only and still built on version-one evidence that `PROJECT.md` and
`paper/AGENTS.md` both class as development history. The bibliography, Background, and vocabulary are
the parts of this draft designed to carry into `synthid_dual_model_confirmatory_v2` unchanged, which
is why this pass was worth doing before the rebuild rather than after it.
