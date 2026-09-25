# Lane 3 — Reconciliation of the two lanes (RUN LAST)

**Date:** 2026-09-21
**Run this only after both lanes report done.** It is a procedure, not a list of known conflicts:
the conflicts do not exist yet. Work through it in order and fill the conflict ledger as you go.

**Owner:** either person, or both together. Whoever runs it needs write access to both lanes'
files, which is why it must not start before both lanes have stopped writing.

## Inputs

| From | Artifact |
|---|---|
| Lane 1 | `evidence/derived/2026-09-21_results_delta.json` (the Results Delta Packet) |
| Lane 1 | new entries in `evidence/measurements.yaml`; new dirs under `outputs/`; regenerated `paper/figures/**` and `paper/figures/figure_values.json`; new `docs/research/*protocol*` and `*execution*` |
| Lane 1 | `docs/research/carbon_provenance_discrepancy_audit_2026_09_21.md` |
| Lane 2 | edited `paper/manuscript/source/main.tex` and `refs.bib` |
| Lane 2 | the placeholder register and the assumption register in `2026-09-21_lane2_claims_background.md` |
| Both | the coverage tables at the end of each lane document |
| Reference | the PAT feedback itself (OpenReview forum `vo1qxcMxxx`, note `LyX9i394f8`) |

**Resolve AD-5 before anything else.** If Lane 2 edited the repository's `main.tex` while the
submitted PDF was a different, longer document, the first reconciliation job is merging Lane 2's
edits into the submitted source, not checking numbers. Do that, then continue.

---

## 1. Detection checks

Run all of them. Each has a command or a query and a pass/fail definition. Record every failure in
the conflict ledger — do not fix anything until the whole pass is complete, because fixes interact.

### C1 — Orphan placeholders
Any `\evtag{...}` left in the manuscript with no matching ledger entry.

```bash
cd paper/manuscript/source
grep -o '\\evtag{[^}]*}' main.tex | sed 's/\\evtag{//;s/}//' | sort -u > /tmp/tags.txt
grep -o '^  - id: .*' ../../../evidence/measurements.yaml | sed 's/^  - id: //' | sort -u > /tmp/ids.txt
comm -23 /tmp/tags.txt /tmp/ids.txt   # tags with no ledger entry
```

**Pass:** empty output. **Fail:** each line is a conflict — either Lane 1 never produced it (switch
that sentence to its non-existent branch) or the ID was misspelled.

### C2 — Unused results
Any new evidence ID in the delta packet that no manuscript sentence and no figure consumes.

```bash
python3 - <<'PY'
import json, pathlib, re
delta = json.loads(pathlib.Path("evidence/derived/2026-09-21_results_delta.json").read_text())
tex = pathlib.Path("paper/manuscript/source/main.tex").read_text()
figs = pathlib.Path("paper/figures/figure_values.json").read_text()
for e in delta["entries"]:
    i = e["id"]
    if i not in tex and i not in figs:
        print("UNUSED", i, e.get("outcome"))
PY
```

**Pass:** empty. **Fail:** for each, decide which is true — the claim is missing from the paper, or
the run was unnecessary. Both are findings. An unused `refutes` result is the most serious possible
outcome of this whole exercise: it means a run contradicted the paper and nobody wrote it down.

### C3 — Number drift
Every numeral in the manuscript resolves to the ledger, with matching digits and units.

```bash
python3 scripts/check_evidence.py
cd paper && ./scripts/build.sh
```

Then manually reconcile the numbers the checker cannot bind: read §4.1, §4.2, §4.3, §4.4, the
Abstract, and the Conclusion, and confirm each printed value against its `evidence_map.md` row.
**Any number that changed in the ledger must change in all of those places or none.**

**Pass:** checker passes and every manually read number matches. **Fail:** one conflict per
mismatched number, with the file, line, and both values.

### C4 — Branch mismatch
The branch Lane 2 kept must match the `outcome` Lane 1 recorded.

For every row of Lane 2's placeholder register, read the corresponding `outcome` in the delta
packet and confirm the surviving sentence is that branch's text, and that the other branches were
deleted rather than left commented in.

**Pass:** every placeholder's surviving sentence matches its recorded outcome. **Fail:** a
conflict per mismatch. This is the check most likely to fire, because it is the seam the whole
split was built on.

### C5 — Claim-strength inconsistency
For each headline claim, compare its five appearances **pairwise**: Abstract, Introduction,
Results, Discussion, Conclusion, plus Limitations as a sixth. The headline claims are:

1. recall — "detected all marked reads in every condition"
2. false-positive rate — "compatible with / bounded near the declared 1% target"
3. quality — "no statistically detectable difference across 14 measures"
4. robustness scope — "after each tested single substitution, insertion, or deletion"
5. dual-model scope — every claim resting on one model names that model (`paper/AGENTS.md`)

**Pass:** all six locations state the same strength, the same scope, and the same hedging for each
claim. **Fail:** one conflict per disagreeing pair. Watch specifically for the Abstract keeping
"at most one positive among 384 reads" after §4.3 was rewritten for a larger cohort.

### C6 — Falsified assumptions
Walk Lane 2's assumption register (`ASM-01` … `ASM-06`) and check each against what Lane 1 actually
did.

- `ASM-02`: did the new run keep α = 0.01 and the four window lengths? If not, **every sentence in
  L2-17 is void**, and so are the 6.2078 / 49-of-60 / n≥21 figures in L2-06.
- `ASM-04`: is M still 16,136 for the reads discussed? If the read length changed, recompute.
- `ASM-03`: did the 124.8 / 19.6 strength values survive re-derivation?
- `ASM-06`: do the figure axes now read "drift"?

**Pass:** every assumption held, or its dependent text was updated. **Fail:** a conflict naming the
assumption and every task that rests on it.

### C7 — Stale or missing limitations
Read the Limitations section against the delta packet twice, in both directions.

- A limitation the new runs **removed** but the text still asserts (e.g. sample-size precision after
  a successful L1-01).
- A limitation the new runs **introduced** that nobody wrote down (e.g. a second execution platform,
  a new cohort with different sequence sources, a run that produced `inconclusive`).

**Pass:** Limitations matches the evidence as it now stands. **Fail:** one conflict per stale or
missing item. Note that removing a limitation requires a ledger entry supporting the removal; a
limitation may never be dropped because the text reads better without it.

### C8 — Figure / text divergence

```bash
python3 - <<'PY'
import json, pathlib
m = json.loads(pathlib.Path("paper/figures/figure_values.json").read_text())
print(json.dumps(m, indent=1)[:4000])
PY
sha256sum paper/figures/*.pdf paper/figures/*.png
```

Confirm: every value plotted matches the ledger; every figure digest in the manifest matches the
file on disk; captions use `TERM-1` ("Jensen–Shannon drift") and so do the axes; figure numbering
in the text matches the figures as they now appear (this is where AD-5's version divergence will
bite — the submitted PDF numbered the quality and edit figures 3 and 4 in an appendix).

**Pass:** values, digests, terminology and numbering all agree. **Fail:** one conflict each.
No figure may be hand-edited (`paper/AGENTS.md`); a wrong figure is regenerated, never patched.

### C9 — Citation / claim mismatch
For every citation Lane 2 added, confirm the cited source actually supports the sentence it backs.
Check specifically:

- `kuditipudi2024robust` is cited for edit-distance alignment robustness, not for anything about
  genomic tokenization;
- `kirchenbauer2023watermark` is cited for local-context hashing being standard, which is the
  precise claim PAT asked for;
- `zhang2025securing` and any new biological-watermarking citations are described by what they
  actually verify (model access? alignment? coding regions only?);
- any benchmark citation (BEND, GenBench) is described as future work, never as something run here.

**Pass:** every added citation supports its sentence. **Fail:** one conflict per overclaim. Also
flag any citation added for a claim the new results changed.

### C10 — Scope creep
Grep the diff of both lanes for anything that crossed a declared boundary.

```bash
git diff --stat
git diff | grep -nE 'multi(ple)?[- ]edit|edit rate|detector.guided|red.green|green.list|viab|express|function(al)?|safe(ty)?|secure|cryptographic' | head -50
```

**Pass:** no new claim about biological function, viability, expression or safety; no cryptographic
security claim; no multiple-edit or detector-guided experiment; no second watermark construction;
every scope-gated task carries an author sign-off in the lane document. **Fail:** one conflict per
crossing, and it outranks any reviewer request (see precedence below).

### C11 — Ledger hygiene

```bash
python3 scripts/check_evidence.py
PYTHONPATH=src python3 -m unittest discover -s tests -v
git status --porcelain outputs/ evidence/
git diff --stat -- outputs/
```

**Pass:** unique IDs; `[V]` vs `[A]` correctly labelled (measured vs derived); every new entry has
value, unit, uncertainty, sample count, scope, artifact, SHA-256, protocol path, execution path and
command; no file under `outputs/*_v1/` modified; no v1 ID renamed into `synthid.v2.*`; superseded
v1 IDs either still cited deliberately or removed from `paper/context/evidence_map.md`. **Fail:**
one conflict each.

**Also update `paper/context/evidence_map.md`** — it is the declared complete map of every number in
the manuscript, and new IDs that the paper cites must appear there. A new ID cited in the text but
absent from the map is a C11 failure.

### C12 — Reviewer coverage
Every PAT point must land somewhere: a paper change, a rebuttal paragraph, or a justified decline.
Reconcile the two lanes' coverage tables against this list.

| PAT point | Landing place | Verified |
|---|---|---|
| W1 edit-rate robustness | L2-08 paper text + rebuttal + decline register (L1-07 only if AD-2 was signed) | ☐ |
| W2 missing baselines / overhead | L2-13 + L2-07 + decline register | ☐ |
| W3 downstream biological tasks | L2-16 + decline register | ☐ |
| W4 FPR sample size | L1-01 + L2-17 | ☐ |
| W5a GoF statistic | L2-01 | ☐ |
| W5b 256-state correction | L2-02 | ☐ |
| W6 two window-score summaries | L2-03 | ☐ |
| W7 cross-model strength gap | L1-03 + L2-19 | ☐ |
| W8 provenance discrepancy | L1-02 + L2-18 | ☐ |
| W9 AI Use Statement | L2-09 | ☐ |
| B1 text-watermark synchronization contrast | L2-12 | ☐ |
| B2 token-phase scope | L2-14 | ☐ |
| B3 SynthID local-context precision | L2-15 | ☐ |
| M2 Bonferroni conservatism | L2-05 (+ L1-06 if run) | ☐ |
| M3 short-window boundary | L2-06 | ☐ |
| M5 complexity and optimizations | L2-07 + L1-04 | ☐ |
| A2 code availability | L2-10 | ☐ |
| T1 detached accent | L2-11 | ☐ |
| T2 hyphenation throughout | L2-11 | ☐ |
| T3 "decoder only" | L2-11 | ☐ |
| T4 "Jensen Shannon drift" | L2-11 | ☐ |
| T5 "distinct 6 mer fraction" | L2-11 | ☐ |
| T6 name max-effect measures | L2-04 | ☐ |
| T7 figure terminology | L1-05 + L2-11 | ☐ |

**Pass:** every row ticked. **Fail:** an unticked row is an unanswered reviewer point.

---

## 2. Conflict ledger

Append one row per finding. Do not fix while detecting.

```
| ID | Type (C1–C12) | Severity | Evidence (file:line, evidence id) | Lane 1 says | Lane 2 says | Resolution rule applied | Fix | Owner | Verified by |
|----|----|----|----|----|----|----|----|----|----|
| CONF-01 |  |  |  |  |  |  |  |  |  |
```

Severity: **blocking** (a false or unsupported claim would ship), **major** (a reviewer point goes
unanswered or an inconsistency is visible), **minor** (wording, terminology, formatting).

## 3. Resolution precedence

Apply in this order. A higher rule wins outright; do not split the difference.

1. **The declared scope outranks a reviewer request.** Threat model, claim boundary, and the
   single-construction rule are not negotiable by review pressure. A scope crossing is reverted even
   if it would answer PAT better, unless an author sign-off is recorded in the lane document.
2. **Measured evidence outranks drafted prose.** If a run contradicts a sentence, the sentence
   changes.
3. **The ledger outranks the manuscript.** If the manuscript and `evidence/measurements.yaml`
   disagree, the manuscript is wrong until a new measurement says otherwise.
4. **A failed, missing or inconclusive run forces the hedged branch.** Never the confident one, and
   never a partially confident blend. `not_run` means the submitted claim stands unchanged plus its
   limitation.
5. **When two sections disagree, the weaker claim wins** — unless the ledger positively supports the
   stronger, in which case the weaker sections are raised to match.
6. **Anything unresolved is disclosed, not smoothed.** The paper's existing habit of disclosing the
   Carbon provenance gap is the standard to hold to.

## 4. Correction sequence

Order matters; each step feeds the next.

1. **Ledger.** Add and correct `evidence/measurements.yaml`; update
   `paper/context/evidence_map.md`; run `scripts/check_evidence.py` until clean.
2. **Figures.** Regenerate from the corrected ledger: `python3 scripts/make_paper_figures.py
   --model carbon` then `--model generator`. Never hand-edit.
3. **Results sections.** §4.1–§4.4 and Table 1 — the numbers land here first.
4. **Propagate outward.** Abstract, Introduction contribution list, Discussion, Conclusion, in that
   order, so the strongest summary statements are written last against settled numbers.
5. **Limitations last.** It is the section that must describe the paper as it finally is, including
   anything the reconciliation left unresolved.
6. **Rebuttal text last of all.** Rewrite the OpenReview response so it matches the revised paper.
   A rebuttal promising something the paper does not contain is worse than no rebuttal.
7. **Re-run the whole detection pass (C1–C12).** Fixes interact; one pass is not enough.

## 5. Final acceptance checklist

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/doctor.py
python3 scripts/check_evidence.py
uv run ruff check .
cd paper && ./scripts/build.sh
```

Plus, all of which must hold simultaneously:

- ☐ C1 clean: zero `\evtag{` remaining in `main.tex`
- ☐ C2 clean: zero unused new evidence IDs, and zero `refutes` outcomes unaddressed in the text
- ☐ C3 clean: every manuscript number resolves to the ledger with matching digits and units
- ☐ C4 clean: every surviving branch matches its recorded `outcome`
- ☐ C5 clean: Abstract, Intro, Results, Discussion, Conclusion and Limitations agree on all five
  headline claims
- ☐ C6 clean: every assumption held, or its dependent text was updated
- ☐ C7 clean: Limitations neither stale nor incomplete
- ☐ C8 clean: figure values, digests, terminology and numbering agree with text and ledger
- ☐ C9 clean: every added citation supports its sentence
- ☐ C10 clean: no scope crossing without a recorded sign-off
- ☐ C11 clean: ledger hygiene, no mutated v1 artifacts, evidence map updated
- ☐ C12 clean: all 24 PAT rows ticked
- ☐ conflict ledger fully resolved, every row with a named verifier
- ☐ no host names, local paths, allocation names, raw run IDs or keys anywhere in the manuscript
- ☐ a dated review note added under `paper/reviews/` recording what changed; review history not
  overwritten

## 6. "What changed since submission" — one page for the response

Write it last, from the conflict ledger and the delta packet, in this shape:

1. **New evidence** — what was run, on what cohort, at what scale, with the new IDs and the
   direction of each result.
2. **Claims that changed** — each with its before and after strength, and the evidence that forced
   the change. Include every `weakens` and `refutes`.
3. **Clarifications** — the reproducibility gaps PAT identified and now closed: the G statistic and
   its Monte Carlo reference, the 256-state correction, the two window-score summaries and their
   selection rule, the named max-effect measures, the short-window boundary condition, the
   complexity analysis.
4. **Declined, with reasons** — the edit-rate sweep, the competing-construction baseline, the
   downstream biological benchmarks, each with the scope clause that governs it and what was added
   to the paper in its place.
5. **Still open** — anything the reconciliation could not settle, stated plainly. This list should
   not be empty, and a reviewer will trust the rest of the document more because it is not.
