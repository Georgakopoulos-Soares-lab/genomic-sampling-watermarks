# Submission-readiness pass

Date: 2026-09-09
Scope: full read of `paper/manuscript/source/main.tex` after the day's three rewrites, plus
mechanical checks. Four defects found and fixed; the rest is a blocker list the authors must clear.

## Defects found and fixed

1. **Broken antecedent in Background.** The GENERator marginalisation sentences added in the citation
   pass were spliced in front of "That choice is what makes the watermarking problem different", so
   "that choice" pointed at marginalisation instead of six-base tokenisation. The marginalisation
   material now stands as its own paragraph, positioned as the reason both models are pinned to a
   released revision, and the antecedent is spelled out as "that choice of six-base tokenisation".
2. **A Carbon-only limitation stated as a global one.** The false-positive paragraph in Limitations
   still read "one ordinary prompt of 192 passed and no wrong-key prompt did", which is Carbon's
   pattern only; GENERator's is mirrored. It now gives both patterns and states that the 2.87% and
   1.90% bounds apply in either model and either control family.
3. **Two vocabulary words used but not declared.** The paper states that Table 1 fixes one name per
   idea and that the rest of the text uses only those. `recall` and `false-positive rate` entered
   during the structure pass without table rows. Both are now declared.
4. **Stale singular in Background.** "including the one used here" now reads "including both used
   here".

Source lines were also rewrapped to the repository's 100-column convention: 21 lines that the
scripted substitutions had left long.

## Mechanical checks, all passing

- **Every empirical number resolves to the ledger.** Carbon verified this pass: 13/256 and 12.8, arm
  scores 7.53386 and 7.54238, +0.00852 with interval -0.04426 to +0.05973, effect 0.0201, largest
  effect 0.084 (0.083737), smallest adjusted P 0.85, threshold 6.21 (6.207796), weakest marked read
  124.8 (124.777), strongest ordinary 6.60 (6.601607), strongest wrong-key 5.69 (5.694553), medians
  790.6, 774.7, 431.5, 443.7, weakest-in-any-condition 82.2 (82.161), full-window wins 383, and
  shorter-window wins 181 (0+1+180) and 152 (0+1+151) with 203 and 232 full-window wins. GENERator
  was verified the same way in the dual-model pass.
- **Floats**: all six labels referenced; no orphans.
- **Bibliography**: 31 entries, 31 cited, no dangling keys.
- **Build**: zero undefined citations, zero undefined references, zero overfull boxes, 16 pages.
- **No infrastructure leakage**: no host names, scratch paths, cluster names, run identifiers, or key
  material anywhere in the source.
- **Repository**: `ruff check` clean; 108 tests, zero failures, 8 documented skips.

## Blockers before submission

These are author decisions or missing runs, not text problems.

1. **No deposit for data, code, or keys.** *Data and code availability* says the two fixture keys are
   "published with this study" but names no repository, DOI, or archive, and everything else is
   "available from the authors on request". A provenance paper whose keys cannot be obtained cannot be
   reproduced, and several venues refuse on-request availability outright. This is the single largest
   gap.
2. **`scripts/check_evidence.py` cannot pass.** Five Carbon artifacts under
   `outputs/carbon_synthid_e16_v1/` and `outputs/carbon_synthid_position_independent_v1/` are absent
   from the working copy, so half the paper's numbers are currently unauditable from the repository
   while the GENERator half is fully present. Restore them before anyone reviews the evidence trail.
3. **Confirmatory M5 Pro replication, and the Carbon protocol-hash discrepancy.** Both are now
   disclosed in Limitations rather than hidden, which makes the paper honest but not finished:
   `paper/README.md` and the rebuild plan both say these gates must be closed before submission. That
   instruction now conflicts with submitting on version-one evidence, and the conflict is the
   authors' to resolve explicitly.
4. **Missing submission boilerplate.** No corresponding-author email, no author-contributions
   statement, no competing-interests statement, no funding statement, and no biosecurity or dual-use
   statement. The last one is likely to be required, or at least expected, for a paper about marking
   model-written DNA.
5. **No venue template.** The manuscript is 16 pages in `article` class. Section order, figure
   placement, abstract length, and reference style will all move once a venue is chosen.
6. **Figures cover Carbon only.** Disclosed in every caption and in Limitations. A reviewer may still
   ask for GENERator panels; Figures 3a, 4a, and 4b cannot be produced for GENERator because its
   window strengths and winning window lengths were never retained. Producing them needs a rerun, not
   a plotting change.
7. **The false-positive rate remains unresolved at 192 prompts**, in both models, with the interval
   reaching 2.87%. Tightening it needs more independent prompts.

## Addendum — 2026-09-10 — two-column layout

Blocker 5 above ("no venue template") is partly closed. The manuscript was single-column 11pt on
letter paper, which matched no other paper in this lab. The three sibling projects all use the same
house style, so the manuscript now adopts it:

| Project | Class |
|---|---|
| `beaconing` | `\documentclass[10pt,twocolumn]{article}` |
| `fhe-dna-gpt` | `\documentclass[10pt,twocolumn]{article}` |
| `prs` (arXiv upload) | `\documentclass[10pt,twocolumn]{article}` |

Applied: `10pt,twocolumn`; the shared geometry
`[a4paper, top=2.0cm, bottom=2.4cm, left=1.5cm, right=1.5cm, columnsep=0.65cm]`; `titlesec` section
formatting; `captionsetup{font=small, labelfont=bf}`; a `fancyhdr` page-number footer; and
`hyperref` with the lab's `blue!60!black` link colours plus PDF metadata. Front matter is a
`\twocolumn[...]` block so the title, authors, affiliations, and abstract span the full page width
and the body flows into two columns on page 1.

All six floats became `figure*`/`table*`. In two-column mode an unstarred float is column-width,
which would have rendered the four two-panel figures and the two wide tables unreadably narrow.
Float parameters were loosened (`dbltopfraction` 0.9, `dblfloatpagefraction` 0.7, `textfraction`
0.07, `dbltopnumber` 2) because full-width floats can only float forward to a page top; that pulled
Table 2 and Figures 3 and 4 one to two pages earlier, and no page is a float dump.

Three fixes the conversion forced:

1. The $P_{\mathrm{read}}$ equation overflowed a column, since it carried two statements joined by
   `\qquad`. It is now an `aligned` block over two lines. Same content.
2. `\titleformat` requested bold small caps, which Latin Modern does not provide in T1; LaTeX was
   silently substituting bold roman. The `\scshape` was dropped, so the requested shape now matches
   the rendered one. The sibling papers have this same latent warning.
3. `cmap`, `inputenc`, and the `\pdfgentounicode` block were copied from the house preamble and are
   inert under the XeTeX engine `tectonic` runs, each emitting a warning. Removed.

Result: 11 pages, down from 16, A4, zero undefined citations, zero undefined references, zero
overfull boxes. Pages 1, 2, 8, and 11 were rendered and inspected; figures are legible at full
width and the two-column bibliography wraps its URLs correctly.

Verified unchanged by the conversion: all 35 spot-checked empirical values still present, the seven
section headings, all six floats, and all 31 bibliography entries still cited.

Not adopted: the lab's `natbib`/`\citep` convention. This manuscript uses `\cite` with the `plain`
style, and switching would rewrite every citation call and the whole reference format. It is a
separate decision, best made with the venue.
