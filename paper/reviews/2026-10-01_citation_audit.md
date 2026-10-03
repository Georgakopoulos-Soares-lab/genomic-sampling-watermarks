# Citation audit (2026-10-01)

All 39 cited works were checked against primary sources (publisher pages, proceedings, arXiv,
bioRxiv, Crossref, PubMed, Hugging Face, GitHub), in four groups. For each work the audit
checked that it exists, checked every bibliography field, and checked whether each citing
sentence is supported by the source. Every cited work exists, and every identifier resolves. The
fixes below were applied to `paper/manuscript/source/main.tex` and `refs.bib`. The bibliography
now has 42 printed entries, three of them new. The manuscript builds with no undefined citations
and no BibTeX warnings.

## Claims corrected in the text

| Location | Problem | Fix |
|---|---|---|
| Introduction, provenance sentence (`baker2024protein`) | The *Science* editorial proposes storing synthesis records in repositories queried only in emergencies, not marks carried by the sequence. The previous sentence of the paragraph says such records can be separated from the sequence. | The sentence now describes the editorial's proposal and states the sequence-attached signal as this paper's own motivation. The entry is marked as an editorial. |
| Introduction, generated-sequence list (`carbon2026`, `generatorv22026`) | Neither paper generates coding, regulatory, or genome-scale designs; Carbon lists these as future work. | Removed from this citation; the list rests on Evo, GENERator, and King et al. |
| Introduction, model description | "differ in … training corpus" is misleading. The Carbon corpus is built mainly on GENERator-v2's pre-training data (verified in the Carbon paper, §3.2). | Now states that the models are not independent. The overlap is also noted in the Discussion and Limitations. |
| Introduction, model citations (`carbon2026`) | The Carbon paper releases only 3B and 8B models. | The Carbon-500M and GENERator-v2 checkpoint cards are now co-cited. |
| Background, designed DNA (`heider2007dna`) | DNA-Crypt did not originate signature watermarks in genomic DNA. | Credits Arita and Ohashi 2004 (new entry, verified with Crossref and PubMed) before DNA-Crypt. |
| Background, attack sentence | "stronger adaptive capabilities" fits key recovery and spoofing, not recursive paraphrasing. | "stronger attacker capabilities, including adaptive ones". |
| Background, Golowich and Moitra | They do not borrow from synchronization codes, and their construction does not insert index symbols; each token is read as an index, over a large alphabet. | Rewritten. The paper now says it is a different construction built on pseudorandom codes. The synchronization-string citation remains in the Discussion, where it is supported. |
| Background, Zhao et al. | "doubles" is the paper's rounding, and the baseline is the previous-token-keyed watermark. | "roughly doubles the provable edit tolerance relative to the soft watermark keyed on the previous token". |
| Background, distribution-preserving schemes | "pursue edit robustness by different means" is false for Christ et al., Hu et al., and SynthID-Text. | "differ in whether and how they address edits". |
| Background and Methods, GENERator default sampling | The released code draws the six bases of a token independently from per-base marginals; this is not sequential sampling. | "per-base sampling path" and "per-base marginal sampling". |
| Background, tokenization offset (`wu2025generator`) | "absorbs" overstates the paper, and GENERator-v2 uses a different scheme. | "mitigates … and GENERator-v2 cycles through all six offsets". |
| Methods, repeated-context rule | No source was cited. | Cites the SynthID paper. |
| Limitations, attacks | The sentence implied that watermark stealing needs the key or score; it needs only many watermarked outputs. SynthID-specific attacks were not mentioned. | Rewritten. It separates Reynolds et al. (needs the detector's P-values) from Jovanovic et al. (needs only outputs). It adds that SynthID-Text has been weakened by paraphrasing and back-translation (Han et al. 2025, new) and by adaptive attacks (Diaa et al.). It adds that the mean score is vulnerable to adding tournament layers, which a layer-inflation attack exploits (Omidi et al. 2026, new; arXiv metadata verified). |

## Bibliography metadata corrected

- **Zhang et al.:** title corrected to "…for Language Models".
- **Carbon:** "Ed Beeching" (not Edward). Title case fixed. The DOI and version now print, because the `plain` style drops the `doi` field.
- **GENERator-v2:** version, posting date, and DOI now print.
- **Pages, volumes, issues, and DOIs added:**
  - DiPmark: pages 53443–53470.
  - Watermark stealing: pages 22570–22593.
  - Golowich and Moitra: volume 37, pages 20645–20693, DOI.
  - Christ and Gunn (codes): LNCS, pages 325–347.
  - HyenaDNA: pages 43177–43201.
  - Nucleotide Transformer: issue 2.
  - Caduceus: PMLR 235, pages 43632–43648.
  - King et al.: issue 6811.
  - Zhang et al. 2025: volume 38, pages 152050–152080, DOI.
  - DART-Eval: volume 37, pages 62024–62061, DOI.
- **Hu et al.:** arXiv ID added.
- **SemStamp:** "Volume 1: Long Papers", publisher, and DOI added.
- **Sadasivan et al.:** title case fixed.
- **Haeupler and Shahrasbi:** "Singleton" protected in the title.
- **SynthID-Text code:** commit `addb4a15` (13 June 2025) restored. The repository has moved on since that commit, and the formula and defaults the paper relies on were verified there.

## Checked and left unchanged

- **Model-card revisions:** not reinstated for Carbon-500M and GENERator-v2. The 2026-09-11 editorial decision keeps pinned model revisions out of the manuscript; they remain in `sources.yaml` and the evidence ledger. The audit recommended pinning them because both cards change over time. Revisit if the venue expects pinned software versions.
- **Gibson et al.:** `and others` still shortens the 24-author list. This is a style choice; all named authors are correct.
- **GenBench:** correctly cited as a preprint. The NeurIPS workshop record has a different title and author list.
- **Optional coverage, not added:**
  - Evo 2 (single-nucleotide genome-scale generation).
  - DNABERT-2 (the original source of the Caduceus point).
  - Fernandez et al., "Three Bricks" (low-FPR watermark tests).
  - Genomic Benchmarks and OmniGenBench (further benchmark suites).

  The audit verified that these works exist but did not read them for claim support.
- **Unused entries:** `fairoze2025publicly`, `wu2024collisions`, and `gloaguen2025spoofing` are in `refs.bib` but uncited, so they do not print.

`docs/research/literature_map.md` carried the same Golowich and Moitra error and was corrected.
