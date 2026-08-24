"""Validation of E11/E12 key-reuse attack reports before evidence review.

Every aggregate is recomputed from the stored per-trial rows, and every statistic is
re-derived from the match count it was built from.

Two checks here exist only for this experiment. First, the attacked sequences must be
scored against a threshold calibrated on the *unattacked* null families, because a
threshold calibrated on attacked material would measure something else. Second, the
report must state which direction each family's detection rate points: a high rate is
a vulnerability for the spoofing family and a failed attack for the removal families,
and a table that does not say so invites the reader to average them.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from genomic_watermarks.attacks import BLOCK_SHUFFLE_ATTACK, SHUFFLE_ATTACK, SPLICE_ATTACK
from genomic_watermarks.detector.search import (
    DECISION_RULE,
    ORIENTATIONS,
    calibrate_threshold,
    detection_rate,
    empirical_p_value,
    joint_detection_rate_interval,
    standardized_agreement,
)
from genomic_watermarks.dna import KMER_SIZE
from genomic_watermarks.pilot import ContextCase
from genomic_watermarks.watermark import ORDINARY_SCHEME, PARTITION_MC_SCHEME

POOLED_FAMILIES = ("wrong_key_watermarked", "any_key_ordinary")
GENUINE_FAMILY = "genuine"
SPOOF_FAMILY = "spoof"
REMOVAL_FAMILY = "removal"
FIXED_KEY_FAMILIES = ("fixed_key_many_query_ordinary", "fixed_key_many_query_public_dna")
FAMILIES = (
    GENUINE_FAMILY,
    SPOOF_FAMILY,
    REMOVAL_FAMILY,
    *FIXED_KEY_FAMILIES,
    *POOLED_FAMILIES,
)
# A high detection rate means the opposite thing for these two families, which is why
# they may never share an axis or be averaged together.
HIGH_RATE_IS_BAD = (SPOOF_FAMILY,)
HIGH_RATE_IS_GOOD = (GENUINE_FAMILY,)

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


def validate_attack_report(
    report: Mapping[str, Any],
    cohort_cases: Sequence[ContextCase],
    *,
    expected_offsets: int = 8,
    expected_null_keys: int = 20,
    expected_target_fpr: float = 0.01,
) -> dict[str, Any]:
    """Validate the attacker model, the shared calibration, and every reported cell."""

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
    _require(report.get("control_method") == ORDINARY_SCHEME, "unexpected control method")
    _require(report.get("decision_rule") == DECISION_RULE, "unexpected decision rule")
    _require(report.get("key_source") == "public_fixture", "unexpected key source")
    _require(int(report.get("null_keys")) == expected_null_keys, "null key count is inconsistent")
    _require(int(report.get("support_size")) == 4096, "the declared support must be 4,096 tokens")
    _require(
        set(report.get("attacks", ())) == {SPLICE_ATTACK, SHUFFLE_ATTACK, BLOCK_SHUFFLE_ATTACK},
        "unexpected attack set",
    )
    knowledge = str(report.get("attacker_knowledge", ""))
    for phrase in ("never queries the model", "never observes the key"):
        _require(phrase in knowledge, f"the attacker model must state that it {phrase}")
    _require(
        "vulnerability" in str(report.get("sign_of_the_result", "")),
        "the report must state that a high spoofing detection rate is a vulnerability",
    )

    search = report.get("detector_search")
    _require(isinstance(search, Mapping), "detector_search must be an object")
    _require(
        list(search.get("orientations")) == list(ORIENTATIONS), "both strands must be searched"
    )
    _require(
        list(search.get("phases")) == list(range(KMER_SIZE)), "all six phases must be searched"
    )
    _require(
        search.get("window_tokens") == "full_sequence_only",
        "this experiment declares no sliding windows",
    )
    offsets = list(search.get("stream_offsets"))
    _require(offsets == list(range(expected_offsets)), "stream offsets are inconsistent")
    minimum_window = int(search.get("minimum_window_tokens", 16))

    def expected_hypotheses_at(token_length: int) -> int:
        scorable = sum(
            1
            for phase in range(KMER_SIZE)
            if (token_length if phase == 0 else token_length - 1) >= minimum_window
        )
        return len(ORIENTATIONS) * scorable * len(offsets)

    cohort_ids = {case.cohort_id for case in cohort_cases}
    _require(len(cohort_ids) == 1, "cohort cases must share one cohort_id")
    _require(report.get("cohort_id") == next(iter(cohort_ids)), "cohort_id does not match the file")
    case_ids = tuple(str(value) for value in report.get("case_ids", ()))
    _require(case_ids, "report must declare at least one prompt")
    _require(len(set(case_ids)) == len(case_ids), "case_ids must be unique")
    _require(int(report.get("case_count")) == len(case_ids), "case_count is inconsistent")
    _require(
        int(report.get("outputs_available_to_attacker")) == len(case_ids),
        "the attacker's output budget must equal the number of watermarked outputs",
    )
    donor_counts = tuple(int(v) for v in report.get("donor_counts", ()))
    _require(donor_counts and min(donor_counts) >= 2, "splicing needs at least two donors")
    _require(max(donor_counts) <= len(case_ids), "a donor count exceeds the available output count")
    block_widths = tuple(int(v) for v in report.get("block_widths", ()))
    _require(block_widths and min(block_widths) >= 2, "block widths must be at least two tokens")

    token_lengths = tuple(int(v) for v in report.get("token_lengths", ()))
    _require(token_lengths, "at least one evaluated length is required")
    _require(list(token_lengths) == sorted(set(token_lengths)), "evaluated lengths must be sorted")

    trials = report.get("trials")
    _require(isinstance(trials, list) and trials, "trials must be a non-empty list")
    _require(int(report.get("trial_count")) == len(trials), "trial_count is inconsistent")

    grouped: dict[tuple[int, str, Any, Any], list[Mapping[str, Any]]] = {}
    for row in trials:
        _require(isinstance(row, Mapping), "each trial must be an object")
        family = str(row.get("family"))
        _require(family in FAMILIES, f"unknown trial family {family}")
        _require(str(row.get("cluster")) in case_ids, "trial references an undeclared prompt")
        length = int(row.get("token_length"))
        _require(length in token_lengths, "trial uses an undeclared length")
        _require(
            int(row.get("base_length")) == length * KMER_SIZE, "trial base length is inconsistent"
        )
        _require(
            int(row.get("hypotheses_searched")) == expected_hypotheses_at(length),
            "trial did not search the declared hypothesis count",
        )
        total = int(row.get("total"))
        matches = int(row.get("matches"))
        phase = int(row.get("phase"))
        _require(0 <= phase < KMER_SIZE, "trial phase is invalid")
        _require(
            total == (length if phase == 0 else length - 1),
            "trial token total does not match its length and phase",
        )
        _require(0 <= matches <= total, "invalid match count")
        _require(
            _close(float(row.get("statistic")), standardized_agreement(matches, total)),
            "trial statistic does not match its stored match count",
        )
        _require(row.get("orientation") in ORIENTATIONS, "trial orientation is invalid")
        _require(int(row.get("stream_offset")) in offsets, "trial offset is outside the search")
        if family in POOLED_FAMILIES:
            key_index = row.get("key_index")
            _require(
                isinstance(key_index, int) and 0 <= key_index < expected_null_keys,
                "null trial key index is outside the declared key set",
            )
        else:
            _require(
                row.get("key_index") is None,
                "only the wrong-key null families may carry a key index",
            )
        grouped.setdefault((length, family, row.get("attack"), row.get("parameter")), []).append(
            row
        )

    for length in token_lengths:
        for family in POOLED_FAMILIES:
            _require(
                len(grouped.get((length, family, None, None), []))
                == len(case_ids) * expected_null_keys,
                f"{family} trial count is inconsistent at length {length}",
            )
        _require(
            len(grouped.get((length, GENUINE_FAMILY, None, None), [])) == len(case_ids),
            f"one genuine trial per prompt is required at length {length}",
        )

    lengths_value = report.get("lengths")
    _require(isinstance(lengths_value, list) and lengths_value, "lengths must be a non-empty list")
    replicates = int(report["bootstrap_replicates"])
    seed = int(report["bootstrap_seed"])

    summary: list[dict[str, Any]] = []
    for entry in lengths_value:
        length = int(entry["token_length"])
        pooled = [
            float(row["statistic"])
            for family in POOLED_FAMILIES
            for row in grouped[(length, family, None, None)]
        ]
        calibration = calibrate_threshold(pooled, expected_target_fpr)
        reported = entry["calibration"]
        _require(
            list(reported["pooled_null_families"]) == list(POOLED_FAMILIES),
            "the threshold must be calibrated on the unattacked null families only",
        )
        for name, expected_value in (
            ("target_false_positive_rate", expected_target_fpr),
            ("threshold", calibration.threshold),
            ("achieved_false_positive_rate", calibration.achieved_false_positive_rate),
            ("attainable_false_positive_rate", calibration.attainable_false_positive_rate),
        ):
            _require(
                _close(float(reported[name]), expected_value),
                f"calibration {name} is inconsistent at length {length}",
            )
        _require(
            calibration.achieved_false_positive_rate <= expected_target_fpr,
            f"the calibrated threshold does not meet its target at length {length}",
        )

        rows_out: list[dict[str, Any]] = []
        for cell in entry["cells"]:
            key = (length, str(cell["family"]), cell["attack"], cell["parameter"])
            rows = grouped.get(key)
            _require(bool(rows), f"reported cell {key} has no stored trials")
            values = [float(row["statistic"]) for row in rows]
            _require(int(cell["trials"]) == len(values), f"cell {key} trial count is inconsistent")
            expected_rate = detection_rate(values, calibration.threshold)
            _require(
                _close(float(cell["detection_rate"]), expected_rate),
                f"cell {key} detection rate is inconsistent",
            )
            _require(
                _close(
                    float(cell["maximum_empirical_global_p_value"]),
                    max(empirical_p_value(value, pooled) for value in values),
                ),
                f"cell {key} global p-value is inconsistent",
            )
            interval = cell.get("detection_rate_joint_interval")
            if interval is not None:
                by_cluster: dict[str, list[float]] = {}
                for row in rows:
                    by_cluster.setdefault(str(row["cluster"]), []).append(float(row["statistic"]))
                recomputed = joint_detection_rate_interval(
                    by_cluster, pooled, expected_target_fpr, replicates=replicates, seed=seed
                )
                _require(
                    float(interval["resamples_the_threshold"]) == 1.0,
                    "the interval must resample the calibrated threshold",
                )
                for name in ("detection_rate", "lower", "upper"):
                    _require(
                        _close(float(interval[name]), recomputed[name]),
                        f"cell {key} interval {name} is inconsistent",
                    )
            rows_out.append(
                {
                    "family": cell["family"],
                    "attack": cell["attack"],
                    "parameter": cell["parameter"],
                    "trials": len(values),
                    "detection_rate": expected_rate,
                    "mean_statistic": math.fsum(values) / len(values),
                    "detection_rate_lower": (interval or {}).get("lower"),
                    "detection_rate_upper": (interval or {}).get("upper"),
                    "high_rate_means": (
                        "vulnerability"
                        if cell["family"] in HIGH_RATE_IS_BAD
                        else "intended detection"
                        if cell["family"] in HIGH_RATE_IS_GOOD
                        else "failed attack"
                        if cell["family"] == REMOVAL_FAMILY
                        else "false positive"
                    ),
                }
            )

        genuine = next(r for r in rows_out if r["family"] == GENUINE_FAMILY)
        spoofs = [r for r in rows_out if r["family"] == SPOOF_FAMILY]
        summary.append(
            {
                "token_length": length,
                "base_length": length * KMER_SIZE,
                "threshold": calibration.threshold,
                "achieved_false_positive_rate": calibration.achieved_false_positive_rate,
                "genuine_detection_rate": genuine["detection_rate"],
                "spoof_detection_rate_minimum": min(r["detection_rate"] for r in spoofs)
                if spoofs
                else None,
                "spoof_matches_genuine": all(
                    r["detection_rate"] >= genuine["detection_rate"] for r in spoofs
                )
                if spoofs
                else None,
                "cells": rows_out,
            }
        )

    utility = report.get("utility_rows")
    _require(isinstance(utility, list) and utility, "utility rows are required")
    proxies = tuple(report.get("proxy_metrics", ()))
    _require(proxies, "the proxy metric list is required")
    for row in utility:
        _require(
            set(row["proxies"]) == set(proxies) and set(row["reference_proxies"]) == set(proxies),
            "a utility row does not cover the declared proxy metrics",
        )

    return {
        "valid": True,
        "policy_id": report["policy_id"],
        "cohort_id": report["cohort_id"],
        "prompt_count": len(case_ids),
        "outputs_available_to_attacker": len(case_ids),
        "null_keys": expected_null_keys,
        "target_false_positive_rate": expected_target_fpr,
        "threshold_calibrated_on_unattacked_nulls": True,
        "trial_count": len(trials),
        "utility_rows": len(utility),
        "raw_fields_absent": True,
        "lengths": summary,
    }
