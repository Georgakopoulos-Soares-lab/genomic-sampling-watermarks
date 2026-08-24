"""Validation of E15 order-sensitive proxy reports before evidence review.

Every summary is recomputed from the stored per-sequence rows, including the exact
paired sign-flip p-value, because that test is the whole result: the relative shifts
in this experiment are large and the p-values are what show the direction is absent.
A report whose magnitudes were right and whose p-values were wrong would invert the
conclusion.

Two checks are specific to this experiment. The reference model must have been fitted
only on prompts no scored sequence came from, or the independent-model score is
circular. And the report must carry its interpretation boundary, because a drop in a
reading frame is the kind of number a reader will otherwise take for biological
damage.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from genomic_watermarks.attacks import BLOCK_SHUFFLE_ATTACK, SHUFFLE_ATTACK, SPLICE_ATTACK
from genomic_watermarks.pilot import ContextCase
from genomic_watermarks.sequence_proxies import PROXY_METRICS, exact_sign_flip_test
from genomic_watermarks.structure_proxies import STRUCTURE_METRICS
from genomic_watermarks.watermark import PARTITION_MC_SCHEME

_POLICIES = ("C_tok", "G_tok", "G_bp")
_FORBIDDEN_RAW_FIELDS = {
    "generated_dna",
    "key",
    "logits",
    "probabilities",
    "sampled_token",
    "secret_key",
    "sequence",
}
_REQUIRED_BOUNDARY_PHRASES = (
    "NOT evidence of functional",
    "not an independent biological model",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _find_forbidden_fields(value: Any, path: str = "report") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key) in _FORBIDDEN_RAW_FIELDS:
                found.append(child_path)
            found.extend(_find_forbidden_fields(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_find_forbidden_fields(child, f"{path}[{index}]"))
    return found


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-11, abs_tol=1e-12)


def validate_structure_report(
    report: Mapping[str, Any],
    cohort_cases: Sequence[ContextCase],
) -> dict[str, Any]:
    """Recompute every summary from the stored rows and check the experiment's premises."""

    forbidden = _find_forbidden_fields(report)
    _require(not forbidden, f"report contains forbidden raw field(s): {', '.join(forbidden)}")

    _require(report.get("schema_version") == 1, "unsupported report schema_version")
    _require(
        report.get("classification") == "engineering_pilot_not_paper_evidence",
        "unexpected report classification",
    )
    _require(report.get("complete") is True, "report is not marked complete")
    _require(report.get("policy_id") in _POLICIES, "report policy is not a primary policy")
    _require(report.get("watermark_method") == PARTITION_MC_SCHEME, "unexpected watermark method")
    _require(
        set(report.get("attacks", ())) == {SHUFFLE_ATTACK, BLOCK_SHUFFLE_ATTACK, SPLICE_ATTACK},
        "unexpected attack set",
    )
    _require(
        list(report.get("composition_metrics", ())) == list(PROXY_METRICS),
        "composition metric list does not match the admitted proxies",
    )
    _require(
        list(report.get("structure_metrics", ())) == list(STRUCTURE_METRICS),
        "structure metric list does not match the declared measures",
    )
    boundary = str(report.get("interpretation_boundary", ""))
    for phrase in _REQUIRED_BOUNDARY_PHRASES:
        _require(phrase in boundary, f"the interpretation boundary must state: {phrase}")

    case_ids = tuple(str(value) for value in report.get("case_ids", ()))
    _require(case_ids, "report must declare at least one prompt")
    _require(int(report.get("case_count")) == len(case_ids), "case_count is inconsistent")
    known = {case.case_id for case in cohort_cases}
    _require(set(case_ids) <= known, "report references a prompt outside the cohort")

    reference = report.get("reference_model")
    _require(isinstance(reference, Mapping), "the reference model description is required")
    held_out = [str(value) for value in reference.get("held_out_prompt_ids", ())]
    _require(held_out, "the reference model must name the prompts it was fitted on")
    overlap = set(held_out) & set(case_ids)
    _require(
        not overlap,
        f"the reference model saw scored prompt(s): {', '.join(sorted(overlap))}",
    )
    _require(
        reference.get("overlaps_scored_prompts") is False,
        "the report must record that the reference does not overlap the scored prompts",
    )
    _require(
        int(reference.get("held_out_prompt_count")) == len(held_out),
        "held-out prompt count is inconsistent",
    )

    orders = tuple(int(value) for value in report.get("markov_orders", ()))
    _require(orders, "at least one Markov order is required")

    rows = report.get("rows")
    _require(isinstance(rows, list) and rows, "rows must be a non-empty list")
    _require(int(report.get("row_count")) == len(rows), "row_count is inconsistent")

    grouped: dict[tuple[str, Any], list[Mapping[str, Any]]] = {}
    for row in rows:
        _require(isinstance(row, Mapping), "each row must be an object")
        attack = str(row.get("attack"))
        _require(attack in {SHUFFLE_ATTACK, BLOCK_SHUFFLE_ATTACK, SPLICE_ATTACK}, "unknown attack")
        for order in orders:
            key = f"structure_order_{order}"
            for block in (key, f"{key}_reference", f"{key}_relative_shift"):
                _require(
                    set(row[block]) == set(STRUCTURE_METRICS),
                    f"{block} does not cover the declared structure metrics",
                )
            for metric in STRUCTURE_METRICS:
                base = abs(float(row[f"{key}_reference"][metric])) or 1.0
                expected = (
                    abs(float(row[key][metric]) - float(row[f"{key}_reference"][metric])) / base
                )
                _require(
                    _close(float(row[f"{key}_relative_shift"][metric]), expected),
                    f"{key} relative shift for {metric} does not match its stored values",
                )
        grouped.setdefault((attack, row.get("parameter")), []).append(row)

    summaries = report.get("summaries")
    _require(isinstance(summaries, list) and summaries, "summaries must be a non-empty list")

    checked: list[dict[str, Any]] = []
    for summary in summaries:
        attack = str(summary["attack"])
        key = (attack, summary["parameter"])
        selected = grouped.get(key)
        _require(bool(selected), f"summary {key} has no stored rows")
        _require(
            int(summary["trials"]) == len(selected), f"summary {key} trial count is inconsistent"
        )
        composition = summary["composition_relative_shift"]
        largest = max(PROXY_METRICS, key=lambda metric: float(composition[metric]["mean"]))
        _require(
            summary["largest_composition_metric"] == largest,
            f"summary {key} names the wrong largest composition metric",
        )
        _require(
            _close(
                float(summary["largest_composition_shift"]),
                float(composition[largest]["mean"]),
            ),
            f"summary {key} largest composition shift is inconsistent",
        )
        for order in orders:
            block = summary[f"structure_order_{order}"]
            for metric in STRUCTURE_METRICS:
                values = [
                    float(row[f"structure_order_{order}_relative_shift"][metric])
                    for row in selected
                ]
                _require(
                    _close(
                        float(block["relative_shift"][metric]["mean"]),
                        math.fsum(values) / len(values),
                    ),
                    f"summary {key} relative shift for {metric} is inconsistent",
                )
            # The sign-flip test is the result, so it is recomputed rather than trusted.
            if attack == SPLICE_ATTACK:
                _require(
                    "sign_flip" not in block,
                    "a splice has no single source sequence, so a paired test is not defined",
                )
                continue
            _require("sign_flip" in block, f"summary {key} is missing its paired test")
            for metric in STRUCTURE_METRICS:
                differences = [
                    float(row[f"structure_order_{order}"][metric])
                    - float(row[f"structure_order_{order}_reference"][metric])
                    for row in selected
                ]
                recomputed = exact_sign_flip_test(differences)
                stored = block["sign_flip"][metric]
                _require(
                    _close(float(stored["p_value"]), float(recomputed["p_value"])),
                    f"summary {key} sign-flip p-value for {metric} is inconsistent",
                )
        first = orders[0]
        block = summary[f"structure_order_{first}"]
        checked.append(
            {
                "attack": attack,
                "parameter": summary["parameter"],
                "trials": len(selected),
                "largest_composition_shift": float(summary["largest_composition_shift"]),
                "longest_orf_relative_shift": float(
                    block["relative_shift"]["longest_orf_bases"]["mean"]
                ),
                "longest_orf_sign_flip_p_value": (
                    float(block["sign_flip"]["longest_orf_bases"]["p_value"])
                    if "sign_flip" in block
                    else None
                ),
                "independent_model_relative_shift": float(
                    block["relative_shift"]["independent_model_mean_log2_probability"]["mean"]
                ),
            }
        )

    directional = [
        row
        for row in checked
        if row["longest_orf_sign_flip_p_value"] is not None
        and row["longest_orf_sign_flip_p_value"] <= 0.05
    ]
    return {
        "valid": True,
        "policy_id": report["policy_id"],
        "cohort_id": report["cohort_id"],
        "prompt_count": len(case_ids),
        "reference_held_out": True,
        "reference_prompt_count": len(held_out),
        "markov_orders": list(orders),
        "row_count": len(rows),
        "raw_fields_absent": True,
        "conditions_with_directional_orf_effect": len(directional),
        "largest_independent_model_shift": max(
            row["independent_model_relative_shift"] for row in checked
        ),
        "conditions": checked,
    }
