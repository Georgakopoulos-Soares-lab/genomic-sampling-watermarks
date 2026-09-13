# Author edits: before-and-after evidence

Date: 2026-09-13

## Scope and baseline

This implements the author's approved manuscript-editing plan. Changes are limited to
`paper/manuscript/source/main.tex`, `paper/manuscript/source/refs.bib`, this review record,
and the rebuilt manuscript PDFs. No experiment, analysis code, figure asset, protocol, or
measurement-ledger entry was changed. The length and key-variability analyses remain excluded
as agreed.

The working tree was clean before editing. The source baseline is commit
`f47faba94c11e0aeef62fd386c98ff6ffc98d1b9`. The excerpts and complete diff below compare against
the actual source present at that commit, rather than treating wording from an older draft as
the current source.

The PDF open in the IDE (`paper/manuscript/main.pdf`) was a stale copy. Its extracted Figure 4
caption said: "Effects of single-base edits on detection in Carbon. All panels are Carbon."
The source already included `fig4_edits_generator`, a both-model caption, and both-model Results.
The September 11 GENERator analysis amendment and ledger already supported those panels.
Rebuilding and refreshing the IDE copy brings those existing changes into the viewed PDF.

## Disposition of every author comment

| Comment | Before | After / disposition |
|---|---|---|
| 1 | Abstract: "Genomic language models can generate DNA sequences that lack an enduring record of their origin." | Replaced with the requested sentence beginning "Genomic language models can generate synthetic DNA sequences" and ending "no inherent record of their origin." |
| 2 | Abstract named an unspecified "boundary" and "six-base token phase"; Introduction only briefly linked reverse complementation to strand uncertainty. | Abstract now names the generated region's location, six-mer token boundaries, and strand orientation. Introduction defines generation boundaries as where the generated region begins and ends and explains that reverse complementation changes token identities and order. Background defines token phase and distinguishes it from reference-genome alignment. |
| 3 | Abstract: "We apply the SynthID tournament watermark to Carbon-500M and GENERator-v2 1.2B" without the requested token description. | Uses "We integrate" and describes both models as processing and generating non-overlapping six-mer tokens under the evaluated sampling policy. The qualification preserves the existing GENERator-v2 direct-token-policy distinction. |
| 4 | "at most one positive per model, control family, and condition" | "no more than one positive result for each model, control family, and condition" |
| 5 | The current abstract said window-level results "show that the search can recover usable token alignment," without explicitly saying both models. | Explicitly says "In both models" and describes the results as consistent with preserved or recovered alignment. This states the evidence's scope without claiming direct measurement of exact alignment recovery. |
| 6 | Five names in the author block and PDF metadata, including Aris Karatzikos and Charalambos Koilakos. | Removed those two names from both locations. Retained the other three authors, the first two authors' equal-contribution markers, affiliation, and correspondence. Adjusted the author line break. |
| 7 | Abstract and Limitations both used "independent confirmatory replication remains outstanding." | Removed the abstract sentence and all "outstanding" wording from the manuscript. Limitations now says: "The evaluation used one execution per model on a shared prompt cohort." Hardware and Carbon protocol-provenance disclosures remain factual and unchanged. |
| 8 | Introduction listed coding sequences, regulatory elements, and extended genomic sequences; opening citations omitted GENERator-v2 and PMID 42561074. | Uses the requested expanded list, adds the existing GENERator-v2 citation, and cites the new King et al. Science reference with PMID 42561074. |
| 9 (unnumbered citation request) | The Introduction's statistical-watermark statement had no adjacent citation. Kirchenbauer et al. was already in the bibliography and cited later. | Places `kirchenbauer2023watermark` directly after the generation-time statistical-signal statement and adds the official PMLR URL to its existing bibliography entry. No duplicate entry. |
| 10 | Introduction referred to a shared "canonical six-base-token policy." | Explicitly describes shared non-overlapping six-mer tokenization and direct canonical-token sampling under the evaluated policy. Uses American spelling. |
| 11 | The current source and existing Figure 4 assets already covered both models; the IDE PDF showed the older Carbon-only figure. | Retained the existing verified Carbon a/b and GENERator-v2 c/d panels, rebuilt the manuscript, and refreshed the IDE PDF. Both-model Figure 4 appears on page 8. No plot regeneration was needed. |
| 12 | The current Results and Discussion already included both-model strength and window-length results. | Retained those numerical results. Made the alignment interpretation explicit for Carbon-500M and GENERator-v2 1.2B in Discussion and kept abstract, Introduction, and Conclusion wording consistent with the evidence. |
| 13 | "Genomic tokenisation and alignment" and mixed British/American prose. | "Genomic tokenization and alignment" and an American-English spelling pass throughout manuscript prose and captions. Published reference titles and proper names were preserved. |
| 14 | One evaluated prompt length and one generated continuation length; no length-independence plot. | Excluded as agreed. No length-independence claim added. See rationale below. |
| 15 | Two fixture keys associated with different replay seeds; no experiment isolating key effects. | Excluded as agreed. No key-independence claim added. See rationale below. |
| 16 | No discussion sentence about varying tournament depth. | Added the requested future-work trade-off among watermark strength, detection power, and sequence-level distortion, naming both Carbon-500M and GENERator-v2 1.2B. |
| 17 | Data and code availability offered materials on request and omitted the project GitHub link. | Added a clickable project GitHub repository link. Code, prompt definitions, scripts, and ledger are described as maintained there; generated sequences and result files absent from the repository remain available on request. |
| 18 | Competing interests and funding acknowledgments were absent. | Added the supplied competing-interests and funding statements verbatim, using the American-English heading "Acknowledgments." The supplied grant identifier is R35GM155468, awarded to I.G.S. |
| 19 | Title case in the displayed title and PDF metadata. | Both now read "Tracing model-generated DNA with position-independent synthID watermarking." The requested `synthID` title spelling is intentional; established `SynthID` naming elsewhere is retained. |

## Additional caption correction within the consistency review

Figure 3's caption said "Results are the same in all four edit conditions." That was inconsistent
with the already reported GENERator wrong-key results: its positive in the unedited, substitution,
and insertion conditions is absent after deletion. The caption now limits the all-condition statement
to marked prompts and explicitly notes the wrong-key difference. Table values, plotted values, and
measurement entries were not changed.

The supporting entries are `synthid.generator.detector.clean.other_key_rate`,
`synthid.generator.detector.substitution_1nt.other_key_rate`,
`synthid.generator.detector.insertion_1nt.other_key_rate`, and
`synthid.generator.detector.deletion_1nt.other_key_rate`.

## Scientific and bibliographic basis

- Both-model window interpretations use the existing `synthid.detector.strength_separation`,
  `synthid.detector.strongest_window_length`, `synthid.generator.detector.strength_separation`,
  and `synthid.generator.detector.strongest_window_length` entries in the
  [measurement ledger](../../evidence/measurements.yaml). Their admission and provenance are documented
  in the [evidence map](../context/evidence_map.md) and
  [September 11 analysis amendment](../../docs/research/generator_v1_analysis_amendment_2026_09_11.md).
- The strongest-window result supports a local-region interpretation; it does not establish exact
  generation-boundary recovery. That distinction is now explicit in Discussion, consistent with the
  [threat model](../../docs/threat_model.md).
- The new `king2026bacteriophages` entry is King et al., "Generative design of bacteriophages with
  genome language models," *Science* 393, eaec2657 (2026), DOI `10.1126/science.aec2657`,
  PMID `42561074`. Metadata, authorship, and the genome-scale context were checked against the
  [RCSB deposited study's primary citation](https://www.rcsb.org/structure/36CQ) and
  [the authors' publication list](https://evodesign.org/publications). The PMID is also printed in
  the compiled reference. The new citation supports the Introduction's account of the broader field,
  not a biological-function claim for this watermark study.
- Kirchenbauer et al.'s citation and URL were checked against the
  [official ICML/PMLR proceedings page](https://proceedings.mlr.press/v202/kirchenbauer23a.html).
- Authorship, title casing, the competing-interests declaration, and funding wording follow the
  author's explicit instructions. This editorial pass does not independently attest to grant or
  conflict-of-interest facts.

## Excluded analyses and reasons

**Comment 14: prompt/generation length.** A plot establishing independence from prompt length or
generation length would require additional analysis, evidence entries, and plotting work; varying
prompt length would require new generation. The four detection-window lengths in the existing
experiment are not a controlled comparison of prompt or generation lengths. Shorter continuations
can provide fewer watermark bits, and longer surrounding reads increase the search correction, so
"length does not matter" is not supported. The existing Discussion explains this scope limit.

**Comment 15: key selection.** The two existing fixture keys are associated with different replay
seeds. Comparing those draws cannot isolate key effects or establish invariance to key choice.
A separate study could quantify variability across independently sampled keys with controlled
sampling variation. No such analysis, figure, or claim was added.

The tournament-depth suggestion is a future-work statement only; no depth sweep was performed.

## Verification

The manuscript was built with the existing `paper/scripts/build.sh` using Tectonic and BibTeX.
The resulting 11-page PDF was rendered with Poppler and every page visually checked, including
the revised author block, both-model Figures 2-4, mathematical expressions, table, declarations,
and references. The final GitHub link uses descriptive clickable text to avoid stretching a long
URL across the narrow column. The last build has underfull-box spacing warnings, including
bibliography entries, but no overfull boxes, missing characters, or unresolved citations.

Focused checks confirmed:

- All 28 cited bibliography keys resolve and bibliography keys are unique.
- The new PMID and article identifier appear in the rendered bibliography.
- The removed author names and "outstanding" wording are absent from manuscript text and PDF text.
- PDF title and author metadata match the revised title page; the GitHub URL is present as a PDF link.
- Requested opening, control wording, neutral execution scope, declarations, and American spellings
  are present in the source.
- Mathematical expressions, Methods and Results numerical tokens, and table contents are unchanged.
- All 14 existing figure PDF/PNG assets are byte-identical to the baseline and match their recorded
  hashes in `paper/figures/figure_values.json`.
- The measurement ledger and figure-value manifest are byte-identical to the baseline.

The full evidence checker was run before and after editing. Both runs exit with status 1 because
the same five Carbon source artifacts are absent; no additional evidence-checker errors appeared:

```text
ERROR: missing evidence artifact: outputs/carbon_synthid_e16_v1/distribution_summary.json
ERROR: missing evidence artifact: outputs/carbon_synthid_e16_v1/sequence_comparison_summary.json
ERROR: missing evidence artifact: outputs/carbon_synthid_e16_v1/generation_summary.json
ERROR: missing evidence artifact: outputs/carbon_synthid_position_independent_v1/summary.json
ERROR: missing evidence artifact: outputs/carbon_synthid_position_independent_v1/trials.jsonl
```

Figure-file integrity and unchanged text numerals do not resolve the missing-source limitation.
No experiment or model-dependent tests were run for this editorial change.

Reproduction commands from the repository root:

```bash
git diff --check
python3 scripts/check_evidence.py
(cd paper && ./scripts/build.sh)
pdfinfo paper/manuscript/build/main.pdf
pdfinfo -url paper/manuscript/build/main.pdf
cp paper/manuscript/build/main.pdf paper/manuscript/main.pdf
cmp paper/manuscript/build/main.pdf paper/manuscript/main.pdf
```

The final refresh copies the verified build output to the exact PDF path open in the IDE; the
build script itself was not changed. Source and PDF digests and the exact source diff follow.

## Artifact digests

SHA-256 digests identify the exact baseline and delivered artifacts.

| Artifact | Before SHA-256 | After SHA-256 |
|---|---|---|
| `paper/manuscript/source/main.tex` | `8826ccb3ae78d2bea94ff567e2aeb8316711fcf7ea44af1fa46a7878dd853614` | `ea7bd55ae63bf969a94f24d79c30b2e388326735ccd4ea704bc5f2bf26e275f4` |
| `paper/manuscript/source/refs.bib` | `f2e57ec89925c7b4cc3e1f6b14bdf5cd8ac4ecde4c6e8053eabc851f186a7650` | `83fb8aa9bb1483e838d396b41998b471a2097e048a2f3c19182f8c31ebad82d5` |
| `paper/manuscript/main.pdf` | `21ea3de767e0f20ab43243e3aa1d0aa4365e52d65cade989eaf3ca726e00167e` | `265c7a089d58538d8a2d15fb3f3b2cdb91a8790dc6082654352815b066a0116b` |
| `paper/manuscript/build/main.pdf` | `49b273e988364d51716d180f3501e178e486549a3c82525364bacb054f869316` | `265c7a089d58538d8a2d15fb3f3b2cdb91a8790dc6082654352815b066a0116b` |
| `evidence/measurements.yaml` | `065e0f3ba7649d63c37cb15ce546ec791ac08b14f8948ff4187890a4ec37b0f1` | `065e0f3ba7649d63c37cb15ce546ec791ac08b14f8948ff4187890a4ec37b0f1` |
| `paper/figures/figure_values.json` | `6bd35c233c4453c133ddd0f4f7efda5fc4e8702494baf95a5f5c275b7c81fbec` | `6bd35c233c4453c133ddd0f4f7efda5fc4e8702494baf95a5f5c275b7c81fbec` |

Both delivered PDF paths contain identical bytes. The source files and old IDE PDF have separate
baselines because the IDE copy had not incorporated the existing September 11 source changes.

## Exact before-and-after source diff

The following diff was generated directly from the captured clean source baseline and the final
files. It includes every LaTeX and bibliography change in this edit, including spelling and
formatting adjustments. No figure or measurement changes are hidden in this appendix.

```diff
--- before/paper/manuscript/source/main.tex
+++ after/paper/manuscript/source/main.tex
@@ -21,8 +21,8 @@
   linkcolor=blue!60!black,
   citecolor=blue!60!black,
   urlcolor=blue!60!black,
-  pdftitle={Tracing Model-Generated DNA with Position-Independent SynthID Watermarking},
-  pdfauthor={Kimon Antonios Provatas; Christos Galanopoulos; Aris Karatzikos; Charalambos Koilakos; Ilias Georgakopoulos-Soares},
+  pdftitle={Tracing model-generated DNA with position-independent synthID watermarking},
+  pdfauthor={Kimon Antonios Provatas; Christos Galanopoulos; Ilias Georgakopoulos-Soares},
   pdfsubject={Position-independent detection of the SynthID tournament watermark in two genomic language models},
   pdfkeywords={genomic language models; watermarking; SynthID; provenance; position-independent detection}
 }
@@ -53,14 +53,12 @@
 
 \twocolumn[{%
 \begin{center}
-{\LARGE\bfseries Tracing Model-Generated DNA\\[3pt]
-with Position-Independent SynthID Watermarking\par}
+{\LARGE\bfseries Tracing model-generated DNA\\[3pt]
+with position-independent synthID watermarking\par}
 \vspace{1.0em}
 {\large
 Kimon Antonios Provatas\textsuperscript{1,*}\hspace{0.9em}
-Christos Galanopoulos\textsuperscript{1,*}\hspace{0.9em}
-Aris Karatzikos\textsuperscript{1}\\[4pt]
-Charalambos Koilakos\textsuperscript{1}\hspace{0.9em}
+Christos Galanopoulos\textsuperscript{1,*}\\[4pt]
 Ilias Georgakopoulos-Soares\textsuperscript{1,\dag}\par}
 \vspace{0.6em}
 {\footnotesize
@@ -71,24 +69,26 @@
 \begin{minipage}{0.86\textwidth}
 \small
 \textbf{Abstract.}
-Genomic language models can generate DNA sequences that lack an enduring record of their origin.
-Generation-time watermarking could supply such provenance, but verification in DNA is a
-synchronisation problem: once generation metadata are absent, a verifier may not know the boundary,
-strand orientation, or six-base token phase of the generated region.
-
-We apply the SynthID tournament watermark to Carbon-500M and GENERator-v2 1.2B and evaluate
-whether a verifier can recover the mark using only DNA, a key, and fixed public settings. The
+Genomic language models can generate synthetic DNA sequences, yet the resulting sequences contain
+no inherent record of their origin. Generation-time watermarking could supply such provenance.
+In DNA, however, the unknown location of the generated region, six-mer token boundaries, and strand
+orientation complicate detection, particularly when generated sequence is embedded within a longer read.
+
+We integrate the SynthID tournament watermark into Carbon-500M and GENERator-v2 1.2B---two genomic
+language models that process and generate non-overlapping six-mer tokens under the evaluated
+sampling policy. We evaluate whether a verifier can recover the mark using only DNA, a key, and
+fixed public settings. The
 verifier corrects one read-level test over both strands, every start position, and four window
 lengths. In each model, it detected all 384 held-out marked reads when unedited and after each
-tested single-base substitution, insertion, or deletion; ordinary and wrong-key controls yielded
-at most one positive per model, control family, and condition. Neither model showed a statistically
-detectable difference in model likelihood or the pre-specified sequence measures after
-multiple-testing correction. Window-level results show that the search can recover usable token
-alignment after insertions and deletions. These findings support statistical provenance detection
+tested single-base substitution, insertion, or deletion. Ordinary and wrong-key controls yielded
+no more than one positive result for each model, control family, and condition. Neither model showed
+a statistically detectable difference in model likelihood or the pre-specified sequence measures after
+multiple-testing correction. In both models, window-level results are consistent with preserved or
+recovered six-mer token alignment after insertions and deletions. These findings support statistical
+provenance detection
 within the tested corpus and portability of the implementation across the two evaluated models.
 They do not establish biological function, secret-key security, or robustness beyond the evaluated
-non-adaptive single-base edits. Each model was evaluated in a single execution; independent
-confirmatory replication remains outstanding.
+non-adaptive single-base edits.
 \end{minipage}
 \vspace{1.2em}
 \end{center}
@@ -99,25 +99,29 @@
 \section{Introduction}
 
 Genomic language models increasingly support the generation of coding sequences, regulatory
-elements, and extended genomic sequences \cite{nguyen2024evo,wu2025generator,carbon2026}. A
+elements, genome-scale constructs, and functionally constrained DNA designs
+\cite{nguyen2024evo,wu2025generator,carbon2026,generatorv22026,king2026bacteriophages}. A
 nucleotide sequence, however, does not retain an inherent record of whether it originated in a
 biological sample, a computational design process, or a generative model. That provenance can be
 lost when a sequence is separated from the logs and metadata maintained by its generating system.
 Mechanisms that remain associated with a sequence throughout design and synthesis are therefore of
 increasing interest \cite{baker2024protein}.
 
-Watermarking offers one such mechanism by embedding a distributed statistical signal during
-generation. A verifier holding the corresponding key can later test for that signal without access
-to the model, prompt, or generation logs. In DNA, this becomes a synchronisation problem. Models
-that generate non-overlapping six-base tokens do not encode their token boundaries in the emitted
-sequence: an unknown boundary creates six possible phases, reverse complementation adds strand
-uncertainty, and surrounding sequence obscures the location and extent of the generated region.
+Watermarking provides one approach to this problem by embedding a statistical signal during
+generation \cite{kirchenbauer2023watermark}. A verifier holding the corresponding key can later
+test for that signal without access to the model, prompt, or generation logs. In DNA, this becomes
+a synchronization problem. Models that generate non-overlapping six-mer tokens do not encode their
+token boundaries in the emitted sequence, leaving six possible token phases. Reverse complementation
+changes token identities and their order, so verification must consider both strand orientations.
+Surrounding sequence can also obscure the generation boundaries: where the generated region begins
+and ends within the read.
 The verifier must search these alternatives while still controlling the false-positive probability
 of the final read-level decision.
 
 Here, we integrate the SynthID tournament watermark \cite{dathathri2024scalable} into Carbon-500M
-\cite{carbon2026} and GENERator-v2 1.2B \cite{generatorv22026}. The models share a direct
-canonical six-base-token policy but differ in size, training corpus, and tokenizer construction.
+\cite{carbon2026} and GENERator-v2 1.2B \cite{generatorv22026}. Under the evaluated policy, these
+models share non-overlapping six-mer tokenization and direct sampling from canonical tokens, but
+differ in size, training corpus, and tokenizer construction.
 We ask whether the sampler follows its intended fixed-key distribution, whether watermarking
 changes a pre-specified panel of model and sequence proxies, and whether a verifier can recover the
 mark without knowing the generation boundary, strand, or token phase. The detector searches both
@@ -127,9 +131,10 @@
 In both models, the verifier detected every held-out marked read under the tested unedited and
 single-base edit conditions. The quality-proxy comparisons showed no statistically detectable
 difference after correction, while ordinary and wrong-key control counts were compatible with the
-declared false-positive target. The window-level results explain how the search recovers usable
-alignment after insertions and deletions. These findings establish statistical detection within the
-evaluated corpus, not biological function, secret-key security, or equivalence between the models.
+declared false-positive target. In both models, the window-level results are consistent with the
+search selecting regions with preserved or recovered six-mer token alignment after insertions and
+deletions. These findings establish statistical detection within the evaluated corpus, not biological
+function, secret-key security, or equivalence between the models.
 Distribution preservation denotes an expectation over fresh keyed functions; at a fixed key and
 context, sampling follows the explicitly reweighted distribution.
 
@@ -139,7 +144,7 @@
 
 DNA watermarking predates its application to generative models. The first synthetic bacterial
 genome included watermark sequences encoding identifying information to distinguish the synthetic
-chromosome from its natural counterpart \cite{gibson2010creation}. DNA-Crypt formalised message
+chromosome from its natural counterpart \cite{gibson2010creation}. DNA-Crypt formalized message
 embedding through synonymous codon choices and error correction \cite{heider2007dna}. Related
 approaches embed information within an open reading frame while preserving the encoded amino acid
 sequence, with experimental evidence that embedded messages can persist during viral replication
@@ -150,7 +155,7 @@
 and consideration of the biological consequences of those changes. Generation-time watermarking
 addresses a complementary setting: the mark is introduced through the model's sampling
 distribution as the sequence is generated, without requiring a separately allocated payload
-region. A fixed, recognisable marker also differs from a distributed keyed signal in its
+region. A fixed, recognizable marker also differs from a distributed keyed signal in its
 susceptibility to targeted removal or copying.
 
 \subsection{Watermarking language-model output}
@@ -171,7 +176,7 @@
 
 We use the binary tournament construction of SynthID-Text \cite{dathathri2024scalable}. At each
 generation step, a secret key and a short context of recently generated tokens determine binary
-mark bits for each candidate token and tournament layer. Each layer favours candidates with a
+mark bits for each candidate token and tournament layer. Each layer favors candidates with a
 mark bit of 1. Averaged over fresh keyed functions, the tournament preserves the model's
 next-token distribution; at a fixed key and context, it samples from a reweighted distribution.
 Detection reconstructs the mark bits from the output and tests for an excess of 1s.
@@ -182,18 +187,20 @@
 and public settings without access to the generating model or its probabilities. SynthID-Text has
 also been evaluated in a large-scale text deployment \cite{dathathri2024scalable}.
 
-\subsection{Genomic tokenisation and alignment}
-
-Several generative genomic models, including both evaluated here, tokenise DNA into non-overlapping
+\subsection{Genomic tokenization and alignment}
+
+Several generative genomic models, including both evaluated here, tokenize DNA into non-overlapping
 six-base tokens to reduce token-sequence length \cite{wu2025generator,carbon2026,generatorv22026}.
-The watermark sampler operates on the realised distribution over those tokens. We therefore define
+The watermark sampler operates on the realized distribution over those tokens. We therefore define
 both models on their direct canonical 4{,}096-token distributions; for GENERator, this excludes the
 released base-by-base sampling path \cite{generatorv2checkpoint}. A shared vocabulary alone would
 not make the sampling comparison meaningful without a shared policy definition.
 
-Six-base tokenisation also creates the study's central synchronization problem: token boundaries
-are not represented in the emitted nucleotide sequence. A verifier must therefore consider all six
-phases, both strand orientations, and candidate locations and lengths of the generated region.
+Six-mer tokenization also creates the study's central synchronization problem: token boundaries
+are not represented in the emitted nucleotide sequence. Here, token phase is the nucleotide offset
+at which the sequence is partitioned into consecutive six-mers; it does not refer to alignment to a
+reference genome. A verifier must therefore consider all six phases, both strand orientations, and
+candidate locations and lengths of the generated region.
 Selecting the strongest window without correcting for that search would overstate the evidence. Our
 setting consequently addresses detection from an observed read, a key, and public settings without
 assuming a coding region, reference alignment, or known generation boundary. This is complementary
@@ -208,7 +215,7 @@
   Carbon-500M \cite{carbon2026,carbon500m} and GENERator-v2-eukaryote-1.2b-base
   \cite{generatorv22026,generatorv2checkpoint}, which are decoder-only genomic language models with
   non-overlapping six-base tokens. At every step, we restricted logits to the 4{,}096 canonical DNA
-  tokens and normalised once. For GENERator, this specifies its direct canonical token distribution,
+  tokens and normalized once. For GENERator, this specifies its direct canonical token distribution,
   not the base-by-base path used by its released code by default. Temperature was 1.0, with no top-$k$
   or top-$p$ truncation.
 
@@ -313,7 +320,7 @@
 (3{,}072 bases), so each model contributes 512 marked and 512 ordinary continuations. The
 two draws use different replay seeds in both arms, and the two marked draws use two different keys.
 Both keys are published for reproducibility. Deployment would require independently generated
-secret keys shared only with authorised generators and verifiers.
+secret keys shared only with authorized generators and verifiers.
 
 \subsection{Sampler validation}
 
@@ -442,7 +449,7 @@
 \begin{table*}[t]
 \centering
 \caption{Positive detections for each model across 192 held-out prompts with two draws each.
-Each edit affects exactly one base. The final two rows of each block summarise unedited reads at
+Each edit affects exactly one base. The final two rows of each block summarize unedited reads at
 the prompt level, accounting for paired draws; intervals are exact and two-sided. All marked
 prompts also had both draws detected in every edit condition. Results are reported separately
 for each model.}
@@ -481,8 +488,9 @@
 of the best window in each unedited read, one point per read, on a log scale.
 The dashed line denotes the threshold corrected for the search over 16{,}136 windows. All marked
 reads exceed the threshold. \textbf{b,d}, Proportion of the 192 held-out prompts with positive
-detections, with exact 95\% intervals, split across a break in the axis. Results are the same in
-all four edit conditions. The control intervals reach above the 1\% target, so these data are
+detections, with exact 95\% intervals, split across a break in the axis. All marked prompts were
+detected in all four edit conditions. GENERator's wrong-key positive is absent after deletion.
+The control intervals reach above the 1\% target, so these data are
 consistent with a false-positive rate below 1\% without establishing one. Panels \textbf{a,b} show
 Carbon and panels \textbf{c,d} show GENERator.}
 \label{fig:detection}
@@ -548,21 +556,22 @@
 statistical procedure is unchanged between Carbon and GENERator. Their agreement in detection
 outcomes and the absence of measurable quality loss provide evidence beyond a single model
 application. However, the models share the same prompt cohort and token length, limiting
-extrapolation to other corpora and tokenisation schemes. This comparison also does not establish
+extrapolation to other corpora and tokenization schemes. This comparison also does not establish
 relative biological quality or equivalence between the models.
 
 The strongest-window results clarify the role of alignment search after insertions and deletions.
 A substitution preserves downstream token boundaries, whereas an insertion or deletion changes the
 alignment of every subsequent token within a window spanning the edit. The increased frequency of
 shorter strongest windows is consistent with the verifier selecting regions whose alignment remains
-usable. Exhaustive search over starting bases also permits recovery of the original alignment
-downstream of an edit. This interpretation explains the observed single-edit results, but provides
-no general guarantee against more extensive modification. Theoretical work on watermark removal
-further emphasises that robustness depends on the permitted adversarial capabilities
+usable in both Carbon-500M and GENERator-v2 1.2B. Exhaustive search over starting bases also permits
+recovery of the original alignment downstream of an edit. The strongest window does not identify
+the exact generation boundaries. This interpretation explains the observed single-edit results, but
+provides no general guarantee against more extensive modification. Theoretical work on watermark removal
+further emphasizes that robustness depends on the permitted adversarial capabilities
 \cite{zhang2024sand}. Here, each read received exactly one randomly specified edit, without access
 to the verifier's score.
 
-The alignment problem is related to synchronisation errors in coding theory. Synchronisation
+The alignment problem is related to synchronization errors in coding theory. Synchronization
 strings explicitly encode indexing information to support recovery from insertions and deletions
 \cite{haeupler2017synchronization}. Pseudorandom codes combine computational indistinguishability
 with decodability under specified error models, motivating their use in watermarking
@@ -578,14 +587,18 @@
 approaches may support broader provenance workflows, but their compatibility and biological
 consequences would require separate evaluation.
 
+Future work should evaluate the trade-off between watermark strength, detection power, and
+sequence-level distortion across different tournament depths in both Carbon-500M and
+GENERator-v2 1.2B.
+
 \section{Limitations}
 
 
 This is a scoped empirical evaluation rather than a general proof of watermark robustness,
 biological safety, or secret-key security. The study covers two models, one watermark construction,
-one verifier, and one shared prompt cohort. Each model contributes a single execution, and
-independent confirmatory replication remains outstanding. Both models use six-base tokens; models
-with single-base or variable-length tokenisation would present different alignment requirements.
+and one verifier. The evaluation used one execution per model on a shared prompt cohort.
+Both models use six-base tokens; models
+with single-base or variable-length tokenization would present different alignment requirements.
 The shared cohort limits extrapolation across genomic sources, and longer reads would increase the
 search correction. Generation was performed on GPU hardware and detection on x86-64 CPUs; neither
 result has been independently replicated across computing platforms. For Carbon, the retained
@@ -616,17 +629,29 @@
 read-level correction over both strands, every starting base, and four window lengths. Control
 counts were compatible with the declared false-positive target, although 192 independent prompts
 provide limited precision near a 1\% rate. In both models, the strongest-window distributions
-support alignment recovery through the search after insertions and deletions. These findings
+are consistent with the search selecting regions with preserved or recovered token alignment after
+insertions and deletions. These findings
 support statistical provenance detection in model-generated DNA within the evaluated scope; they
 require independent replication, broader sequence coverage, and biological validation before
 broader conclusions can be drawn.
 
 \section*{Data and code availability}
 
-The two experimental keys are published as public fixtures for reproducibility. They are not
-deployment secrets, and the experiments do not assess resistance to secret-key recovery. The
-generated sequences, verifier outputs underlying the figures, prompt set, and analysis and figure
-code are available from the authors on request.
+The source code, prompt definitions, analysis and figure scripts, and evidence ledger are maintained
+in the \href{https://github.com/Georgakopoulos-Soares-lab/genomic-sampling-watermarks}{project GitHub repository}.
+Generated sequences and underlying result files not included in the repository are available from
+the authors on request. The two experimental keys are published as public fixtures for
+reproducibility. They are not deployment secrets, and the experiments do not assess resistance to
+secret-key recovery.
+
+\section*{Competing interests}
+
+The authors declare no competing financial or non-financial interests.
+
+\section*{Acknowledgments}
+
+This work has been supported by the National Institute of General Medical Sciences of the National
+Institutes of Health [R35GM155468 to I.G.S.]; and start-up funds awarded to I.G.S.
 
 \bibliographystyle{plain}
 \bibliography{refs}
--- before/paper/manuscript/source/refs.bib
+++ after/paper/manuscript/source/refs.bib
@@ -39,6 +39,7 @@
   volume    = {202},
   pages     = {17061--17084},
   year      = {2023},
+  url       = {https://proceedings.mlr.press/v202/kirchenbauer23a.html},
   note      = {arXiv:2301.10226}
 }
 
@@ -111,6 +112,21 @@
   doi     = {10.1126/science.ado9336}
 }
 
+% Added 2026-09-13; publication metadata and PMID verified against the RCSB primary citation
+% (https://www.rcsb.org/structure/36CQ) and the authors' publication list.
+@article{king2026bacteriophages,
+  title   = {Generative design of bacteriophages with genome language models},
+  author  = {King, Samuel H. and Driscoll, Claudia L. and Li, David B. and Guo, Daniel and
+             Merchant, Aditi T. and Brixi, Garyk and Wilkinson, Max E. and Hie, Brian L.},
+  journal = {Science},
+  volume  = {393},
+  pages   = {eaec2657},
+  year    = {2026},
+  doi     = {10.1126/science.aec2657},
+  url     = {https://pubmed.ncbi.nlm.nih.gov/42561074/},
+  note    = {PMID: 42561074}
+}
+
 @article{dallatorre2025nucleotide,
   title   = {{Nucleotide Transformer}: building and evaluating robust foundation models for human genomics},
   author  = {Dalla-Torre, Hugo and Gonzalez, Liam and Mendoza-Revilla, Javier and
```
