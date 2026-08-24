"""Validation tests for the E8/E9 matched baseline comparison report.

The fairness conditions are what make a cross-method comparison mean anything, so
each one is tampered with here and the validator must reject it.
"""

from __future__ import annotations

import copy
import math
import unittest

from genomic_watermarks.baseline_comparison_report import validate_baseline_comparison_report
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
from genomic_watermarks.pilot import ContextCase, numeric_summary
from genomic_watermarks.watermark import ORDINARY_SCHEME, PARTITION_MC_SCHEME

OFFSETS = 2
NULL_KEYS = 3
TARGET_FPR = 0.2
LENGTHS = (8, 32)
MIN_WINDOW = 8
PROMPTS = ("case_0", "case_1", "case_2", "case_3")
REPLICATES = 200
SEED = 11


def hypotheses_at(token_length: int) -> int:
    """A short prefix loses five of six phases to the minimum-window rule."""

    scorable = sum(
        1 for phase in range(6) if (token_length if phase == 0 else token_length - 1) >= MIN_WINDOW
    )
    return len(ORIENTATIONS) * scorable * OFFSETS


HYPOTHESES = len(ORIENTATIONS) * 6 * OFFSETS
METHODS = (PARTITION_MC_SCHEME, ITS_SCHEME, EXP_SCHEME)
NULL_FAMILIES = ("wrong_key_watermarked", "any_key_ordinary", "any_key_public_dna")
POOLED = ("wrong_key_watermarked", "any_key_ordinary")
# Per-token separation each method gets in the fixture, so the three arms are not
# identical and a per-method mix-up cannot pass unnoticed.
SIGNAL = {PARTITION_MC_SCHEME: 0.0, ITS_SCHEME: 0.35, EXP_SCHEME: 2.0}
MOMENTS = {ITS_SCHEME: (ITS_NULL_MEAN, ITS_NULL_SD), EXP_SCHEME: (EXP_NULL_MEAN, EXP_NULL_SD)}


def build_cases() -> tuple[ContextCase, ...]:
    return tuple(
        ContextCase(case_id=name, sequence="ATCGGC" * 16, cohort_id="fixture_cohort")
        for name in PROMPTS
    )


def make_trial(
    method: str, family: str, case_id: str, length: int, level: float, key_index: int | None
) -> dict[str, object]:
    """One trial row, built the way the runner builds it: primitive first."""

    row: dict[str, object] = {
        "method": method,
        "family": family,
        "case_id": case_id,
        "key_index": key_index,
        "token_length": length,
        "base_length": length * 6,
        "total": length,
        "orientation": ORIENTATIONS[0],
        "phase": 0,
        "stream_offset": 0,
        "hypotheses_searched": hypotheses_at(length),
    }
    if method == PARTITION_MC_SCHEME:
        matches = min(length, max(0, int(round(length / 2 + level * math.sqrt(length) / 2))))
        row["matches"] = matches
        row["statistic"] = standardized_agreement(matches, length)
    else:
        null_mean, null_sd = MOMENTS[method]
        total_score = length * null_mean + level * null_sd * math.sqrt(length)
        row["total_score"] = total_score
        row["statistic"] = standardized_score(
            total_score, length, null_mean=null_mean, null_sd=null_sd
        )
    return row


def build_report() -> dict[str, object]:
    trials: list[dict[str, object]] = []
    for method in METHODS:
        for length in LENGTHS:
            for index, case_id in enumerate(PROMPTS):
                positive_level = SIGNAL[method] * math.sqrt(length) + index % 2
                trials.append(make_trial(method, "positive", case_id, length, positive_level, None))
                for key_index in range(NULL_KEYS):
                    level = ((index + key_index) % 3) / 2.0
                    for family in NULL_FAMILIES:
                        trials.append(make_trial(method, family, case_id, length, level, key_index))

    method_results: list[dict[str, object]] = []
    for method in METHODS:
        lengths_report: list[dict[str, object]] = []
        for length in LENGTHS:
            rows = [
                row for row in trials if row["method"] == method and row["token_length"] == length
            ]
            pooled = [float(row["statistic"]) for row in rows if row["family"] in POOLED]
            positive_rows = [row for row in rows if row["family"] == "positive"]
            positives = [float(row["statistic"]) for row in positive_rows]
            calibration = calibrate_threshold(pooled, TARGET_FPR)
            by_cluster: dict[str, list[float]] = {}
            for row in positive_rows:
                by_cluster.setdefault(str(row["case_id"]), []).append(float(row["statistic"]))
            interval = joint_detection_rate_interval(
                by_cluster, pooled, TARGET_FPR, replicates=REPLICATES, seed=SEED
            )
            per_token = [
                float(row["statistic"]) / math.sqrt(int(row["total"])) for row in positive_rows
            ]
            lengths_report.append(
                {
                    "token_length": length,
                    "base_length": length * 6,
                    "hypotheses_searched": hypotheses_at(length),
                    "calibration": {
                        "pooled_null_families": list(POOLED),
                        "pooled_null_trials": len(pooled),
                        "target_false_positive_rate": TARGET_FPR,
                        "achieved_false_positive_rate": (calibration.achieved_false_positive_rate),
                        "attainable_false_positive_rate": (
                            calibration.attainable_false_positive_rate
                        ),
                        "target_is_attainable": calibration.is_attainable,
                        "threshold": calibration.threshold,
                    },
                    "positive": {
                        "trials": len(positives),
                        "detection_rate": detection_rate(positives, calibration.threshold),
                        "statistic": numeric_summary(positives),
                        "minimum_empirical_global_p_value": min(
                            empirical_p_value(value, pooled) for value in positives
                        ),
                        "maximum_empirical_global_p_value": max(
                            empirical_p_value(value, pooled) for value in positives
                        ),
                        "detection_rate_joint_interval": interval,
                    },
                    "null_families": {
                        family: {
                            "trials": sum(1 for row in rows if row["family"] == family),
                            "exceedance_rate_at_threshold": detection_rate(
                                [
                                    float(row["statistic"])
                                    for row in rows
                                    if row["family"] == family
                                ],
                                calibration.threshold,
                            ),
                            "statistic": numeric_summary(
                                float(row["statistic"]) for row in rows if row["family"] == family
                            ),
                        }
                        for family in NULL_FAMILIES
                    },
                    "separation": {
                        "minimum_positive_statistic": min(positives),
                        "maximum_pooled_null_statistic": max(pooled),
                        "positives_strictly_above_all_pooled_nulls": min(positives) > max(pooled),
                    },
                    "derived_signal_per_token": {
                        "value": numeric_summary(per_token),
                        "unit": "standard deviations of this method's own null, per 6-mer token",
                        "boundary": "derived",
                    },
                }
            )
        fully = [
            entry["base_length"]
            for entry in lengths_report
            if entry["positive"]["detection_rate"] >= 1.0
        ]
        method_results.append(
            {
                "method": method,
                "stream_domain": f"fixture/{method}",
                "shortest_fully_detected_base_length": min(fully) if fully else None,
                "lengths": lengths_report,
            }
        )

    return {
        "schema_version": 1,
        "classification": "engineering_pilot_not_paper_evidence",
        "complete": True,
        "policy_id": "C_tok",
        "cohort_id": "fixture_cohort",
        "methods": list(METHODS),
        "control_method": ORDINARY_SCHEME,
        "decision_rule": DECISION_RULE,
        "key_source": "public_fixture",
        "null_key_source": "public_fixture_labels",
        "null_keys": NULL_KEYS,
        "case_count": len(PROMPTS),
        "case_ids": list(PROMPTS),
        "generated_tokens_per_case": max(LENGTHS),
        "token_lengths": list(LENGTHS),
        "detector_search": {
            "orientations": list(ORIENTATIONS),
            "phases": list(range(6)),
            "window_tokens": "full_sequence_only",
            "window_stride_tokens": 0,
            "stream_offsets": list(range(OFFSETS)),
            "minimum_window_tokens": MIN_WINDOW,
        },
        "identical_search_across_methods": True,
        "support_size": 4096,
        "sequences": {
            "partition_path": "fixture_partition.jsonl",
            "partition_sha256": "0" * 64,
            "partition_experiment_label": "fixture-e4",
            "baseline_path": "fixture_baseline.jsonl",
            "baseline_sha256": "1" * 64,
            "baseline_experiment_label": "fixture-e8e9",
        },
        "cohort": {"prompts_path": "fixture.jsonl"},
        "bootstrap_replicates": REPLICATES,
        "bootstrap_seed": SEED,
        "trial_count": len(trials),
        "trials": trials,
        "method_results": method_results,
    }


class BaselineComparisonReportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.report = build_report()
        self.cases = build_cases()

    def validate(self, report: dict[str, object]) -> dict[str, object]:
        return validate_baseline_comparison_report(
            report,
            self.cases,
            expected_offsets=OFFSETS,
            expected_null_keys=NULL_KEYS,
            expected_target_fpr=TARGET_FPR,
        )

    def test_a_consistent_report_validates(self) -> None:
        result = self.validate(self.report)
        self.assertTrue(result["valid"])
        self.assertTrue(result["identical_search_across_methods"])
        self.assertEqual(
            result["hypotheses_searched"],
            {str(length * 6): hypotheses_at(length) for length in LENGTHS},
        )
        self.assertEqual([entry["method"] for entry in result["methods"]], list(METHODS))

    def test_the_fixture_separates_the_three_methods(self) -> None:
        """A fixture where all arms scored alike could not catch a per-method mix-up."""

        signals = {
            entry["method"]: entry["lengths"][-1]["signal_per_token"]
            for entry in self.validate(self.report)["methods"]
        }
        self.assertLess(signals[PARTITION_MC_SCHEME], signals[ITS_SCHEME])
        self.assertLess(signals[ITS_SCHEME], signals[EXP_SCHEME])

    def test_one_method_searching_fewer_hypotheses_is_rejected(self) -> None:
        """The fairness condition: a smaller search would buy a cheaper threshold."""

        tampered = copy.deepcopy(self.report)
        for row in tampered["trials"]:
            if row["method"] == EXP_SCHEME:
                row["hypotheses_searched"] = hypotheses_at(int(row["token_length"])) // 2
        with self.assertRaisesRegex(ValueError, "declared hypothesis count"):
            self.validate(tampered)

    def test_a_partition_statistic_inconsistent_with_its_matches_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        for row in tampered["trials"]:
            if row["method"] == PARTITION_MC_SCHEME and row["family"] == "positive":
                row["statistic"] = float(row["statistic"]) + 1.0
                break
        with self.assertRaisesRegex(ValueError, "stored match count"):
            self.validate(tampered)

    def test_a_baseline_statistic_inconsistent_with_its_total_score_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        for row in tampered["trials"]:
            if row["method"] == ITS_SCHEME and row["family"] == "positive":
                row["statistic"] = float(row["statistic"]) * 2.0
                break
        with self.assertRaisesRegex(ValueError, "stored total score"):
            self.validate(tampered)

    def test_an_interval_that_ignores_the_threshold_is_rejected(self) -> None:
        """The defect the 2026-08-23 audit found must not be reintroducible."""

        tampered = copy.deepcopy(self.report)
        entry = tampered["method_results"][0]["lengths"][0]
        entry["positive"]["detection_rate_joint_interval"]["resamples_the_threshold"] = 0.0
        with self.assertRaisesRegex(ValueError, "resample the calibrated threshold"):
            self.validate(tampered)

    def test_a_widened_interval_bound_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        entry = tampered["method_results"][1]["lengths"][0]
        entry["positive"]["detection_rate_joint_interval"]["lower"] = -1.0
        with self.assertRaisesRegex(ValueError, "interval lower is inconsistent"):
            self.validate(tampered)

    def test_a_non_strict_decision_rule_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        tampered["decision_rule"] = "statistic >= threshold"
        with self.assertRaisesRegex(ValueError, "unexpected decision rule"):
            self.validate(tampered)

    def test_a_raw_sequence_field_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        tampered["trials"][0]["generated_dna"] = "ACGTAC"
        with self.assertRaisesRegex(ValueError, "forbidden raw field"):
            self.validate(tampered)

    def test_a_threshold_that_misses_its_target_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        entry = tampered["method_results"][0]["lengths"][0]
        entry["calibration"]["threshold"] = -100.0
        with self.assertRaisesRegex(ValueError, "calibration threshold is inconsistent"):
            self.validate(tampered)

    def test_a_missing_null_family_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        tampered["trials"] = [
            row for row in tampered["trials"] if row["family"] != "any_key_public_dna"
        ]
        tampered["trial_count"] = len(tampered["trials"])
        with self.assertRaisesRegex(ValueError, "any_key_public_dna trial count"):
            self.validate(tampered)


if __name__ == "__main__":
    unittest.main()
