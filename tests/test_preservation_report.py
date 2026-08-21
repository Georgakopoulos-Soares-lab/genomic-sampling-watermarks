from __future__ import annotations

import copy
import unittest

from genomic_watermarks.gof import summarize_p_values
from genomic_watermarks.models.huggingface import POLICIES
from genomic_watermarks.pilot import ContextCase
from genomic_watermarks.preservation_report import validate_preservation_report
from genomic_watermarks.watermark import ORDINARY_SCHEME, PARTITION_MC_SCHEME

DRAWS = 40
REPLICATES = 99
SEED = 7


def build_cases(count: int = 3) -> tuple[ContextCase, ...]:
    return tuple(
        ContextCase(
            case_id=f"case_{index}",
            sequence="ATCGGC" * (2 + index),
            cohort_id="fixture_cohort",
        )
        for index in range(count)
    )


def build_report(cases: tuple[ContextCase, ...], p_values: dict[str, tuple[float, float]]):
    spec = POLICIES["C_tok"].policy
    states = []
    for case in cases:
        watermarked_p, ordinary_p = p_values[case.case_id]
        states.append(
            {
                "case_id": case.case_id,
                "prompt_sequence_sha256": case.sequence_sha256,
                "context_bases": len(case.sequence),
                "draws_per_arm": DRAWS,
                "entropy_bits": 10.0,
                "effective_support": 500.0,
                "top1_mass": 0.01,
                "categories": 4096,
                "watermarked_agreement_rate": 0.95,
                "watermarked": {
                    "statistic": 100.0,
                    "p_value": watermarked_p,
                    "distinct_tokens": 30,
                },
                "ordinary": {
                    "statistic": 101.0,
                    "p_value": ordinary_p,
                    "distinct_tokens": 31,
                },
            }
        )
    return {
        "schema_version": 1,
        "classification": "engineering_pilot_not_paper_evidence",
        "complete": True,
        "policy_id": "C_tok",
        "model_id": spec.model_id,
        "revision": spec.revision,
        "cohort_id": "fixture_cohort",
        "case_count": len(cases),
        "case_ids": [case.case_id for case in cases],
        "watermark_method": PARTITION_MC_SCHEME,
        "control_method": ORDINARY_SCHEME,
        "key_source": "public_fixture",
        "stream_domain": "fixture/label",
        "temperature": 1.0,
        "truncation": "none",
        "device": "mps",
        "dtype": "bfloat16",
        "test": {
            "draws_per_state_and_arm": DRAWS,
            "replicates": REPLICATES,
            "seed": SEED,
        },
        "states": states,
        "watermarked_p_value_family": summarize_p_values(
            {case.case_id: p_values[case.case_id][0] for case in cases}
        ),
        "ordinary_p_value_family": summarize_p_values(
            {case.case_id: p_values[case.case_id][1] for case in cases}
        ),
    }


class PreservationReportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = build_cases()
        self.p_values = {
            "case_0": (0.50, 0.30),
            "case_1": (0.20, 0.80),
            "case_2": (0.02, 0.60),
        }
        self.report = build_report(self.cases, self.p_values)

    def validate(self, report):
        return validate_preservation_report(
            report,
            self.cases,
            expected_draws=DRAWS,
            expected_replicates=REPLICATES,
            expected_seed=SEED,
        )

    def test_a_consistent_report_validates_and_reports_multiplicity(self) -> None:
        result = self.validate(self.report)
        self.assertTrue(result["valid"])
        self.assertEqual(result["policy_id"], "C_tok")
        self.assertEqual(result["state_count"], 3)
        self.assertEqual(result["watermarked_rejections_at_alpha"], 1)
        self.assertEqual(result["watermarked_rejections_at_bonferroni"], 0)
        self.assertEqual(result["ordinary_rejections_at_alpha"], 0)
        self.assertAlmostEqual(result["bonferroni_alpha"], 0.05 / 3)
        self.assertAlmostEqual(result["watermarked_minimum_p_value"], 0.02)
        self.assertTrue(result["raw_fields_absent"])

    def test_bonferroni_rejection_is_reported_when_it_happens(self) -> None:
        report = build_report(
            self.cases,
            {"case_0": (0.50, 0.30), "case_1": (0.20, 0.80), "case_2": (0.01, 0.60)},
        )
        result = self.validate(report)
        self.assertEqual(result["watermarked_rejections_at_bonferroni"], 1)

    def test_wrong_revision_device_or_dtype_is_rejected(self) -> None:
        for field, value, message in (
            ("revision", "0" * 40, "revision does not match"),
            ("device", "cpu", "must use MPS"),
            ("dtype", "float32", "dtype violates"),
            ("temperature", 0.8, "temperature must equal"),
            ("truncation", "top_k", "truncation must be disabled"),
            ("key_source", "runtime_environment", "published fixture key"),
            ("watermark_method", "its", "unexpected watermark method"),
        ):
            report = copy.deepcopy(self.report)
            report[field] = value
            with self.assertRaisesRegex(ValueError, message):
                self.validate(report)

    def test_forbidden_raw_fields_are_rejected(self) -> None:
        for field in ("key", "logits", "probabilities", "sequence", "tokens"):
            report = copy.deepcopy(self.report)
            report["states"][0][field] = "value"
            with self.assertRaisesRegex(ValueError, "forbidden raw field"):
                self.validate(report)

    def test_cohort_and_state_consistency_is_enforced(self) -> None:
        report = copy.deepcopy(self.report)
        report["states"][1]["prompt_sequence_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "prompt checksum is inconsistent"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        report["states"][1]["context_bases"] = 12345
        with self.assertRaisesRegex(ValueError, "context length is inconsistent"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        report["case_ids"] = ["case_1", "case_0", "case_2"]
        with self.assertRaisesRegex(ValueError, "retain cohort order"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        report["case_ids"] = ["case_0", "case_1", "unknown"]
        with self.assertRaisesRegex(ValueError, "unknown case"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        report["case_count"] = 99
        with self.assertRaisesRegex(ValueError, "case_count is inconsistent"):
            self.validate(report)

    def test_test_shape_must_match_the_frozen_protocol(self) -> None:
        for field, message in (
            ("draws_per_state_and_arm", "draws per state and arm"),
            ("replicates", "replicates is inconsistent"),
            ("seed", "Monte Carlo seed"),
        ):
            report = copy.deepcopy(self.report)
            report["test"][field] = 1
            with self.assertRaisesRegex(ValueError, message):
                self.validate(report)

    def test_invalid_p_values_are_rejected(self) -> None:
        report = copy.deepcopy(self.report)
        report["states"][0]["watermarked"]["p_value"] = 0.0
        with self.assertRaisesRegex(ValueError, "invalid watermarked p-value"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        report["states"][0]["watermarked"]["p_value"] = 0.1234567
        with self.assertRaisesRegex(ValueError, "Monte Carlo lattice"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        report["states"][0]["ordinary"]["distinct_tokens"] = DRAWS + 1
        with self.assertRaisesRegex(ValueError, "distinct token count"):
            self.validate(report)

    def test_family_summary_must_match_the_state_p_values(self) -> None:
        report = copy.deepcopy(self.report)
        report["watermarked_p_value_family"]["minimum_p_value"] = 0.99
        with self.assertRaisesRegex(ValueError, "family summary minimum_p_value"):
            self.validate(report)

        report = copy.deepcopy(self.report)
        del report["ordinary_p_value_family"]["rejections_at_alpha"]
        with self.assertRaisesRegex(ValueError, "family summary is missing"):
            self.validate(report)


if __name__ == "__main__":
    unittest.main()
