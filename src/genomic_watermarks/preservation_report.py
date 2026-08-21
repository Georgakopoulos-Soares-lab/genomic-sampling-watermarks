"""Validation of E3 stage-1 distribution-preservation reports before evidence review."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from genomic_watermarks.gof import summarize_p_values
from genomic_watermarks.models.huggingface import POLICIES
from genomic_watermarks.pilot import ContextCase
from genomic_watermarks.watermark import ORDINARY_SCHEME, PARTITION_MC_SCHEME

ARMS = ("watermarked", "ordinary")

_FORBIDDEN_RAW_FIELDS = {
    "key",
    "logits",
    "probabilities",
    "sampled_token",
    "secret_key",
    "sequence",
    "tokens",
}
_EXPECTED_DTYPES = {"C_tok": "bfloat16", "G_tok": "float32", "G_bp": "float32"}
_ALPHA = 0.05


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


def validate_preservation_report(
    report: Mapping[str, Any],
    cohort_cases: Sequence[ContextCase],
    *,
    expected_draws: int = 8_000,
    expected_replicates: int = 999,
    expected_seed: int = 2718,
) -> dict[str, Any]:
    """Validate protocol shape, cohort identity, p-value bounds, and family summaries."""

    _require(expected_draws > 0, "expected draws must be positive")
    _require(expected_replicates > 0, "expected replicates must be positive")
    forbidden = _find_forbidden_fields(report)
    _require(not forbidden, f"report contains forbidden raw field(s): {', '.join(forbidden)}")

    _require(report.get("schema_version") == 1, "unsupported report schema_version")
    _require(
        report.get("classification") == "engineering_pilot_not_paper_evidence",
        "unexpected report classification",
    )
    _require(report.get("complete") is True, "report is not marked complete")
    _require(
        report.get("watermark_method") == PARTITION_MC_SCHEME,
        "unexpected watermark method",
    )
    _require(report.get("control_method") == ORDINARY_SCHEME, "unexpected control method")
    _require(
        report.get("key_source") == "public_fixture",
        "stage-1 must declare the published fixture key, never runtime secret material",
    )

    policy_id = str(report.get("policy_id"))
    _require(policy_id in _EXPECTED_DTYPES, "report policy is not part of the E3 stage-1 shape")
    spec = POLICIES[policy_id].policy
    _require(report.get("model_id") == spec.model_id, "model_id does not match the pinned policy")
    _require(report.get("revision") == spec.revision, "revision does not match the pinned policy")
    _require(report.get("device") == "mps", "primary E3 report must use MPS")
    _require(report.get("dtype") == _EXPECTED_DTYPES[policy_id], "dtype violates the E3 shape")
    _require(float(report.get("temperature")) == 1.0, "temperature must equal 1.0")
    _require(report.get("truncation") == "none", "truncation must be disabled")

    test = report.get("test")
    _require(isinstance(test, Mapping), "test must be an object")
    _require(
        int(test.get("draws_per_state_and_arm")) == expected_draws,
        "draws per state and arm is inconsistent",
    )
    _require(int(test.get("replicates")) == expected_replicates, "replicates is inconsistent")
    _require(int(test.get("seed")) == expected_seed, "Monte Carlo seed is inconsistent")

    cases_by_id = {case.case_id: case for case in cohort_cases}
    _require(len(cases_by_id) == len(cohort_cases), "cohort case IDs must be unique")
    cohort_ids = {case.cohort_id for case in cohort_cases}
    _require(len(cohort_ids) == 1, "cohort cases must share one cohort_id")
    _require(report.get("cohort_id") == next(iter(cohort_ids)), "cohort_id does not match the file")

    case_ids_value = report.get("case_ids")
    _require(isinstance(case_ids_value, list), "case_ids must be a list")
    case_ids = tuple(str(case_id) for case_id in case_ids_value)
    _require(case_ids, "report must contain at least one state")
    _require(len(set(case_ids)) == len(case_ids), "report case_ids must be unique")
    _require(all(case_id in cases_by_id for case_id in case_ids), "report contains an unknown case")
    cohort_order = tuple(case.case_id for case in cohort_cases if case.case_id in case_ids)
    _require(case_ids == cohort_order, "report states must retain cohort order")
    _require(int(report.get("case_count")) == len(case_ids), "case_count is inconsistent")

    states_value = report.get("states")
    _require(isinstance(states_value, list), "states must be a list")
    _require(len(states_value) == len(case_ids), "one state row per case is required")
    p_values: dict[str, dict[str, float]] = {arm: {} for arm in ARMS}
    for row, case_id in zip(states_value, case_ids, strict=True):
        _require(isinstance(row, Mapping), "each state must be an object")
        _require(str(row.get("case_id")) == case_id, "state order does not match case_ids")
        case = cases_by_id[case_id]
        _require(
            row.get("prompt_sequence_sha256") == case.sequence_sha256,
            f"prompt checksum is inconsistent for {case_id}",
        )
        _require(
            int(row.get("context_bases")) == len(case.sequence),
            f"context length is inconsistent for {case_id}",
        )
        _require(
            int(row.get("draws_per_arm")) == expected_draws,
            f"draws per arm is inconsistent for {case_id}",
        )
        agreement = float(row.get("watermarked_agreement_rate"))
        _require(
            math.isfinite(agreement) and 0.0 <= agreement <= 1.0,
            f"invalid agreement rate for {case_id}",
        )
        entropy = float(row.get("entropy_bits"))
        support = float(row.get("effective_support"))
        top1 = float(row.get("top1_mass"))
        _require(math.isfinite(entropy) and 0.0 <= entropy <= 12.0, f"invalid entropy {case_id}")
        _require(math.isfinite(support) and 1.0 <= support <= 4096.0, f"invalid support {case_id}")
        _require(math.isfinite(top1) and 0.0 < top1 <= 1.0, f"invalid top1 mass {case_id}")
        _require(int(row.get("categories")) == 4096, "the declared support must be 4,096 tokens")
        for arm in ARMS:
            outcome = row.get(arm)
            _require(isinstance(outcome, Mapping), f"{arm} outcome must be an object for {case_id}")
            statistic = float(outcome.get("statistic"))
            p_value = float(outcome.get("p_value"))
            _require(
                math.isfinite(statistic) and statistic >= 0.0,
                f"invalid {arm} statistic for {case_id}",
            )
            _require(
                math.isfinite(p_value) and 0.0 < p_value <= 1.0,
                f"invalid {arm} p-value for {case_id}",
            )
            _require(
                _close(
                    p_value, round(p_value * (expected_replicates + 1)) / (expected_replicates + 1)
                ),
                f"{arm} p-value for {case_id} is not a Monte Carlo lattice value",
            )
            _require(
                p_value >= 1.0 / (expected_replicates + 1),
                f"{arm} p-value for {case_id} is below the Monte Carlo floor",
            )
            distinct = int(outcome.get("distinct_tokens"))
            _require(
                0 < distinct <= expected_draws,
                f"invalid {arm} distinct token count for {case_id}",
            )
            p_values[arm][case_id] = p_value

    for arm in ARMS:
        observed = report.get(f"{arm}_p_value_family")
        _require(isinstance(observed, Mapping), f"{arm}_p_value_family must be an object")
        expected = summarize_p_values(p_values[arm], _ALPHA)
        for name, expected_value in expected.items():
            _require(name in observed, f"{arm} family summary is missing {name}")
            _require(
                _close(float(observed[name]), expected_value),
                f"{arm} family summary {name} does not match the state p-values",
            )

    return {
        "valid": True,
        "policy_id": policy_id,
        "cohort_id": report["cohort_id"],
        "state_count": len(case_ids),
        "draws_per_state_and_arm": expected_draws,
        "replicates": expected_replicates,
        "monte_carlo_seed": expected_seed,
        "alpha": _ALPHA,
        "bonferroni_alpha": _ALPHA / len(case_ids),
        "watermarked_rejections_at_alpha": int(
            sum(value < _ALPHA for value in p_values["watermarked"].values())
        ),
        "watermarked_rejections_at_bonferroni": int(
            sum(value < _ALPHA / len(case_ids) for value in p_values["watermarked"].values())
        ),
        "ordinary_rejections_at_alpha": int(
            sum(value < _ALPHA for value in p_values["ordinary"].values())
        ),
        "ordinary_rejections_at_bonferroni": int(
            sum(value < _ALPHA / len(case_ids) for value in p_values["ordinary"].values())
        ),
        "watermarked_minimum_p_value": min(p_values["watermarked"].values()),
        "ordinary_minimum_p_value": min(p_values["ordinary"].values()),
        "raw_fields_absent": True,
    }
