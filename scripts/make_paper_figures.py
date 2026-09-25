#!/usr/bin/env python3
"""Build the manuscript figures from admitted evidence artifacts.

Every plotted value is either a protocol constant, a ledger measurement, or a
summary derived from an artifact whose SHA-256 is recorded in
``evidence/measurements.yaml``.  The script refuses to run if a source artifact
does not match its recorded digest, and it writes every derived value it plots
to ``paper/figures/figure_values.json`` so that a reviewer can check a figure
without rerunning it.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyArrowPatch, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.paper_analysis import quality_summary  # noqa: E402

FIGURE_DIR = ROOT / "paper" / "figures"
GENERATOR_ANALYSIS = ROOT / "evidence/derived/generator_v1_paper_analysis_2026_09_11.json"

# Source artifacts and the digests recorded in the evidence ledger.
QUALITY_ARTIFACT = ROOT / "outputs/carbon_synthid_e16_v1/sequence_comparison_summary.json"
QUALITY_SHA256 = "6c9a73ea92592465b3a7c5121ab6a7e296839bc22a02edaa8050c36ebad7b0da"
TRIALS_ARTIFACT = ROOT / "outputs/carbon_synthid_position_independent_v1/trials.jsonl"
TRIALS_SHA256 = "323d998561843dda5b204c33d3de9d6a281aaa700ceddc535b0d7af32e0ac81c"

# ---------------------------------------------------------------------------
# Shared vocabulary.  The manuscript, the figures, and this script use one name
# per concept; nothing below invents a synonym.
# ---------------------------------------------------------------------------
FAMILIES = (
    ("watermarked_correct_key", "Marked, right key"),
    ("ordinary_corresponding_key", "Ordinary"),
    ("watermarked_wrong_key", "Marked, wrong key"),
)
CONDITIONS = (
    ("clean", "None"),
    ("substitution_1nt", "Substitution"),
    ("insertion_1nt", "Insertion"),
    ("deletion_1nt", "Deletion"),
)
WINDOW_LENGTHS = (384, 768, 1536, 3072)

READ_BASES = 3456
PROMPT_BASES = 384
TARGET_FALSE_POSITIVE_RATE = 0.01
EVALUATION_PROMPTS = 192

# Validated palette (dataviz skill reference instance, light surface #ffffff).
# Categorical slots 1-3 clear every all-pairs gate; the window ramp is the
# single-hue blue ordinal ramp.  Aqua sits below 3:1 contrast, so every series
# in every panel carries a direct label rather than colour alone.
SERIES_COLOUR = {
    "watermarked_correct_key": "#2a78d6",
    "ordinary_corresponding_key": "#eb6834",
    "watermarked_wrong_key": "#1baf7a",
}
WINDOW_COLOUR = {384: "#86b6ef", 768: "#3987e5", 1536: "#1c5cab", 3072: "#0d366b"}
INK = "#0b0b0b"
INK_SOFT = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SURFACE = "#ffffff"

SINGLE_COLUMN = 3.50  # inches, 89 mm
DOUBLE_COLUMN = 7.20  # inches, 183 mm

RC_PARAMS = {
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 7,
    "axes.labelsize": 7,
    "axes.titlesize": 7,
    "axes.labelcolor": INK,
    "axes.edgecolor": AXIS,
    "axes.linewidth": 0.5,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.labelsize": 6.5,
    "ytick.labelsize": 6.5,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.major.width": 0.5,
    "ytick.major.width": 0.5,
    "xtick.major.size": 2.5,
    "ytick.major.size": 2.5,
    "text.color": INK,
    "lines.linewidth": 0.9,
    "legend.fontsize": 6.5,
    "legend.frameon": False,
    "grid.color": GRID,
    "grid.linewidth": 0.5,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "savefig.dpi": 600,
    "figure.dpi": 150,
}

LN10 = math.log(10.0)


def strength(natural_log_p: float) -> float:
    """Return evidence strength, ``-log10(p)``, from a natural-log tail."""

    return -natural_log_p / LN10


def check_digest(path: Path, expected: str) -> None:
    if not path.is_file():
        raise SystemExit(
            f"missing evidence artifact {path.relative_to(ROOT)}. Generated experiment outputs are "
            "not tracked in the repository; restore the run directory before rebuilding figures."
        )
    observed = hashlib.sha256(path.read_bytes()).hexdigest()
    if observed != expected:
        raise SystemExit(
            f"artifact digest mismatch for {path.relative_to(ROOT)}: "
            f"expected {expected}, observed {observed}"
        )


def panel_letter(axes: Any, letter: str, x: float = -0.14, y: float = 1.06) -> None:
    axes.text(
        x,
        y,
        letter,
        transform=axes.transAxes,
        fontsize=8,
        fontweight="bold",
        va="bottom",
        ha="left",
        color=INK,
    )


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
METRIC_LABEL = {
    "gc_fraction": "GC content",
    "base_entropy_bits": "Base entropy",
    "dinucleotide_entropy_bits": "2-mer entropy",
    "trinucleotide_entropy_bits": "3-mer entropy",
    "distinct_hexamer_fraction": "Distinct 6-mers",
    "longest_homopolymer_run": "Longest single-base run",
    "mean_homopolymer_run": "Mean single-base run",
    "purine_fraction": "Purine content",
    "cpg_fraction": "CpG content",
    "js_divergence_from_prompt_k1_bits": "1-mer Jensen-Shannon drift from prompt",
    "js_divergence_from_prompt_k2_bits": "2-mer Jensen-Shannon drift from prompt",
    "js_divergence_from_prompt_k3_bits": "3-mer Jensen-Shannon drift from prompt",
    "mean_negative_log_likelihood_per_token": "Model score",
    "perplexity": "Perplexity",
}


def load_quality() -> dict[str, Any]:
    check_digest(QUALITY_ARTIFACT, QUALITY_SHA256)
    summary = json.loads(QUALITY_ARTIFACT.read_text(encoding="utf-8"))
    quality = quality_summary(summary)
    for row in quality["rows"]:
        row["label"] = METRIC_LABEL[row["metric"]]
    return quality


def set_evaluation_prompts(count: int) -> None:
    """Point the grid check at a cohort of a different size."""

    global EVALUATION_PROMPTS
    if count <= 0:
        raise ValueError("evaluation prompts must be positive")
    EVALUATION_PROMPTS = count


def load_trials(
    artifact: Path | None = None, digest: str | None = None
) -> list[dict[str, Any]]:
    """Load a verified trial file. Accepts .jsonl or .jsonl.gz."""

    path = artifact or TRIALS_ARTIFACT
    check_digest(path, digest or TRIALS_SHA256)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def select(trials: list[dict[str, Any]], family: str, condition: str) -> list[dict[str, Any]]:
    return [
        trial for trial in trials if trial["family"] == family and trial["condition"] == condition
    ]


def prompt_rates(trials: list[dict[str, Any]]) -> dict[str, Any]:
    """Use both draws for recall, either draw for controls, separately by edit."""
    from scipy.stats import beta

    rates: dict[str, Any] = {}
    for condition, _ in CONDITIONS:
        rates[condition] = {}
        for family, _ in FAMILIES:
            clusters: dict[str, dict[int, bool]] = defaultdict(dict)
            for row in select(trials, family, condition):
                if row["draw_id"] in clusters[row["case_id"]]:
                    raise ValueError("duplicate draw in figure data")
                clusters[row["case_id"]][row["draw_id"]] = row["detected"]
            if len(clusters) != EVALUATION_PROMPTS or any(
                set(draws) != {0, 1} for draws in clusters.values()
            ):
                raise ValueError("incomplete prompt/draw grid in figure data")
            positives = sum(
                all(draws.values()) if family == "watermarked_correct_key" else any(draws.values())
                for draws in clusters.values()
            )
            count = len(clusters)
            lower = (
                0.0 if positives == 0 else float(beta.ppf(0.025, positives, count - positives + 1))
            )
            upper = (
                1.0
                if positives == count
                else float(beta.ppf(0.975, positives + 1, count - positives))
            )
            rates[condition][family] = {
                "positive_prompts": positives,
                "prompts": count,
                "percent": 100.0 * positives / count,
                "exact_95_percent_interval": [100 * lower, 100 * upper],
            }
    return rates


# ---------------------------------------------------------------------------
# Figure 1: how the mark is written and how it is read
# ---------------------------------------------------------------------------
ILLUSTRATIVE_P = np.array([0.26, 0.19, 0.15, 0.12, 0.10, 0.08, 0.06, 0.04])
ILLUSTRATIVE_G = np.array([1, 0, 1, 1, 0, 0, 1, 0])


def figure_method(path_stem: str) -> dict[str, Any]:
    weighted_g = float(ILLUSTRATIVE_P @ ILLUSTRATIVE_G)
    keyed = ILLUSTRATIVE_P * (1.0 + ILLUSTRATIVE_G - weighted_g)

    figure = plt.figure(figsize=(DOUBLE_COLUMN, 2.55))
    grid = figure.add_gridspec(
        2,
        2,
        width_ratios=[1.0, 1.30],
        height_ratios=[3.2, 1.0],
        wspace=0.34,
        hspace=0.16,
        left=0.075,
        right=0.985,
        top=0.86,
        bottom=0.13,
    )
    top = figure.add_subplot(grid[0, 0])
    bits = figure.add_subplot(grid[1, 0], sharex=top)
    read = figure.add_subplot(grid[:, 1])

    positions = np.arange(len(ILLUSTRATIVE_P))
    width = 0.38
    top.bar(
        positions - width / 2,
        ILLUSTRATIVE_P,
        width=width,
        color="#c9c8c1",
        edgecolor=SURFACE,
        linewidth=0.4,
        label="model",
    )
    top.bar(
        positions + width / 2,
        keyed,
        width=width,
        color=SERIES_COLOUR["watermarked_correct_key"],
        edgecolor=SURFACE,
        linewidth=0.4,
        label="after one keyed layer",
    )
    top.set_ylabel("Probability")
    top.set_ylim(0, 0.45)
    top.set_yticks([0, 0.1, 0.2, 0.3, 0.4])
    top.legend(
        loc="upper right",
        handlelength=1.0,
        handletextpad=0.5,
        borderpad=0.0,
        labelspacing=0.35,
        labelcolor=INK_SOFT,
    )
    top.set_title(
        "A layer lifts the candidates whose mark bit is 1",
        fontsize=6.5,
        color=INK_SOFT,
        pad=4,
    )
    top.tick_params(labelbottom=False)

    for position, bit in zip(positions, ILLUSTRATIVE_G, strict=True):
        filled = bit == 1
        bits.add_patch(
            Rectangle(
                (position - 0.18, 0.28),
                0.36,
                0.44,
                facecolor=SERIES_COLOUR["watermarked_correct_key"] if filled else SURFACE,
                edgecolor=SERIES_COLOUR["watermarked_correct_key"],
                linewidth=0.6,
            )
        )
        bits.text(
            position,
            -0.28,
            str(int(bit)),
            ha="center",
            va="center",
            fontsize=6,
            color=INK_SOFT,
        )
    bits.set_xlim(-0.75, len(ILLUSTRATIVE_P) - 0.25)
    bits.set_ylim(-0.7, 1.05)
    bits.set_ylabel("Mark bit", labelpad=8)
    bits.set_yticks([])
    bits.set_xticks([])
    for spine in bits.spines.values():
        spine.set_visible(False)
    bits.set_xlabel("Candidate tokens (8 of 4,096)", labelpad=2)

    # Panel b: what the verifier sees.
    read.set_xlim(-150, 5250)
    read.set_ylim(-0.20, 6.30)
    read.axis("off")

    read.add_patch(
        Rectangle(
            (0, 5.30),
            PROMPT_BASES,
            0.55,
            facecolor="#e8e7e0",
            edgecolor=AXIS,
            linewidth=0.5,
        )
    )
    read.add_patch(
        Rectangle(
            (PROMPT_BASES, 5.30),
            READ_BASES - PROMPT_BASES,
            0.55,
            facecolor="#c9c8c1",
            edgecolor=AXIS,
            linewidth=0.5,
        )
    )
    read.text(
        PROMPT_BASES / 2,
        5.96,
        "prompt",
        ha="center",
        va="bottom",
        fontsize=6.5,
        color=INK_SOFT,
    )
    read.text(
        (READ_BASES + PROMPT_BASES) / 2,
        5.96,
        "continuation",
        ha="center",
        va="bottom",
        fontsize=6.5,
        color=INK_SOFT,
    )
    read.text(
        READ_BASES,
        5.16,
        f"{READ_BASES:,}-base read",
        ha="right",
        va="top",
        fontsize=6.2,
        color=MUTED,
    )
    read.plot(
        [PROMPT_BASES, PROMPT_BASES],
        [4.25, 5.90],
        linestyle=(0, (2, 1.6)),
        linewidth=0.7,
        color=SERIES_COLOUR["ordinary_corresponding_key"],
    )
    read.text(
        PROMPT_BASES + 110,
        4.20,
        "the verifier is not told where this line is, which strand\n"
        "it reads, or how the bases group into tokens",
        fontsize=6.2,
        color=SERIES_COLOUR["ordinary_corresponding_key"],
        va="top",
        ha="left",
    )

    offsets = {3072: 260, 1536: 980, 768: 1740, 384: 2380}
    rows = {3072: 2.85, 1536: 2.10, 768: 1.35, 384: 0.60}
    for length in sorted(WINDOW_LENGTHS, reverse=True):
        row = rows[length]
        start = offsets[length]
        read.add_patch(
            Rectangle(
                (start, row),
                length,
                0.34,
                facecolor=WINDOW_COLOUR[length],
                edgecolor="none",
            )
        )
        read.add_patch(
            FancyArrowPatch(
                (start - 190, row + 0.17),
                (start + length + 190, row + 0.17),
                arrowstyle="<|-|>",
                mutation_scale=4.0,
                linewidth=0.5,
                color=MUTED,
                shrinkA=0,
                shrinkB=0,
            )
        )
        read.text(
            READ_BASES + 300,
            row + 0.17,
            f"{length:,} bases\n{READ_BASES - length + 1:,} starts",
            fontsize=6.0,
            color=INK_SOFT,
            va="center",
            ha="left",
            linespacing=1.25,
        )
    read.text(
        -150,
        -0.02,
        "every start, both strands  →  "
        f"{2 * sum(READ_BASES - length + 1 for length in WINDOW_LENGTHS):,} windows  →  one answer",
        fontsize=6.4,
        color=INK,
        va="center",
        ha="left",
    )

    panel_letter(top, "a", x=-0.155, y=1.10)
    panel_letter(read, "b", x=-0.045, y=0.985)

    return save_figure(
        figure,
        path_stem,
        {
            "illustrative_model_probability": ILLUSTRATIVE_P.tolist(),
            "illustrative_mark_bits": ILLUSTRATIVE_G.tolist(),
            "illustrative_probability_after_one_layer": [round(v, 6) for v in keyed],
            "windows_searched": 2 * sum(READ_BASES - length + 1 for length in WINDOW_LENGTHS),
        },
    )


def save_figure(figure: Any, stem: str, values: dict[str, Any]) -> dict[str, Any]:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    pdf = FIGURE_DIR / f"{stem}.pdf"
    png = FIGURE_DIR / f"{stem}.png"
    figure.savefig(pdf)
    figure.savefig(png, dpi=400)
    plt.close(figure)
    return {
        "pdf": str(pdf.relative_to(ROOT)),
        "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "png": str(png.relative_to(ROOT)),
        "png_sha256": hashlib.sha256(png.read_bytes()).hexdigest(),
        "values": values,
    }


# ---------------------------------------------------------------------------
# Figure 2: sequence quality
# ---------------------------------------------------------------------------
def figure_quality(
    path_stem: str,
    quality: dict[str, Any],
    letters: tuple[str, str] = ("a", "b"),
) -> dict[str, Any]:
    figure = plt.figure(figsize=(DOUBLE_COLUMN, 2.45))
    grid = figure.add_gridspec(
        1,
        2,
        width_ratios=[1.0, 1.0],
        wspace=0.85,
        left=0.075,
        right=0.985,
        top=0.86,
        bottom=0.20,
    )
    score = figure.add_subplot(grid[0, 0])
    forest = figure.add_subplot(grid[0, 1])

    blue = SERIES_COLOUR["watermarked_correct_key"]
    lower, upper = quality["interval"]
    score.axvline(0.0, color=AXIS, linewidth=0.6, zorder=1)
    score.plot([lower, upper], [0, 0], color=blue, linewidth=1.4, solid_capstyle="round", zorder=2)
    score.plot([quality["difference"]], [0], marker="o", markersize=4.2, color=blue, zorder=3)
    score.set_ylim(-1.0, 1.35)
    score.set_yticks([])
    score.spines["left"].set_visible(False)
    score.set_xlim(-0.075, 0.075)
    score.set_xticks([-0.06, -0.03, 0.0, 0.03, 0.06])
    score.set_xlabel("Marked − ordinary model score (nats per 6-mer)")
    score.text(
        quality["difference"],
        0.20,
        f"{quality['difference']:+.5f}",
        ha="center",
        va="bottom",
        fontsize=6.5,
        color=INK,
    )
    score.text(
        quality["difference"],
        -0.30,
        f"95% interval {lower:+.5f} to {upper:+.5f}".replace("-", "\u2212"),
        ha="center",
        va="top",
        fontsize=6.0,
        color=MUTED,
    )
    score.text(
        0.0,
        1.30,
        "no difference",
        ha="center",
        va="top",
        fontsize=6.2,
        color=MUTED,
    )
    score.set_title(
        f"{quality['pairs']} matched pairs from {quality['prompts']} prompts  ·  "
        f"$P$ = {quality['p_value']:.2f}",
        fontsize=6.5,
        color=INK_SOFT,
        pad=5,
    )

    rows = quality["rows"]
    order = list(range(len(rows)))[::-1]
    forest.axvline(0.0, color=AXIS, linewidth=0.6, zorder=1)
    for y, row in zip(order, rows, strict=True):
        forest.plot(
            [row["interval_lower"], row["interval_upper"]],
            [y, y],
            color=blue,
            linewidth=1.0,
            solid_capstyle="round",
            zorder=2,
        )
        forest.plot(
            [row["standardized_effect"]],
            [y],
            marker="o",
            markersize=2.9,
            color=blue,
            zorder=3,
        )
    forest.set_yticks(order)
    forest.set_yticklabels([row["label"] for row in rows], fontsize=6.2)
    forest.tick_params(axis="y", length=0)
    forest.set_ylim(-0.8, len(rows) - 0.2)
    forest.set_xlim(-0.30, 0.30)
    forest.set_xticks([-0.2, -0.1, 0.0, 0.1, 0.2])
    forest.set_xlabel("Marked − ordinary, in standard deviations")
    forest.spines["left"].set_visible(False)
    forest.set_title(
        "All 14 measures: every interval crosses zero",
        fontsize=6.5,
        color=INK_SOFT,
        pad=5,
    )

    panel_letter(score, letters[0], x=-0.135, y=1.10)
    panel_letter(forest, letters[1], x=-0.335, y=1.10)

    return save_figure(
        figure,
        path_stem,
        {
            "model_score_difference": quality["difference"],
            "model_score_interval": quality["interval"],
            "model_score_p_value": quality["p_value"],
            "ordinary_mean_model_score": quality["ordinary_mean"],
            "watermarked_mean_model_score": quality["watermarked_mean"],
            "standardized_effects": [
                {
                    "metric": row["metric"],
                    "label": row["label"],
                    "standardized_effect": row["standardized_effect"],
                    "interval": [row["interval_lower"], row["interval_upper"]],
                    "benjamini_hochberg_p_value": row["benjamini_hochberg_p_value"],
                }
                for row in rows
            ],
        },
    )


# ---------------------------------------------------------------------------
# Figure 3: detection without a known boundary
# ---------------------------------------------------------------------------
def figure_detection(
    path_stem: str,
    trials: list[dict[str, Any]],
    letters: tuple[str, str] = ("a", "b"),
) -> dict[str, Any]:
    windows = select(trials, "watermarked_correct_key", "clean")[0]["hypotheses_searched"]
    threshold = math.log10(windows / TARGET_FALSE_POSITIVE_RATE)

    figure = plt.figure(figsize=(DOUBLE_COLUMN, 2.40))
    outer = figure.add_gridspec(
        1,
        2,
        width_ratios=[1.10, 1.0],
        wspace=0.30,
        left=0.075,
        right=0.985,
        top=0.83,
        bottom=0.20,
    )
    strip = figure.add_subplot(outer[0, 0])
    inner = outer[0, 1].subgridspec(2, 1, height_ratios=[1.0, 1.15], hspace=0.14)
    high = figure.add_subplot(inner[0, 0])
    low = figure.add_subplot(inner[1, 0], sharex=high)

    rng = np.random.default_rng(20260903)
    summary: dict[str, Any] = {"windows_searched": windows, "threshold_strength": threshold}
    for index, (family, label) in enumerate(FAMILIES):
        y = len(FAMILIES) - 1 - index
        chosen = select(trials, family, "clean")
        values = np.array([strength(trial["minimum_local_log_p_value"]) for trial in chosen])
        strip.scatter(
            values,
            y + rng.uniform(-0.19, 0.19, size=values.size),
            s=2.2,
            color=SERIES_COLOUR[family],
            alpha=0.55,
            linewidths=0,
            zorder=3,
        )
        strip.text(
            1.56,
            y + 0.30,
            label,
            fontsize=6.4,
            color=SERIES_COLOUR[family],
            va="bottom",
            ha="left",
        )
        summary[family] = {
            "clean_strength_values": values.tolist(),
            "clean_strength_min": float(values.min()),
            "clean_strength_median": float(np.median(values)),
            "clean_strength_max": float(values.max()),
        }

    strip.axvline(threshold, color=INK, linewidth=0.7, linestyle=(0, (2.5, 1.6)), zorder=4)
    strip.text(
        threshold * 1.16,
        -0.42,
        "threshold",
        fontsize=6.2,
        color=INK,
        va="center",
        ha="left",
    )
    strip.set_xscale("log")
    strip.set_xlim(1.5, 2200)
    strip.set_xticks([2, 10, 100, 1000])
    strip.set_xticklabels(["2", "10", "100", "1,000"])
    strip.set_ylim(-0.70, 2.85)
    strip.set_yticks([])
    strip.spines["left"].set_visible(False)
    strip.set_xlabel("Window strength,  $-\\log_{10}P_{\\mathrm{win}}$")
    strip.set_title(
        # Derived from the data, not a constant: the same code renders cohorts of
        # different sizes and a hardcoded count would silently misreport them.
        f"{sum(len(select(trials, family, 'clean')) for family, _ in FAMILIES):,}"
        " unedited reads, one point each",
        fontsize=6.5,
        color=INK_SOFT,
        pad=5,
    )

    positions = np.arange(len(CONDITIONS))
    offsets = {
        "watermarked_correct_key": -0.22,
        "ordinary_corresponding_key": 0.0,
        "watermarked_wrong_key": 0.22,
    }
    rates = prompt_rates(trials)
    for family, _ in FAMILIES:
        records = [rates[condition][family] for condition, _ in CONDITIONS]
        rate = np.array([record["percent"] for record in records])
        lower = np.array([record["exact_95_percent_interval"][0] for record in records])
        upper = np.array([record["exact_95_percent_interval"][1] for record in records])
        axes = high if family == "watermarked_correct_key" else low
        x = positions + offsets[family]
        axes.errorbar(
            x,
            rate,
            yerr=[rate - lower, upper - rate],
            fmt="o",
            markersize=3.0,
            color=SERIES_COLOUR[family],
            elinewidth=0.9,
            capsize=1.6,
            capthick=0.7,
            zorder=3,
        )

    high.set_ylim(96.6, 101.6)
    high.set_yticks([98, 100])
    high.tick_params(labelbottom=False)
    high.spines["bottom"].set_visible(False)
    high.set_title(
        "Prompts with the mark found (%)",
        fontsize=6.5,
        color=INK_SOFT,
        pad=13,
    )
    high.text(
        0.02,
        0.94,
        "Marked, right key",
        transform=high.transAxes,
        fontsize=6.4,
        color=SERIES_COLOUR["watermarked_correct_key"],
        va="top",
        ha="left",
    )
    low.set_ylim(-0.45, 4.2)
    low.set_yticks([0, 2, 4])
    low.axhline(
        100.0 * TARGET_FALSE_POSITIVE_RATE,
        color=INK,
        linewidth=0.7,
        linestyle=(0, (2.5, 1.6)),
        zorder=1,
    )
    low.text(
        0.985,
        0.36,
        "1% target",
        transform=low.transAxes,
        fontsize=6.2,
        color=INK,
        va="bottom",
        ha="right",
    )
    low.text(
        0.02,
        0.97,
        "Ordinary",
        transform=low.transAxes,
        fontsize=6.4,
        color=SERIES_COLOUR["ordinary_corresponding_key"],
        va="top",
        ha="left",
    )
    low.text(
        0.24,
        0.97,
        "Marked, wrong key",
        transform=low.transAxes,
        fontsize=6.4,
        color=SERIES_COLOUR["watermarked_wrong_key"],
        va="top",
        ha="left",
    )
    low.set_xlim(-0.55, positions[-1] + 0.55)
    low.set_xticks(positions)
    low.set_xticklabels([label for _, label in CONDITIONS], fontsize=6.0)
    low.set_xlabel("Edit applied to the read")
    low.spines["top"].set_visible(False)

    for axes, y_position in ((high, 0.0), (low, 1.0)):
        axes.plot(
            [-0.014, 0.014],
            [y_position - 0.014, y_position + 0.014],
            transform=axes.transAxes,
            color=AXIS,
            linewidth=0.7,
            clip_on=False,
        )
    panel_letter(strip, letters[0], x=-0.055, y=1.10)
    panel_letter(high, letters[1], x=-0.175, y=1.10)

    return save_figure(figure, path_stem, {"clean_strength": summary, "prompt_level_rates": rates})


# ---------------------------------------------------------------------------
# Figure 4: what one edited base does
# ---------------------------------------------------------------------------
def figure_edits(
    path_stem: str,
    trials: list[dict[str, Any]],
    letters: tuple[str, str] = ("a", "b"),
) -> dict[str, Any]:
    windows = select(trials, "watermarked_correct_key", "clean")[0]["hypotheses_searched"]
    threshold = math.log10(windows / TARGET_FALSE_POSITIVE_RATE)

    figure = plt.figure(figsize=(DOUBLE_COLUMN, 2.45))
    grid = figure.add_gridspec(
        1,
        2,
        width_ratios=[1.0, 1.05],
        wspace=0.28,
        left=0.075,
        right=0.985,
        top=0.86,
        bottom=0.19,
    )
    spread = figure.add_subplot(grid[0, 0])
    mix = figure.add_subplot(grid[0, 1])

    blue = SERIES_COLOUR["watermarked_correct_key"]
    rng = np.random.default_rng(20260903)
    positions = np.arange(len(CONDITIONS))
    per_condition: dict[str, Any] = {}
    for position, (condition, label) in zip(positions, CONDITIONS, strict=True):
        chosen = select(trials, "watermarked_correct_key", condition)
        values = np.array([strength(trial["minimum_local_log_p_value"]) for trial in chosen])
        spread.scatter(
            position + rng.uniform(-0.19, 0.19, size=values.size),
            values,
            s=2.2,
            color=blue,
            alpha=0.40,
            linewidths=0,
            zorder=2,
        )
        median = float(np.median(values))
        spread.plot(
            [position - 0.27, position + 0.27],
            [median, median],
            color=INK,
            linewidth=1.0,
            zorder=3,
        )
        per_condition[condition] = {
            "label": label,
            "strength_values": values.tolist(),
            "strength_min": float(values.min()),
            "strength_median": median,
            "strength_max": float(values.max()),
            "threshold_strength": math.log10(
                chosen[0]["hypotheses_searched"] / TARGET_FALSE_POSITIVE_RATE
            ),
        }

    spread.axhline(threshold, color=INK, linewidth=0.7, linestyle=(0, (2.5, 1.6)), zorder=4)
    spread.text(
        len(CONDITIONS) - 0.52,
        threshold * 1.16,
        "threshold",
        fontsize=6.2,
        color=INK,
        va="bottom",
        ha="right",
    )
    spread.set_yscale("log")
    spread.set_ylim(3.5, 1600)
    spread.set_yticks([10, 100, 1000])
    spread.set_yticklabels(["10", "100", "1,000"])
    spread.set_xlim(-0.55, positions[-1] + 0.55)
    spread.set_xticks(positions)
    spread.set_xticklabels([label for _, label in CONDITIONS], fontsize=6.2)
    spread.set_ylabel("Window strength,  $-\\log_{10}P_{\\mathrm{win}}$")
    spread.set_xlabel("Edit applied to the read")
    spread.set_title(
        f"{len(select(trials, 'watermarked_correct_key', 'clean')):,}"
        " marked reads per condition; bar is the median",
        fontsize=6.5,
        color=INK_SOFT,
        pad=5,
    )

    counts: dict[str, dict[int, int]] = {}
    for condition, _ in CONDITIONS:
        tally = dict.fromkeys(WINDOW_LENGTHS, 0)
        for trial in select(trials, "watermarked_correct_key", condition):
            tally[trial["best_hypothesis"]["window_base_length"]] += 1
        counts[condition] = tally

    rows = np.arange(len(CONDITIONS))[::-1]
    for row, (condition, _) in zip(rows, CONDITIONS, strict=True):
        left = 0.0
        total = sum(counts[condition].values())
        for length in WINDOW_LENGTHS:
            share = 100.0 * counts[condition][length] / total
            if share <= 0:
                continue
            mix.barh(
                row,
                share,
                left=left,
                height=0.52,
                color=WINDOW_COLOUR[length],
                edgecolor=SURFACE,
                linewidth=0.6,
            )
            if share >= 12:
                mix.text(
                    left + share / 2,
                    row,
                    f"{counts[condition][length]:,}",
                    ha="center",
                    va="center",
                    fontsize=6.0,
                    color=SURFACE if length >= 1536 else INK,
                )
            left += share

    # Only advertise lengths that actually occur: a legend key with no bar segment
    # invites a reader to hunt for data that is not there.
    present = [
        length
        for length in WINDOW_LENGTHS
        if any(counts[condition][length] for condition, _ in CONDITIONS)
    ]
    for length in present:
        mix.plot([], [], color=WINDOW_COLOUR[length], linewidth=4, label=f"{length:,} bases")
    mix.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        ncol=max(1, len(present)),
        handlelength=1.1,
        handletextpad=0.5,
        columnspacing=1.4,
        borderpad=0.0,
        labelcolor=INK_SOFT,
    )
    mix.set_yticks(rows)
    mix.set_yticklabels([label for _, label in CONDITIONS], fontsize=6.2)
    mix.tick_params(axis="y", length=0)
    mix.set_xlim(0, 100)
    mix.set_xticks([0, 25, 50, 75, 100])
    mix.set_xlabel("Reads whose best window had this length (%)")
    mix.set_ylim(-0.6, len(CONDITIONS) - 0.4)
    mix.spines["left"].set_visible(False)

    panel_letter(spread, letters[0], x=-0.115, y=1.10)
    panel_letter(mix, letters[1], x=-0.245, y=1.10)

    return save_figure(
        figure,
        path_stem,
        {
            "threshold_strength": threshold,
            "correct_key_strength": per_condition,
            "best_window_length_counts": {
                condition: {str(length): count for length, count in tally.items()}
                for condition, tally in counts.items()
            },
        },
    )


def add_generator_figures(manifest_path: Path) -> dict[str, Any]:
    """Add matched panels without needing or replacing missing Carbon source data."""
    import yaml
    from derive_generator_paper_analysis import derive

    ledger = yaml.safe_load((ROOT / "evidence/measurements.yaml").read_text())
    entry = next(
        row
        for row in ledger["measurements"]
        if row["id"] == "synthid.generator.quality.metric_family_effects"
    )
    if entry["status"] != "A" or ROOT / entry["source"]["artifact"] != GENERATOR_ANALYSIS:
        raise ValueError("unexpected GENERator panel evidence identity")
    check_digest(GENERATOR_ANALYSIS, entry["source"]["sha256"])
    analysis = json.loads(GENERATOR_ANALYSIS.read_text())
    if analysis["data"] != derive():
        raise ValueError("derived panel data do not match the verified original artifacts")
    manifest = json.loads(manifest_path.read_text())
    # Reuse only unchanged, previously published Carbon graphics. This verifies
    # the graphics, not the absent underlying Carbon trials: that gap remains open.
    for record in manifest["figures"].values():
        for extension in ("pdf", "png"):
            check_digest(ROOT / record[extension], record[f"{extension}_sha256"])
    quality = analysis["data"]["quality"]
    for row in quality["rows"]:
        row["label"] = METRIC_LABEL[row["metric"]]
    trials_record = analysis["sources"]["trials"]
    check_digest(ROOT / trials_record["path"], trials_record["sha256"])
    trials = [json.loads(line) for line in (ROOT / trials_record["path"]).read_text().splitlines()]
    # Rates are independently reconstructed from paired trials for the plot.
    rates = prompt_rates(trials)
    for condition, families in rates.items():
        for family, fields in families.items():
            derived = analysis["data"]["detection"][condition][family]
            for field, value in fields.items():
                expected = derived[field]
                if isinstance(value, list):
                    if not np.allclose(value, expected, atol=1e-10, rtol=0):
                        raise ValueError("plot interval differs from the derived result")
                elif value != expected:
                    raise ValueError("plot rate differs from the derived result")
    manifest["sources"]["generator_analysis_artifact"] = str(GENERATOR_ANALYSIS.relative_to(ROOT))
    manifest["sources"]["generator_analysis_sha256"] = entry["source"]["sha256"]
    manifest["generator_plot_provenance"] = {
        "command": ".venv/bin/python scripts/make_paper_figures.py --model generator",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "matplotlib": matplotlib.__version__,
        "numpy": np.__version__,
        "jitter_seed": 20260903,
        "panel_order": "Carbon a/b above GENERator c/d; same axes, units, and colours",
        "carbon_artifacts": "PDF/PNG digests verified; original Carbon sources unavailable",
    }
    manifest["figures"].update(
        {
            "fig2_quality_generator": figure_quality("fig2_quality_generator", quality, ("c", "d")),
            "fig3_detection_generator": figure_detection(
                "fig3_detection_generator", trials, ("c", "d")
            ),
            "fig4_edits_generator": figure_edits("fig4_edits_generator", trials, ("c", "d")),
        }
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        choices=("carbon", "generator"),
        default="carbon",
        help="rebuild Carbon from its sources, or add GENERator panels to the verified manifest",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=FIGURE_DIR / "figure_values.json",
        help="where to write the plotted values and figure digests",
    )
    parser.add_argument(
        "--trials",
        type=Path,
        help="trial file to plot instead of the pinned version-one artifact; .jsonl or .jsonl.gz",
    )
    parser.add_argument("--trials-sha256", help="expected digest of --trials")
    parser.add_argument(
        "--evaluation-prompts",
        type=int,
        default=EVALUATION_PROMPTS,
        help="prompt-cluster count the trial grid must contain",
    )
    parser.add_argument(
        "--stem-suffix",
        default="",
        help="appended to figure file stems, so a rebuild never overwrites another run's figures",
    )
    parser.add_argument(
        "--panels",
        choices=("ab", "cd"),
        default="ab",
        help="panel letters; GENERator panels are lettered c and d",
    )
    arguments = parser.parse_args()

    plt.rcParams.update(RC_PARAMS)

    if arguments.trials is not None:
        # Accept a relative path from the repository root as well as an absolute one.
        arguments.trials = (
            arguments.trials if arguments.trials.is_absolute() else (ROOT / arguments.trials)
        ).resolve()
        # Direct-trials mode. Renders only the detection and edit figures, because
        # quality and method panels come from artifacts this mode does not touch.
        # The version-one figures and their manifest are left exactly as they are.
        if not arguments.trials_sha256:
            raise SystemExit("--trials requires --trials-sha256")
        set_evaluation_prompts(arguments.evaluation_prompts)
        letters = ("a", "b") if arguments.panels == "ab" else ("c", "d")
        trials = load_trials(arguments.trials, arguments.trials_sha256)
        manifest = (
            json.loads(arguments.manifest.read_text()) if arguments.manifest.exists() else {}
        )
        manifest.setdefault("sources", {}).update(
            {
                "trials_artifact": str(arguments.trials.relative_to(ROOT)),
                "trials_sha256": arguments.trials_sha256,
                "evaluation_prompts": arguments.evaluation_prompts,
            }
        )
        suffix = arguments.stem_suffix
        manifest.setdefault("figures", {}).update(
            {
                f"fig3_detection{suffix}": figure_detection(
                    f"fig3_detection{suffix}", trials, letters
                ),
                f"fig4_edits{suffix}": figure_edits(f"fig4_edits{suffix}", trials, letters),
            }
        )
        arguments.manifest.parent.mkdir(parents=True, exist_ok=True)
        arguments.manifest.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        for name, record in manifest["figures"].items():
            print(f"{name}: {record['pdf']} {record['pdf_sha256'][:16]}")
        return 0

    if arguments.model == "generator":
        manifest = add_generator_figures(arguments.manifest)
    else:
        quality = load_quality()
        trials = load_trials()
        manifest = json.loads(arguments.manifest.read_text()) if arguments.manifest.exists() else {}
        manifest.setdefault("sources", {}).update(
            {
                "quality_artifact": str(QUALITY_ARTIFACT.relative_to(ROOT)),
                "quality_sha256": QUALITY_SHA256,
                "trials_artifact": str(TRIALS_ARTIFACT.relative_to(ROOT)),
                "trials_sha256": TRIALS_SHA256,
            }
        )
        manifest.setdefault("figures", {}).update(
            {
                "fig1_method": figure_method("fig1_method"),
                "fig2_quality": figure_quality("fig2_quality", quality),
                "fig3_detection": figure_detection("fig3_detection", trials),
                "fig4_edits": figure_edits("fig4_edits", trials),
            }
        )
    arguments.manifest.parent.mkdir(parents=True, exist_ok=True)
    arguments.manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for name, record in manifest["figures"].items():
        print(f"{name}: {record['pdf']}")
    print(f"values: {arguments.manifest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
