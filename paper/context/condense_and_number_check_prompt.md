# Prompt: number audit, readability, and a much shorter paper

Paste everything below the line into a fresh session opened at the repository root. The session
needs file editing and shell access.

---

You are revising `paper/manuscript/source/main.tex`. The paper shows that the SynthID tournament
watermark can be embedded in two genomic language models (Carbon-500M, GENERator-v2 1.2B) and
detected from DNA alone, without knowing where the generated region starts, which strand it is on,
or how it was split into six-base tokens.

The science is settled. The paper is too long (7,609 words of main text, 17 pages), and it reads
as a stream of terms and numbers. Your job has three parts, in this order:

1. Audit every number.
2. Rewrite the paper to roughly 60% of its length, as one coherent argument.
3. Make every paragraph readable by a reviewer who has not seen the project.

## Read first

`paper/AGENTS.md`; the "Writing boundaries" section of `paper/context/evidence_map.md`;
`evidence/measurements.yaml`; then `main.tex` end to end.

## What must not change

- **Values.** No number may change value, rounding, unit, model, or cohort. You may remove a
  number from the text, but every value the paper still reports must remain somewhere: the text,
  a table, or the supplement.
- **Claims and their strength.** No claim may be added or strengthened. Keep these qualifiers in
  substance:
  - the false-positive rate is given only as a one-sided 95% upper confidence bound;
  - the 1.015% wrong-key cell (Carbon, deletion) is reported;
  - edits were placed without reference to the detector, and an adaptive editor was not tested;
  - each insertion or deletion event changes 1–5 bases, so the edit rate counts events;
  - the second cohort is the same team's repeat, not an independent replication;
  - the Carbon protocol-document mismatch and its audit;
  - sampler correctness rests on the implementation tests (§3.5);
  - distribution preservation holds in expectation over fresh keyed functions;
  - no claim of biological function, viability, safety, or secret-key security.
- **Names and structure.** Any claim that rests on one model names that model. Do not alter the
  model names. Keep every `\label` and `\cite` key that remains in use, every figure file, and
  every table cell value.

## Part 1: build a number register before editing anything

Extract every numeral in the Abstract, body, captions, and tables. Group them by the quantity they
report, for example "ordinary-output bound, GENERator, deletion, second cohort". For each
quantity, record:

- every location where it appears;
- its value at each location;
- the ledger identifier or figure manifest it comes from (`paper/figures/figure_values*.json`);
- the ledger value.

Then check:

- the same quantity has the same value and precision everywhere;
- text, tables, captions, and the plotted figure values agree;
- every count matches its denominator, and every percentage, ratio, and "eight times" follows
  from ledger values;
- every number is attached to the right model and cohort.

Save the register as `paper/reviews/<date>_number_register.md`. If you find a discrepancy, the
ledger wins. Fix it and list it at the top of the register. Re-check the register after Part 2.

## Part 2: one argument, about 4,500 words

**Storyline.** Present one study with two cohorts that have distinct roles. Remove any trace of
an "original study, then later additions" chronology.

- **Development cohort** (256 prompts): window-score selection, sampler checks, quality measures,
  and a first detection run.
- **Detection cohort** (1,608 prompts, 1,544 held out): detection, false-positive rate, single
  edits, and the edit-rate series. It carries the detection headline. The development cohort's
  detection appears as one confirming sentence.

**Word budget** (main text). Keep figures and tables:

| Section | Now | Target |
|---|---|---|
| Abstract | 304 | ≤ 200 |
| Introduction | 520 | ~450 |
| Background | 1,336 | ~650 |
| Methods | 2,561 | ~1,300 |
| Results | 1,564 | ~1,300 |
| Discussion | 578 | ~350 |
| Limitations | 886 | ~400 |
| Conclusion | 164 | ~120 |

**Move to a short "Supplementary information" section** (after the references, with the existing
supplementary figures). Keep the content; just take it out of the main line:

- the development-cohort detection table (current Table 1), so the second-cohort table becomes
  Table 1;
- the search-cost and timing analysis;
- the Bonferroni-conservatism measurement (effective number of tests);
- the GENERator aligned-detector diagnostic;
- the window-score selection details;
- the full weakest-read analysis (the main text keeps two sentences: typical strength is the same
  in both models, and the extreme is one repetitive read);
- the per-condition window-length counts.

**Cut or merge where the paper repeats itself:**

- Background §2.2 and §2.4 make the frameshift argument twice. Make it once.
- The biological and secret-key disclaimers appear in nearly every section. Keep them in the
  Abstract (one clause), Limitations, and the Ethics statement only.
- Results and Discussion restate the same numbers. The Discussion should interpret, not repeat.
- The Limitations paragraph on downstream benchmarks can shrink to three sentences.

## Part 3: readability, not terms and numbers

- **One point per paragraph.** Each paragraph makes one point, and its first sentence states it.
- **The finding before the numbers.** Each result says what was found in words, then gives at
  most the two or three numbers that support it. Everything else goes to a table or the supplement.
- **Few numbers per sentence.** A sentence carries at most two numbers, except in captions and
  tables. Never list values that a table already shows.
- **Define a term once, in plain words, where a reader first needs it.** For example: window,
  strength ($-\log_{10} P_{\mathrm{win}}$), token phase, scored token, wrong-key control, and
  per-base edit rate. Drop terms that are used only once.
- **One name per concept.** Use one name for each concept throughout: marked read, ordinary read,
  wrong-key control, development cohort, detection cohort, strength, token phase, edit rate.
- **No internal or machine-written vocabulary.** Avoid em-dash asides, "rather than" contrasts used
  for rhythm, signposting openers ("Here, we", "Notably"), and stacked hedges. Avoid internal
  vocabulary such as frozen, gate, ledger (outside the availability statements), v1/v2/v3,
  pilot, and sign-off.
- **Test.** After each section, read it as a newcomer. If a sentence cannot be understood without
  the previous three, rewrite it.

## Checks before you finish

```bash
cp paper/manuscript/source/main.tex /tmp/main_before.tex   # do this before your first edit
# Number values: anything "added" must be in the register with a ledger source; "removed" values
# must still appear in a table or the supplement, or be listed as deliberately dropped.
python3 - <<'PY'
import re, collections, pathlib
def numbers(path):
    t = pathlib.Path(path).read_text(encoding="utf-8")
    t = re.sub(r"(?m)(?<!\\)%.*$", "", t)
    t = re.sub(r"\\(label|ref|cite|includegraphics)\{[^}]*\}", "", t).replace("{,}", ",")
    return collections.Counter(re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", t))
b, a = numbers("/tmp/main_before.tex"), numbers("paper/manuscript/source/main.tex")
print("values no longer anywhere:", sorted(set(b) - set(a)))
print("new values:", sorted(set(a) - set(b)))
PY
python3 scripts/check_evidence.py      # only the five known missing Carbon primary-cohort files may fail
R=/workspaces/gsw-runtime; (cd paper/manuscript/source && $R/tectonic main.tex --outdir $R/build)
grep -c "LaTeX Warning" $R/build/main.log  # must be 0; no undefined references or citations
```

Then read the built PDF once from start to finish, in order. You can extract its text with
`$R/venv/bin/python -c "import pymupdf; ..."`.

## Deliverables

1. The revised `main.tex`, about 4,500 words of main text. Install the built PDF at
   `paper/manuscript/main.pdf`.
2. `paper/reviews/<date>_number_register.md`: the register, with discrepancies found and fixed at
   the top.
3. `paper/reviews/<date>_condensation.md`. It should contain:
   - word counts before and after, by section;
   - what moved to the supplement and what was cut;
   - every value no longer reported anywhere, with the reason;
   - the new figure and table numbering.
4. Updated `paper/context/evidence_map.md`, and an updated figure and table mapping in
   `paper/reviews/2026-09-21_openreview_rebuttal_draft.md`, because Table 1 moves.

Edit nothing else. Do not overwrite earlier review notes, and do not commit.
