#!/usr/bin/env python3
"""Write the LaTeX tabular bodies for the local-cohort tables of the manuscript.

Every cell is read from the derived result file
``evidence/derived/synthid_v5/synthid_v5_derived_2026_11_13.json``, whose numbers are the
``synthid.v5.*`` ledger entries (``scripts/emit_synthid_v5_ledger.py --verify`` checks the ledger
against the same file). Nothing here is typed by hand except labels and rounding. The output files
are ``\\input`` by ``manuscript/source/main.tex`` and carry no captions.

Usage: python3 paper/scripts/make_v5_tables.py   (from anywhere; paths are repository-relative)
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DERIVED = ROOT / "evidence/derived/synthid_v5/synthid_v5_derived_2026_11_13.json"
OUT = ROOT / "paper/manuscript/source/tables"

MODELS = ("carbon", "generator")


def n(x: int) -> str:
    """Integer with the manuscript's thousands convention."""
    s = f"{int(x):,}"
    return s.replace(",", "{,}")


def pct(fraction: float, digits: int = 3) -> str:
    return f"{100 * fraction:.{digits}f}"


def strength(x: float) -> str:
    return f"{x:.1f}"


def ms(x: float) -> str:
    return f"{x:.2f}" if x < 10 else f"{x:.1f}"


def write(name: str, lines: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------------------------
# S1 layout
# --------------------------------------------------------------------------------------------

def layout_label(cell: str) -> str:
    series, _, rest = cell.partition("_")
    if series in {"A", "B"}:
        return f"{series}, {n(int(rest[1:]))}"
    if series == "C":
        parts = rest.split("_")
        length = n(int(parts[0][1:]))
        phase = parts[1][1:]
        strand = "fwd" if parts[2] == "fw" else "rev"
        return f"C, {length}, phase {phase}, {strand}"
    if series == "D":
        length, flank = rest.split("_")
        return f"D, {n(int(length[1:]))} + {n(int(flank[1:]))}"
    if series == "E":
        return f"E, start {n(int(rest[1:]))}"
    if series == "F":
        return f"F, crop {n(int(rest[1:]))}"
    raise ValueError(cell)


def layout_cells(d: dict, model: str, cell: str) -> list[str]:
    c = d["s1"][model]["cells"][cell]
    m, o = c["marked"], c["ordinary"]
    return [
        n(m["reads_detected"]),
        n(m["prompts_both_draws_detected"]),
        strength(m["median_strength"]),
        n(o["reads_positive"]),
        n(o["prompts_any_draw_positive"]) + f" ({pct(o['prompt_any_draw_exact_one_sided_95_upper_bound'], 2)})",
    ]


def layout_main(d: dict) -> None:
    groups = [
        ["A_l0384", "A_l0576", "A_l1152", "A_l3072"],
        ["B_l0384", "B_l0576", "B_l1152", "B_l3072"],
        ["D_l0768_f0000", "D_l0768_f4608", "D_l3072_f4608"],
        ["F_c0768", "F_c2304"],
    ]
    lines = [
        r"\begin{tabular}{@{}l rrrr@{\hspace{10pt}}rrrr@{}}",
        r"\toprule",
        r"& \multicolumn{4}{c}{\textbf{Carbon-500M}} & \multicolumn{4}{c}{\textbf{GENERator-v2 1.2B}} \\",
        r"\cmidrule(lr){2-5}\cmidrule(l){6-9}",
        r"Layout & Reads & Prompts & Strength & Ordinary & Reads & Prompts & Strength & Ordinary \\",
        r"\midrule",
    ]
    for gi, group in enumerate(groups):
        if gi:
            lines.append(r"\midrule")
        for cell in group:
            row = []
            for model in MODELS:
                r = layout_cells(d, model, cell)
                row += [r[0], r[1], r[2], r[3]]
            lines.append(f"{layout_label(cell)} & " + " & ".join(row) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("v5_layout_main", lines)


def layout_all(d: dict) -> None:
    cells = list(d["s1"]["carbon"]["cells"].keys())
    assert cells == list(d["s1"]["generator"]["cells"].keys())
    assert len(cells) == 54
    head = [
        r"\begin{tabular}{@{}l rrrrr@{\hspace{4pt}}rrrrr@{}}",
        r"\toprule",
        r"& \multicolumn{5}{c}{\textbf{Carbon-500M}} & \multicolumn{5}{c}{\textbf{GENERator-v2 1.2B}} \\",
        r"\cmidrule(lr){2-6}\cmidrule(l){7-11}",
        r"Layout & Reads & Prompts & Strength & Ord.\ reads & Ord.\ prompts (bound) "
        r"& Reads & Prompts & Strength & Ord.\ reads & Ord.\ prompts (bound) \\",
        r"\midrule",
    ]
    lines = list(head)
    prev = None
    for cell in cells:
        series = cell[0]
        if prev is not None and series != prev:
            lines.append(r"\midrule")
        prev = series
        row = layout_cells(d, "carbon", cell) + layout_cells(d, "generator", cell)
        lines.append(f"{layout_label(cell)} & " + " & ".join(row) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("v5_layout_all", lines)


# --------------------------------------------------------------------------------------------
# S2 detector comparison
# --------------------------------------------------------------------------------------------

S2_CELLS = [
    ("reference", "Standard layout"),
    ("reference_insertion", "Standard layout, one insertion"),
    ("B_l0768", "768-base region, embedded"),
    ("B_l1152", "1,152-base region, embedded"),
    ("B_l3072", "3,072-base region, embedded"),
]
S2_DETECTORS = [
    ("aligned_oracle", "Aligned oracle"),
    ("phase_only", "Phase only"),
    ("verifier", "Verifier"),
    ("fine_grid", "Fine grid"),
]


def detectors_main(d: dict) -> None:
    lines = [
        r"\begin{tabular}{@{}l r rrrr@{\hspace{10pt}}rrrr@{}}",
        r"\toprule",
        r"& & \multicolumn{4}{c}{\textbf{Carbon-500M}} & \multicolumn{4}{c}{\textbf{GENERator-v2 1.2B}} \\",
        r"\cmidrule(lr){3-6}\cmidrule(l){7-10}",
        r"Detector & Windows & Marked & Ordinary & Strength & ms & Marked & Ordinary & Strength & ms \\",
        r"\midrule",
    ]
    for ci, (cell, title) in enumerate(S2_CELLS):
        if ci:
            lines.append(r"\midrule")
        lines.append(r"\multicolumn{10}{@{}l}{\textit{" + title + r"}} \\")
        for det, dname in S2_DETECTORS:
            wins = set()
            row = []
            for model in MODELS:
                e = d["s2"][model]["cells"][cell][det]
                mk, od = e["marked"], e["ordinary"]
                assert mk["windows_searched_min"] == mk["windows_searched_max"]
                wins.add(mk["windows_searched_max"])
                row += [
                    n(mk["reads_detected"]),
                    n(od["reads_positive"]),
                    strength(mk["median_corrected_strength"]),
                    ms(mk["median_ms_per_read_single_process"]),
                ]
            assert len(wins) == 1, (cell, det, wins)
            lines.append(f"\\quad {dname} & {n(wins.pop())} & " + " & ".join(row) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("v5_detectors_main", lines)


def detectors_prompts(d: dict) -> None:
    lines = [
        r"\begin{tabular}{@{}l rr@{\hspace{12pt}}rr@{}}",
        r"\toprule",
        r"& \multicolumn{2}{c}{\textbf{Carbon-500M}} & \multicolumn{2}{c}{\textbf{GENERator-v2 1.2B}} \\",
        r"\cmidrule(lr){2-3}\cmidrule(l){4-5}",
        r"Detector & Marked prompts & Ordinary prompts (bound) & Marked prompts & Ordinary prompts (bound) \\",
        r"\midrule",
    ]
    for ci, (cell, title) in enumerate(S2_CELLS):
        if ci:
            lines.append(r"\midrule")
        lines.append(r"\multicolumn{5}{@{}l}{\textit{" + title + r"}} \\")
        for det, dname in S2_DETECTORS:
            row = []
            for model in MODELS:
                e = d["s2"][model]["cells"][cell][det]
                mk, od = e["marked"], e["ordinary"]
                row += [
                    n(mk["prompts_both_draws_detected"]),
                    n(od["prompts_any_draw_positive"]) + f" ({pct(od['prompt_exact_one_sided_95_upper_bound'], 2)})",
                ]
            lines.append(f"\\quad {dname} & " + " & ".join(row) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("v5_detectors_prompts", lines)


# --------------------------------------------------------------------------------------------
# S3 null calibration
# --------------------------------------------------------------------------------------------

S3_SOURCES = [
    ("Carbon-500M, ordinary output", ("ordinary_model_output", "carbon")),
    ("GENERator-v2 1.2B, ordinary output", ("ordinary_model_output", "generator")),
    ("Carbon-500M, marked output", ("marked_independent_key", "carbon")),
    ("GENERator-v2 1.2B, marked output", ("marked_independent_key", "generator")),
    ("Natural genomic spans", ("natural_dna", None)),
]


def s3_entry(d: dict, key: tuple) -> dict:
    family, model = key
    return d["s3"][family] if model is None else d["s3"][family][model]


def null_main(d: dict) -> None:
    lines = [
        r"\begin{tabular}{@{}l r r r r@{}}",
        r"\toprule",
        r"Source of reads & Positive / decisions & Rate (\%) & Per-key rate (\%) & Reads positive under $\geq 1$ key \\",
        r"\midrule",
    ]
    for label, key in S3_SOURCES:
        e = s3_entry(d, key)
        u = e["reads_positive_under_at_least_one_key"]
        lines.append(
            f"{label} & {n(e['positives'])}/{n(e['decisions'])} & {pct(e['rate'])} & "
            f"{'0' if e['per_key_rate_min'] == 0 else pct(e['per_key_rate_min'])}"
            f"--{pct(e['per_key_rate_max'])} & {n(u['count'])}/{n(u['reads'])} ({pct(u['fraction'], 2)}\\%) \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("v5_null_main", lines)


def null_calibration(d: dict) -> None:
    levels = [0.01, 0.05, 0.10, 0.25, 0.50]
    lines = [
        r"\begin{tabular}{@{}l rrrrr@{}}",
        r"\toprule",
        r"& \multicolumn{5}{c}{Nominal level (\%)} \\",
        r"\cmidrule(l){2-6}",
        r"Source of reads & 1 & 5 & 10 & 25 & 50 \\",
        r"\midrule",
    ]
    for label, key in S3_SOURCES:
        e = s3_entry(d, key)
        cal = {round(c["nominal_level"], 2): c for c in e["calibration"]}
        assert sorted(cal) == levels
        assert not any(c["exceeds_nominal"] for c in cal.values())
        cells = [f"{pct(cal[l]['fraction'])} ({n(cal[l]['count'])})" for l in levels]
        lines.append(f"{label} & " + " & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("v5_null_calibration", lines)


# --------------------------------------------------------------------------------------------
# S4 entropy
# --------------------------------------------------------------------------------------------

def entropy_main(d: dict) -> None:
    names = {"carbon": "Carbon-500M", "generator": "GENERator-v2 1.2B"}
    lines = [
        r"\begin{tabular}{@{}l c c@{}}",
        r"\toprule",
        r"Model & Strength & Mark bits equal to 1 \\",
        r"\midrule",
    ]
    for model in MODELS:
        m = d["s4"]["models"][model]
        cells = []
        for key in ("spearman_entropy_vs_s0_strength", "spearman_entropy_vs_mark_bit_fraction"):
            s = m[key]
            lo, hi = s["bootstrap_95_interval"]
            cells.append(f"{s['estimate']:.3f} [{lo:.3f}, {hi:.3f}]")
        lines.append(f"{names[model]} & " + " & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("v5_entropy_main", lines)


# --------------------------------------------------------------------------------------------
# S0 standard layout
# --------------------------------------------------------------------------------------------

S0_CONDITIONS = [
    ("clean", "None"),
    ("substitution_1nt", "One substitution"),
    ("insertion_1nt", "One insertion"),
    ("deletion_1nt", "One deletion"),
]


def s0_table(d: dict) -> None:
    lines = [
        r"\begin{tabular}{@{}l rrrr@{\hspace{10pt}}rrrr@{}}",
        r"\toprule",
        r"& \multicolumn{4}{c}{\textbf{Carbon-500M}} & \multicolumn{4}{c}{\textbf{GENERator-v2 1.2B}} \\",
        r"\cmidrule(lr){2-5}\cmidrule(l){6-9}",
        r"Edit applied to the sequence & Correct key & Strength & Ordinary & Wrong key "
        r"& Correct key & Strength & Ordinary & Wrong key \\",
        r"\midrule",
    ]
    for cond, label in S0_CONDITIONS:
        row = []
        for model in MODELS:
            rows = {r["family"]: r for r in d["s0"][model]["rows"] if r["condition"] == cond}
            ck = rows["watermarked_correct_key"]
            od = rows["ordinary_corresponding_key"]
            wk = rows["watermarked_wrong_key"]
            assert ck["prompt_both_draws"]["positives"] == ck["prompt_both_draws"]["trials"] == 512
            row += [
                f"{n(ck['reads_detected'])}/{n(ck['reads'])}",
                strength(ck["median_strength_neg_log10_smallest_window_p"]),
                f"{od['prompt_any_draw']['positives']} ({pct(od['prompt_any_draw']['exact_one_sided_95_upper_bound'])})",
                f"{wk['prompt_any_draw']['positives']} ({pct(wk['prompt_any_draw']['exact_one_sided_95_upper_bound'])})",
            ]
        lines.append(f"{label} & " + " & ".join(row) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("v5_s0", lines)


def main() -> None:
    d = json.loads(DERIVED.read_text(encoding="utf-8"))
    layout_main(d)
    layout_all(d)
    detectors_main(d)
    detectors_prompts(d)
    null_main(d)
    null_calibration(d)
    entropy_main(d)
    s0_table(d)
    print("wrote", ", ".join(sorted(p.name for p in OUT.glob("v5_*.tex"))))


if __name__ == "__main__":
    main()
