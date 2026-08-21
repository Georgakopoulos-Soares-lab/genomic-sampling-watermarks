"""Validation of E4 clean-detection reports before evidence review.

Every aggregate in the report is recomputed from its stored per-trial rows, so an
aggregation mistake cannot pass review. The detector itself is deterministic and
model-free, so a reviewer can also rerun the whole pilot from the sequences file.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from genomic_watermarks.cluster_analysis import analyze_prompt_clusters
from genomic_watermarks.detector.search import (
    ORIENTATIONS,
    calibrate_threshold,
    detection_rate,
    empirical_p_value,
    standardized_agreement,
)
from genomic_watermarks.dna import KMER_SIZE
from genomic_watermarks.pilot import ContextCase
from genomic_watermarks.watermark import ORDINARY_SCHEME, PARTITION_MC_SCHEME

POSITIVE_FAMILY = "positive"
NULL_FAMILIES = ("wrong_key_watermarked", "any_key_ordinary", "any_key_public_dna")
POOLED_FAMILIES = ("wrong_key_watermarked", "any_key_ordinary")
FAMILIES = (POSITIVE_FAMILY, *NULL_FAMILIES)

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


def validate_detection_report(
    report: Mapping[str, Any],
    cohort_cases: Sequence[ContextCase],
    *,
    expected_offsets: int = 8,
    expected_null_keys: int = 20,
    expected_target_fpr: float = 0.01,
) -> dict[str, Any]:
    """Validate the declared search, trial bookkeeping, and every reported aggregate."""

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
    _require(report.get("key_source") == "public_fixture", "unexpected key source")
    _require(report.get("null_key_source") == "public_fixture_labels", "unexpected null key source")
    _require(int(report.get("null_keys")) == expected_null_keys, "null key count is inconsistent")
    _require(int(report.get("support_size")) == 4096, "the declared support must be 4,096 tokens")

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
        "this pilot declares no sliding windows",
    )
    offsets = list(search.get("stream_offsets"))
    _require(offsets == list(range(expected_offsets)), "stream offsets are inconsistent")
    expected_hypotheses = len(ORIENTATIONS) * KMER_SIZE * len(offsets)

    cohort_ids = {case.cohort_id for case in cohort_cases}
    _require(len(cohort_ids) == 1, "cohort cases must share one cohort_id")
    _require(report.get("cohort_id") == next(iter(cohort_ids)), "cohort_id does not match the file")
    cases_by_id = {case.case_id: case for case in cohort_cases}
    case_ids = tuple(str(case_id) for case_id in report.get("case_ids", ()))
    _require(case_ids, "report must declare at least one prompt")
    _require(len(set(case_ids)) == len(case_ids), "case_ids must be unique")
    _require(all(case_id in cases_by_id for case_id in case_ids), "report contains an unknown case")
    _require(int(report.get("case_count")) == len(case_ids), "case_count is inconsistent")

    token_lengths = tuple(int(value) for value in report.get("token_lengths", ()))
    _require(token_lengths, "at least one evaluated length is required")
    _require(list(token_lengths) == sorted(set(token_lengths)), "evaluated lengths must be sorted")
    generated = int(report.get("generated_tokens_per_case"))
    _require(max(token_lengths) <= generated, "an evaluated length exceeds the generated length")

    trials = report.get("trials")
    _require(isinstance(trials, list) and trials, "trials must be a non-empty list")
    _require(int(report.get("trial_count")) == len(trials), "trial_count is inconsistent")
    grouped: dict[tuple[int, str], list[Mapping[str, Any]]] = {
        (length, family): [] for length in token_lengths for family in FAMILIES
    }
    for row in trials:
        _require(isinstance(row, Mapping), "each trial must be an object")
        family = str(row.get("family"))
        _require(family in FAMILIES, f"unknown trial family {family}")
        case_id = str(row.get("case_id"))
        _require(case_id in case_ids, "trial references an undeclared prompt")
        length = int(row.get("token_length"))
        _require(length in token_lengths, "trial uses an undeclared length")
        _require(
            int(row.get("base_length")) == length * KMER_SIZE,
            "trial base length is inconsistent",
        )
        _require(
            int(row.get("hypotheses_searched")) == expected_hypotheses,
            "trial did not search the declared hypothesis count",
        )
        total = int(row.get("total"))
        matches = int(row.get("matches"))
        phase = int(row.get("phase"))
        _require(0 <= phase < KMER_SIZE, "trial phase is invalid")
        # A phase-shifted read of an L-token prefix loses its final incomplete k-mer.
        expected_total = length if phase == 0 else length - 1
        _require(
            total == expected_total,
            "trial token total does not match its length and phase",
        )
        _require(0 <= matches <= total, "invalid match count")
        _require(
            _close(float(row.get("statistic")), standardized_agreement(matches, total)),
            "trial statistic does not match its match count",
        )
        _require(row.get("orientation") in ORIENTATIONS, "trial orientation is invalid")
        _require(int(row.get("stream_offset")) in offsets, "trial offset is outside the search")
        key_index = row.get("key_index")
        if family == POSITIVE_FAMILY:
            _require(key_index is None, "positive trials must not carry a null key index")
        else:
            _require(
                isinstance(key_index, int) and 0 <= key_index < expected_null_keys,
                "null trial key index is outside the declared key set",
            )
        grouped[(length, family)].append(row)

    for length in token_lengths:
        _require(
            len(grouped[(length, POSITIVE_FAMILY)]) == len(case_ids),
            f"one positive trial per prompt is required at length {length}",
        )
        for family in POOLED_FAMILIES:
            _require(
                len(grouped[(length, family)]) == len(case_ids) * expected_null_keys,
                f"{family} trial count is inconsistent at length {length}",
            )

    lengths_value = report.get("lengths")
    _require(isinstance(lengths_value, list), "lengths must be a list")
    _require(
        [int(entry["token_length"]) for entry in lengths_value] == list(token_lengths),
        "reported lengths do not match the declared lengths",
    )

    summary: list[dict[str, Any]] = []
    for entry in lengths_value:
        length = int(entry["token_length"])
        pooled = [
            float(row["statistic"])
            for family in POOLED_FAMILIES
            for row in grouped[(length, family)]
        ]
        positives = [float(row["statistic"]) for row in grouped[(length, POSITIVE_FAMILY)]]
        calibration = calibrate_threshold(pooled, expected_target_fpr)
        reported = entry["calibration"]
        _require(
            list(reported["pooled_null_families"]) == list(POOLED_FAMILIES),
            "pooled null families are inconsistent",
        )
        _require(
            int(reported["pooled_null_trials"]) == len(pooled),
            "pooled null trial count is inconsistent",
        )
        _require(
            _close(float(reported["target_false_positive_rate"]), expected_target_fpr),
            "target false-positive rate is inconsistent",
        )
        for name, expected_value in (
            ("threshold", calibration.threshold),
            ("achieved_false_positive_rate", calibration.achieved_false_positive_rate),
            ("attainable_false_positive_rate", calibration.attainable_false_positive_rate),
        ):
            _require(
                _close(float(reported[name]), expected_value),
                f"calibration {name} does not match the stored trials at length {length}",
            )
        _require(
            bool(reported["target_is_attainable"]) is calibration.is_attainable,
            "attainability flag is inconsistent",
        )
        _require(
            calibration.achieved_false_positive_rate <= expected_target_fpr,
            "the calibrated threshold does not meet its target",
        )

        positive = entry["positive"]
        expected_rate = detection_rate(positives, calibration.threshold)
        _require(int(positive["trials"]) == len(positives), "positive trial count is inconsistent")
        _require(
            _close(float(positive["detection_rate"]), expected_rate),
            f"detection rate does not match the stored trials at length {length}",
        )
        indicators = {
            str(row["case_id"]): (float(float(row["statistic"]) >= calibration.threshold),)
            for row in grouped[(length, POSITIVE_FAMILY)]
        }
        bootstrap = report["lengths"][token_lengths.index(length)]["positive"][
            "detection_rate_prompt_cluster_bootstrap"
        ]
        cluster = analyze_prompt_clusters(
            indicators,
            bootstrap_replicates=int(bootstrap["replicates"]),
            bootstrap_seed=int(bootstrap["seed"]),
        )
        for name, expected_value in (
            ("mean", cluster.overall_mean),
            ("lower", cluster.interval_lower),
            ("upper", cluster.interval_upper),
        ):
            _require(
                _close(float(bootstrap[name]), expected_value),
                f"bootstrap {name} does not match the stored trials at length {length}",
            )
        _require(
            int(bootstrap["clusters"]) == len(case_ids),
            "the bootstrap must resample prompts, one value per prompt",
        )
        _require(
            _close(
                float(positive["minimum_empirical_global_p_value"]),
                min(empirical_p_value(value, pooled) for value in positives),
            ),
            "minimum global p-value does not match the stored trials",
        )
        _require(
            _close(
                float(positive["maximum_empirical_global_p_value"]),
                max(empirical_p_value(value, pooled) for value in positives),
            ),
            "maximum global p-value does not match the stored trials",
        )

        for family in NULL_FAMILIES:
            rows = grouped[(length, family)]
            observed = entry["null_families"][family]
            _require(int(observed["trials"]) == len(rows), f"{family} trial count is inconsistent")
            if not rows:
                _require(
                    observed["exceedance_rate_at_threshold"] is None,
                    f"{family} reported an exceedance rate without trials",
                )
                continue
            _require(
                _close(
                    float(observed["exceedance_rate_at_threshold"]),
                    detection_rate(
                        [float(row["statistic"]) for row in rows], calibration.threshold
                    ),
                ),
                f"{family} exceedance rate does not match the stored trials at length {length}",
            )

        separation = entry["separation"]
        _require(
            _close(float(separation["minimum_positive_statistic"]), min(positives))
            and _close(float(separation["maximum_pooled_null_statistic"]), max(pooled)),
            "separation summary does not match the stored trials",
        )
        _require(
            bool(separation["positives_strictly_above_all_pooled_nulls"])
            is (min(positives) > max(pooled)),
            "separation flag is inconsistent",
        )
        summary.append(
            {
                "token_length": length,
                "base_length": length * KMER_SIZE,
                "threshold": calibration.threshold,
                "achieved_false_positive_rate": calibration.achieved_false_positive_rate,
                "attainable_false_positive_rate": calibration.attainable_false_positive_rate,
                "detection_rate": expected_rate,
                "detection_rate_lower": cluster.interval_lower,
                "detection_rate_upper": cluster.interval_upper,
                "minimum_positive_statistic": min(positives),
                "maximum_pooled_null_statistic": max(pooled),
                "separated": min(positives) > max(pooled),
                "public_dna_exceedance": (
                    detection_rate(
                        [
                            float(row["statistic"])
                            for row in grouped[(length, "any_key_public_dna")]
                        ],
                        calibration.threshold,
                    )
                    if grouped[(length, "any_key_public_dna")]
                    else None
                ),
            }
        )

    return {
        "valid": True,
        "policy_id": report["policy_id"],
        "cohort_id": report["cohort_id"],
        "prompt_count": len(case_ids),
        "null_keys": expected_null_keys,
        "hypotheses_searched": expected_hypotheses,
        "target_false_positive_rate": expected_target_fpr,
        "trial_count": len(trials),
        "raw_fields_absent": True,
        "lengths": summary,
    }
