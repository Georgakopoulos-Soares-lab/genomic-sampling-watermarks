"""Validation of E7 stage-2 windowed detector reports before evidence review.

Every reported aggregate is recomputed from the stored per-trial rows. The
validator also enforces the two structural properties the comparison depends on:
the windowed search must contain the full-read window, so that it is a superset
of the unwindowed comparator rather than a different statistic, and both searches
must have scored the identical set of trials, so that the comparison is paired.
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

POOLED_FAMILIES = ("wrong_key_watermarked", "any_key_ordinary")
FAMILIES = ("positive", *POOLED_FAMILIES)
SEARCH_IDS = ("windowed", "unwindowed")
EDIT_CHANNELS = ("insertion", "deletion")

_POLICIES = ("C_tok", "G_tok", "G_bp")
_FORBIDDEN_RAW_FIELDS = {
    "generated_dna",
    "edited_dna",
    "observed_dna",
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


def validate_windowed_report(
    report: Mapping[str, Any],
    cohort_cases: Sequence[ContextCase],
    *,
    expected_null_keys: int = 8,
    expected_replicates: int = 5,
    expected_target_fpr: float = 0.01,
) -> dict[str, Any]:
    """Validate the paired windowed and unwindowed searches and every aggregate."""

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

    observed_bases = int(report.get("observed_bases"))
    _require(
        observed_bases > 0 and observed_bases % KMER_SIZE == 0,
        "observed_bases must be a positive multiple of six",
    )
    observed_tokens = observed_bases // KMER_SIZE

    searches = report.get("searches")
    _require(isinstance(searches, Mapping), "searches must be an object")
    _require(set(searches) == set(SEARCH_IDS), "a windowed and an unwindowed search are required")
    windowed = searches["windowed"]["search"]
    _require(windowed.get("kind") == "windowed", "the windowed search must declare its kind")
    _require(bool(windowed.get("drift_is_signed")) is True, "drift must be declared as signed")
    window_tokens = [int(value) for value in windowed["window_tokens"]]
    _require(
        observed_tokens in window_tokens,
        "the windowed search must include the full-read window so it contains the comparator",
    )
    drifts = [int(value) for value in windowed["drift_offsets"]]
    _require(min(drifts) < 0 < max(drifts), "the drift range must be signed in both directions")
    _require(
        list(searches["unwindowed"]["search"]["orientations"]) == list(ORIENTATIONS),
        "the comparator must search both strands",
    )
    hypotheses = {search_id: int(searches[search_id]["hypotheses"]) for search_id in SEARCH_IDS}
    _require(
        hypotheses["windowed"] > hypotheses["unwindowed"],
        "the windowed search must score more hypotheses than the comparator",
    )

    cohort_ids = {case.cohort_id for case in cohort_cases}
    _require(len(cohort_ids) == 1, "cohort cases must share one cohort_id")
    _require(report.get("cohort_id") == next(iter(cohort_ids)), "cohort_id does not match the file")
    known = {case.case_id for case in cohort_cases}
    case_ids = tuple(str(case_id) for case_id in report.get("case_ids", ()))
    _require(case_ids, "report must declare at least one prompt")
    _require(all(case_id in known for case_id in case_ids), "report contains an unknown case")
    _require(int(report.get("case_count")) == len(case_ids), "case_count is inconsistent")

    rates = tuple(float(value) for value in report.get("edit_rates", ()))
    _require(rates and list(rates) == sorted(set(rates)), "edit rates must be sorted and unique")

    trials = report.get("trials")
    _require(isinstance(trials, list) and trials, "trials must be a non-empty list")
    _require(int(report.get("trial_count")) == len(trials), "trial_count is inconsistent")
    grouped: dict[tuple[float, str, str], list[Mapping[str, Any]]] = {
        (rate, search_id, family): []
        for rate in rates
        for search_id in SEARCH_IDS
        for family in FAMILIES
    }
    for row in trials:
        _require(isinstance(row, Mapping), "each trial must be an object")
        family = str(row.get("family"))
        _require(family in FAMILIES, f"unknown trial family {family}")
        _require(str(row.get("case_id")) in case_ids, "trial references an undeclared prompt")
        rate = float(row.get("edit_rate"))
        _require(rate in rates, "trial uses an undeclared edit rate")
        search_id = str(row.get("search_id"))
        _require(search_id in SEARCH_IDS, "trial uses an undeclared search")
        _require(
            int(row.get("hypotheses_searched")) == hypotheses[search_id],
            "trial did not search the declared hypothesis count",
        )
        phase = int(row.get("phase"))
        _require(0 <= phase < KMER_SIZE, "trial phase is invalid")
        total = int(row.get("total"))
        matches = int(row.get("matches"))
        if search_id == "windowed":
            _require(total in window_tokens, "a windowed trial must score a declared window length")
            _require(
                int(row.get("window_start")) + int(row.get("drift")) >= 0,
                "a windowed trial may not use a negative key start",
            )
        else:
            _require(
                total == (observed_tokens if phase == 0 else observed_tokens - 1),
                "an unwindowed trial must score the whole read",
            )
        _require(0 <= matches <= total, "invalid match count")
        _require(
            _close(float(row.get("statistic")), standardized_agreement(matches, total)),
            "trial statistic does not match its match count",
        )
        _require(row.get("orientation") in ORIENTATIONS, "trial orientation is invalid")
        grouped[(rate, search_id, family)].append(row)

    for rate in rates:
        counts = {
            search_id: {family: len(grouped[(rate, search_id, family)]) for family in FAMILIES}
            for search_id in SEARCH_IDS
        }
        _require(
            counts["windowed"] == counts["unwindowed"],
            f"the two searches must score the same trials at rate {rate}",
        )
        _require(
            counts["windowed"]["positive"] == len(case_ids) * expected_replicates,
            f"positive trial count is inconsistent at rate {rate}",
        )
        for family in POOLED_FAMILIES:
            _require(
                counts["windowed"][family] == len(case_ids) * expected_null_keys,
                f"{family} trial count is inconsistent at rate {rate}",
            )

    conditions = report.get("conditions")
    _require(isinstance(conditions, list), "conditions must be a list")
    _require(
        len(conditions) == len(rates) * len(SEARCH_IDS),
        "one condition entry per rate and search is required",
    )

    summary: list[dict[str, Any]] = []
    for entry in conditions:
        rate = float(entry["edit_rate"])
        search_id = str(entry["search_id"])
        _require(rate in rates and search_id in SEARCH_IDS, "condition is outside the grid")
        nulls = [
            float(row["statistic"])
            for family in POOLED_FAMILIES
            for row in grouped[(rate, search_id, family)]
        ]
        positive_rows = grouped[(rate, search_id, "positive")]
        positives = [float(row["statistic"]) for row in positive_rows]
        calibration = calibrate_threshold(nulls, expected_target_fpr)
        reported = entry["calibration"]
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
        _require(
            _close(float(positive["detection_rate"]), expected_rate),
            f"detection rate does not match the stored trials at rate {rate}, {search_id}",
        )
        detected = [row for row in positive_rows if float(row["statistic"]) > calibration.threshold]
        _require(
            int(positive["detected_trials"]) == len(detected),
            "detected trial count is inconsistent",
        )
        _require(
            list(positive["recovered_drift"]) == sorted({int(row["drift"]) for row in detected}),
            "recovered drift set does not match the stored trials",
        )
        _require(
            list(positive["recovered_window_tokens"])
            == sorted({int(row["window_tokens"]) for row in detected}),
            "recovered window set does not match the stored trials",
        )
        indicators = {str(row["case_id"]): [] for row in positive_rows}
        for row in positive_rows:
            indicators[str(row["case_id"])].append(
                float(float(row["statistic"]) > calibration.threshold)
            )
        bootstrap = positive["detection_rate_prompt_cluster_bootstrap"]
        cluster = analyze_prompt_clusters(
            {k: tuple(v) for k, v in indicators.items()},
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
            rows = grouped[(rate, search_id, family)]
            observed = entry["null_families"][family]
            _require(
                _close(
                    float(observed["exceedance_rate_at_threshold"]),
                    detection_rate(
                        [float(row["statistic"]) for row in rows], calibration.threshold
                    ),
                ),
                f"{family} exceedance rate does not match the stored trials",
            )
        summary.append(
            {
                "edit": edit,
                "edit_rate": rate,
                "search_id": search_id,
                "hypotheses_searched": hypotheses[search_id],
                "threshold": calibration.threshold,
                "achieved_false_positive_rate": calibration.achieved_false_positive_rate,
                "attainable_false_positive_rate": calibration.attainable_false_positive_rate,
                "detection_rate": expected_rate,
                "detection_rate_lower": cluster.interval_lower,
                "detection_rate_upper": cluster.interval_upper,
                "positive_trials": len(positives),
                "pooled_null_trials": len(nulls),
                "detected_trials": len(detected),
                "recovered_drift": sorted({int(row["drift"]) for row in detected}),
                "recovered_window_tokens": sorted({int(row["window_tokens"]) for row in detected}),
                "minimum_positive_statistic": min(positives),
                "maximum_pooled_null_statistic": max(nulls),
                "wrong_key_watermarked_exceedance": detection_rate(
                    [
                        float(row["statistic"])
                        for row in grouped[(rate, search_id, "wrong_key_watermarked")]
                    ],
                    calibration.threshold,
                ),
                "any_key_ordinary_exceedance": detection_rate(
                    [
                        float(row["statistic"])
                        for row in grouped[(rate, search_id, "any_key_ordinary")]
                    ],
                    calibration.threshold,
                ),
            }
        )

    by_key = {(row["edit_rate"], row["search_id"]): row for row in summary}
    paired = []
    for rate in rates:
        win = by_key[(rate, "windowed")]
        flat = by_key[(rate, "unwindowed")]
        paired.append(
            {
                "edit_rate": rate,
                "windowed_detection_rate": win["detection_rate"],
                "unwindowed_detection_rate": flat["detection_rate"],
                "detection_rate_gain": win["detection_rate"] - flat["detection_rate"],
                "windowed_threshold": win["threshold"],
                "unwindowed_threshold": flat["threshold"],
                "threshold_cost": win["threshold"] - flat["threshold"],
                "windowed_recovered_drift": win["recovered_drift"],
            }
        )

    detected_rates = [
        row["edit_rate"]
        for row in summary
        if row["search_id"] == "windowed" and row["detection_rate"] >= 1.0
    ]
    comparator_rates = [
        row["edit_rate"]
        for row in summary
        if row["search_id"] == "unwindowed" and row["detection_rate"] >= 1.0
    ]
    return {
        "valid": True,
        "policy_id": report["policy_id"],
        "cohort_id": report["cohort_id"],
        "edit": edit,
        "edit_rates": list(rates),
        "observed_bases": observed_bases,
        "prompt_count": len(case_ids),
        "positive_replicates_per_prompt": expected_replicates,
        "null_keys": expected_null_keys,
        "target_false_positive_rate": expected_target_fpr,
        "hypotheses_by_search": hypotheses,
        "trial_count": len(trials),
        "raw_fields_absent": True,
        "conditions": summary,
        "paired_comparison": paired,
        "windowed_maximum_fully_detected_rate": max(detected_rates) if detected_rates else None,
        "unwindowed_maximum_fully_detected_rate": (
            max(comparator_rates) if comparator_rates else None
        ),
    }
