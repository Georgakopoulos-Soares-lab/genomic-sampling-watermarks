from __future__ import annotations

import copy
import unittest

from genomic_watermarks.cluster_analysis import analyze_prompt_clusters
from genomic_watermarks.detector.search import (
    ORIENTATIONS,
    WindowedSearchConfig,
    calibrate_threshold,
    detection_rate,
    empirical_p_value,
    standardized_agreement,
)
from genomic_watermarks.pilot import ContextCase, numeric_summary
from genomic_watermarks.watermark import ORDINARY_SCHEME, PARTITION_MC_SCHEME
from genomic_watermarks.windowed_report import validate_windowed_report

PROMPTS = ("case_0", "case_1", "case_2", "case_3")
RATES = (0.0, 0.01)
NULL_KEYS = 2
REPLICATES = 2
TARGET_FPR = 0.25
OBSERVED_BASES = 192
OBSERVED_TOKENS = OBSERVED_BASES // 6
WINDOWS = (16, OBSERVED_TOKENS)
DRIFTS = tuple(range(-2, 3))
POOLED = ("wrong_key_watermarked", "any_key_ordinary")
BOOTSTRAP, SEED = 300, 3
CONFIG = WindowedSearchConfig(window_tokens=WINDOWS, drift_offsets=DRIFTS)
HYP = {"windowed": CONFIG.hypothesis_count(OBSERVED_BASES), "unwindowed": 2 * 6 * 8}


def build_cases():
    return tuple(
        ContextCase(case_id=name, sequence="ATCGGC" * 16, cohort_id="fixture_cohort")
        for name in PROMPTS
    )


def trial(family, case_id, rate, search_id, matches, total, replicate, key_index, drift=0):
    return {
        "family": family,
        "case_id": case_id,
        "edit_rate": rate,
        "replicate": replicate,
        "key_index": key_index,
        "search_id": search_id,
        "statistic": standardized_agreement(matches, total),
        "matches": matches,
        "total": total,
        "orientation": ORIENTATIONS[0],
        "phase": 0,
        "window_start": 0,
        "drift": drift,
        "window_tokens": total,
        "hypotheses_searched": HYP[search_id],
    }


def build_report():
    trials = []
    for rate in RATES:
        for index, case_id in enumerate(PROMPTS):
            for replicate in range(REPLICATES):
                strong = OBSERVED_TOKENS if rate == 0.0 else OBSERVED_TOKENS - 2
                weak = OBSERVED_TOKENS if rate == 0.0 else OBSERVED_TOKENS // 2
                trials.append(
                    trial("positive", case_id, rate, "windowed", 16, 16, replicate, None, 1)
                    if rate > 0.0
                    else trial(
                        "positive",
                        case_id,
                        rate,
                        "windowed",
                        strong,
                        OBSERVED_TOKENS,
                        replicate,
                        None,
                        0,
                    )
                )
                trials.append(
                    trial(
                        "positive",
                        case_id,
                        rate,
                        "unwindowed",
                        weak,
                        OBSERVED_TOKENS,
                        replicate,
                        None,
                    )
                )
            for key_index in range(NULL_KEYS):
                base = OBSERVED_TOKENS // 2 + (index + key_index) % 2
                for family in POOLED:
                    trials.append(trial(family, case_id, rate, "windowed", 9, 16, 0, key_index, 0))
                    trials.append(
                        trial(
                            family,
                            case_id,
                            rate,
                            "unwindowed",
                            base,
                            OBSERVED_TOKENS,
                            0,
                            key_index,
                        )
                    )

    conditions = []
    for rate in RATES:
        for search_id in ("windowed", "unwindowed"):
            rows = [r for r in trials if r["edit_rate"] == rate and r["search_id"] == search_id]
            nulls = [float(r["statistic"]) for r in rows if r["family"] in POOLED]
            pos_rows = [r for r in rows if r["family"] == "positive"]
            positives = [float(r["statistic"]) for r in pos_rows]
            cal = calibrate_threshold(nulls, TARGET_FPR)
            detected = [r for r in pos_rows if float(r["statistic"]) > cal.threshold]
            ind = {c: [] for c in PROMPTS}
            for r in pos_rows:
                ind[r["case_id"]].append(float(float(r["statistic"]) > cal.threshold))
            cluster = analyze_prompt_clusters(
                {k: tuple(v) for k, v in ind.items()},
                bootstrap_replicates=BOOTSTRAP,
                bootstrap_seed=SEED,
            )
            conditions.append(
                {
                    "edit": "deletion",
                    "edit_rate": rate,
                    "search_id": search_id,
                    "observed_bases": OBSERVED_BASES,
                    "hypotheses_searched": HYP[search_id],
                    "calibration": {
                        "scope": "per rate and search, pooled N1 and N2",
                        "pooled_null_families": list(POOLED),
                        "pooled_null_trials": len(nulls),
                        "target_false_positive_rate": TARGET_FPR,
                        "achieved_false_positive_rate": cal.achieved_false_positive_rate,
                        "attainable_false_positive_rate": cal.attainable_false_positive_rate,
                        "threshold": cal.threshold,
                    },
                    "positive": {
                        "trials": len(positives),
                        "detection_rate": detection_rate(positives, cal.threshold),
                        "statistic": numeric_summary(positives),
                        "minimum_empirical_global_p_value": min(
                            empirical_p_value(v, nulls) for v in positives
                        ),
                        "detection_rate_prompt_cluster_bootstrap": {
                            "mean": cluster.overall_mean,
                            "lower": cluster.interval_lower,
                            "upper": cluster.interval_upper,
                            "clusters": float(len(PROMPTS)),
                            "confidence_level": 0.95,
                            "replicates": float(BOOTSTRAP),
                            "seed": float(SEED),
                        },
                        "recovered_window_tokens": sorted(
                            {int(r["window_tokens"]) for r in detected}
                        )
                        if detected
                        else [],
                        "recovered_drift": sorted({int(r["drift"]) for r in detected}),
                        "detected_trials": len(detected),
                    },
                    "null_families": {
                        f: {
                            "trials": len([r for r in rows if r["family"] == f]),
                            "exceedance_rate_at_threshold": detection_rate(
                                [float(r["statistic"]) for r in rows if r["family"] == f],
                                cal.threshold,
                            ),
                            "statistic": numeric_summary(
                                float(r["statistic"]) for r in rows if r["family"] == f
                            ),
                        }
                        for f in POOLED
                    },
                    "separation": {
                        "minimum_positive_statistic": min(positives),
                        "maximum_pooled_null_statistic": max(nulls),
                    },
                }
            )

    return {
        "schema_version": 1,
        "classification": "engineering_pilot_not_paper_evidence",
        "complete": True,
        "policy_id": "C_tok",
        "cohort_id": "fixture_cohort",
        "experiment_label": "fixture-stage2",
        "generation_experiment_label": "fixture-generation",
        "watermark_method": PARTITION_MC_SCHEME,
        "control_method": ORDINARY_SCHEME,
        "key_source": "public_fixture",
        "null_key_source": "public_fixture_labels",
        "null_keys": NULL_KEYS,
        "edit": "deletion",
        "edit_rates": list(RATES),
        "positive_replicates_per_prompt": REPLICATES,
        "observed_bases": OBSERVED_BASES,
        "support_size": 4096,
        "case_count": len(PROMPTS),
        "case_ids": list(PROMPTS),
        "searches": {
            "unwindowed": {
                "search": {"orientations": list(ORIENTATIONS), "stream_offsets": list(range(8))},
                "hypotheses": HYP["unwindowed"],
            },
            "windowed": {"search": CONFIG.describe(), "hypotheses": HYP["windowed"]},
        },
        "sequences": {"path": "outputs/fixture.jsonl", "sha256": "0" * 64},
        "cohort": {"prompts_path": "fixture.jsonl"},
        "trial_count": len(trials),
        "trials": trials,
        "conditions": conditions,
    }


class WindowedReportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = build_cases()
        self.report = build_report()

    def validate(self, report):
        return validate_windowed_report(
            report,
            self.cases,
            expected_null_keys=NULL_KEYS,
            expected_replicates=REPLICATES,
            expected_target_fpr=TARGET_FPR,
        )

    def test_a_consistent_report_validates_and_pairs_the_searches(self) -> None:
        result = self.validate(self.report)
        self.assertTrue(result["valid"])
        self.assertEqual(result["edit"], "deletion")
        self.assertEqual(len(result["paired_comparison"]), len(RATES))
        self.assertEqual(result["hypotheses_by_search"], HYP)
        for pair in result["paired_comparison"]:
            self.assertAlmostEqual(
                pair["detection_rate_gain"],
                pair["windowed_detection_rate"] - pair["unwindowed_detection_rate"],
            )

    def test_the_windowed_search_must_contain_the_full_read_window(self) -> None:
        report = copy.deepcopy(self.report)
        report["searches"]["windowed"]["search"]["window_tokens"] = [16]
        with self.assertRaisesRegex(ValueError, "must include the full-read window"):
            self.validate(report)

    def test_drift_must_be_declared_signed_in_both_directions(self) -> None:
        report = copy.deepcopy(self.report)
        report["searches"]["windowed"]["search"]["drift_is_signed"] = False
        with self.assertRaisesRegex(ValueError, "drift must be declared as signed"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        report["searches"]["windowed"]["search"]["drift_offsets"] = [0, 1, 2]
        with self.assertRaisesRegex(ValueError, "signed in both directions"):
            self.validate(report)

    def test_the_windowed_search_must_score_more_hypotheses(self) -> None:
        report = copy.deepcopy(self.report)
        report["searches"]["windowed"]["hypotheses"] = 1
        with self.assertRaisesRegex(ValueError, "more hypotheses than the comparator"):
            self.validate(report)

    def test_both_searches_must_score_the_same_trials(self) -> None:
        report = copy.deepcopy(self.report)
        report["trials"] = [
            r
            for r in report["trials"]
            if not (r["search_id"] == "unwindowed" and r["family"] == "positive")
        ]
        report["trial_count"] = len(report["trials"])
        with self.assertRaisesRegex(ValueError, "must score the same trials"):
            self.validate(report)

    def test_a_negative_key_start_is_rejected(self) -> None:
        report = copy.deepcopy(self.report)
        for row in report["trials"]:
            if row["search_id"] == "windowed":
                row["window_start"] = 0
                row["drift"] = -1
                break
        with self.assertRaisesRegex(ValueError, "negative key start"):
            self.validate(report)

    def test_reported_aggregates_must_match_the_stored_trials(self) -> None:
        report = copy.deepcopy(self.report)
        report["conditions"][0]["positive"]["detection_rate"] = 0.123
        with self.assertRaisesRegex(ValueError, "detection rate does not match"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        report["conditions"][0]["positive"]["recovered_drift"] = [99]
        with self.assertRaisesRegex(ValueError, "recovered drift set"):
            self.validate(report)

    def test_forbidden_raw_fields_are_rejected(self) -> None:
        report = copy.deepcopy(self.report)
        report["trials"][0]["observed_dna"] = "ATCG"
        with self.assertRaisesRegex(ValueError, "forbidden raw field"):
            self.validate(report)


if __name__ == "__main__":
    unittest.main()
