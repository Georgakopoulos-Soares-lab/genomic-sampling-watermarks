# Language and flow pass on the manuscript (2026-09-30)

Scope: prose only in `paper/manuscript/source/main.tex`. No figure, table cell, equation, label,
citation key, figure file name, float environment, or preamble line was changed. The baseline for
every comparison below is the manuscript as found at the start of the pass (SHA-256
`2fc4373d...`). Requested context files `paper/context/00_terminology.md`,
`paper/context/02_claims_and_limits.md`, and `~/.agents/policies/writing-style.md` do not exist.
The pass followed `CLAUDE.md`, `AGENTS.md`, `paper/AGENTS.md`, the "Writing boundaries" section
of `paper/context/evidence_map.md`, and `paper/context/language_flow_prompt.md`.

Main text, Introduction through Conclusion, excluding floats: 7,712 words before and 7,256 after
(-5.9%). The abstract grew from 340 to 354 words, and the end statements fell from 428 to 401.
The built PDF fell from 18 to 17 pages.

## Sections restructured and why

- **Abstract.** Removed the em-dash. Named the one wrong-key setting above 1%, Carbon after a
  deletion, as the model-naming rule requires; the value comes from Table 2. Changed "same
  chromosomes" to "same chromosome records" and "token alignment" to "token phase".
- **Introduction.** Removed the "Here, we" opener. Defined token phase at its first use, including
  the existing clarification that it is not alignment to a reference genome. Moved the
  distribution-preservation statement from a stray closing sentence into the paragraph that poses
  the sampler question it motivates. Removed "declared" and "pre-specified".
- **Background 2.2 and 2.4.** These two subsections overlapped in four places. The frameshift
  argument, why a single indel destroys downstream token identity and keyed context, is now only
  in 2.2, where it is contrasted with text-watermark synchronization. 2.4 refers back to it. The
  statement that verification is a search over strands, phases, start positions, and window
  lengths, with the correction built into the method, is stated once at the end of the
  frameshift argument in 2.2 in plain words. 2.4 keeps only the reason for the correction
  (selecting the strongest window without correction overstates the evidence). The codon and
  protein comparison is now only in the 2.2 property paragraph; its duplicate in 2.4 is removed.
  "SynthID belongs to the latter class" and "in its non-distortionary configuration" are merged
  into one sentence. 2.4 is retitled "Genomic tokenization and token phase". "This is why ...
  rather than ... rather than an afterthought" and the em-dash in the SemStamp sentence were
  rewritten. "The distinction is sharper than a difference of degree" was cut as throat-clearing.
- **Background 2.3.** Merged the two paragraphs that each gave the rationale for choosing SynthID.
  "In expectation over fresh keyed functions" appeared twice in one sentence; it is now stated in
  2.3's first paragraph and referred back to ("in the averaged sense above"), with the fixed-key
  reweighted distribution kept explicit.
- **Background to Limitations.** The two sentences saying that no same-cohort comparison against
  an alternative construction was run, and the closing meta-sentence "We therefore compare
  properties, not measured performance", moved to Limitations and were merged with the duplicate
  Discussion paragraph. All of the content is kept, including the biased-logit example, the two
  reasons, and the statement that the property comparison does not substitute for measured
  performance.
- **Methods.** 3.1: the hardware paragraph moved to the end of 3.4, where both cohorts are
  defined. "Arms" became "samplers". 3.3: window lengths and $N$ are now introduced before the
  formula that uses them. "Scored token" and window "strength" are defined in plain words at
  first use. The two statements that Bonferroni needs no independence were merged. "Far from
  independent" and "strongly" were removed. The colon reveals in the window-geometry paragraph
  were split, and the complexity paragraph's semicolon chain was split. 3.4: rewritten so that
  both cohorts read as one design. It covers shared prompt construction, then the primary cohort
  with its 64/192 split and window-score selection (moved here from Results 4.3), then the second
  cohort, then generation, read construction, and the three read sets (also moved from 4.3), then
  hardware. 3.5: the Monte Carlo rationale is reordered so the reason comes before the choice.
  3.6: the measure list uses semicolons between items so the internal comma list is readable.
  3.7 and 3.8: past tense for what was done. 3.8 is retitled "Edit-rate experiment".
- **Results.** Removed the "We first report ... then ..." preamble. Every subsection now opens
  with its finding. 4.3: removed the setup paragraph that duplicated Methods 3.4 (prompt split,
  window-score selection, read construction, read sets, search identity, and the
  $M = 16{,}136$ / 6.21 values for unedited reads, all of which are stated in 3.3 and 3.4). Split
  the long strength paragraph into separate paragraphs for strengths, the weakest GENERator read,
  and prompt-level intervals. The GENERator known-phase null diagnostic is described in plain
  words. 4.4: opens with the window-length shift and keeps a brief threat-model sentence.
  4.5: retitled from "replication" to "detection and false-positive rate", because Limitations
  states that it is not an independent replication. "We report it as observed" was cut, and
  "unmarked reads" became "ordinary reads". 4.6: colon reveals were split.
- **Discussion.** Replaced the paragraph that recapped all results with a statement of the main
  result and the methodological contribution. The future-work sentence is merged into the
  paragraph on margin and continuation length. The portability paragraph keeps one sentence
  disclaiming equivalence, because that is the result that invites the misreading; the
  extrapolation caveat is left to Limitations. The strongest-window paragraph no longer repeats
  Results 4.4's substitution versus indel mechanism. The coding-theory paragraph lost two
  em-dashes and the word "channel"; Davey and MacKay are named from the bibliography entry.
- **Limitations.** Split into scope, the alternative-construction comparison (moved in),
  execution and the Carbon audit, false-positive evidence, threat model, keys, and biological
  proxies. The audit's em-dash list became its own sentence. "A later audit" became "An audit".
  "Exceeds it" became "exceeds that level", and "one wrong-key cell" now names Carbon after a
  deletion. The in-silico benchmark paragraph lost its em-dashes and its meta-commentary.
- **Conclusion.** Replaced the colon reveal with a sentence. "Token alignment" became "token
  phase".
- **End statements.** AI use: "evidence ledger" became "recorded measurements", and the colon
  was split. Ethics: "cohort" became "cohorts", and "reproducibility fixtures" became "published
  for reproducibility". Reproducibility: the asset list that duplicated Data availability is
  shortened to a pointer, and the key sentence is left to Data availability. Data availability:
  "public fixtures" was removed.
- **Captions.** Figure 1: "token alignment" became "token phase". Figure 2: "pre-specified" was
  removed. Table 2: "per cell" became "per model and condition", and "wrong-key family" became
  "wrong-key control". Figure S1: "three families" became the marked, ordinary, and wrong-key
  sets.

## Vocabulary removed (occurrences, before to after)

| Item | Before | After | Note |
|---|---|---|---|
| em-dash `---` | 8 | 0 | |
| "rather than" | 19 | 4 | Kept: Zhao edit tolerance versus guarantee; local context versus absolute position; offset versus frame; reading annotated DNA versus what a model writes |
| arm / arms | 12 | 0 | |
| family (all senses) | 16 | 5 | All 5 remaining are multiple-testing uses: "one multiple-testing family", "form one family", "their own family", "this family size", "family-wise error rate" |
| cell / cells | 6 | 0 | |
| declared | 6 | 0 | |
| pre-specified | 6 | 0 | "Specified before analysis" kept in the abstract and Methods 3.6; α is "set in advance" |
| fixture(s) | 3 | 0 | |
| replay seed | 1 | 0 | Now "sampling seeds" |
| draw-zero trajectory | 1 | 0 | Now "the first ordinary continuation" |
| authorized | 1 | 0 | Now "intended generators and verifiers" |
| window-score summary | 1 | 0 | |
| scored bits | 1 | 0 | "Scored token" is defined in 3.3 |
| calibration prompts / Evaluation prompts | 2 | 0 | Now "reserved prompts" and "held-out prompt" |
| token alignment | 9 | 0 | Now "token phase" |
| unmarked (reads) | 2 | 0 | Now "ordinary"; 13/12,352 = 0.105% and 23/12,352 = 0.186% match Table 2's ordinary counts |
| "Here," openers | 3 | 0 | |
| "This is why" | 1 | 0 | |
| far (intensifier) / strongly | 2 / 1 | 0 / 0 | "How far below α it falls" is kept as a measurement phrase |
| "later" (chronology) | 1 | 0 | "A later audit"; the remaining uses of "later" are positional ("every later token") |
| meta-commentary ("we report it as observed", "We state that absence as a limitation", "We therefore compare properties ...") | 3 | 0 | |
| "without reference to the detector" | 5 | 4 | Abstract, Introduction, Figure 5 caption, and Limitations; Background says "never consult the detector" |
| "fresh keyed" | 7 | 4 | |
| "one-sided 95" | 7 | 6 | The Discussion recap is gone |
| "ledger" | 3 | 2 | Both remaining uses are in the Reproducibility and Data availability statements |
| prose colons / "; " | 31 / 58 | 6 / 38 | The remaining colons introduce lists, a definition, or a subsection title |

## Check 1 (numbers)

Run with the corrected regexes against the baseline:

```
removed: {'10': 1, '2': 1, '384': 1, '95': 1, '256': 1, '16,136': 1, '6.21': 1, '3,072': 1, '792.9': 1, '799.7': 1}
added:   {'1': 1}
```

Each removed numeral is a duplicate cut on purpose, and each value is still stated elsewhere:

- `10`, `2`, `95`: from the Discussion recap ("one-sided 95% upper confidence bound ... below
  the declared 1% target", "2% per-base rate", "failed for most reads at 10%"). These are still
  in the abstract, Introduction, Results 4.5 and 4.6, Methods 3.8, and Conclusion.
- `384`: Methods 3.3, "the shortest window the verifier evaluates, which is 384 bases", which
  repeated the sentence that opens the same paragraph.
- `256`: Methods 3.4, "We refer to the 256-prompt cohort as the primary cohort", which became
  "The primary cohort contains 256 prompts".
- `16,136`, `6.21`: Results 4.3 setup, "Unedited reads require M = 16,136 windows and a threshold
  of 6.21", already stated in Methods 3.3.
- `3,072`: Results 4.2, "continuations of 3,072 bases", already stated in Methods 3.4.
- `792.9`, `799.7`: Results 4.3, the second-cohort medians, which are reported in Results 4.5.

The net `'1': 1` added has three parts. Two `1`s are bit values: "at least 1,004 of the 1,800
bits to be 1" and "when all 21 are 1" replace "to be positive" and "are positive", so that mark
bits are described the same way as "the fraction of 1s" elsewhere. One `1` was removed with the
Discussion recap's "1% target". Every other occurrence of `1` is unchanged in value and differs
only in surrounding words. No model name was altered or removed: all instances of "Carbon-500M",
"GENERator-v2 1.2B", and "GENERator-v2-eukaryote-1.2b-base" remain.

## Check 2 (keys)

```
label ok
ref ok
cite ok
```

The set of unique keys is unchanged. Three instance counts fell because the sentences that
carried them were duplicates. `\cite{chen2025protein}` went from 2 to 1 and
`\cite{zhang2025securing}` from 3 to 2, both from the 2.4 complementarity sentence that repeated
2.2. `\ref{sec:prompts}` went from 2 to 1 because the hardware paragraph moved into §3.4 itself.

## Check 3 (vocabulary grep)

```
962:protocol documents, and evidence ledger needed to reproduce the analysis are available as
968:analysis and figure scripts, the protocol documents, and the evidence ledger to which every number
```

Both hits are in the Reproducibility and Data availability statements, where the task allows
"ledger".

## Check 4 and build

`python3 scripts/check_evidence.py` fails only with the five known missing Carbon primary-cohort
artifacts (`outputs/carbon_synthid_e16_v1/*` ×3 and
`outputs/carbon_synthid_position_independent_v1/*` ×2). `paper/scripts/build.sh` cannot run here
because no TeX engine is installed. The manuscript was built with tectonic 0.15.0 into a scratch
directory instead. It produced no LaTeX warnings, no undefined references, no errors, and no
overfull boxes (the baseline had one). The built PDF was read start to finish, and two ambiguous
sentences were fixed (§2.4 "DNA, which must recover ..."; Figure S1 read counts).

## Left unchanged because it would touch a claim or a number

- **Precision mismatches.** Limitations restates 2.868% and 1.903% as 2.87% and 1.90%, and the
  abstract and Conclusion give 0.85% where Results gives 0.850%. Harmonizing either would change a
  numeral, so they are left for the authors.
- **"Statistically indistinguishable"** (Limitations) is worded more strongly than "no
  statistically detectable difference" used elsewhere. It was kept verbatim; the authors may want
  to align it.
- **"Equivalently, a read is positive only if ..."** describes what is logically an
  if-and-only-if. "Only if" was kept so as not to restate the decision rule.
- **Zhao et al.** "this buys twice the edit tolerance ... rather than the guarantee itself" was
  kept because its intended meaning cannot be sharpened without the authors.
- **Strength definition.** Written as "the negative base-ten logarithm of $P_{\mathrm{win}}$". The
  form $-\log_{10} P_{\mathrm{win}}$ would add a numeral (the subscript 10); the figure axes
  already show it.
- **Future work.** "Watermark strength" was rephrased as tournament depth trading detection
  power against distortion, so that "strength" keeps its single defined meaning.
- **Short model names.** "Carbon" and "GENERator" were not expanded to full names, because that
  would add numerals. The PDF hyphenates "Carbon-500M" across a line in the AI use statement;
  preventing that needs markup around the protected name, so it was left.
- **Disclaimers kept in Results and Discussion.** Each was kept because the specific result next
  to it invites the misreading, and the invariants require the qualifiers wherever they appear.
  They are: equivalence in 4.2 and in the portability paragraph, the threat model in 4.4 and in
  the strongest-window paragraph, and the Introduction's closing scope sentence.
- **Author check: "committed artifact".** "Was not retained as a committed artifact" became "was
  not retained as a recorded result". Please confirm this still says what is meant.
