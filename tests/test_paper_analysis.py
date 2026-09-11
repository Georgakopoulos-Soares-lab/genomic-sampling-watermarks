from __future__ import annotations

import copy
import math
import unittest

from genomic_watermarks.paper_analysis import (
    CONDITIONS,
    FAMILIES,
    detection_summary,
    quality_summary,
)


def quality_fixture() -> dict:
    names = ["mean_negative_log_likelihood_per_token", *[f"metric_{i}" for i in range(13)]]
    return {
        "multiple_testing_family": names,
        "prompt_count": 256,
        "pair_count": 512,
        "main_key_averaged": {
            name: {
                "paired": {
                    "mean_difference": -2.0,
                    "standardized_effect": -0.5,
                    "interval_lower": -6.0,
                    "interval_upper": 1.0,
                    "p_value": 0.5,
                    "benjamini_hochberg_p_value": 0.8,
                },
                "ordinary": {"mean": 10.0},
                "watermarked": {"mean": 8.0},
            }
            for name in names
        },
    }


def detection_fixture() -> tuple[list[dict], dict]:
    trials, cells = [], []
    for condition in CONDITIONS:
        for family in FAMILIES:
            has_positive_draw = condition != "deletion_1nt"
            for draw in (0, 1):
                detected = has_positive_draw and draw == 0
                trials.append(
                    {
                        "case_id": "paired-prompt",
                        "draw_id": draw,
                        "condition": condition,
                        "family": family,
                        "hypotheses_searched": 100,
                        "target_false_positive_rate": 0.01,
                        "minimum_local_log_p_value": -1000.0 if detected else -1.0,
                        "minimum_local_p_value": 0.0 if detected else math.exp(-1.0),
                        "sequence_log_p_value": -1000.0 + math.log(100) if detected else 0.0,
                        "detected": detected,
                        "best_hypothesis": {"window_base_length": 384},
                    }
                )
            cells.append(
                {
                    "condition": condition,
                    "family": family,
                    "detections": int(has_positive_draw),
                    "trials": 2,
                    "prompt_both_draws": {
                        "detections": 0,
                        "trials": 1,
                        "exact_95_interval": [0.0, 0.975],
                    },
                    "prompt_any_draw": {
                        "detections": int(has_positive_draw),
                        "trials": 1,
                        "exact_95_interval": [0.025, 1.0] if has_positive_draw else [0.0, 0.975],
                    },
                    "winning_window_base_length_counts": {"384": 2},
                }
            )
    return trials, {"evaluation_prompts": 1, "rates": cells}


class PaperAnalysisTest(unittest.TestCase):
    def test_negative_effect_preserves_interval_order_and_scale(self) -> None:
        row = quality_summary(quality_fixture())["rows"][0]
        self.assertEqual(row["interval_lower"], -1.5)
        self.assertEqual(row["interval_upper"], 0.25)
        self.assertEqual(row["standardization_scale"], 0.25)

    def test_zero_difference_does_not_invent_a_variance(self) -> None:
        source = quality_fixture()
        source["main_key_averaged"]["metric_0"]["paired"]["mean_difference"] = 0
        with self.assertRaisesRegex(ValueError, "cannot recover"):
            quality_summary(source)

    def test_prompt_event_and_edit_condition_are_not_pooled(self) -> None:
        trials, source = detection_fixture()
        result = detection_summary(trials, source)
        self.assertEqual(result["clean"][FAMILIES[0]]["positive_prompts"], 0)
        self.assertEqual(result["clean"][FAMILIES[2]]["positive_prompts"], 1)
        self.assertEqual(result["deletion_1nt"][FAMILIES[2]]["positive_prompts"], 0)
        self.assertEqual(
            result["deletion_1nt"][FAMILIES[2]]["exact_95_percent_interval"], [0.0, 97.5]
        )

    def test_underflowed_probability_keeps_finite_strength(self) -> None:
        trials, source = detection_fixture()
        result = detection_summary(trials, source)
        self.assertAlmostEqual(result["clean"][FAMILIES[0]]["maximum"], 1000 / math.log(10))

    def test_missing_or_duplicate_trial_is_rejected(self) -> None:
        trials, source = detection_fixture()
        for bad in (trials[:-1], trials[:-1] + [copy.deepcopy(trials[0])]):
            with self.assertRaisesRegex(ValueError, "trial grid"):
                detection_summary(bad, source)

    def test_uncorrected_probability_cannot_be_used_as_read_probability(self) -> None:
        trials, source = detection_fixture()
        trials[0]["sequence_log_p_value"] = trials[0]["minimum_local_log_p_value"]
        with self.assertRaisesRegex(ValueError, "full-search correction"):
            detection_summary(trials, source)


if __name__ == "__main__":
    unittest.main()
