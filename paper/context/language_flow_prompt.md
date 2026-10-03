# Prompt: language and flow pass on the manuscript

Paste everything below the line into a fresh session opened at the repository root. The session
should be able to edit files and run shell commands.

---

You are editing the prose of a finished scientific manuscript,
`paper/manuscript/source/main.tex`. It reports the SynthID tournament watermark in two genomic
language models, Carbon-500M and GENERator-v2 1.2B, and a verifier that detects the watermark in
DNA without knowing where the generated region starts, which strand it is on, or how it was split
into six-base tokens.

The science is settled and every number has been checked. **Your job is only the writing.** The
paper must read as if two careful researchers wrote it for reviewers in machine learning and
computational biology. Right now it reads like a changelog assembled by several drafting passes
and an AI assistant. Make it read naturally, with a clear line of argument, and without the
internal project vocabulary and machine-written tics listed below.

## Read first

1. `paper/AGENTS.md`: manuscript rules.
2. The "Writing boundaries" section of `paper/context/evidence_map.md`: what the paper may and may
   not claim.
3. `paper/manuscript/source/main.tex`, read end to end before changing anything. Note where the
   argument repeats itself and where a reader would lose the thread.

## What you must not change

Treat these as invariants. A single violation makes the pass unusable.

- **Numbers.** Every numeral keeps its value, precision, and unit (for example 0.850\%, 1.015\%,
  3{,}088, 790.6, 16{,}136, 6.21). Do not round, re-express, or recompute anything, and do not add
  a number that is not already in the text.
- **Claims and their strength.** Do not add, drop, strengthen, or weaken a claim. The following
  qualifiers carry scope and must survive in substance wherever they appear:
  - "one-sided 95\% upper confidence bound" (never just "bounded the false-positive rate");
  - edits placed "without reference to the detector", and the statement that an editor who
    inspects the detector, key, or score was not tested;
  - the second cohort is "not an independent replication" and comes from the same chromosome
    records;
  - the wrong-key cell at 1.015\% is reported, not hidden;
  - the Carbon protocol-document mismatch and its audit (eight of nine settings recovered);
  - distribution preservation holds in expectation over fresh keyed functions, and fixed-key
    sampling follows the reweighted distribution;
  - no claim of biological function, viability, safety, or secret-key security.
- **Model naming.** Any claim that rests on one model must name that model. Do not merge per-model
  statements into a joint one. Never alter the model names themselves: "Carbon-500M",
  "GENERator-v2 1.2B", and "GENERator-v2-eukaryote-1.2b-base". The "v2" in GENERator's name is
  part of the model's name, not a version label to remove.
- **LaTeX structure.** Leave every `\label`, `\ref`, `\cite` key, equation, table cell, figure file
  name, float environment, and the preamble untouched. You may reorder or merge sentences and
  paragraphs within a section, and you may retitle a section or subsection.
- **Scope of edits.** Edit only `main.tex`, plus the review note described at the end. Do not touch
  figures, the bibliography, the ledger, or scripts.

## Remove internal project vocabulary

The reader never saw the lab's process, so none of its vocabulary belongs in the paper. Remove or
replace every instance of the following. Most are already gone; check for all of them and for
anything like them.

| Remove | Replace with, or instead |
|---|---|
| frozen, freeze, locked, gated, gate, gating | say what was fixed and when: "chosen before any output was generated" |
| eval, eval set, evaluation cohort as a label | "held-out prompts" or "the prompts used for evaluation" |
| v1, v2, v3, version one, pilot, lane, PAT, CONF-, AD-, L1-, E16, E-numbers, `synthid.*` identifiers | "the primary cohort", "the second cohort", "the edit-rate experiment" |
| admitted, admission, evidence identity, namespace, ledger (outside the Reproducibility and Data availability statements), sign-off, authorized, amendment | delete; describe the study, not its bookkeeping |
| predeclared, pre-declared, preregistered, pre-specified (6 uses), "declared" (6 uses: "declared 1\% target", "declared quality proxies", "declared law") | "the 1\% target"; "specified before analysis" once where it matters; otherwise nothing |
| arm, arms (9 uses) | "marked and ordinary outputs", or "each sampler"; keep "arm" at most where a clinical-trial reading helps, once |
| family, control family, primary family, secondary family (16 uses) | keep "family" only in the multiple-testing sense ("one family under Benjamini–Hochberg correction"); otherwise "control", "ordinary-output control", "wrong-key control" |
| cell, condition-cell | "condition", "setting", or name it ("Carbon after a deletion") |
| draw-zero trajectory, replay seed, fixture key | "the first ordinary continuation", "sampling seed", "published key" |
| public replay, channel, falsification check, manufactures structure, confirmatory characterization, operational rate, full-cohort | plain description of what was done |
| window-score summary, read-level decision, scored bits, strength (if undefined at first use) | define once in plain words at first use, then use consistently |

## Remove machine-written tics

These patterns make text read as AI-generated. Rewrite each instance you find; do not just swap
synonyms. When a flagged sentence also carries part of the argument, rephrase it and keep the
point; do not delete it. For example, the Background sentence explaining that verification is
posed as a search over strands, phases, start positions, and window lengths, not as an
alignment, links the background to the method and must survive in plain words.

- **Em-dash asides** (`---`, currently 8). Keep at most two in the whole paper; use commas,
  parentheses, or a new sentence.
- **"Rather than" and "not X but Y" contrasts** (19 uses of "rather than"). Keep only those that
  make a real distinction the reader needs; state the positive claim directly otherwise.
- **Paragraph-opening signposts**: "Here, we", "In this section", "We first report... then...",
  "This is why", "the precise sense in which", "It is worth noting", "Importantly", "Notably",
  "Crucially", "Taken together". Open with the finding or the claim instead.
- **Stacked hedges and repeated disclaimers.** The paper disclaims biological function, equivalence
  between models, and adversarial robustness in nearly every section. State each disclaimer fully
  once in Limitations, briefly in the Abstract and the Ethics statement, and not in the Results or
  Discussion unless a specific result invites the misreading.
- **Triplets and parallel lists** used for rhythm ("strand orientation, start position, and window
  length" is fine as content; "X, Y, and Z" used as cadence is not). Vary sentence length and
  structure; mix short declarative sentences with longer ones.
- **Semicolon chains and colon reveals** ("The result is clear: ..."). Split into sentences.
- **Meta-commentary about the paper itself**: "We state that absence as a limitation", "we
  therefore compare properties, not measured performance", "we report it as observed". Say the
  fact; let the reader draw the inference.
- **Vague intensifiers and filler**: "robust" (unless technical), "underscores", "highlights",
  "leverage", "pivotal", "landscape", "delve", "far", "strongly", "substantially", "wide margin".
  Use the number instead where one exists.
- **Repeated phrases.** "in expectation over fresh keyed functions" appears verbatim several
  times; "without reference to the detector" and "one-sided 95\% upper confidence bound" recur.
  Keep the precise wording at first use and once where precision matters later; elsewhere refer
  back briefly ("this bound", "these random edits").

## Improve flow

- **One line of argument.** Introduction: problem, why DNA makes it hard (unknown boundary, strand,
  token phase), what we do, what we find. Methods: in the order a reader needs to reproduce it.
  Results: each subsection opens with its finding, then the supporting numbers. Discussion:
  interpretation and relation to prior work, not a repeat of Results.
- **Two cohorts, told once.** The primary cohort (192 held-out prompts) and the second cohort
  (1,544 held-out prompts) should read as one designed study, not as an original study followed by
  later additions. Remove any residue of chronology such as "subsequently", "later", "we have
  since", or "in a follow-up".
- **Background.** Sections 2.2 and 2.4 are long and overlap on text-watermark synchronization and
  six-mer tokenization. Tighten them so each point is made once, in the section where it belongs.
- **Terminology.** Pick one term per concept and hold it: marked read / ordinary read / wrong-key
  control; primary cohort / second cohort; window strength ($-\log_{10} P_{\mathrm{win}}$);
  per-base edit rate; token phase; Jensen–Shannon drift. Do not introduce synonyms for variety.
- **Tense and voice.** Past tense for what was done and found; present tense for what the method
  is and what a figure shows. First person plural is fine; avoid passive constructions that hide
  the actor when "we" is clearer.
- **Length.** Aim to shorten the main text by roughly 5–10\% through removed repetition, not
  through cut content.
- American spelling throughout, matching the current text.

## Check your work before finishing

Run all of these and fix any failure. Before your first edit, save the manuscript as you found it:
`cp paper/manuscript/source/main.tex /tmp/main_before.tex`. The checks compare against that copy.

```bash
# 1. Numbers unchanged: compares the multiset of numerals before and after.
python3 - <<'PY'
import re, collections, pathlib
def numbers(path):
    text = pathlib.Path(path).read_text(encoding="utf-8")
    text = re.sub(r"(?m)(?<!\\)%.*$", "", text)          # drop comments, keep \%
    text = re.sub(r"\\(label|ref|cite|includegraphics)\{[^}]*\}", "", text)
    text = text.replace("{,}", ",")
    return collections.Counter(re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", text))
before = numbers("/tmp/main_before.tex")
after = numbers("paper/manuscript/source/main.tex")
print("removed:", dict(before - after))
print("added:  ", dict(after - before))
PY
# Every removed number must be a duplicate you deliberately cut; every added number must be
# zero. Investigate anything else.

# 2. LaTeX keys unchanged
for k in label ref cite; do
  diff <(grep -o "\\\\$k{[^}]*}" /tmp/main_before.tex | sort -u) \
       <(grep -o "\\\\$k{[^}]*}" paper/manuscript/source/main.tex | sort -u) && echo "$k ok"
done

# 3. Banned vocabulary gone (review every hit)
grep -niE "frozen|freeze|\bgat(e|ed|es|ing)\b|\beval\b|(^|[^-[:alnum:]])v[123]\b|pilot|synthid\.|ledger|admitted|sign-off|predeclared|pre-declared|draw-zero|public replay|channel|operational|subsequently|---" \
  paper/manuscript/source/main.tex | grep -v includegraphics

# 4. Evidence and build
python3 scripts/check_evidence.py   # only the five known missing Carbon primary-cohort files may fail
cd paper && ./scripts/build.sh
```

Then read the built PDF once from start to finish as a reviewer would, and fix anything that
still reads as stitched together.

## Deliverables

1. The edited `paper/manuscript/source/main.tex`.
2. A dated note, `paper/reviews/<YYYY-MM-DD>_language_flow_pass.md`, that lists:
   - each section you restructured and why;
   - the vocabulary you removed, with counts;
   - the output of check 1, with any deliberately removed duplicate numbers named;
   - anything you wanted to change but did not, because it would have touched a claim or a
     number.

Do not overwrite earlier review notes.
