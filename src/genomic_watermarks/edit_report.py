"""Validation of edit-robustness reports before evidence review.

Every reported aggregate is recomputed from the report's stored per-trial rows.
The validator also returns the per-rate null summaries needed to check the
claim that the null statistic distribution does not depend on the edit rate.
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
from genomic_watermarks.pilot import ContextCase, numeric_summary
from genomic_watermarks.watermark import ORDINARY_SCHEME, PARTITION_MC_SCHEME

POOLED_FAMILIES = ("wrong_key_watermarked", "any_key_ordinary")
FAMILIES = ("positive", *POOLED_FAMILIES)
EDIT_CHANNELS = ("substitution", "insertion", "deletion")

_POLICIES = ("C_tok", "G_tok", "G_bp")
_FORBIDDEN_RAW_FIELDS = {
    "generated_dna",
    "edited_dna",
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


def validate_edit_report(
    report: Mapping[str, Any],
    cohort_cases: Sequence[ContextCase],
    *,
    expected_offsets: int = 8,
    expected_null_keys: int = 8,
    expected_replicates: int = 5,
    expected_target_fpr: float = 0.01,
) -> dict[str, Any]:
    """Validate the declared search, the edit grid, and every reported aggregate."""

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
    _require(
        int(report.get("positive_replicates_per_prompt")) == expected_replicates,
        "positive replicate count is inconsistent",
    )
    _require(int(report.get("support_size")) == 4096, "the declared support must be 4,096 tokens")
    edit = str(report.get("edit"))
    _require(edit in EDIT_CHANNELS, f"unknown edit channel {edit}")

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
    expected_hypotheses = len(ORIENTATIONS) * KMER_SIZE * len(offsets)

    cohort_ids = {case.cohort_id for case in cohort_cases}
    _require(len(cohort_ids) == 1, "cohort cases must share one cohort_id")
    _require(report.get("cohort_id") == next(iter(cohort_ids)), "cohort_id does not match the file")
    known = {case.case_id for case in cohort_cases}
    case_ids = tuple(str(case_id) for case_id in report.get("case_ids", ()))
    _require(case_ids, "report must declare at least one prompt")
    _require(len(set(case_ids)) == len(case_ids), "case_ids must be unique")
    _require(all(case_id in known for case_id in case_ids), "report contains an unknown case")
    _require(int(report.get("case_count")) == len(case_ids), "case_count is inconsistent")

    rates = tuple(float(value) for value in report.get("edit_rates", ()))
    _require(rates, "at least one edit rate is required")
    _require(list(rates) == sorted(set(rates)), "edit rates must be sorted and unique")
    _require(all(0.0 <= rate <= 1.0 for rate in rates), "edit rates must lie in [0, 1]")
    token_lengths = tuple(int(value) for value in report.get("token_lengths", ()))
    _require(token_lengths, "at least one evaluated length is required")
    _require(list(token_lengths) == sorted(set(token_lengths)), "evaluated lengths must be sorted")

    trials = report.get("trials")
    _require(isinstance(trials, list) and trials, "trials must be a non-empty list")
    _require(int(report.get("trial_count")) == len(trials), "trial_count is inconsistent")
    grouped: dict[tuple[float, int, str], list[Mapping[str, Any]]] = {
        (rate, length, family): []
        for rate in rates
        for length in token_lengths
        for family in FAMILIES
    }
    for row in trials:
        _require(isinstance(row, Mapping), "each trial must be an object")
        family = str(row.get("family"))
        _require(family in FAMILIES, f"unknown trial family {family}")
        _require(str(row.get("case_id")) in case_ids, "trial references an undeclared prompt")
        rate = float(row.get("edit_rate"))
        _require(rate in rates, "trial uses an undeclared edit rate")
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
        phase = int(row.get("phase"))
        _require(0 <= phase < KMER_SIZE, "trial phase is invalid")
        total = int(row.get("total"))
        matches = int(row.get("matches"))
        _require(
            total == (length if phase == 0 else length - 1),
            "trial token total does not match its length and phase",
        )
        _require(0 <= matches <= total, "invalid match count")
        _require(
            _close(float(row.get("statistic")), standardized_agreement(matches, total)),
            "trial statistic does not match its match count",
        )
        _require(row.get("orientation") in ORIENTATIONS, "trial orientation is invalid")
        _require(int(row.get("stream_offset")) in offsets, "trial offset is outside the search")
        replicate = int(row.get("replicate"))
        key_index = row.get("key_index")
        if family == "positive":
            _require(key_index is None, "positive trials must not carry a null key index")
            _require(
                0 <= replicate < expected_replicates,
                "positive replicate index is outside the declared count",
            )
        else:
            _require(replicate == 0, "null trials use the first edit replicate only")
            _require(
                isinstance(key_index, int) and 0 <= key_index < expected_null_keys,
                "null trial key index is outside the declared key set",
            )
        grouped[(rate, length, family)].append(row)

    for rate in rates:
        for length in token_lengths:
            _require(
                len(grouped[(rate, length, "positive")]) == len(case_ids) * expected_replicates,
                f"positive trial count is inconsistent at rate {rate}, length {length}",
            )
            for family in POOLED_FAMILIES:
                _require(
                    len(grouped[(rate, length, family)]) == len(case_ids) * expected_null_keys,
                    f"{family} trial count is inconsistent at rate {rate}, length {length}",
                )

    conditions = report.get("conditions")
    _require(isinstance(conditions, list) and conditions, "conditions must be a non-empty list")
    _require(
        len(conditions) == len(rates) * len(token_lengths),
        "one condition per rate and length is required",
    )

    summary: list[dict[str, Any]] = []
    null_invariance: dict[int, dict[str, Any]] = {}
    for length in token_lengths:
        per_rate_null_max: dict[str, float] = {}
        per_rate_null_mean: dict[str, float] = {}
        for rate in rates:
            nulls = [
                float(row["statistic"])
                for family in POOLED_FAMILIES
                for row in grouped[(rate, length, family)]
            ]
            per_rate_null_max[f"{rate:g}"] = max(nulls)
            per_rate_null_mean[f"{rate:g}"] = numeric_summary(nulls)["mean"]
        null_invariance[length] = {
            "per_rate_null_maximum": per_rate_null_max,
            "per_rate_null_mean": per_rate_null_mean,
            "null_mean_spread": max(per_rate_null_mean.values()) - min(per_rate_null_mean.values()),
            "null_maximum_spread": max(per_rate_null_max.values())
            - min(per_rate_null_max.values()),
        }

    for entry in conditions:
        rate = float(entry["edit_rate"])
        length = int(entry["token_length"])
        _require(
            rate in rates and length in token_lengths, "condition is outside the declared grid"
        )
        _require(str(entry["edit"]) == edit, "condition declares a different edit channel")
        nulls = [
            float(row["statistic"])
            for family in POOLED_FAMILIES
            for row in grouped[(rate, length, family)]
        ]
        positives_rows = grouped[(rate, length, "positive")]
        positives = [float(row["statistic"]) for row in positives_rows]
        calibration = calibrate_threshold(nulls, expected_target_fpr)
        reported = entry["calibration"]
        _require(
            int(reported["pooled_null_trials"]) == len(nulls),
            "pooled null trial count is inconsistent",
        )
        for name, expected_value in (
            ("threshold", calibration.threshold),
            ("achieved_false_positive_rate", calibration.achieved_false_positive_rate),
            ("attainable_false_positive_rate", calibration.attainable_false_positive_rate),
        ):
            _require(
                _close(float(reported[name]), expected_value),
                f"calibration {name} does not match the stored trials at rate {rate}",
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
            f"detection rate does not match the stored trials at rate {rate}, length {length}",
        )
        indicators: dict[str, list[float]] = {case_id: [] for case_id in case_ids}
        for row in positives_rows:
            indicators[str(row["case_id"])].append(
                float(float(row["statistic"]) >= calibration.threshold)
            )
        bootstrap = positive["detection_rate_prompt_cluster_bootstrap"]
        cluster = analyze_prompt_clusters(
            {case_id: tuple(values) for case_id, values in indicators.items()},
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
                f"bootstrap {name} does not match the stored trials at rate {rate}",
            )
        _require(
            int(bootstrap["clusters"]) == len(case_ids),
            "the bootstrap must resample prompts, one cluster per prompt",
        )
        _require(
            _close(
                float(positive["minimum_empirical_global_p_value"]),
                min(empirical_p_value(value, nulls) for value in positives),
            ),
            "minimum global p-value does not match the stored trials",
        )
        for family in POOLED_FAMILIES:
            rows = grouped[(rate, length, family)]
            observed = entry["null_families"][family]
            _require(int(observed["trials"]) == len(rows), f"{family} trial count is inconsistent")
            _require(
                _close(
                    float(observed["exceedance_rate_at_threshold"]),
                    detection_rate(
                        [float(row["statistic"]) for row in rows], calibration.threshold
                    ),
                ),
                f"{family} exceedance rate does not match the stored trials at rate {rate}",
            )
        separation = entry["separation"]
        _require(
            _close(float(separation["minimum_positive_statistic"]), min(positives))
            and _close(float(separation["maximum_pooled_null_statistic"]), max(nulls)),
            "separation summary does not match the stored trials",
        )
        summary.append(
            {
                "edit": edit,
                "edit_rate": rate,
                "token_length": length,
                "base_length": length * KMER_SIZE,
                "threshold": calibration.threshold,
                "achieved_false_positive_rate": calibration.achieved_false_positive_rate,
                "attainable_false_positive_rate": calibration.attainable_false_positive_rate,
                "detection_rate": expected_rate,
                "detection_rate_lower": cluster.interval_lower,
                "detection_rate_upper": cluster.interval_upper,
                "positive_trials": len(positives),
                "pooled_null_trials": len(nulls),
                "wrong_key_watermarked_exceedance": detection_rate(
                    [
                        float(row["statistic"])
                        for row in grouped[(rate, length, "wrong_key_watermarked")]
                    ],
                    calibration.threshold,
                ),
                "any_key_ordinary_exceedance": detection_rate(
                    [
                        float(row["statistic"])
                        for row in grouped[(rate, length, "any_key_ordinary")]
                    ],
                    calibration.threshold,
                ),
                "minimum_positive_statistic": min(positives),
                "maximum_pooled_null_statistic": max(nulls),
            }
        )

    maximum_fully_detected: dict[int, float | None] = {}
    for length in token_lengths:
        detected = [
            row["edit_rate"]
            for row in summary
            if row["token_length"] == length and row["detection_rate"] >= 1.0
        ]
        maximum_fully_detected[length] = max(detected) if detected else None

    return {
        "valid": True,
        "policy_id": report["policy_id"],
        "cohort_id": report["cohort_id"],
        "edit": edit,
        "edit_rates": list(rates),
        "prompt_count": len(case_ids),
        "positive_replicates_per_prompt": expected_replicates,
        "null_keys": expected_null_keys,
        "hypotheses_searched": expected_hypotheses,
        "target_false_positive_rate": expected_target_fpr,
        "trial_count": len(trials),
        "raw_fields_absent": True,
        "conditions": summary,
        "null_invariance_by_length": {str(k): v for k, v in null_invariance.items()},
        "maximum_fully_detected_rate_by_length": {
            str(length): value for length, value in maximum_fully_detected.items()
        },
    }
