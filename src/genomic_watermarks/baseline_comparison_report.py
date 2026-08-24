"""Validation of E8/E9 matched baseline comparison reports before evidence review.

Every aggregate is recomputed from the stored per-trial rows, including each
statistic from the primitive it was built from, so neither an aggregation mistake
nor a detector mistake can pass review.

The check this file exists for is the fairness condition. A comparison between
watermark constructions is worthless if one construction searched fewer
alignments, was calibrated on a different target, or saw different prompts. Those
are verified from the trials rather than read from a flag the runner set.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from genomic_watermarks.baselines import EXP_SCHEME, ITS_SCHEME
from genomic_watermarks.detector.baseline_search import (
    EXP_NULL_MEAN,
    EXP_NULL_SD,
    ITS_NULL_MEAN,
    ITS_NULL_SD,
    standardized_score,
)
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

POSITIVE_FAMILY = "positive"
NULL_FAMILIES = ("wrong_key_watermarked", "any_key_ordinary", "any_key_public_dna")
POOLED_FAMILIES = ("wrong_key_watermarked", "any_key_ordinary")
FAMILIES = (POSITIVE_FAMILY, *NULL_FAMILIES)
METHODS = (PARTITION_MC_SCHEME, ITS_SCHEME, EXP_SCHEME)

_NULL_MOMENTS = {
    ITS_SCHEME: (ITS_NULL_MEAN, ITS_NULL_SD),
    EXP_SCHEME: (EXP_NULL_MEAN, EXP_NULL_SD),
}
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


def validate_baseline_comparison_report(
    report: Mapping[str, Any],
    cohort_cases: Sequence[ContextCase],
    *,
    expected_offsets: int = 8,
    expected_null_keys: int = 20,
    expected_target_fpr: float = 0.01,
) -> dict[str, Any]:
    """Validate the shared search, the per-method calibration, and every aggregate."""

    forbidden = _find_forbidden_fields(report)
    _require(not forbidden, f"report contains forbidden raw field(s): {', '.join(forbidden)}")

    _require(report.get("schema_version") == 1, "unsupported report schema_version")
    _require(
        report.get("classification") == "engineering_pilot_not_paper_evidence",
        "unexpected report classification",
    )
    _require(report.get("complete") is True, "report is not marked complete")
    _require(report.get("policy_id") in _POLICIES, "report policy is not a primary policy")
    _require(list(report.get("methods", ())) == list(METHODS), "unexpected method set")
    _require(report.get("control_method") == ORDINARY_SCHEME, "unexpected control method")
    _require(report.get("decision_rule") == DECISION_RULE, "unexpected decision rule")
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
        "this comparison declares no sliding windows",
    )
    offsets = list(search.get("stream_offsets"))
    _require(offsets == list(range(expected_offsets)), "stream offsets are inconsistent")
    minimum_window = int(search.get("minimum_window_tokens"))
    _require(minimum_window > 0, "minimum_window_tokens must be positive")

    def expected_hypotheses_at(token_length: int) -> int:
        """How many hypotheses the declared search scores for a prefix of this length.

        Not a constant. A non-zero phase drops the final incomplete k-mer, so a
        short prefix can fall below ``minimum_window_tokens`` on five of the six
        phases and be scored on phase zero alone. At 16 tokens that is 16
        hypotheses rather than 96, and a validator that demanded 96 would reject a
        correct run.
        """

        scorable = sum(
            1
            for phase in range(KMER_SIZE)
            if (token_length if phase == 0 else token_length - 1) >= minimum_window
        )
        return len(ORIENTATIONS) * scorable * len(offsets)

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
    _require(
        max(token_lengths) <= int(report.get("generated_tokens_per_case")),
        "an evaluated length exceeds the generated length",
    )

    trials = report.get("trials")
    _require(isinstance(trials, list) and trials, "trials must be a non-empty list")
    _require(int(report.get("trial_count")) == len(trials), "trial_count is inconsistent")

    grouped: dict[tuple[str, int, str], list[Mapping[str, Any]]] = {
        (method, length, family): []
        for method in METHODS
        for length in token_lengths
        for family in FAMILIES
    }
    for row in trials:
        _require(isinstance(row, Mapping), "each trial must be an object")
        method = str(row.get("method"))
        _require(method in METHODS, f"unknown trial method {method}")
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
            int(row.get("hypotheses_searched")) == expected_hypotheses_at(length),
            "trial did not search the declared hypothesis count",
        )
        phase = int(row.get("phase"))
        _require(0 <= phase < KMER_SIZE, "trial phase is invalid")
        total = int(row.get("total"))
        # A phase-shifted read of an L-token prefix loses its final incomplete k-mer.
        _require(
            total == (length if phase == 0 else length - 1),
            "trial token total does not match its length and phase",
        )
        statistic = float(row.get("statistic"))
        if method == PARTITION_MC_SCHEME:
            matches = int(row.get("matches"))
            _require(0 <= matches <= total, "invalid match count")
            _require(
                _close(statistic, standardized_agreement(matches, total)),
                "partition statistic does not match its stored match count",
            )
        else:
            null_mean, null_sd = _NULL_MOMENTS[method]
            _require(
                _close(
                    statistic,
                    standardized_score(
                        float(row["total_score"]), total, null_mean=null_mean, null_sd=null_sd
                    ),
                ),
                f"{method} statistic does not match its stored total score",
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
        grouped[(method, length, family)].append(row)

    for method in METHODS:
        for length in token_lengths:
            _require(
                len(grouped[(method, length, POSITIVE_FAMILY)]) == len(case_ids),
                f"{method} needs one positive trial per prompt at length {length}",
            )
            for family in POOLED_FAMILIES:
                _require(
                    len(grouped[(method, length, family)]) == len(case_ids) * expected_null_keys,
                    f"{method} {family} trial count is inconsistent at length {length}",
                )
            # The public-DNA family scores the prompts themselves, which are shorter
            # than the generated sequences, so it is simply absent at the longer
            # evaluated lengths. It is either complete or empty, never partial.
            public = len(grouped[(method, length, "any_key_public_dna")])
            _require(
                public in (0, len(case_ids) * expected_null_keys),
                f"{method} public-DNA trial count is partial at length {length}",
            )

    results = report.get("method_results")
    _require(isinstance(results, list), "method_results must be a list")
    _require(
        [entry["method"] for entry in results] == list(METHODS),
        "method_results does not cover the declared methods in order",
    )

    replicates = int(report["bootstrap_replicates"])
    seed = int(report["bootstrap_seed"])
    summary: list[dict[str, Any]] = []
    for entry in results:
        method = str(entry["method"])
        lengths_value = entry["lengths"]
        _require(
            [int(item["token_length"]) for item in lengths_value] == list(token_lengths),
            f"{method} reported lengths do not match the declared lengths",
        )
        method_rows: list[dict[str, Any]] = []
        for item in lengths_value:
            length = int(item["token_length"])
            pooled = [
                float(row["statistic"])
                for family in POOLED_FAMILIES
                for row in grouped[(method, length, family)]
            ]
            positive_rows = grouped[(method, length, POSITIVE_FAMILY)]
            positives = [float(row["statistic"]) for row in positive_rows]
            calibration = calibrate_threshold(pooled, expected_target_fpr)
            reported = item["calibration"]
            _require(
                list(reported["pooled_null_families"]) == list(POOLED_FAMILIES),
                "pooled null families are inconsistent",
            )
            _require(
                int(reported["pooled_null_trials"]) == len(pooled),
                "pooled null trial count is inconsistent",
            )
            for name, expected_value in (
                ("target_false_positive_rate", expected_target_fpr),
                ("threshold", calibration.threshold),
                ("achieved_false_positive_rate", calibration.achieved_false_positive_rate),
                ("attainable_false_positive_rate", calibration.attainable_false_positive_rate),
            ):
                _require(
                    _close(float(reported[name]), expected_value),
                    f"{method} calibration {name} is inconsistent at length {length}",
                )
            _require(
                calibration.achieved_false_positive_rate <= expected_target_fpr,
                f"{method} threshold does not meet its target at length {length}",
            )

            positive = item["positive"]
            expected_rate = detection_rate(positives, calibration.threshold)
            _require(
                int(positive["trials"]) == len(positives), "positive trial count is inconsistent"
            )
            _require(
                _close(float(positive["detection_rate"]), expected_rate),
                f"{method} detection rate is inconsistent at length {length}",
            )
            by_cluster: dict[str, list[float]] = {}
            for row in positive_rows:
                by_cluster.setdefault(str(row["case_id"]), []).append(float(row["statistic"]))
            interval = joint_detection_rate_interval(
                by_cluster, pooled, expected_target_fpr, replicates=replicates, seed=seed
            )
            stored = positive["detection_rate_joint_interval"]
            _require(
                float(stored["resamples_the_threshold"]) == 1.0,
                "the interval must resample the calibrated threshold",
            )
            for name in ("detection_rate", "lower", "upper"):
                _require(
                    _close(float(stored[name]), interval[name]),
                    f"{method} interval {name} is inconsistent at length {length}",
                )
            _require(
                int(stored["clusters"]) == len(case_ids),
                "the interval must resample prompts, one cluster per prompt",
            )
            _require(
                _close(
                    float(positive["minimum_empirical_global_p_value"]),
                    min(empirical_p_value(value, pooled) for value in positives),
                )
                and _close(
                    float(positive["maximum_empirical_global_p_value"]),
                    max(empirical_p_value(value, pooled) for value in positives),
                ),
                f"{method} global p-values are inconsistent at length {length}",
            )

            for family in NULL_FAMILIES:
                rows = grouped[(method, length, family)]
                observed = item["null_families"][family]
                _require(
                    int(observed["trials"]) == len(rows),
                    f"{method} {family} trial count is inconsistent",
                )
                if not rows:
                    _require(
                        observed["exceedance_rate_at_threshold"] is None,
                        f"{method} {family} reported an exceedance rate without trials",
                    )
                    continue
                _require(
                    _close(
                        float(observed["exceedance_rate_at_threshold"]),
                        detection_rate(
                            [float(row["statistic"]) for row in rows], calibration.threshold
                        ),
                    ),
                    f"{method} {family} exceedance rate is inconsistent at length {length}",
                )

            separation = item["separation"]
            _require(
                _close(float(separation["minimum_positive_statistic"]), min(positives))
                and _close(float(separation["maximum_pooled_null_statistic"]), max(pooled)),
                f"{method} separation summary is inconsistent at length {length}",
            )
            _require(
                bool(separation["positives_strictly_above_all_pooled_nulls"])
                is (min(positives) > max(pooled)),
                f"{method} separation flag is inconsistent at length {length}",
            )

            per_token = [
                float(row["statistic"]) / math.sqrt(int(row["total"])) for row in positive_rows
            ]
            derived = item["derived_signal_per_token"]["value"]
            _require(
                _close(float(derived["mean"]), math.fsum(per_token) / len(per_token)),
                f"{method} derived per-token signal is inconsistent at length {length}",
            )
            method_rows.append(
                {
                    "token_length": length,
                    "base_length": length * KMER_SIZE,
                    "threshold": calibration.threshold,
                    "achieved_false_positive_rate": calibration.achieved_false_positive_rate,
                    "detection_rate": expected_rate,
                    "detection_rate_lower": interval["lower"],
                    "detection_rate_upper": interval["upper"],
                    "separated": min(positives) > max(pooled),
                    "signal_per_token": math.fsum(per_token) / len(per_token),
                    "public_dna_exceedance": (
                        detection_rate(
                            [
                                float(row["statistic"])
                                for row in grouped[(method, length, "any_key_public_dna")]
                            ],
                            calibration.threshold,
                        )
                        if grouped[(method, length, "any_key_public_dna")]
                        else None
                    ),
                }
            )
        fully = [row["base_length"] for row in method_rows if row["detection_rate"] >= 1.0]
        _require(
            entry["shortest_fully_detected_base_length"] == (min(fully) if fully else None),
            f"{method} shortest fully detected length is inconsistent",
        )
        summary.append(
            {
                "method": method,
                "shortest_fully_detected_base_length": min(fully) if fully else None,
                "lengths": method_rows,
            }
        )

    # The fairness condition, recomputed rather than read from the runner's flag.
    counts_by_length: dict[int, set[int]] = {}
    for (method, length, _family), rows in grouped.items():
        for row in rows:
            counts_by_length.setdefault(length, set()).add(int(row["hypotheses_searched"]))
        del method
    identical_search = all(len(values) == 1 for values in counts_by_length.values())
    _require(identical_search, "the three methods did not search the same hypothesis count")
    _require(
        bool(report.get("identical_search_across_methods")) is True,
        "the report must record that the search was identical across methods",
    )

    return {
        "valid": True,
        "policy_id": report["policy_id"],
        "cohort_id": report["cohort_id"],
        "prompt_count": len(case_ids),
        "null_keys": expected_null_keys,
        "hypotheses_searched": {
            str(length * KMER_SIZE): expected_hypotheses_at(length) for length in token_lengths
        },
        "target_false_positive_rate": expected_target_fpr,
        "identical_search_across_methods": True,
        "trial_count": len(trials),
        "raw_fields_absent": True,
        "interval_replicates": replicates,
        "interval_seed": seed,
        "methods": summary,
    }
