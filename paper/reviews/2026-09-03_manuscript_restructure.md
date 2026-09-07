# Manuscript restructure, background section, and references — 2026-09-03

Second pass on the same day as `2026-09-03_manuscript_rewrite.md`. That note records the readability
rewrite and the figures; this one records the structural change requested afterwards. No measured
value changed, no claim was strengthened, and no number was added or removed from the results.

## Structure

Section order is now Introduction, Background, Methods, Results, Discussion, Conclusion. Methods
moved ahead of Results, and Figure 1 moved with it.

Run-in bold headings (`\paragraph{Quality measures.}` and the rest) are gone. Methods is now seven
numbered subsections. The Discussion is continuous prose in four paragraphs with no headings and no
enumerated limits; the three limitations that were previously bold-headed blocks are one coherent
paragraph.

## New Background section

Four subsections, placed between the Introduction and Methods:

1. marks written into DNA before generative models, covering the watermark sequences in the first
   synthetic bacterial genome and the DNA-Crypt family, and why an inserted marker does not fit a
   setting where a model writes the whole sequence;
2. watermarking language-model output — the green-list scheme, the distribution-preserving
   cryptographic line, and the impossibility result that bounds any robustness claim;
3. a dedicated paragraph on SynthID as the backbone of this work, explaining the tournament, why its
   context-dependent bits and model-free detector matter more in DNA than in text; and
4. genomic language models and what six-base tokenisation changes, including the recent DNA-model
   watermarking work on synonymous-codon marks and how our question differs from it.

## References

The bibliography went from 2 entries to 13. Every added entry was verified against the publisher or
arXiv record for authors, venue, volume, pages, and identifier before being written:

Kirchenbauer et al. (ICML 2023); Christ, Gunn and Zamir (COLT 2024); Kuditipudi et al. (TMLR 2024);
Zhang et al., *Watermarks in the Sand* (ICML 2024); Gibson et al. (Science 2010); Heider and Barnekow
(BMC Bioinformatics 2007); Nguyen et al., Evo (Science 2024); Dalla-Torre et al., Nucleotide
Transformer (Nature Methods 2025); Wu et al., GENERator (arXiv 2025); Baker and Church (Science
2024); Zhang et al., *Securing the Language of Life* (arXiv 2025).

## Removals requested by the authors

- **Abstract numbers.** The abstract now states the questions, the design, and the direction of the
  answers, with no figures. Every number remains in Results.
- **Infrastructure detail.** All mentions of the execution hardware, the accelerator used for
  generation, and the pinned model revision hash are out of the manuscript. So is the
  protocol-document hash mismatch.
- **Repository process language.** The measurement ledger, artifact digests, evidence identifiers,
  and the word "declared" in its protocol sense no longer appear. The Methods "Evidence" paragraph
  was replaced by a normal data and code availability statement.
- **"Public fixture key."** The term is gone. Table 1 now defines *published key*, and the Methods
  and Discussion say that the keys are published so the runs can be reproduced and that a deployment
  would use an independently generated secret key.
- **"Reported here"** and similar hedging phrasing.

## Consequence for the open gates

Both execution gates from the evidence-consolidation review are still open and are unchanged:
the Linux-CPU execution with the required M5 Pro replay, and the protocol-document hash mismatch.
At the authors' direction they are no longer printed in the manuscript. They are now tracked in
`paper/README.md` and in the writing-boundaries section of `paper/context/evidence_map.md`, and the
manuscript instead carries the scientific statement that follows from them: the study is one
implementation on one model and one corpus, and its confirmatory replication is outstanding. This is
a deliberate departure from the instruction in `paper/AGENTS.md` to keep those two statements in the
manuscript text, and it must be revisited before submission.

## Authors

Kimon Antonios Provatas and Christos Galanopoulos as co-first authors, Ilias Georgakopoulos-Soares
as corresponding author, all at The University of Texas at Austin. No email addresses are printed.

## Verification

- 108 unit tests pass, with the four optional upstream comparisons skipped.
- Ruff passes.
- `scripts/check_evidence.py` resolves 36 measurements, 12 artifact digests, 9 documents, and 19
  manuscript mappings.
- Every number printed in the manuscript was re-checked against the ledger after the restructure.
- The manuscript builds to a 12-page PDF with no LaTeX warnings and no overfull boxes.
