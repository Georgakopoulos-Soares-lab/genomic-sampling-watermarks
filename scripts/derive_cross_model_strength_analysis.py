#!/usr/bin/env python3
"""Compare clean correct-key strength from the admitted version-one artifacts.

This reads stored detector trials and quality summaries. It does not rerun generation,
model scoring, or detector search. The scored-token counts describe each read's
winning window, not every token in the complete read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.synthid_position_independent import (  # noqa: E402
    fair_binomial_log_survival_probability,
)

ANALYSIS_ID = "cross_model_strength_2026_09_21"
DEFAULT_OUTPUT = ROOT / "evidence/derived/cross_model_strength_2026_09_21.json"
SOURCES = {
    "carbon_trials": (
        "outputs/carbon_synthid_position_independent_v1/trials.jsonl",
        "323d998561843dda5b204c33d3de9d6a281aaa700ceddc535b0d7af32e0ac81c",
    ),
    "generator_trials": (
        "outputs/generator_synthid_position_independent_v1/trials.jsonl",
        "3de1d8f7b8a946d3a5149f48ac30e357ceb2fa812eddbe6a11a5e836c7106d99",
    ),
    "carbon_quality": (
        "outputs/carbon_synthid_e16_v1/sequence_comparison_summary.json",
        "6c9a73ea92592465b3a7c5121ab6a7e296839bc22a02edaa8050c36ebad7b0da",
    ),
    "generator_quality": (
        "outputs/generator_synthid_e16_v1/sequence_comparison_summary.json",
        "d8e3c03b2d0e3a2639c521889ea29dd804e8a741d3cf43818cb79f31ae821401",
    ),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_clean_trials(path: Path) -> list[dict[str, Any]]:
    """Extract and check the complete clean correct-key grid and its local tails."""
    rows = []
    seen = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["condition"] != "clean" or row["family"] != "watermarked_correct_key":
            continue
        identity = (row["case_id"], row["draw_id"])
        if identity in seen:
            raise ValueError(f"duplicate clean correct-key trial: {identity}")
        seen.add(identity)
        best = row["best_hypothesis"]
        potential = best["window_base_length"] // 6 - 4
        if best["window_base_length"] not in (384, 768, 1536, 3072):
            raise ValueError("unexpected winning-window length")
        if best["scored_tokens"] + best["repeated_contexts"] != potential:
            raise ValueError("scored and excluded tokens do not cover the winning window")
        if best["g_total"] != 30 * best["scored_tokens"]:
            raise ValueError("mark-bit total differs from tournament depth times scored tokens")
        if not 0 <= best["g_ones"] <= best["g_total"]:
            raise ValueError("invalid mark-bit count")
        recomputed = fair_binomial_log_survival_probability(best["g_ones"], best["g_total"])
        if not math.isclose(recomputed, best["local_log_p_value"], abs_tol=1e-7):
            raise ValueError("stored local tail differs from exact binomial tail")
        if not math.isclose(recomputed, row["minimum_local_log_p_value"], abs_tol=1e-7):
            raise ValueError("stored winning tail differs from row minimum")
        rows.append(row)
    prompts = {case_id for case_id, _ in seen}
    if (
        len(rows) != 384
        or len(prompts) != 192
        or seen != {(case_id, draw_id) for case_id in prompts for draw_id in (0, 1)}
    ):
        raise ValueError("clean correct-key grid is incomplete")
    return rows


def summarize_trials(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize the selected windows without treating draws as independent prompts."""
    best = [row["best_hypothesis"] for row in rows]
    counts = [row["scored_tokens"] for row in best]
    strengths = [-row["local_log_p_value"] / math.log(10.0) for row in best]
    fractions = [row["g_ones"] / row["g_total"] for row in best]
    repetitions = [row["repeated_contexts"] for row in best]
    potential = sum(counts) + sum(repetitions)
    lengths = Counter(row["window_base_length"] for row in best)
    return {
        "prompts": len({row["case_id"] for row in rows}),
        "reads": len(rows),
        "scored_tokens_in_winning_window": {
            "minimum": min(counts),
            "median": statistics.median(counts),
            "maximum": max(counts),
        },
        "mark_bit_positive_fraction_in_winning_window": {
            "minimum": min(fractions),
            "median": statistics.median(fractions),
            "maximum": max(fractions),
        },
        "local_strength_negative_log10_p": {
            "minimum": min(strengths),
            "median": statistics.median(strengths),
            "maximum": max(strengths),
        },
        "winning_window_base_length_counts": {str(k): lengths[k] for k in sorted(lengths)},
        "winning_windows_with_repeated_contexts": sum(count > 0 for count in repetitions),
        "excluded_contexts": sum(repetitions),
        "potential_scored_tokens": potential,
        "repeated_context_exclusion_fraction": sum(repetitions) / potential,
        "pearson_r_strength_vs_scored_tokens": statistics.correlation(counts, strengths),
    }


def quality_proxies(path: Path) -> dict[str, Any]:
    source = json.loads(path.read_text(encoding="utf-8"))
    if source["prompt_count"] != 256 or source["pair_count"] != 512:
        raise ValueError("unexpected quality cohort size")
    measures = source["main_key_averaged"]
    return {
        "prompts": source["prompt_count"],
        "ordinary_self_nll_nats_per_6mer": measures["mean_negative_log_likelihood_per_token"][
            "ordinary"
        ]["mean"],
        "watermarked_nll_nats_per_6mer": measures["mean_negative_log_likelihood_per_token"][
            "watermarked"
        ]["mean"],
        "ordinary_base_entropy_bits": measures["base_entropy_bits"]["ordinary"]["mean"],
        "watermarked_base_entropy_bits": measures["base_entropy_bits"]["watermarked"]["mean"],
        "ordinary_dinucleotide_entropy_bits": measures["dinucleotide_entropy_bits"]["ordinary"][
            "mean"
        ],
        "watermarked_dinucleotide_entropy_bits": measures["dinucleotide_entropy_bits"][
            "watermarked"
        ]["mean"],
    }


def weakest_window_counterfactual(
    carbon_rows: list[dict[str, Any]], generator_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Hold the weakest GENERator window's observed bit fraction fixed at full length."""
    carbon = max(carbon_rows, key=lambda row: row["minimum_local_log_p_value"])["best_hypothesis"]
    generator = max(generator_rows, key=lambda row: row["minimum_local_log_p_value"])[
        "best_hypothesis"
    ]
    potential = generator["window_base_length"] // 6 - 4
    full_total = potential * 30
    observed_fraction = generator["g_ones"] / generator["g_total"]
    full_ones = round(observed_fraction * full_total)
    full_strength = -fair_binomial_log_survival_probability(full_ones, full_total) / math.log(10.0)
    carbon_strength = -carbon["local_log_p_value"] / math.log(10.0)
    generator_strength = -generator["local_log_p_value"] / math.log(10.0)
    gap = carbon_strength - generator_strength
    sensitivity = full_strength - generator_strength
    return {
        "carbon_weakest_strength": carbon_strength,
        "generator_weakest_strength": generator_strength,
        "weakest_strength_gap": gap,
        "generator_weakest_scored_tokens": generator["scored_tokens"],
        "generator_weakest_repeated_contexts": generator["repeated_contexts"],
        "generator_weakest_mark_bit_positive_fraction": observed_fraction,
        "counterfactual_full_scored_tokens": potential,
        "counterfactual_full_mark_bits": full_total,
        "counterfactual_positive_bits_rounded": full_ones,
        "counterfactual_strength": full_strength,
        "scored_token_count_sensitivity": sensitivity,
        "sensitivity_fraction_of_weakest_gap": sensitivity / gap,
        "interpretation": (
            "Arithmetic sensitivity of the weakest selected GENERator window at its observed "
            "mark-bit fraction; it is not a causal attribution or a re-run detector result."
        ),
    }


def derive(paths: dict[str, Path]) -> dict[str, Any]:
    for name, (_, expected) in SOURCES.items():
        if digest(paths[name]) != expected:
            raise ValueError(f"source digest mismatch: {name}")
    carbon = selected_clean_trials(paths["carbon_trials"])
    generator = selected_clean_trials(paths["generator_trials"])
    carbon_quality = quality_proxies(paths["carbon_quality"])
    generator_quality = quality_proxies(paths["generator_quality"])
    return {
        "carbon": {"detector": summarize_trials(carbon), "quality_proxies": carbon_quality},
        "generator": {
            "detector": summarize_trials(generator),
            "quality_proxies": generator_quality,
        },
        "weakest_window_comparison": weakest_window_counterfactual(carbon, generator),
        "quality_proxy_comparison": {
            "generator_minus_carbon_ordinary_self_nll_nats_per_6mer": (
                generator_quality["ordinary_self_nll_nats_per_6mer"]
                - carbon_quality["ordinary_self_nll_nats_per_6mer"]
            )
        },
        "limits": [
            (
                "Each detector row describes the winning window; scored-token counts for every "
                "possible window or the entire read are not retained here."
            ),
            (
                "The correlation uses two draws per prompt and selected winning windows; it is "
                "descriptive and has no independence-based p-value."
            ),
            (
                "The quality proxies average all 256 prompts, while clean detector rows use 192 "
                "evaluation prompts; no per-read predictive entropy is linked to strength."
            ),
            (
                "Ordinary self-NLL is a cohort-level proxy for model uncertainty on generated "
                "trajectories. Base and dinucleotide entropy describe outputs, not predictive "
                "entropy."
            ),
            (
                "The worst-read counterfactual holds its observed mark-bit fraction fixed while "
                "changing scored-token count; this arithmetic cannot identify the cause of the "
                "cross-model gap."
            ),
        ],
        "conclusion": (
            "Both medians have full winning-window scoring. The weakest GENERator read has many "
            "repeated-context exclusions and a much lower mark-bit fraction; count alone explains "
            "only a small arithmetic portion of the weakest-read strength gap. The available "
            "aggregated quality proxies do not resolve the predictive-entropy hypothesis."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--carbon-trials", type=Path, default=ROOT / SOURCES["carbon_trials"][0])
    parser.add_argument(
        "--generator-trials", type=Path, default=ROOT / SOURCES["generator_trials"][0]
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check", action="store_true", help="verify retained output without writing"
    )
    args = parser.parse_args()
    paths = {name: ROOT / relative for name, (relative, _) in SOURCES.items()}
    paths["carbon_trials"] = args.carbon_trials
    paths["generator_trials"] = args.generator_trials
    data = derive(paths)
    sources = {name: {"path": relative, "sha256": sha} for name, (relative, sha) in SOURCES.items()}
    code = {"scripts/derive_cross_model_strength_analysis.py": digest(Path(__file__))}
    if args.check:
        retained = json.loads(args.output.read_text(encoding="utf-8"))
        if retained["analysis_id"] != ANALYSIS_ID or retained["data"] != data:
            raise ValueError("retained derived values differ from verified sources")
        if retained["sources"] != sources or retained["provenance"]["code_sha256"] != code:
            raise ValueError("retained source or code provenance differs")
    else:
        if args.output.exists():
            raise FileExistsError(f"immutable output exists; use --check: {args.output}")
        record = {
            "schema_version": 1,
            "analysis_id": ANALYSIS_ID,
            "status": "A",
            "generation_rerun": False,
            "detection_rerun": False,
            "sources": sources,
            "data": data,
            "provenance": {
                "git_base_revision": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                ).strip(),
                "code_sha256": code,
                "command": "python3 scripts/derive_cross_model_strength_analysis.py",
                "python": platform.python_version(),
                "system": platform.system(),
                "machine": platform.machine(),
                "device": "cpu",
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(
        json.dumps(
            {"status": "verified" if args.check else "derived", "sha256": digest(args.output)}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
