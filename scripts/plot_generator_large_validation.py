#!/usr/bin/env python3
"""Generate ten GENERATOR SynthID validation diagnostic figures."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.metrics import (  # noqa: E402
    jensen_shannon_divergence_bits,
    total_variation_distance,
)
from genomic_watermarks.sequence_proxies import PROXY_METRICS  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_figure(figure: Any, figures_dir: Path, stem: str) -> dict[str, str]:
    png = figures_dir / f"{stem}.png"
    pdf = figures_dir / f"{stem}.pdf"
    existing = (png.exists(), pdf.exists())
    if any(existing) and not all(existing):
        raise FileExistsError(f"incomplete existing figure pair for {stem}")
    if not all(existing):
        figure.savefig(png, dpi=220, bbox_inches="tight")
        figure.savefig(pdf, bbox_inches="tight")
    return {
        "png": str(png),
        "png_sha256": hashlib.sha256(png.read_bytes()).hexdigest(),
        "pdf": str(pdf),
        "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
    }


def main() -> int:
    args = parse_args()
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd
    except ImportError as error:
        raise RuntimeError("install the optional 'analysis' dependencies first") from error
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "figure.dpi": 140,
            "savefig.transparent": False,
        }
    )
    blue = "#0072B2"
    orange = "#D55E00"
    green = "#009E73"
    purple = "#CC79A7"
    figures_dir = args.output_root / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    distribution = pd.read_parquet(args.output_root / "distribution" / "fixed_state_trials.parquet")
    distribution_summary = load_json(
        args.output_root / "distribution" / "distribution_summary.json"
    )
    key_average_replicates = int(
        distribution_summary["tournament"]["key_average_replicates_per_state"]
    )
    state_manifest = {
        row["case_id"]: row
        for row in (
            json.loads(line)
            for line in (args.output_root / "distribution" / "state_manifest.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        )
    }
    derived: list[dict[str, float | str]] = []
    for row in distribution.to_dict(orient="records"):
        model_probabilities = tuple(float(value) for value in row["model_probabilities"])
        tournament_probabilities = tuple(float(value) for value in row["tournament_probabilities"])
        wm_counts = tuple(int(value) for value in row["watermarked_counts"])
        ordinary_counts = tuple(int(value) for value in row["ordinary_counts"])
        wm_frequency = tuple(value / sum(wm_counts) for value in wm_counts)
        ordinary_frequency = tuple(value / sum(ordinary_counts) for value in ordinary_counts)
        state = state_manifest[str(row["case_id"])]
        derived.append(
            {
                "case_id": row["case_id"],
                "watermarked_tv": total_variation_distance(wm_frequency, tournament_probabilities),
                "ordinary_tv": total_variation_distance(ordinary_frequency, model_probabilities),
                "watermarked_js": jensen_shannon_divergence_bits(
                    wm_frequency, tournament_probabilities
                ),
                "ordinary_js": jensen_shannon_divergence_bits(
                    ordinary_frequency, model_probabilities
                ),
                "entropy": float(state["entropy_bits"]),
                "top1": float(state["top1_mass"]),
                "conditional_tv": float(state["key_conditional_total_variation_distance"]),
                "key_average_tv": float(state["key_averaged_total_variation_distance"]),
            }
        )
    derived_frame = pd.DataFrame(derived)
    artifacts: dict[str, dict[str, str]] = {}

    fig, ax = plt.subplots(figsize=(4.6, 4.0))
    ax.scatter(
        derived_frame["ordinary_tv"],
        derived_frame["watermarked_tv"],
        s=18,
        alpha=0.7,
        color=blue,
        edgecolors="none",
    )
    limit = float(max(derived_frame["ordinary_tv"].max(), derived_frame["watermarked_tv"].max()))
    ax.plot([0, limit], [0, limit], color="black", linestyle="--", linewidth=1, label="equal error")
    ax.set(
        xlabel="Ordinary empirical TV to G_tok",
        ylabel="Watermarked empirical TV to tournament law",
        title="Fixed-state sampler error against each declared law",
    )
    ax.legend(frameon=False)
    artifacts["01_fixed_state_tv"] = save_figure(fig, figures_dir, "01_fixed_state_tv")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.2, 3.5))
    bins = np.linspace(0.0, 1.0, 11)
    ax.hist(
        distribution["ordinary_p_value"],
        bins=bins,
        histtype="step",
        linewidth=2,
        color=orange,
        label="Ordinary",
    )
    ax.hist(
        distribution["watermarked_p_value"],
        bins=bins,
        histtype="step",
        linewidth=2,
        color=blue,
        label="Watermarked",
    )
    ax.axhline(
        len(distribution) / 10.0,
        color="black",
        linestyle=":",
        linewidth=1,
        label="Uniform expectation",
    )
    ax.set(
        xlabel="Monte Carlo G-test p-value",
        ylabel="States",
        title="Fixed-state p-value distributions",
        xlim=(0, 1),
    )
    ax.legend(frameon=False)
    artifacts["02_fixed_state_p_values"] = save_figure(fig, figures_dir, "02_fixed_state_p_values")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.5))
    axes[0].scatter(
        derived_frame["entropy"], derived_frame["watermarked_tv"], s=16, alpha=0.7, color=blue
    )
    axes[1].scatter(
        derived_frame["top1"], derived_frame["watermarked_tv"], s=16, alpha=0.7, color=orange
    )
    axes[0].set(xlabel="G_tok entropy (bits)", ylabel="Watermarked TV distance")
    axes[1].set(xlabel="G_tok top-1 mass", ylabel="Watermarked TV distance")
    fig.suptitle("State concentration and watermark sampling error")
    artifacts["03_state_concentration_error"] = save_figure(
        fig, figures_dir, "03_state_concentration_error"
    )
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.5))
    axes[0].scatter(
        derived_frame["entropy"], derived_frame["conditional_tv"], s=16, alpha=0.7, color=green
    )
    axes[1].scatter(
        derived_frame["top1"], derived_frame["key_average_tv"], s=16, alpha=0.7, color=purple
    )
    axes[0].set(xlabel="G_tok entropy (bits)", ylabel="Fixed-key tournament TV to G_tok")
    axes[1].set(
        xlabel="G_tok top-1 mass",
        ylabel=f"{key_average_replicates}-key average TV to G_tok",
    )
    fig.suptitle("Conditional reweighting and finite-key marginal recovery")
    artifacts["04_state_capacity"] = save_figure(fig, figures_dir, "04_state_capacity")
    plt.close(fig)

    metrics = pd.read_parquet(args.output_root / "sequence_comparison" / "sequence_metrics.parquet")
    nll = metrics.pivot(
        index=["case_id", "draw_id"],
        columns="scheme",
        values="mean_negative_log_likelihood_per_token",
    )
    fig, ax = plt.subplots(figsize=(4.6, 4.0))
    ax.scatter(
        nll["ordinary-categorical-v1"],
        nll["synthid-tournament-v1"],
        s=14,
        alpha=0.6,
        color=blue,
    )
    low = float(nll.min().min())
    high = float(nll.max().max())
    ax.plot([low, high], [low, high], color="black", linestyle="--", linewidth=1)
    ax.set(
        xlabel="Ordinary mean NLL/token",
        ylabel="Watermarked mean NLL/token",
        title="Matched GENERATOR self-likelihood",
    )
    artifacts["05_paired_nll"] = save_figure(fig, figures_dir, "05_paired_nll")
    plt.close(fig)

    sequence_summary = load_json(
        args.output_root / "sequence_comparison" / "sequence_comparison_summary.json"
    )
    proxy_effects = [
        (
            metric,
            float(sequence_summary["main_key_averaged"][metric]["paired"]["standardized_effect"]),
            float(
                sequence_summary["main_key_averaged"][metric]["paired"][
                    "benjamini_hochberg_p_value"
                ]
            ),
        )
        for metric in PROXY_METRICS
    ]
    fig, ax = plt.subplots(figsize=(6.4, 4.5))
    positions = np.arange(len(proxy_effects))
    colors = [orange if q < 0.05 else blue for _metric, _effect, q in proxy_effects]
    ax.barh(positions, [effect for _metric, effect, _q in proxy_effects], color=colors, alpha=0.85)
    ax.axvline(0.0, color="black", linewidth=1)
    ax.set_yticks(positions, [metric.replace("_", " ") for metric, _effect, _q in proxy_effects])
    ax.invert_yaxis()
    ax.set(
        xlabel="Prompt-cluster standardized paired effect",
        title="Sequence-proxy shifts (watermarked − ordinary)",
    )
    artifacts["06_sequence_proxy_effects"] = save_figure(
        fig, figures_dir, "06_sequence_proxy_effects"
    )
    plt.close(fig)

    detection_trials = pd.read_parquet(args.output_root / "detection" / "evaluation_trials.parquet")
    detection_summary = load_json(args.output_root / "detection" / "detection_summary.json")
    longest = max(int(row["token_length"]) for row in detection_summary["lengths"])
    score_subset = detection_trials[detection_trials["token_length"] == longest]
    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    for family, color, linestyle in (
        ("watermarked_correct_key", blue, "-"),
        ("ordinary_corresponding_key", orange, "--"),
    ):
        values = score_subset.loc[score_subset["family"] == family, "statistic"]
        ax.hist(
            values,
            bins=24,
            histtype="step",
            linewidth=2,
            color=color,
            linestyle=linestyle,
            label=family.replace("_", " "),
        )
    longest_summary = next(
        row for row in detection_summary["lengths"] if int(row["token_length"]) == longest
    )
    ax.axvline(
        longest_summary["calibration"]["threshold"],
        color="black",
        linestyle=":",
        label="Analytic 1% threshold",
    )
    ax.set(
        xlabel="Aligned SynthID detector statistic",
        ylabel="Trials",
        title=f"Held-out detector scores ({longest * 6} bp)",
    )
    ax.legend(frameon=False)
    artifacts["07_detector_scores"] = save_figure(fig, figures_dir, "07_detector_scores")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(4.5, 4.0))
    roc = longest_summary["separation"]["roc"]
    ax.plot(
        roc["false_positive_rate"],
        roc["true_positive_rate"],
        color=blue,
        linewidth=2,
        label=f"AUC = {longest_summary['separation']['roc_auc']:.3f}",
    )
    ax.plot([0, 1], [0, 1], color="black", linestyle="--", linewidth=1)
    ax.set(
        xlabel="False-positive rate",
        ylabel="True-positive rate",
        title=f"Held-out ROC ({longest * 6} bp)",
        xlim=(0, 1),
        ylim=(0, 1.01),
    )
    ax.legend(frameon=False, loc="lower right")
    artifacts["08_roc"] = save_figure(fig, figures_dir, "08_roc")
    plt.close(fig)

    bases = [int(row["base_length"]) for row in detection_summary["lengths"]]
    tpr = [float(row["positive"]["rate"]) for row in detection_summary["lengths"]]
    tpr_low = [float(row["positive"]["lower"]) for row in detection_summary["lengths"]]
    tpr_high = [float(row["positive"]["upper"]) for row in detection_summary["lengths"]]
    fig, ax = plt.subplots(figsize=(5.4, 3.6))
    ax.plot(bases, tpr, marker="o", color=blue)
    ax.fill_between(bases, tpr_low, tpr_high, color=blue, alpha=0.2)
    ax.set(
        xlabel="Generated bases evaluated",
        ylabel="Held-out TPR",
        title="Clean detection power",
        ylim=(0, 1.02),
    )
    artifacts["09_tpr_length"] = save_figure(fig, figures_dir, "09_tpr_length")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.4, 3.6))
    family_styles = (
        ("ordinary_corresponding_key", orange, "o"),
        ("watermarked_wrong_key", green, "s"),
        ("ordinary_independent_null_key", purple, "^"),
        ("public_refseq_independent_null_key", blue, "D"),
    )
    for family, color, marker in family_styles:
        values = [
            float(row["null_families"][family]["rate"]) for row in detection_summary["lengths"]
        ]
        ax.plot(bases, values, marker=marker, color=color, label=family.replace("_", " "))
    ax.axhline(0.01, color="black", linestyle=":", label="1% target")
    ax.set(
        xlabel="Generated bases evaluated",
        ylabel="Held-out exceedance rate",
        title="Held-out false-positive families",
    )
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False, fontsize=7)
    artifacts["10_fpr_length"] = save_figure(fig, figures_dir, "10_fpr_length")
    plt.close(fig)

    manifest = {
        "schema_version": 1,
        "classification": "validation_artifact_not_admitted_evidence",
        "figures": artifacts,
        "source_artifacts": {
            "distribution_trials": hashlib.sha256(
                (args.output_root / "distribution" / "fixed_state_trials.parquet").read_bytes()
            ).hexdigest(),
            "sequence_metrics": hashlib.sha256(
                (args.output_root / "sequence_comparison" / "sequence_metrics.parquet").read_bytes()
            ).hexdigest(),
            "detection_trials": hashlib.sha256(
                (args.output_root / "detection" / "evaluation_trials.parquet").read_bytes()
            ).hexdigest(),
        },
        "boundary": "No state or outlier is excluded from these figures.",
    }
    manifest_path = figures_dir / "manifest.json"
    manifest_payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if manifest_path.exists() and manifest_path.read_text(encoding="utf-8") != manifest_payload:
        raise FileExistsError(f"refusing to replace different figure manifest: {manifest_path}")
    if not manifest_path.exists():
        manifest_path.write_text(manifest_payload, encoding="utf-8")
    print(
        json.dumps(
            {
                "figures": len(artifacts),
                "manifest": str(manifest_path),
                "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
