#!/usr/bin/env python3
"""Generate every manuscript figure from the evidence ledger.

Every plotted value is read from `evidence/measurements.yaml`. Nothing is read from
a result artifact, computed here, or hand-entered, so a figure cannot drift from the
admitted number. A missing measurement raises instead of falling back to a default:
a figure with a silently invented point is worse than no figure.

Alongside the figures the script writes a manifest naming, for each figure, the
measurement ids it drew from and the caption claim it supports. That is what makes
the figures auditable against the ledger rather than merely plausible.

Two figures carry an inverted sign and are drawn deliberately differently:
`spoofing` reports a detection rate of 1.000 that is a vulnerability, and `removal`
reports 0.000 that is a successful attack. Neither may share an axis with the
intended-detection rates.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import yaml  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "evidence/measurements.yaml"

POLICIES = (("c_tok", "C_tok"), ("g_tok", "G_tok"), ("g_bp", "G_bp"))
POLICY_COLOR = {"C_tok": "#1b6ca8", "G_tok": "#c1663d", "G_bp": "#2f7d5c"}
POLICY_MARKER = {"C_tok": "o", "G_tok": "s", "G_bp": "^"}
LENGTHS = (384, 768, 1536, 3072)
# The indel experiments stop at 1,536 bases, so the synchronization figure and its
# substitution overlay are both drawn at that length rather than mixing lengths.
INDEL_LENGTH = 1536
ATTACK_RED = "#a3182b"

plt.rcParams.update(
    {
        "figure.dpi": 150,
        "font.size": 9,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linewidth": 0.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "savefig.bbox": "tight",
    }
)


class Ledger:
    """Read-only ledger access that refuses to guess."""

    def __init__(self, path: Path) -> None:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        self._by_id = {m["id"]: m for m in parsed["measurements"]}
        self.used: set[str] = set()

    def get(self, measurement_id: str) -> dict[str, Any]:
        entry = self._by_id.get(measurement_id)
        if entry is None:
            raise KeyError(f"the ledger has no measurement {measurement_id}")
        self.used.add(measurement_id)
        return entry

    def find(self, prefix: str, suffix: str = "") -> list[dict[str, Any]]:
        found = [
            m for mid, m in self._by_id.items() if mid.startswith(prefix) and mid.endswith(suffix)
        ]
        if not found:
            raise KeyError(f"the ledger has no measurement matching {prefix}*{suffix}")
        for m in found:
            self.used.add(m["id"])
        return found

    def one(self, prefix: str, suffix: str = "") -> dict[str, Any]:
        found = self.find(prefix, suffix)
        if len(found) != 1:
            raise KeyError(f"{prefix}*{suffix} matched {len(found)} measurements, expected one")
        return found[0]


def log_length_axis(ax: plt.Axes, ticks: tuple[int, ...]) -> None:
    """Label a log length axis with exactly the evaluated lengths.

    Matplotlib keeps its own minor ticks on a log scale, and their labels collide
    with these into an unreadable smear, so the minor ticks are turned off.
    """

    ax.set_xscale("log")
    ax.set_xticks(list(ticks))
    ax.set_xticklabels([str(value) for value in ticks])
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())


def save(fig: plt.Figure, out: Path, name: str) -> str:
    path = out / f"{name}.pdf"
    fig.savefig(path)
    fig.savefig(out / f"{name}.png")
    plt.close(fig)
    return str(path.relative_to(ROOT))


# --------------------------------------------------------------------------- 1
def figure_capacity(led: Ledger, out: Path) -> dict[str, Any]:
    fig, ax = plt.subplots(figsize=(4.2, 2.9))
    labels, values, lowers, uppers, ids = [], [], [], [], []
    for slug, policy in POLICIES:
        m = led.get(f"e2.capacity.{slug}.mean_information_bits_per_base")
        u = m["uncertainty"]
        labels.append(policy)
        values.append(m["value"])
        lowers.append(m["value"] - u["lower"])
        uppers.append(u["upper"] - m["value"])
        ids.append(m["id"])
    positions = range(len(labels))
    ax.bar(
        positions,
        values,
        yerr=[lowers, uppers],
        capsize=4,
        color=[POLICY_COLOR[p] for p in labels],
        width=0.55,
    )
    ceiling = 1.0 / 6.0
    ax.axhline(ceiling, ls="--", lw=1.0, color="#444444")
    ax.annotate(
        "one bit per 6-mer token = 1/6 bit per base",
        xy=(len(labels) - 1, ceiling),
        xytext=(-4, 4),
        textcoords="offset points",
        ha="right",
        fontsize=7.5,
        color="#444444",
    )
    ax.set_xticks(list(positions))
    ax.set_xticklabels(labels)
    ax.set_ylabel("watermark information (bit / base)")
    ax.set_ylim(0, ceiling * 1.18)
    ax.set_title("Realized channel per released policy", fontsize=9.5)
    return {
        "figure": save(fig, out, "fig01_capacity"),
        "measurement_ids": ids,
        "caption_claim": (
            "Realized maximal-coupling watermark information per DNA base for the three released "
            "generation policies, with equal-weight prompt-cluster percentile intervals over 24 "
            "frozen public prompts. The dashed line is the construction's structural ceiling of "
            "one "
            "coupled bit per 6-mer token."
        ),
        "sign": "higher is more channel",
    }


# --------------------------------------------------------------------------- 2
def figure_clean_detection(led: Ledger, out: Path) -> dict[str, Any]:
    """Detection rate and the margin behind it.

    The detection-rate panel is flat at 1.000, which is the result but carries no
    length information. The margin panel is where the length dependence lives: it
    shows the smallest watermarked statistic pulling away from the largest null
    statistic, and the length at which they stop touching.
    """

    fig, (left, right) = plt.subplots(1, 2, figsize=(7.4, 3.0))
    ids = []
    for slug, policy in POLICIES:
        short = led.get(f"e4.short_detection.{slug}.shortest_fully_detected_bases")
        ids.append(short["id"])
        points = {
            p["base_length"]: {
                "detection_rate": p["detection_rate"],
                "lower": p["detection_rate_lower"],
                "upper": p["detection_rate_upper"],
                "minimum_positive": p["minimum_positive_statistic"],
                "maximum_null": p["maximum_pooled_null_statistic"],
            }
            for p in short["admitted_curve"]["points"]
        }
        for length in LENGTHS:
            entry = led.one(f"e4.clean_detection.{slug}.b{length}.detection_rate")
            ids.append(entry["id"])
            cal = entry["admitted_calibration"]
            points[length] = {
                "detection_rate": entry["value"],
                "lower": entry["uncertainty"]["lower"],
                "upper": entry["uncertainty"]["upper"],
                "minimum_positive": cal["minimum_positive_statistic"],
                "maximum_null": cal["maximum_pooled_null_statistic"],
            }
        xs = sorted(points)
        left.errorbar(
            xs,
            [points[x]["detection_rate"] for x in xs],
            yerr=[
                [points[x]["detection_rate"] - points[x]["lower"] for x in xs],
                [points[x]["upper"] - points[x]["detection_rate"] for x in xs],
            ],
            marker=POLICY_MARKER[policy],
            ms=4,
            lw=1.3,
            capsize=3,
            color=POLICY_COLOR[policy],
            label=policy,
        )
        right.plot(
            xs,
            [points[x]["minimum_positive"] for x in xs],
            marker=POLICY_MARKER[policy],
            ms=4,
            lw=1.3,
            color=POLICY_COLOR[policy],
            label=f"{policy}, weakest watermarked",
        )
        right.plot(
            xs,
            [points[x]["maximum_null"] for x in xs],
            ls=":",
            lw=1.2,
            color=POLICY_COLOR[policy],
            label=f"{policy}, strongest null",
        )
    for axis in (left, right):
        log_length_axis(axis, (96, 192, 384, 768, 1536, 3072))
        axis.set_xlabel("generated length (bases)")
        axis.axvline(96, ls=":", lw=0.9, color="#999999")
    left.set_ylabel("detection rate")
    left.set_ylim(0.45, 1.06)
    left.legend(loc="lower right", fontsize=8)
    left.set_title("Detection at a calibrated 1% FPR", fontsize=9)
    right.set_yscale("log")
    right.set_yticks([3, 4, 6, 10, 20])
    right.set_yticklabels(["3", "4", "6", "10", "20"])
    right.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    right.set_ylabel("detector statistic")
    right.legend(fontsize=6.2, loc="upper left", ncols=1)
    right.set_title("The margin behind that flat line", fontsize=9)
    fig.suptitle(
        "Clean detection is complete from the floor of the declared search",
        fontsize=9.5,
        y=1.03,
    )
    return {
        "figure": save(fig, out, "fig02_clean_detection"),
        "measurement_ids": sorted(set(ids)),
        "caption_claim": (
            "Left: correct-key detection rate on clean watermarked DNA against generated "
            "length, at a false-positive rate calibrated by repeating the identical declared "
            "search on null "
            "trials. It is 1.000 at every evaluated length down to 96 bases, which is the "
            "shortest "
            "sequence the declared search will score rather than a measured limit. Right: the "
            "margin that flat line hides. The weakest watermarked statistic and the strongest "
            "pooled null statistic touch at 96 bases and separate from 144 bases onward, which is "
            "why the strict-separation length is admitted separately from the detection rate."
        ),
        "sign": "higher is intended detection; on the right, a wider gap is a stronger result",
    }


# --------------------------------------------------------------------------- 3
def figure_calibration(led: Ledger, out: Path) -> dict[str, Any]:
    fig, (top, bottom) = plt.subplots(
        2, 1, figsize=(4.6, 4.0), sharex=True, gridspec_kw={"height_ratios": [1.25, 1]}
    )
    ids = []
    for slug, policy in POLICIES:
        thresholds, achieved, xs = [], [], []
        for length in LENGTHS:
            entry = led.one(f"e4.clean_detection.{slug}.b{length}.detection_rate")
            ids.append(entry["id"])
            cal = entry["admitted_calibration"]
            xs.append(length)
            thresholds.append(cal["threshold"])
            achieved.append(cal["achieved_false_positive_rate"])
        top.plot(
            xs,
            thresholds,
            marker=POLICY_MARKER[policy],
            ms=4,
            lw=1.3,
            color=POLICY_COLOR[policy],
            label=policy,
        )
        bottom.plot(
            xs,
            achieved,
            marker=POLICY_MARKER[policy],
            ms=4,
            lw=1.3,
            color=POLICY_COLOR[policy],
            label=policy,
        )
    top.set_ylabel("calibrated threshold")
    top.legend(loc="upper left", fontsize=8, ncols=3)
    top.set_title("The threshold is set by the search, not by a normal tail", fontsize=9.5)
    bottom.axhline(0.01, ls="--", lw=1.0, color="#444444")
    bottom.annotate(
        "target 0.01",
        xy=(3072, 0.01),
        xytext=(-2, 3),
        textcoords="offset points",
        ha="right",
        fontsize=7.5,
        color="#444444",
    )
    log_length_axis(bottom, LENGTHS)
    bottom.set_xlabel("generated length (bases)")
    bottom.set_ylabel("achieved FPR")
    bottom.set_ylim(0, 0.014)
    return {
        "figure": save(fig, out, "fig03_calibration"),
        "measurement_ids": sorted(set(ids)),
        "caption_claim": (
            "Top: the decision threshold chosen empirically from null trials that repeat the "
            "complete declared search of two orientations, six phases, and eight key-stream "
            "offsets. Bottom: the false-positive rate that threshold actually achieves. The "
            "reported statistic is a maximum over the search, so its nominal normal tail is not a "
            "p-value and no threshold here comes from one."
        ),
        "sign": "lower achieved FPR is stricter",
    }


# --------------------------------------------------------------------------- 4
def figure_substitution(led: Ledger, out: Path) -> dict[str, Any]:
    fig, axes = plt.subplots(1, 3, figsize=(7.6, 2.7), sharey=True)
    ids = []
    for ax, (slug, policy) in zip(axes, POLICIES, strict=True):
        for length, shade in zip(LENGTHS, (0.30, 0.50, 0.72, 1.0), strict=True):
            entry = led.one(f"e5.substitution.{slug}.b{length}.max_fully_detected_rate")
            ids.append(entry["id"])
            points = entry["admitted_curve"]["points"]
            xs = [p["edit_rate"] for p in points]
            ys = [p["detection_rate"] for p in points]
            lo = [p["detection_rate"] - p["detection_rate_lower"] for p in points]
            hi = [p["detection_rate_upper"] - p["detection_rate"] for p in points]
            ax.errorbar(
                xs,
                ys,
                yerr=[lo, hi],
                marker="o",
                ms=2.6,
                lw=1.1,
                capsize=2,
                color=POLICY_COLOR[policy],
                alpha=shade,
                label=f"{length} b",
            )
        ax.set_title(policy, fontsize=9)
        ax.set_xlabel("substitutions per base")
        ax.set_ylim(-0.04, 1.05)
    axes[0].set_ylabel("detection rate")
    axes[-1].legend(fontsize=7, title="length", title_fontsize=7)
    fig.suptitle("Substitution robustness", fontsize=9.5, y=1.02)
    return {
        "figure": save(fig, out, "fig04_substitution"),
        "measurement_ids": sorted(set(ids)),
        "caption_claim": (
            "Detection rate against per-base substitution rate, by policy and generated length, at "
            "the calibrated false-positive rate. Intervals are joint resamples: each replicate "
            "resamples the null trials, recalibrates the threshold, and independently resamples "
            "the "
            "prompt clusters."
        ),
        "sign": "higher is more robust",
    }


# --------------------------------------------------------------------------- 5
def figure_crop_strand(led: Ledger, out: Path) -> dict[str, Any]:
    """Detection per crop condition, and why the failures are search failures.

    A bar of "fraction of conditions detected" comes out identical for all three
    policies, which looks like a plotting bug and is not: every failing condition is
    one whose required key-stream offset falls outside the declared search, and that
    is a property of the search rather than of the model. So the figure shows the
    conditions themselves and marks which ones the search could not reach. The
    agreement across policies is asserted rather than assumed.
    """

    grids: dict[str, dict[str, list[dict[str, Any]]]] = {}
    ids = []
    for slug, policy in POLICIES:
        grids[policy] = {}
        for search in ("narrow", "wide"):
            entry = led.one(f"e6.crop_strand.{slug}.{search}.conditions_fully_detected")
            ids.append(entry["id"])
            grids[policy][search] = entry["admitted_conditions"]["grid"]

    reference = grids["C_tok"]
    for search in ("narrow", "wide"):
        order = [row["condition_id"] for row in reference[search]]
        for policy in grids:
            if [row["condition_id"] for row in grids[policy][search]] != order:
                raise ValueError(
                    "policies report different crop conditions; the figure assumes not"
                )

    fig, axes = plt.subplots(1, 2, figsize=(7.8, 3.2), sharey=True)
    for ax, search in zip(axes, ("narrow", "wide"), strict=True):
        rows = reference[search]
        labels = [row["condition_id"].replace("front_crop_", "crop ") for row in rows]
        positions = list(range(len(rows)))
        spread = 0.22
        for index, (_slug, policy) in enumerate(POLICIES):
            values = [row["detection_rate"] for row in grids[policy][search]]
            ax.scatter(
                [pos + (index - 1) * spread for pos in positions],
                values,
                s=26,
                marker=POLICY_MARKER[policy],
                color=POLICY_COLOR[policy],
                label=policy if search == "narrow" else None,
                zorder=3,
            )
        for pos, row in zip(positions, rows, strict=True):
            if not row.get("required_offset_inside_search", True):
                ax.axvspan(pos - 0.45, pos + 0.45, color=ATTACK_RED, alpha=0.10, zorder=0)
        ax.set_xticks(positions)
        ax.set_xticklabels(labels, rotation=60, ha="right", fontsize=6.4)
        ax.set_ylim(-0.06, 1.08)
        ax.set_title(f"{search} offset search", fontsize=9)
    axes[0].set_ylabel("detection rate")
    axes[0].legend(fontsize=7.5, loc="lower left")
    axes[1].annotate(
        "shaded: the required key offset lies\noutside the declared search",
        xy=(0.98, 0.06),
        xycoords="axes fraction",
        ha="right",
        fontsize=7,
        color=ATTACK_RED,
    )
    fig.suptitle("Crops, phase, and the reverse-complement strand", fontsize=9.5, y=1.04)
    return {
        "figure": save(fig, out, "fig05_crop_strand"),
        "measurement_ids": sorted(set(ids)),
        "caption_claim": (
            "Detection rate per crop, phase, and reverse-complement condition under the narrow and "
            "the wide declared key-offset search. The three policies agree condition by condition, "
            "and that is expected rather than suspicious: every failing condition is one whose "
            "required key-stream offset falls outside the declared search, which is a property of "
            "the search and not of the model. Widening the search recovers all but the longest "
            "crop, and it raises the calibrated threshold, and both effects are inside the "
            "calibration because the nulls repeat the same search."
        ),
        "sign": (
            "higher is more robust; a shaded failure is a search-coverage limit, not a fragility"
        ),
    }


# --------------------------------------------------------------------------- 6
def figure_indel(led: Ledger, out: Path) -> dict[str, Any]:
    fig, axes = plt.subplots(1, 3, figsize=(7.8, 2.8), sharey=True)
    ids = []
    for ax, (slug, policy) in zip(axes, POLICIES, strict=True):
        for channel, style in (("deletion", "-"), ("insertion", "--")):
            entry = led.one(f"e7.{channel}.{slug}.b{INDEL_LENGTH}.max_fully_detected_rate")
            ids.append(entry["id"])
            points = [p for p in entry["admitted_curve"]["points"] if p["edit_rate"] > 0]
            ax.plot(
                [p["edit_rate"] for p in points],
                [p["detection_rate"] for p in points],
                style,
                marker="o",
                ms=2.6,
                lw=1.2,
                color=POLICY_COLOR[policy],
                label=f"{channel}, unwindowed",
            )
        stage2 = led.one(f"e7.stage2.deletion.{slug}.windowed_max_fully_detected_rate")
        ids.append(stage2["id"])
        pts = [p for p in stage2["admitted_paired_comparison"]["points"] if p["edit_rate"] > 0]
        ax.plot(
            [p["edit_rate"] for p in pts],
            [p["windowed_detection_rate"] for p in pts],
            "-",
            marker="D",
            ms=3.2,
            lw=1.4,
            color="#5b3a8e",
            label="deletion, windowed search",
        )
        sub = led.one(f"e5.substitution.{slug}.b{INDEL_LENGTH}.max_fully_detected_rate")
        ids.append(sub["id"])
        spts = [p for p in sub["admitted_curve"]["points"] if p["edit_rate"] > 0]
        ax.plot(
            [p["edit_rate"] for p in spts],
            [p["detection_rate"] for p in spts],
            ":",
            lw=1.2,
            color="#888888",
            label="substitution, for scale",
        )
        ax.set_xscale("log")
        ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
        ax.set_xticks([1e-4, 1e-3, 1e-2, 1e-1])
        ax.set_xticklabels(["0.0001", "0.001", "0.01", "0.1"], fontsize=7)
        ax.set_title(policy, fontsize=9)
        ax.set_xlabel("edits per base")
        ax.set_ylim(-0.04, 1.05)
    axes[0].set_ylabel("detection rate")
    # A per-panel legend lands on top of the curves, so it goes under the figure.
    handles, labels = axes[-1].get_legend_handles_labels()
    generic = [
        label.replace("deletion", "deletion").replace("insertion", "insertion") for label in labels
    ]
    fig.legend(
        handles,
        generic,
        fontsize=7.2,
        ncols=4,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.02),
    )
    fig.suptitle(f"The synchronization wall, at {INDEL_LENGTH:,} bases", fontsize=9.5, y=1.03)
    return {
        "figure": save(fig, out, "fig06_indel_synchronization"),
        "measurement_ids": sorted(set(ids)),
        "caption_claim": (
            "Detection against per-base edit rate at 1,536 bases, the longest length the indel "
            "experiments evaluated. Insertions and deletions defeat "
            "the unwindowed detector one to two orders of magnitude below the substitution "
            "tolerance drawn for scale, because one deleted base moves every later token off the "
            "reading grid. A declared sliding-window search moves that limit five- to tenfold "
            "before meeting a second, information-theoretic wall."
        ),
        "sign": "higher is more robust",
    }


# --------------------------------------------------------------------------- 7
def figure_runtime(led: Ledger, out: Path) -> dict[str, Any]:
    fig, ax = plt.subplots(figsize=(5.0, 2.9))
    ids = []
    stages = (
        ("sequential_capacity_wall_seconds", "sequential\ncapacity"),
        ("watermarked_seconds", "watermarked\ngeneration"),
        ("ordinary_seconds", "ordinary\ngeneration"),
        ("clean_detection_wall_seconds", "clean detection\n(no model, no GPU)"),
    )
    width = 0.26
    for index, (slug, policy) in enumerate(POLICIES):
        entry = led.get(f"e14.runtime.{slug}.matched_generation_wall_seconds")
        ids.append(entry["id"])
        runtime = entry["admitted_runtime"]
        values = [runtime[key] for key, _ in stages]
        positions = [i + (index - 1) * width for i in range(len(stages))]
        ax.bar(positions, values, width=width, color=POLICY_COLOR[policy], label=policy)
    ax.set_xticks(range(len(stages)))
    ax.set_xticklabels([label for _, label in stages], fontsize=7.5)
    ax.set_ylabel("wall-clock seconds")
    ax.legend(fontsize=8)
    ax.set_title("Runtime envelope on one laptop (mains power)", fontsize=9.5)
    return {
        "figure": save(fig, out, "fig07_runtime"),
        "measurement_ids": sorted(set(ids)),
        "caption_claim": (
            "Wall-clock time per stage for one policy on one Apple M5 Pro laptop, from single "
            "observations under uncontrolled desktop load. A feasibility envelope, not a "
            "benchmark. "
            "No memory panel is shown because no peak-memory figure is admitted. Detection uses "
            "neither the model nor the GPU. Measured on mains power; the same generation runs "
            "about "
            "ten times slower on battery."
        ),
        "sign": "lower is faster",
    }


# --------------------------------------------------------------------------- 8
def figure_baseline_comparison(led: Ledger, out: Path) -> dict[str, Any]:
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    ids = []
    methods = ("partition_mc", "its", "exp")
    method_label = {
        "partition_mc": "partition coupling (ours)",
        "its": "inverse transform",
        "exp": "exponential",
    }
    method_color = {"partition_mc": "#1b6ca8", "its": "#c1663d", "exp": "#2f7d5c"}
    method_marker = {"partition_mc": "o", "its": "s", "exp": "D"}
    # A bar of the min-to-max band is invisible on a log axis when the band is tight,
    # so each method is a marker at the midpoint with the band drawn as a range bar.
    spread = 0.20
    for index, method in enumerate(methods):
        centres, lows, highs, positions = [], [], [], []
        for policy_index, (slug, _policy) in enumerate(POLICIES):
            entry = led.get(f"e8.e9.matched_baseline.{slug}.signal_per_token")
            ids.append(entry["id"])
            band = entry["admitted_signal_per_token"]["range_across_lengths"][method]
            centre = (band["minimum"] + band["maximum"]) / 2.0
            centres.append(centre)
            lows.append(centre - band["minimum"])
            highs.append(band["maximum"] - centre)
            positions.append(policy_index + (index - 1) * spread)
        ax.errorbar(
            positions,
            centres,
            yerr=[lows, highs],
            fmt=method_marker[method],
            ms=6,
            lw=0,
            elinewidth=2.0,
            capsize=4,
            color=method_color[method],
            label=method_label[method],
        )
    ax.axhline(1.0, ls="--", lw=1.0, color="#444444")
    ax.annotate(
        "one coupled bit per token: the ceiling of ours",
        xy=(0.02, 1.0),
        xytext=(0, -12),
        textcoords="offset points",
        fontsize=7.5,
        color="#444444",
    )
    ax.set_yscale("log")
    ax.set_yticks([0.9, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0])
    ax.set_yticklabels(["0.9", "1.0", "1.5", "2.0", "3.0", "5.0", "8.0"])
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_ylim(0.78, 11.0)
    ax.set_xlim(-0.5, len(POLICIES) - 0.5)
    ax.set_xticks(range(len(POLICIES)))
    ax.set_xticklabels([p for _, p in POLICIES])
    ax.set_ylabel("standardized signal per 6-mer token\n(own-null units)")
    ax.legend(fontsize=7.5, loc="center left", bbox_to_anchor=(0.02, 0.62))
    ax.set_title("Three exact-marginal watermarks, one calibrated detector", fontsize=9.5)
    return {
        "figure": save(fig, out, "fig08_baseline_signal_per_token"),
        "measurement_ids": sorted(set(ids)),
        "caption_claim": (
            "Standardized signal per 6-mer token for the three exact-marginal constructions, each "
            "in units of its own null standard deviation, as a band across the evaluated lengths. "
            "Detection rate is deliberately not plotted: it is 1.000 for all three methods at "
            "every "
            "evaluated length, so plotting it would present a null result as agreement. Partition "
            "coupling sits at its structural ceiling of one coupled bit per token; the exponential "
            "construction is not so bounded and carries about 7.5 times the signal."
        ),
        "sign": (
            "higher is more signal per token; the dashed line is a structural cap, not a target"
        ),
    }


# --------------------------------------------------------------------------- 9
def figure_attacks(led: Ledger, out: Path) -> dict[str, Any]:
    fig, (left, right) = plt.subplots(1, 2, figsize=(7.4, 3.0))
    ids = []
    # Left: forged statistics sit on top of genuine ones.
    for index, (slug, policy) in enumerate(POLICIES):
        entry = led.get(f"e11.spoofing.{slug}.splice_forgery_detection_rate")
        ids.append(entry["id"])
        points = [p for p in entry["admitted_curve"]["points"] if p["donor_outputs"] == 2]
        xs = [p["base_length"] for p in points]
        genuine = [p["genuine_mean_statistic"] for p in points]
        forged = [p["forgery_mean_statistic"] for p in points]
        left.plot(
            xs,
            genuine,
            "-",
            marker=POLICY_MARKER[policy],
            ms=4,
            lw=1.4,
            color=POLICY_COLOR[policy],
            label=f"{policy}, genuine",
        )
        left.plot(
            xs,
            forged,
            "none",
            marker="x",
            ms=6,
            mew=1.4,
            linestyle="None",
            color=ATTACK_RED,
            label="spliced forgery" if index == 0 else None,
        )
        thresholds = [p["threshold"] for p in points]
        if index == 0:
            left.plot(xs, thresholds, ":", lw=1.1, color="#666666", label="calibrated threshold")
    log_length_axis(left, LENGTHS)
    left.set_xlabel("generated length (bases)")
    left.set_ylabel("detector statistic")
    left.legend(fontsize=6.8, loc="upper left")
    left.set_title("Spoofing: a forgery scores like the real thing", fontsize=9)

    # Right: removal by bounded rearrangement.
    for slug, policy in POLICIES:
        entry = led.get(f"e12.removal.{slug}.rearrangement_detection_rate")
        ids.append(entry["id"])
        points = [
            p
            for p in entry["admitted_curve"]["points"]
            if p["attack"] == "block_shuffle" and p["base_length"] == 3072
        ]
        points.sort(key=lambda p: p["block_width_tokens"])
        right.plot(
            [p["block_width_tokens"] for p in points],
            [p["detection_rate"] for p in points],
            marker=POLICY_MARKER[policy],
            ms=4,
            lw=1.3,
            color=POLICY_COLOR[policy],
            label=policy,
        )
    right.set_xscale("log", base=2)
    right.set_xticks([2, 3, 4, 6, 8, 16, 32])
    right.set_xticklabels(["2", "3", "4", "6", "8", "16", "32"])
    right.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    right.set_xlabel("shuffle block width (6-mer tokens)")
    right.set_ylabel("detection rate")
    right.set_ylim(-0.04, 1.05)
    right.legend(fontsize=7.5, loc="lower left")
    right.set_title("Removal: rearranging within blocks, 3,072 bases", fontsize=9)
    fig.suptitle(
        "Key reuse: both panels are attacks, and the signs are opposite",
        fontsize=9.5,
        y=1.04,
    )
    return {
        "figure": save(fig, out, "fig09_key_reuse_attacks"),
        "measurement_ids": sorted(set(ids)),
        "caption_claim": (
            "Left: a sequence spliced position-wise from two watermarked outputs under the same "
            "key "
            "scores indistinguishably from genuine output at every length, so the verifier accepts "
            "it every time. A high value here is a vulnerability, because the statistic is a sum "
            "of "
            "content-blind per-position checks and nothing binds a sequence to itself. Right: "
            "detection after permuting 6-mer positions within blocks of the given width. A low "
            "value here is a successful removal, and it must be read with the utility column: the "
            "attack preserves the 6-mer multiset exactly, so the admitted composition proxies are "
            "nearly blind to it."
        ),
        "sign": (
            "INVERTED. Left panel: high is bad. Right panel: low means the attack succeeded. "
            "Neither may share an axis with the intended-detection figures."
        ),
    }


# --------------------------------------------------------------------------- 10
def figure_unpriced_removal(led: Ledger, out: Path) -> dict[str, Any]:
    """Why a large relative shift is not an effect.

    Left: the longest-ORF relative shift under each bounded rearrangement, beside the
    largest composition shift. Right: the exact paired sign-flip p-value for the same
    cells. The magnitudes look like a result and the paired test says the direction is
    absent, which is the whole point of the panel.
    """

    fig, (left, right) = plt.subplots(1, 2, figsize=(7.6, 3.0))
    ids = []
    widths: list[int] = []
    for slug, policy in POLICIES:
        entry = led.get(f"e15.structure_proxies.{slug}.orf_prices_bounded_rearrangement")
        ids.append(entry["id"])
        cells = [
            cell
            for cell in entry["admitted_conditions"]["grid"]
            if cell["attack"] in {"block_shuffle", "positional_shuffle"}
        ]
        cells.sort(key=lambda cell: cell["block_width_tokens"] or 0)
        labels = [
            "full" if cell["block_width_tokens"] is None else str(cell["block_width_tokens"])
            for cell in cells
        ]
        if not widths:
            widths = list(range(len(cells)))
        left.plot(
            widths,
            [cell["longest_orf_relative_shift"] for cell in cells],
            marker=POLICY_MARKER[policy],
            ms=4,
            lw=1.3,
            color=POLICY_COLOR[policy],
            label=f"{policy}, longest ORF",
        )
        left.plot(
            widths,
            [cell["largest_composition_relative_shift"] for cell in cells],
            ls=":",
            lw=1.1,
            color=POLICY_COLOR[policy],
            label=f"{policy}, composition" if slug == "c_tok" else None,
        )
        right.plot(
            widths,
            [cell["longest_orf_sign_flip_p_value"] for cell in cells],
            marker=POLICY_MARKER[policy],
            ms=4,
            lw=1.3,
            color=POLICY_COLOR[policy],
            label=policy,
        )
    for axis, ticks in ((left, labels), (right, labels)):
        axis.set_xticks(widths)
        axis.set_xticklabels(ticks, fontsize=7.5)
        axis.set_xlabel("shuffle block width (6-mer tokens)")
    left.set_ylabel("relative shift")
    left.legend(fontsize=6.4, loc="upper left")
    left.set_title("The magnitude looks like an effect", fontsize=9)
    right.axhline(0.05, ls="--", lw=1.0, color=ATTACK_RED)
    right.annotate(
        "$p = 0.05$",
        xy=(0.30, 0.05),
        xycoords=("axes fraction", "data"),
        ha="left",
        va="bottom",
        fontsize=7.5,
        color=ATTACK_RED,
    )
    right.set_ylim(-0.05, 1.05)
    right.set_ylabel("paired sign-flip $p$-value")
    right.legend(fontsize=7.5, loc="lower right")
    right.set_title("The direction is absent", fontsize=9)
    fig.suptitle(
        "The removal attack is unpriced by both order-sensitive measures", fontsize=9.5, y=1.04
    )
    return {
        "figure": save(fig, out, "fig10_unpriced_removal"),
        "measurement_ids": sorted(set(ids)),
        "caption_claim": (
            "Left: the relative shift of the longest open reading frame under each bounded "
            "rearrangement, with the largest composition-proxy shift beside it. The reading-frame "
            "shift is the larger of the two on most cells, which looks like an instrument that "
            "prices the attack. Right: the exact paired sign-flip p-value over the eight prompts "
            "for the same cells. Only the complete shuffle on one policy shows a directionally "
            "consistent change; under every bounded shuffle the longest reading frame rises about "
            "as often as it falls, because on high-entropy DNA it is a chance extreme-value "
            "statistic that a permutation re-rolls rather than destroys."
        ),
        "sign": (
            "a large left-panel value is NOT evidence of an effect unless the right panel is below "
            "0.05; this figure exists to make that visible"
        ),
    }


FIGURES = (
    figure_capacity,
    figure_clean_detection,
    figure_calibration,
    figure_substitution,
    figure_crop_strand,
    figure_indel,
    figure_runtime,
    figure_baseline_comparison,
    figure_attacks,
    figure_unpriced_removal,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "paper/figures")
    parser.add_argument("--manifest", type=Path, default=ROOT / "paper/figures/manifest.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    led = Ledger(LEDGER)
    entries = []
    for builder in FIGURES:
        entry = builder(led, args.output)
        entry["name"] = builder.__name__.removeprefix("figure_")
        entries.append(entry)
    manifest = {
        "schema_version": 1,
        "source_of_truth": "evidence/measurements.yaml",
        "rule": (
            "every plotted value is read from the ledger; nothing is computed here, read from a "
            "result artifact, or hand-entered, and a missing measurement raises rather than "
            "falling back to a default"
        ),
        "excluded_by_choice": [
            "no peak-memory panel, because no memory figure is admitted",
            "no detection-rate panel for the baseline comparison, because it is 1.000 in every "
            "cell and would present a null result as agreement",
            "no per-trial statistic distributions, because they are not admitted evidence",
        ],
        "figures": entries,
        "measurement_ids_used": sorted(led.used),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "figures": len(entries),
                "measurements_used": len(led.used),
                "manifest": str(args.manifest.relative_to(ROOT)),
                "files": [e["figure"] for e in entries],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
