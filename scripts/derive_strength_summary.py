#!/usr/bin/env python3
"""Summarize correct-key detection strength across both cohorts and compare edit-rate curves.

This reads admitted artifacts only: the version-one cross-model strength analysis, the
second-cohort (v2) detector trials, and the v3 edit-rate cells. It does not rerun generation,
model scoring, or detector search. Strength is ``-log10`` of the winning window's exact local
binomial tail, the scale plotted in the manuscript's detection figures.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import platform
import statistics
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

ANALYSIS_ID = "strength_summary_2026_09_30"
DEFAULT_OUTPUT = ROOT / "evidence/derived/strength_summary_2026_09_30.json"
MODELS = ("carbon", "generator")
CONDITIONS = ("clean", "substitution_1nt", "insertion_1nt", "deletion_1nt")
EVALUATION_PROMPTS = 1544
DRAWS = (0, 1)
SOURCES = {
    "primary_cohort_strength": (
        "evidence/derived/cross_model_strength_2026_09_21.json",
        "42b52a3de86df6790858a3961c9cadc0024ad2735dc190bc92cf5a65f43dd975",
    ),
    "carbon_second_cohort_trials": (
        "outputs/carbon_synthid_v2_fpr_position_independent/trials.jsonl.gz",
        "a299c61368eef4645fb1c09ca01145f4beb3bf672870082c35bd55be38698414",
    ),
    "generator_second_cohort_trials": (
        "outputs/generator_synthid_v2_fpr_position_independent/trials.jsonl.gz",
        "96f6ad073c25ec0e562d4f1d565ac75ffdfd1ca5697d75bfce9e388a4c609977",
    ),
    "carbon_edit_rate": (
        "evidence/derived/edit_rate_v3_carbon_2026_09_24.json",
        "25c90fe505ef1118e2ba01c3a3337b37b7f07f5b1bc67d6a8e05881780806808",
    ),
    "generator_edit_rate": (
        "evidence/derived/edit_rate_v3_generator_2026_09_24.json",
        "3911289bf8b884fce8fab27be143c38f4c4e4359977a0f4a72024cac92f4437f",
    ),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strength(natural_log_p: float) -> float:
    return -natural_log_p / math.log(10.0)


def correct_key_strengths(rows: list[dict[str, Any]]) -> dict[str, list[float]]:
    """Collect correct-key strengths per condition after checking the complete grid."""
    grid: dict[str, dict[tuple[str, int], float]] = {condition: {} for condition in CONDITIONS}
    for row in rows:
        if row["family"] != "watermarked_correct_key":
            continue
        condition = row["condition"]
        if condition not in grid:
            raise ValueError(f"unexpected read condition: {condition}")
        identity = (row["case_id"], row["draw_id"])
        if identity in grid[condition]:
            raise ValueError(f"duplicate correct-key trial: {condition} {identity}")
        grid[condition][identity] = strength(row["minimum_local_log_p_value"])
    values: dict[str, list[float]] = {}
    for condition, cells in grid.items():
        cases = {case for case, _ in cells}
        if len(cases) != EVALUATION_PROMPTS or len(cells) != EVALUATION_PROMPTS * len(DRAWS):
            raise ValueError(f"incomplete prompt/draw grid for {condition}")
        values[condition] = [cells[key] for key in sorted(cells)]
    return values


def summarize(values: list[float]) -> dict[str, Any]:
    return {
        "reads": len(values),
        "minimum": min(values),
        "median": statistics.median(values),
        "maximum": max(values),
    }


def load_rows(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def primary_cohort(path: Path) -> dict[str, Any]:
    source = json.loads(path.read_text(encoding="utf-8"))["data"]
    result = {}
    for model in MODELS:
        detector = source[model]["detector"]
        result[model] = {
            "reads": detector["reads"],
            "median": detector["local_strength_negative_log10_p"]["median"],
            "minimum": detector["local_strength_negative_log10_p"]["minimum"],
            "median_mark_bit_positive_fraction": detector[
                "mark_bit_positive_fraction_in_winning_window"
            ]["median"],
        }
    return result


def correct_key_rates(path: Path) -> dict[tuple[str, float], float]:
    cells = json.loads(path.read_text(encoding="utf-8"))["cells"]
    rates = {}
    for cell in cells:
        if cell["family"] != "watermarked_correct_key" or cell["edit_kind"] == "clean":
            continue
        if cell["detected"] / cell["reads"] != cell["rate"]:
            raise ValueError("edit-rate cell rate differs from its counts")
        rates[(cell["edit_kind"], cell["edit_rate"])] = cell["rate"]
    return rates


def edit_rate_agreement(carbon: Path, generator: Path) -> dict[str, Any]:
    """Largest absolute difference in correct-key detection between the two models."""
    left = correct_key_rates(carbon)
    right = correct_key_rates(generator)
    if set(left) != set(right):
        raise ValueError("the two edit-rate grids differ")
    kind, rate = max(sorted(left), key=lambda key: abs(left[key] - right[key]))
    return {
        "cells_compared": len(left),
        "maximum_absolute_difference": abs(left[(kind, rate)] - right[(kind, rate)]),
        "at": {"edit_kind": kind, "edit_rate": rate},
    }


def derive(paths: dict[str, Path]) -> dict[str, Any]:
    for name, (_, expected) in SOURCES.items():
        if digest(paths[name]) != expected:
            raise ValueError(f"source digest mismatch: {name}")
    second = {}
    for model in MODELS:
        values = correct_key_strengths(load_rows(paths[f"{model}_second_cohort_trials"]))
        second[model] = {condition: summarize(values[condition]) for condition in CONDITIONS}
    return {
        "primary_cohort_clean_correct_key": primary_cohort(paths["primary_cohort_strength"]),
        "second_cohort_correct_key": second,
        "edit_rate_model_agreement": edit_rate_agreement(
            paths["carbon_edit_rate"], paths["generator_edit_rate"]
        ),
        "limits": [
            "Strength is the uncorrected local strength of each read's winning window.",
            "The two draws per prompt are paired; medians and extremes are descriptive.",
            "The edit-rate comparison covers correct-key detection only, over 28 cells.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check", action="store_true", help="verify retained output without writing"
    )
    args = parser.parse_args()
    paths = {name: ROOT / relative for name, (relative, _) in SOURCES.items()}
    data = derive(paths)
    sources = {name: {"path": relative, "sha256": sha} for name, (relative, sha) in SOURCES.items()}
    code = {"scripts/derive_strength_summary.py": digest(Path(__file__))}
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
                "command": "python3 scripts/derive_strength_summary.py",
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
