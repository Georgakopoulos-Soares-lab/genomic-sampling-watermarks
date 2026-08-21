"""Validation of sequential E2 capacity reports before analysis or evidence review."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from genomic_watermarks.metrics import information_bits_per_base
from genomic_watermarks.models.huggingface import POLICIES
from genomic_watermarks.pilot import ContextCase, numeric_summary
from genomic_watermarks.sequential import (
    PATH_SAMPLING_SCHEME,
    PUBLIC_EVALUATION_SCHEME,
    evaluation_partition_domains,
    public_evaluation_material_sha256,
)

_FORBIDDEN_RAW_FIELDS = {
    "key",
    "logits",
    "probabilities",
    "sampled_token",
    "secret_key",
    "sequence",
}
_EXPECTED_DTYPES = {"C_tok": "bfloat16", "G_tok": "float32", "G_bp": "float32"}


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


def _check_summary(observed: Mapping[str, Any], values: Sequence[float], label: str) -> None:
    expected = numeric_summary(values)
    for name, expected_value in expected.items():
        _require(name in observed, f"{label} is missing {name}")
        _require(
            _close(float(observed[name]), expected_value),
            f"{label}.{name} does not match the state values",
        )


def validate_sequential_report(
    report: Mapping[str, Any],
    cohort_cases: Sequence[ContextCase],
    *,
    expected_states_per_prompt: int = 128,
    expected_partitions_per_state: int = 32,
    allow_prompt_subset: bool = False,
) -> dict[str, Any]:
    """Validate protocol shape, cohort identity, values, derivations, and raw-field exclusions."""

    _require(expected_states_per_prompt > 0, "expected states per prompt must be positive")
    _require(expected_partitions_per_state > 0, "expected partitions per state must be positive")
    forbidden = _find_forbidden_fields(report)
    _require(not forbidden, f"report contains forbidden raw field(s): {', '.join(forbidden)}")

    _require(report.get("schema_version") == 1, "unsupported report schema_version")
    _require(
        report.get("classification") == "engineering_pilot_not_paper_evidence",
        "unexpected report classification",
    )
    _require(report.get("complete") is True, "report is not marked complete")
    policy_id = str(report.get("policy_id"))
    _require(policy_id in _EXPECTED_DTYPES, "report policy is not part of the frozen E2 pilot")
    spec = POLICIES[policy_id].policy
    _require(report.get("model_id") == spec.model_id, "model_id does not match the pinned policy")
    _require(report.get("revision") == spec.revision, "revision does not match the pinned policy")
    _require(report.get("device") == "mps", "primary E2 report must use MPS")
    _require(report.get("dtype") == _EXPECTED_DTYPES[policy_id], "dtype violates the E2 policy")
    _require(float(report.get("temperature")) == 1.0, "temperature must equal 1.0")
    _require(report.get("truncation") == "none", "truncation must be disabled")

    cases_by_id = {case.case_id: case for case in cohort_cases}
    _require(len(cases_by_id) == len(cohort_cases), "cohort case IDs must be unique")
    cohort_ids = {case.cohort_id for case in cohort_cases}
    _require(len(cohort_ids) == 1, "cohort cases must share one cohort_id")
    cohort_id = next(iter(cohort_ids))
    _require(report.get("cohort_id") == cohort_id, "cohort_id does not match the cohort file")

    case_ids_value = report.get("case_ids")
    _require(isinstance(case_ids_value, list), "case_ids must be a list")
    case_ids = tuple(str(case_id) for case_id in case_ids_value)
    _require(case_ids, "report must contain at least one case")
    _require(len(set(case_ids)) == len(case_ids), "report case_ids must be unique")
    _require(all(case_id in cases_by_id for case_id in case_ids), "report contains an unknown case")
    cohort_order = tuple(case.case_id for case in cohort_cases)
    if allow_prompt_subset:
        expected_subset_order = tuple(case_id for case_id in cohort_order if case_id in case_ids)
        _require(case_ids == expected_subset_order, "subset cases must retain cohort order")
    else:
        _require(
            case_ids == cohort_order, "report must contain the complete cohort in frozen order"
        )
    _require(int(report.get("case_count")) == len(case_ids), "case_count is inconsistent")
    _require(
        int(report.get("states_per_prompt")) == expected_states_per_prompt,
        "states_per_prompt is inconsistent",
    )
    _require(
        int(report.get("generated_bases_per_prompt")) == expected_states_per_prompt * 6,
        "generated_bases_per_prompt is inconsistent",
    )

    path = report.get("path_sampling")
    _require(isinstance(path, Mapping), "path_sampling must be an object")
    _require(path.get("scheme") == PATH_SAMPLING_SCHEME, "unexpected path sampling scheme")
    _require(path.get("base_seed") == 1729, "unexpected path sampling seed")
    _require(path.get("watermarked") is False, "capacity path must be unwatermarked")

    partition = report.get("partition_evaluation")
    _require(isinstance(partition, Mapping), "partition_evaluation must be an object")
    _require(partition.get("scheme") == PUBLIC_EVALUATION_SCHEME, "unexpected partition scheme")
    _require(
        partition.get("public_material_sha256") == public_evaluation_material_sha256(),
        "public evaluation material identifier does not match",
    )
    _require(
        partition.get("paired_and_reused_across_states") is True,
        "partitions must be paired and reused across states",
    )
    _require(
        int(partition.get("partitions_per_state")) == expected_partitions_per_state,
        "partitions_per_state is inconsistent",
    )
    expected_domains = list(
        evaluation_partition_domains(cohort_id, policy_id, expected_partitions_per_state)
    )
    _require(partition.get("domains") == expected_domains, "partition domains are inconsistent")

    states_value = report.get("states")
    _require(isinstance(states_value, list), "states must be a list")
    expected_state_count = len(case_ids) * expected_states_per_prompt
    _require(len(states_value) == expected_state_count, "state row count is inconsistent")
    _require(int(report.get("state_count")) == expected_state_count, "state_count is inconsistent")
    states_by_case: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    all_information: list[float] = []
    all_entropy: list[float] = []
    all_support: list[float] = []
    all_top1: list[float] = []
    for row in states_value:
        _require(isinstance(row, Mapping), "each state must be an object")
        case_id = str(row.get("case_id"))
        _require(case_id in case_ids, "state references an undeclared case")
        masses = row.get("partition_masses")
        information = row.get("information_bits_per_base")
        _require(isinstance(masses, list), "partition_masses must be a list")
        _require(isinstance(information, list), "information_bits_per_base must be a list")
        _require(len(masses) == expected_partitions_per_state, "partition mass count is wrong")
        _require(len(information) == expected_partitions_per_state, "information count is wrong")
        for mass, bits in zip(masses, information, strict=True):
            mass_value = float(mass)
            bits_value = float(bits)
            _require(
                math.isfinite(mass_value) and 0.0 <= mass_value <= 1.0, "invalid partition mass"
            )
            _require(
                math.isfinite(bits_value) and 0.0 <= bits_value <= 1.0 / 6.0,
                "invalid information value",
            )
            _require(
                _close(bits_value, information_bits_per_base(mass_value)),
                "information value does not match its partition mass",
            )
            all_information.append(bits_value)
        entropy = float(row.get("entropy_bits"))
        support = float(row.get("effective_support"))
        top1 = float(row.get("top1_mass"))
        _require(math.isfinite(entropy) and 0.0 <= entropy <= 12.0, "invalid entropy")
        _require(math.isfinite(support) and 1.0 <= support <= 4096.0, "invalid support")
        _require(math.isfinite(top1) and 0.0 < top1 <= 1.0, "invalid top1 mass")
        all_entropy.append(entropy)
        all_support.append(support)
        all_top1.append(top1)
        states_by_case[case_id].append(row)

    for case_id in case_ids:
        rows = states_by_case[case_id]
        _require(len(rows) == expected_states_per_prompt, f"wrong state count for {case_id}")
        _require(
            [int(row.get("state_index")) for row in rows]
            == list(range(expected_states_per_prompt)),
            f"state indexes are inconsistent for {case_id}",
        )
        initial_bases = len(cases_by_id[case_id].sequence)
        _require(
            [int(row.get("context_bases")) for row in rows]
            == [initial_bases + 6 * index for index in range(expected_states_per_prompt)],
            f"context growth is inconsistent for {case_id}",
        )

    summary = report.get("summary")
    _require(isinstance(summary, Mapping), "summary must be an object")
    _check_summary(
        summary.get("information_bits_per_base", {}), all_information, "information summary"
    )
    _check_summary(summary.get("entropy_bits", {}), all_entropy, "entropy summary")
    _check_summary(summary.get("effective_support", {}), all_support, "support summary")
    _check_summary(summary.get("top1_mass", {}), all_top1, "top1 summary")

    prompt_summaries_value = report.get("prompt_summaries")
    _require(isinstance(prompt_summaries_value, list), "prompt_summaries must be a list")
    prompt_summaries = {str(row.get("case_id")): row for row in prompt_summaries_value}
    _require(tuple(prompt_summaries) == case_ids, "prompt summaries must match case order")
    for case_id in case_ids:
        prompt_summary = prompt_summaries[case_id]
        case = cases_by_id[case_id]
        _require(
            prompt_summary.get("prompt_sequence_sha256") == case.sequence_sha256,
            f"prompt checksum is inconsistent for {case_id}",
        )
        prompt_information = [
            float(value)
            for row in states_by_case[case_id]
            for value in row["information_bits_per_base"]
        ]
        _check_summary(
            prompt_summary.get("information_bits_per_base", {}),
            prompt_information,
            f"prompt summary {case_id}",
        )

    return {
        "valid": True,
        "policy_id": policy_id,
        "cohort_id": cohort_id,
        "case_count": len(case_ids),
        "state_count": expected_state_count,
        "partitions_per_state": expected_partitions_per_state,
        "raw_fields_absent": True,
    }
