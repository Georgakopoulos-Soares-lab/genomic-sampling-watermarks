"""Deterministic summaries of stored trials for the dual-model manuscript.

No model inference or detector search is performed here. Source-artifact hashes
and the stored binomial tails are checked by the analysis entry point.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from typing import Any

CONDITIONS = ("clean", "substitution_1nt", "insertion_1nt", "deletion_1nt")
FAMILIES = (
    "watermarked_correct_key",
    "ordinary_corresponding_key",
    "watermarked_wrong_key",
)
WINDOW_LENGTHS = (384, 768, 1536, 3072)


def quality_summary(source: dict[str, Any]) -> dict[str, Any]:
    """Rescale stored raw bootstrap bounds by the Carbon figure convention.

    These are raw-effect intervals expressed in observed standard-deviation units,
    not a new bootstrap that re-estimates the standard deviation in every replicate.
    """
    rows = []
    for name in source["multiple_testing_family"]:
        paired = source["main_key_averaged"][name]["paired"]
        difference = paired["mean_difference"]
        effect = paired["standardized_effect"]
        if difference == 0:
            raise ValueError(f"cannot recover the standardization scale for {name}")
        scale = effect / difference
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError(f"invalid standardization scale for {name}")
        lower = paired["interval_lower"] * scale
        upper = paired["interval_upper"] * scale
        if not all(math.isfinite(x) for x in (effect, lower, upper)) or lower > upper:
            raise ValueError(f"invalid interval for {name}")
        rows.append(
            {
                "metric": name,
                "standardized_effect": effect,
                "mean_difference": difference,
                "standardization_scale": scale,
                "interval_lower": lower,
                "interval_upper": upper,
                "benjamini_hochberg_p_value": paired["benjamini_hochberg_p_value"],
            }
        )
    if len(rows) != 14 or len({row["metric"] for row in rows}) != 14:
        raise ValueError("expected the 14 distinct pre-specified sequence measures")
    score = source["main_key_averaged"]["mean_negative_log_likelihood_per_token"]
    largest = max(rows, key=lambda row: abs(row["standardized_effect"]))
    return {
        "rows": rows,
        "difference": score["paired"]["mean_difference"],
        "interval": [score["paired"]["interval_lower"], score["paired"]["interval_upper"]],
        "p_value": score["paired"]["p_value"],
        "ordinary_mean": score["ordinary"]["mean"],
        "watermarked_mean": score["watermarked"]["mean"],
        "prompts": source["prompt_count"],
        "pairs": source["pair_count"],
        "largest_absolute_effect": abs(largest["standardized_effect"]),
        "largest_absolute_effect_metric": largest["metric"],
    }


def detection_summary(
    trials: list[dict[str, Any]],
    source: dict[str, Any],
) -> dict[str, Any]:
    """Summarize complete trial grids without pooling draws or edit conditions.

    Mark bits' logarithmic tail is used even when its ordinary probability has
    underflowed to zero. Prompt intervals are retained from the checked source.
    """
    prompt_ids = {row["case_id"] for row in trials}
    expected = {
        (case_id, draw, condition, family)
        for case_id in prompt_ids
        for draw in (0, 1)
        for condition in CONDITIONS
        for family in FAMILIES
    }
    identities = [
        (row["case_id"], row["draw_id"], row["condition"], row["family"]) for row in trials
    ]
    if len(prompt_ids) != source["evaluation_prompts"]:
        raise ValueError("prompt count differs from the source summary")
    if len(identities) != len(expected) or set(identities) != expected:
        raise ValueError("duplicate or incomplete trial grid")
    cells = {(cell["condition"], cell["family"]): cell for cell in source["rates"]}
    if len(source["rates"]) != 12 or set(cells) != {
        (condition, family) for condition in CONDITIONS for family in FAMILIES
    }:
        raise ValueError("duplicate or incomplete summary grid")

    result: dict[str, Any] = {}
    for condition in CONDITIONS:
        result[condition] = {}
        for family in FAMILIES:
            selected = [
                row for row in trials if row["condition"] == condition and row["family"] == family
            ]
            windows = {row["hypotheses_searched"] for row in selected}
            targets = {row["target_false_positive_rate"] for row in selected}
            if len(windows) != 1 or len(targets) != 1:
                raise ValueError("inconsistent threshold within a condition")
            window_count = windows.pop()
            target = targets.pop()
            by_prompt: dict[str, list[bool]] = defaultdict(list)
            strengths = []
            for row in selected:
                local_log_p = row["minimum_local_log_p_value"]
                if not math.isfinite(local_log_p) or local_log_p > 0:
                    raise ValueError("invalid local log probability")
                corrected = min(0.0, local_log_p + math.log(window_count))
                if not math.isclose(corrected, row["sequence_log_p_value"], abs_tol=1e-10):
                    raise ValueError("full-search correction does not match stored result")
                if row["detected"] != (corrected <= math.log(target)):
                    raise ValueError("decision does not match the corrected threshold")
                by_prompt[row["case_id"]].append(row["detected"])
                strengths.append(-local_log_p / math.log(10.0))
            positive = sum(
                all(draws) if family == FAMILIES[0] else any(draws) for draws in by_prompt.values()
            )
            prompt_field = "prompt_both_draws" if family == FAMILIES[0] else "prompt_any_draw"
            cell = cells[condition, family]
            record = cell[prompt_field]
            if record["detections"] != positive or record["trials"] != len(by_prompt):
                raise ValueError("prompt-level rate does not match stored summary")
            detections = sum(row["detected"] for row in selected)
            if cell["detections"] != detections or cell["trials"] != len(selected):
                raise ValueError("read-level rate does not match stored summary")
            lengths = Counter(row["best_hypothesis"]["window_base_length"] for row in selected)
            if set(lengths) - set(WINDOW_LENGTHS):
                raise ValueError("unexpected strongest-window length")
            if {str(k): v for k, v in lengths.items()} != cell["winning_window_base_length_counts"]:
                raise ValueError("strongest-window counts do not match source summary")
            result[condition][family] = {
                "trials": len(selected),
                "detections": detections,
                "windows_searched": window_count,
                "threshold_strength": math.log10(window_count / target),
                "minimum": min(strengths),
                "median": statistics.median(strengths),
                "maximum": max(strengths),
                "window_base_length_counts": {str(k): lengths[k] for k in WINDOW_LENGTHS},
                "prompt_event": prompt_field,
                "positive_prompts": positive,
                "prompts": len(by_prompt),
                "percent": 100.0 * positive / len(by_prompt),
                "exact_95_percent_interval": [100.0 * x for x in record["exact_95_interval"]],
            }
    return result
