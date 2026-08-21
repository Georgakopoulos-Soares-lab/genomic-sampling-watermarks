from __future__ import annotations

import copy
import unittest

from genomic_watermarks.cluster_analysis import analyze_prompt_clusters
from genomic_watermarks.detector.search import (
    ORIENTATIONS,
    calibrate_threshold,
    detection_rate,
    empirical_p_value,
    standardized_agreement,
)
from genomic_watermarks.edit_report import validate_edit_report
from genomic_watermarks.pilot import ContextCase, numeric_summary
from genomic_watermarks.watermark import ORDINARY_SCHEME, PARTITION_MC_SCHEME

OFFSETS = 2
NULL_KEYS = 2
REPLICATES = 2
TARGET_FPR = 0.25
RATES = (0.0, 0.5)
LENGTHS = (16,)
PROMPTS = ("case_0", "case_1", "case_2", "case_3")
BOOTSTRAP = 400
SEED = 5
HYPOTHESES = len(ORIENTATIONS) * 6 * OFFSETS
POOLED = ("wrong_key_watermarked", "any_key_ordinary")


def build_cases() -> tuple[ContextCase, ...]:
    return tuple(
        ContextCase(case_id=name, sequence="ATCGGC" * 16, cohort_id="fixture_cohort")
        for name in PROMPTS
    )


def trial(family, case_id, rate, length, matches, replicate, key_index):
    return {
        "family": family,
        "case_id": case_id,
        "edit_rate": rate,
        "replicate": replicate,
        "key_index": key_index,
        "token_length": length,
        "base_length": length * 6,
        "statistic": standardized_agreement(matches, length),
        "matches": matches,
        "total": length,
        "orientation": ORIENTATIONS[0],
        "phase": 0,
        "stream_offset": 0,
        "hypotheses_searched": HYPOTHESES,
    }


def build_report() -> dict[str, object]:
    trials = []
    for rate in RATES:
        # rate 0.0 detects everywhere; rate 0.5 detects only half the prompts.
        for index, case_id in enumerate(PROMPTS):
            for replicate in range(REPLICATES):
                if rate == 0.0 or index % 2 == 0:
                    matches = LENGTHS[0]
                else:
                    matches = LENGTHS[0] // 2
                trials.append(
                    trial("positive", case_id, rate, LENGTHS[0], matches, replicate, None)
                )
            for key_index in range(NULL_KEYS):
                base = LENGTHS[0] // 2 + (index + key_index) % 2
                for family in POOLED:
                    trials.append(trial(family, case_id, rate, LENGTHS[0], base, 0, key_index))

    conditions = []
    for rate in RATES:
        length = LENGTHS[0]
        rows = [row for row in trials if row["edit_rate"] == rate]
        nulls = [float(r["statistic"]) for r in rows if r["family"] in POOLED]
        positives_rows = [r for r in rows if r["family"] == "positive"]
        positives = [float(r["statistic"]) for r in positives_rows]
        calibration = calibrate_threshold(nulls, TARGET_FPR)
        indicators = {case_id: [] for case_id in PROMPTS}
        for row in positives_rows:
            indicators[row["case_id"]].append(
                float(float(row["statistic"]) >= calibration.threshold)
            )
        cluster = analyze_prompt_clusters(
            {k: tuple(v) for k, v in indicators.items()},
            bootstrap_replicates=BOOTSTRAP,
            bootstrap_seed=SEED,
        )
        conditions.append(
            {
                "edit": "substitution",
                "edit_rate": rate,
                "token_length": length,
                "base_length": length * 6,
                "hypotheses_searched": HYPOTHESES,
                "calibration": {
                    "scope": "per rate and length, pooled N1 and N2",
                    "pooled_null_families": list(POOLED),
                    "pooled_null_trials": len(nulls),
                    "target_false_positive_rate": TARGET_FPR,
                    "achieved_false_positive_rate": calibration.achieved_false_positive_rate,
                    "attainable_false_positive_rate": calibration.attainable_false_positive_rate,
                    "target_is_attainable": calibration.is_attainable,
                    "threshold": calibration.threshold,
                },
                "positive": {
                    "trials": len(positives),
                    "replicates_per_prompt": REPLICATES,
                    "detection_rate": detection_rate(positives, calibration.threshold),
                    "statistic": numeric_summary(positives),
                    "minimum_empirical_global_p_value": min(
                        empirical_p_value(v, nulls) for v in positives
                    ),
                    "maximum_empirical_global_p_value": max(
                        empirical_p_value(v, nulls) for v in positives
                    ),
                    "detection_rate_prompt_cluster_bootstrap": {
                        "mean": cluster.overall_mean,
                        "lower": cluster.interval_lower,
                        "upper": cluster.interval_upper,
                        "width": cluster.interval_width,
                        "clusters": float(len(PROMPTS)),
                        "confidence_level": 0.95,
                        "replicates": float(BOOTSTRAP),
                        "seed": float(SEED),
                    },
                },
                "null_families": {
                    family: {
                        "trials": len([r for r in rows if r["family"] == family]),
                        "exceedance_rate_at_threshold": detection_rate(
                            [float(r["statistic"]) for r in rows if r["family"] == family],
                            calibration.threshold,
                        ),
                        "statistic": numeric_summary(
                            float(r["statistic"]) for r in rows if r["family"] == family
                        ),
                    }
                    for family in POOLED
                },
                "separation": {
                    "minimum_positive_statistic": min(positives),
                    "maximum_pooled_null_statistic": max(nulls),
                    "positives_strictly_above_all_pooled_nulls": min(positives) > max(nulls),
                },
            }
        )

    return {
        "schema_version": 1,
        "classification": "engineering_pilot_not_paper_evidence",
        "complete": True,
        "policy_id": "C_tok",
        "cohort_id": "fixture_cohort",
        "experiment_label": "fixture-edit",
        "generation_experiment_label": "fixture-generation",
        "watermark_method": PARTITION_MC_SCHEME,
        "control_method": ORDINARY_SCHEME,
        "key_source": "public_fixture",
        "null_key_source": "public_fixture_labels",
        "null_keys": NULL_KEYS,
        "edit": "substitution",
        "edit_rates": list(RATES),
        "edit_seed_scheme": "fixture",
        "positive_replicates_per_prompt": REPLICATES,
        "support_size": 4096,
        "case_count": len(PROMPTS),
        "case_ids": list(PROMPTS),
        "token_lengths": list(LENGTHS),
        "detector_search": {
            "orientations": list(ORIENTATIONS),
            "phases": [0, 1, 2, 3, 4, 5],
            "window_tokens": "full_sequence_only",
            "window_stride_tokens": 0,
            "stream_offsets": list(range(OFFSETS)),
            "minimum_window_tokens": 16,
        },
        "sequences": {"path": "outputs/fixture.jsonl", "sha256": "0" * 64},
        "cohort": {"prompts_path": "fixture.jsonl"},
        "trial_count": len(trials),
        "trials": trials,
        "conditions": conditions,
    }


class EditReportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = build_cases()
        self.report = build_report()

    def validate(self, report):
        return validate_edit_report(
            report,
            self.cases,
            expected_offsets=OFFSETS,
            expected_null_keys=NULL_KEYS,
            expected_replicates=REPLICATES,
            expected_target_fpr=TARGET_FPR,
        )

    def test_a_consistent_report_validates_and_summarizes_the_grid(self) -> None:
        result = self.validate(self.report)
        self.assertTrue(result["valid"])
        self.assertEqual(result["edit"], "substitution")
        self.assertEqual(result["edit_rates"], list(RATES))
        self.assertEqual(len(result["conditions"]), len(RATES) * len(LENGTHS))
        self.assertEqual(result["maximum_fully_detected_rate_by_length"]["16"], 0.0)
        self.assertIn("16", result["null_invariance_by_length"])
        invariance = result["null_invariance_by_length"]["16"]
        self.assertEqual(set(invariance["per_rate_null_mean"]), {"0", "0.5"})
        self.assertGreaterEqual(invariance["null_mean_spread"], 0.0)

    def test_a_length_with_no_full_detection_reports_none(self) -> None:
        report = copy.deepcopy(self.report)
        for row in report["trials"]:
            if row["family"] == "positive":
                row["matches"] = LENGTHS[0] // 2
                row["statistic"] = standardized_agreement(row["matches"], LENGTHS[0])
        for entry in report["conditions"]:
            rows = [
                r
                for r in report["trials"]
                if r["edit_rate"] == entry["edit_rate"] and r["family"] == "positive"
            ]
            nulls = [
                float(r["statistic"])
                for r in report["trials"]
                if r["edit_rate"] == entry["edit_rate"] and r["family"] in POOLED
            ]
            calibration = calibrate_threshold(nulls, TARGET_FPR)
            positives = [float(r["statistic"]) for r in rows]
            entry["positive"]["detection_rate"] = detection_rate(positives, calibration.threshold)
            entry["positive"]["statistic"] = numeric_summary(positives)
            entry["positive"]["minimum_empirical_global_p_value"] = min(
                empirical_p_value(v, nulls) for v in positives
            )
            entry["positive"]["maximum_empirical_global_p_value"] = max(
                empirical_p_value(v, nulls) for v in positives
            )
            indicators = {case_id: [] for case_id in PROMPTS}
            for row in rows:
                indicators[row["case_id"]].append(
                    float(float(row["statistic"]) >= calibration.threshold)
                )
            cluster = analyze_prompt_clusters(
                {k: tuple(v) for k, v in indicators.items()},
                bootstrap_replicates=BOOTSTRAP,
                bootstrap_seed=SEED,
            )
            entry["positive"]["detection_rate_prompt_cluster_bootstrap"].update(
                {
                    "mean": cluster.overall_mean,
                    "lower": cluster.interval_lower,
                    "upper": cluster.interval_upper,
                    "width": cluster.interval_width,
                }
            )
            entry["separation"]["minimum_positive_statistic"] = min(positives)
            entry["separation"]["positives_strictly_above_all_pooled_nulls"] = min(positives) > max(
                nulls
            )
        result = self.validate(report)
        self.assertIsNone(result["maximum_fully_detected_rate_by_length"]["16"])

    def test_edit_grid_and_channel_are_enforced(self) -> None:
        for field, value, message in (
            ("edit", "teleportation", "unknown edit channel"),
            ("edit_rates", [0.5, 0.0], "sorted and unique"),
            ("edit_rates", [1.5], "must lie in"),
            ("null_keys", 99, "null key count is inconsistent"),
            ("positive_replicates_per_prompt", 99, "positive replicate count is inconsistent"),
        ):
            report = copy.deepcopy(self.report)
            report[field] = value
            with self.assertRaisesRegex(ValueError, message):
                self.validate(report)

    def test_trial_bookkeeping_is_enforced(self) -> None:
        report = copy.deepcopy(self.report)
        report["trials"][0]["statistic"] = 42.0
        with self.assertRaisesRegex(ValueError, "statistic does not match"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        report["trials"][0]["edit_rate"] = 0.123
        with self.assertRaisesRegex(ValueError, "undeclared edit rate"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        for row in report["trials"]:
            if row["family"] in POOLED:
                row["replicate"] = 1
                break
        with self.assertRaisesRegex(ValueError, "first edit replicate only"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        report["trials"] = [r for r in report["trials"] if r["family"] != "positive"]
        report["trial_count"] = len(report["trials"])
        with self.assertRaisesRegex(ValueError, "positive trial count is inconsistent"):
            self.validate(report)

    def test_reported_aggregates_must_match_the_stored_trials(self) -> None:
        report = copy.deepcopy(self.report)
        report["conditions"][0]["calibration"]["threshold"] = 0.123
        with self.assertRaisesRegex(ValueError, "calibration threshold does not match"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        report["conditions"][0]["positive"]["detection_rate"] = 0.5
        with self.assertRaisesRegex(ValueError, "detection rate does not match"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        report["conditions"][0]["null_families"]["any_key_ordinary"][
            "exceedance_rate_at_threshold"
        ] = 0.99
        with self.assertRaisesRegex(ValueError, "exceedance rate does not match"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        report["conditions"][0]["positive"]["detection_rate_prompt_cluster_bootstrap"][
            "clusters"
        ] = 99
        with self.assertRaisesRegex(ValueError, "one cluster per prompt"):
            self.validate(report)

    def test_condition_grid_must_be_complete(self) -> None:
        report = copy.deepcopy(self.report)
        report["conditions"] = report["conditions"][:1]
        with self.assertRaisesRegex(ValueError, "one condition per rate and length"):
            self.validate(report)

    def test_forbidden_raw_fields_are_rejected(self) -> None:
        for field in ("generated_dna", "edited_dna", "key", "sequence"):
            report = copy.deepcopy(self.report)
            report["trials"][0][field] = "value"
            with self.assertRaisesRegex(ValueError, "forbidden raw field"):
                self.validate(report)


if __name__ == "__main__":
    unittest.main()
