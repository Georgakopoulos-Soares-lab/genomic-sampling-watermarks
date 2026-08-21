from __future__ import annotations

import copy
import unittest

from genomic_watermarks.cluster_analysis import analyze_prompt_clusters
from genomic_watermarks.detection_report import validate_detection_report
from genomic_watermarks.detector.search import (
    ORIENTATIONS,
    calibrate_threshold,
    detection_rate,
    empirical_p_value,
    standardized_agreement,
)
from genomic_watermarks.pilot import ContextCase, numeric_summary
from genomic_watermarks.watermark import ORDINARY_SCHEME, PARTITION_MC_SCHEME

OFFSETS = 2
NULL_KEYS = 3
TARGET_FPR = 0.2
LENGTHS = (16, 32)
PROMPTS = ("case_0", "case_1", "case_2", "case_3")
REPLICATES = 500
SEED = 11
HYPOTHESES = len(ORIENTATIONS) * 6 * OFFSETS


def build_cases() -> tuple[ContextCase, ...]:
    return tuple(
        ContextCase(case_id=name, sequence="ATCGGC" * 16, cohort_id="fixture_cohort")
        for name in PROMPTS
    )


def trial(
    family: str,
    case_id: str,
    length: int,
    matches: int,
    key_index: int | None,
) -> dict[str, object]:
    return {
        "family": family,
        "case_id": case_id,
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
    trials: list[dict[str, object]] = []
    for length in LENGTHS:
        for index, case_id in enumerate(PROMPTS):
            trials.append(trial("positive", case_id, length, length - index % 2, None))
            for key_index in range(NULL_KEYS):
                base = length // 2 + (index + key_index) % 3
                trials.append(trial("wrong_key_watermarked", case_id, length, base, key_index))
                trials.append(trial("any_key_ordinary", case_id, length, base, key_index))
                if length == LENGTHS[0]:
                    trials.append(trial("any_key_public_dna", case_id, length, base, key_index))

    lengths_report: list[dict[str, object]] = []
    for length in LENGTHS:
        rows = [row for row in trials if row["token_length"] == length]
        pooled = [
            float(row["statistic"])
            for row in rows
            if row["family"] in {"wrong_key_watermarked", "any_key_ordinary"}
        ]
        positives = [float(row["statistic"]) for row in rows if row["family"] == "positive"]
        calibration = calibrate_threshold(pooled, TARGET_FPR)
        indicators = {
            str(row["case_id"]): (float(float(row["statistic"]) >= calibration.threshold),)
            for row in rows
            if row["family"] == "positive"
        }
        cluster = analyze_prompt_clusters(
            indicators, bootstrap_replicates=REPLICATES, bootstrap_seed=SEED
        )
        families: dict[str, object] = {}
        for family in ("wrong_key_watermarked", "any_key_ordinary", "any_key_public_dna"):
            family_rows = [row for row in rows if row["family"] == family]
            statistics = [float(row["statistic"]) for row in family_rows]
            families[family] = {
                "trials": len(family_rows),
                "exceedance_rate_at_threshold": (
                    detection_rate(statistics, calibration.threshold) if statistics else None
                ),
                "statistic": numeric_summary(statistics) if statistics else None,
            }
        lengths_report.append(
            {
                "token_length": length,
                "base_length": length * 6,
                "hypotheses_searched": HYPOTHESES,
                "calibration": {
                    "pooled_null_families": ["wrong_key_watermarked", "any_key_ordinary"],
                    "pooled_null_trials": len(pooled),
                    "target_false_positive_rate": TARGET_FPR,
                    "achieved_false_positive_rate": calibration.achieved_false_positive_rate,
                    "attainable_false_positive_rate": calibration.attainable_false_positive_rate,
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
                    "detection_rate_prompt_cluster_bootstrap": {
                        "mean": cluster.overall_mean,
                        "lower": cluster.interval_lower,
                        "upper": cluster.interval_upper,
                        "width": cluster.interval_width,
                        "clusters": float(len(PROMPTS)),
                        "confidence_level": 0.95,
                        "replicates": float(REPLICATES),
                        "seed": float(SEED),
                    },
                },
                "null_families": families,
                "separation": {
                    "minimum_positive_statistic": min(positives),
                    "maximum_pooled_null_statistic": max(pooled),
                    "positives_strictly_above_all_pooled_nulls": min(positives) > max(pooled),
                },
            }
        )

    return {
        "schema_version": 1,
        "classification": "engineering_pilot_not_paper_evidence",
        "complete": True,
        "policy_id": "C_tok",
        "cohort_id": "fixture_cohort",
        "experiment_label": "fixture-label",
        "watermark_method": PARTITION_MC_SCHEME,
        "control_method": ORDINARY_SCHEME,
        "key_source": "public_fixture",
        "null_key_source": "public_fixture_labels",
        "null_keys": NULL_KEYS,
        "support_size": 4096,
        "case_count": len(PROMPTS),
        "case_ids": list(PROMPTS),
        "generated_tokens_per_case": max(LENGTHS),
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
        "lengths": lengths_report,
    }


class DetectionReportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = build_cases()
        self.report = build_report()

    def validate(self, report):
        return validate_detection_report(
            report,
            self.cases,
            expected_offsets=OFFSETS,
            expected_null_keys=NULL_KEYS,
            expected_target_fpr=TARGET_FPR,
        )

    def test_a_consistent_report_validates_and_summarizes_every_length(self) -> None:
        result = self.validate(self.report)
        self.assertTrue(result["valid"])
        self.assertEqual(result["policy_id"], "C_tok")
        self.assertEqual(result["prompt_count"], len(PROMPTS))
        self.assertEqual(result["hypotheses_searched"], HYPOTHESES)
        self.assertEqual([entry["token_length"] for entry in result["lengths"]], list(LENGTHS))
        for entry in result["lengths"]:
            self.assertLessEqual(entry["achieved_false_positive_rate"], TARGET_FPR)
            self.assertEqual(entry["base_length"], entry["token_length"] * 6)
        self.assertIsNotNone(result["lengths"][0]["public_dna_exceedance"])
        self.assertIsNone(result["lengths"][1]["public_dna_exceedance"])

    def test_declared_search_must_cover_both_strands_and_all_phases(self) -> None:
        for field, value, message in (
            ("orientations", ["forward"], "both strands"),
            ("phases", [0, 1, 2], "all six phases"),
            ("window_tokens", [16], "no sliding windows"),
            ("stream_offsets", [0], "stream offsets are inconsistent"),
        ):
            report = copy.deepcopy(self.report)
            report["detector_search"][field] = value
            with self.assertRaisesRegex(ValueError, message):
                self.validate(report)

    def test_forbidden_raw_fields_are_rejected(self) -> None:
        for field in ("generated_dna", "key", "logits", "sequence"):
            report = copy.deepcopy(self.report)
            report["trials"][0][field] = "value"
            with self.assertRaisesRegex(ValueError, "forbidden raw field"):
                self.validate(report)

    def test_trial_bookkeeping_is_enforced(self) -> None:
        report = copy.deepcopy(self.report)
        report["trials"][0]["statistic"] = 99.0
        with self.assertRaisesRegex(ValueError, "statistic does not match"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        report["trials"][0]["hypotheses_searched"] = 3
        with self.assertRaisesRegex(ValueError, "declared hypothesis count"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        report["trials"][0]["phase"] = 2
        with self.assertRaisesRegex(ValueError, "total does not match its length and phase"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        report["trials"][0]["key_index"] = 1
        with self.assertRaisesRegex(ValueError, "must not carry a null key index"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        report["trials"] = [row for row in report["trials"] if row["family"] != "positive"]
        report["trial_count"] = len(report["trials"])
        with self.assertRaisesRegex(ValueError, "one positive trial per prompt"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        report["trials"] = report["trials"][:-1]
        report["trial_count"] = len(report["trials"])
        with self.assertRaisesRegex(ValueError, "trial count is inconsistent"):
            self.validate(report)

    def test_reported_aggregates_must_match_the_stored_trials(self) -> None:
        for path, value, message in (
            (("calibration", "threshold"), 0.5, "calibration threshold does not match"),
            (
                ("calibration", "achieved_false_positive_rate"),
                0.5,
                "achieved_false_positive_rate does not match",
            ),
            (("positive", "detection_rate"), 0.25, "detection rate does not match"),
            (
                ("positive", "minimum_empirical_global_p_value"),
                0.9,
                "minimum global p-value does not match",
            ),
        ):
            report = copy.deepcopy(self.report)
            entry = report["lengths"][0]
            entry[path[0]][path[1]] = value
            with self.assertRaisesRegex(ValueError, message):
                self.validate(report)

        report = copy.deepcopy(self.report)
        report["lengths"][0]["null_families"]["any_key_ordinary"][
            "exceedance_rate_at_threshold"
        ] = 0.99
        with self.assertRaisesRegex(ValueError, "exceedance rate does not match"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        report["lengths"][0]["separation"][
            "positives_strictly_above_all_pooled_nulls"
        ] = not report["lengths"][0]["separation"]["positives_strictly_above_all_pooled_nulls"]
        with self.assertRaisesRegex(ValueError, "separation flag is inconsistent"):
            self.validate(report)

    def test_bootstrap_must_resample_prompts(self) -> None:
        report = copy.deepcopy(self.report)
        report["lengths"][0]["positive"]["detection_rate_prompt_cluster_bootstrap"]["lower"] = 0.0
        with self.assertRaisesRegex(ValueError, "bootstrap lower does not match"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        report["lengths"][0]["positive"]["detection_rate_prompt_cluster_bootstrap"]["clusters"] = 99
        with self.assertRaisesRegex(ValueError, "must resample prompts"):
            self.validate(report)

    def test_key_and_policy_scope_is_enforced(self) -> None:
        for field, value, message in (
            ("policy_id", "K_tok", "not a primary policy"),
            ("key_source", "runtime_environment", "unexpected key source"),
            ("null_key_source", "unknown", "unexpected null key source"),
            ("support_size", 64, "must be 4,096 tokens"),
            ("watermark_method", "its", "unexpected watermark method"),
        ):
            report = copy.deepcopy(self.report)
            report[field] = value
            with self.assertRaisesRegex(ValueError, message):
                self.validate(report)

    def test_evaluated_lengths_must_fit_the_generated_corpus(self) -> None:
        report = copy.deepcopy(self.report)
        report["generated_tokens_per_case"] = 8
        with self.assertRaisesRegex(ValueError, "exceeds the generated length"):
            self.validate(report)


if __name__ == "__main__":
    unittest.main()
