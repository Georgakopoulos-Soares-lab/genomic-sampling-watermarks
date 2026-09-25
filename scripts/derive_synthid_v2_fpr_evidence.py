#!/usr/bin/env python3
"""Derive the SynthID v2 false-positive-rate ledger cells from the detector summaries.

The protocol reports an exact one-sided 95% upper bound on the prompt-level rate,
``Beta^{-1}(0.95; positives + 1, prompts - positives)``. The detector summary stores a
two-sided interval, so the one-sided bound is computed here. The regularized incomplete
beta function is implemented directly because the analysis node cannot load SciPy.
"""

from __future__ import annotations

import argparse
import json
from math import exp, lgamma, log
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = Path("/scratch/10899/kimopro/synthid_v2_fpr")
MODELS = ("carbon", "generator")
FAMILY_SUFFIX = {
    "watermarked_correct_key": "correct_key_rate",
    "ordinary_corresponding_key": "ordinary_rate",
    "watermarked_wrong_key": "wrong_key_rate",
}


def betainc_regularized(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b) by the Lentz continued fraction."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    if x > (a + 1.0) / (a + b + 2.0):
        return 1.0 - betainc_regularized(b, a, 1.0 - x)
    log_beta = lgamma(a) + lgamma(b) - lgamma(a + b)
    front = exp(a * log(x) + b * log(1.0 - x) - log_beta)
    f, c, d = 1.0, 1.0, 0.0
    for index in range(400):
        m = index // 2
        if index == 0:
            numerator = 1.0
        elif index % 2 == 0:
            numerator = (m * (b - m) * x) / ((a + 2 * m - 1.0) * (a + 2 * m))
        else:
            numerator = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1.0))
        d = 1.0 + numerator * d
        d = 1.0 / (d if abs(d) > 1e-30 else 1e-30)
        c = 1.0 + numerator / c
        if abs(c) < 1e-30:
            c = 1e-30
        f *= c * d
        if abs(1.0 - c * d) < 1e-15:
            break
    return front * (f - 1.0) / a


def one_sided_upper(positives: int, prompts: int, confidence: float = 0.95) -> float:
    """Exact one-sided Clopper-Pearson upper bound on the prompt-level rate."""
    if positives >= prompts:
        return 1.0
    low, high = 0.0, 1.0
    for _ in range(200):
        middle = (low + high) / 2.0
        if betainc_regularized(positives + 1, prompts - positives, middle) < confidence:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def self_check() -> None:
    """The protocol predeclares these bounds at 1,544 prompts; reproduce them exactly."""
    for positives, expected in ((0, 0.0019384), (8, 0.0093294), (15, 0.0149200)):
        observed = one_sided_upper(positives, 1544)
        if abs(observed - expected) > 5e-7:
            raise AssertionError(
                f"bound self-check failed at {positives} positives: "
                f"{observed:.7f} != {expected:.7f}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=RUN_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    self_check()
    cells: list[dict[str, object]] = []
    for model in MODELS:
        summary = json.loads(
            (args.run_root / model / "position_independent/summary.json").read_text()
        )
        prompts = int(summary["evaluation_prompts"])
        for rate in summary["rates"]:
            prompt = rate["prompt_any_draw"]
            positives = int(prompt["detections"])
            cells.append(
                {
                    "id": f"synthid.v2.{model}.detector."
                    f"{rate['condition']}.{FAMILY_SUFFIX[rate['family']]}",
                    "model": model,
                    "family": rate["family"],
                    "condition": rate["condition"],
                    "read_detections": int(rate["detections"]),
                    "read_trials": int(rate["trials"]),
                    "read_rate": rate["rate"],
                    "prompt_positives": positives,
                    "prompt_clusters": prompts,
                    "prompt_rate": positives / prompts,
                    "prompt_exact_two_sided_95_interval": prompt["exact_95_interval"],
                    "prompt_one_sided_95_upper": one_sided_upper(positives, prompts),
                    "winning_window_base_length_counts": rate[
                        "winning_window_base_length_counts"
                    ],
                    "winning_orientation_counts": rate["winning_orientation_counts"],
                }
            )

    payload = {
        "schema_version": 1,
        "study": "L1-01 SynthID v2 false-positive-rate scaling",
        "evaluation_prompts": 1544,
        "draws_per_prompt": 2,
        "bound_rule": "Beta^{-1}(0.95; positives + 1, prompts - positives); 1 when all positive",
        "prompt_positive_rule": "a prompt is positive when either draw is detected",
        "predeclared_sub_one_percent_threshold_positives": 8,
        "cells": cells,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cells": len(cells), "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
