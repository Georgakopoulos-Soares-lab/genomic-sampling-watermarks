from __future__ import annotations

import copy
import hashlib
import unittest

from genomic_watermarks.metrics import information_bits_per_base
from genomic_watermarks.models.huggingface import POLICIES
from genomic_watermarks.pilot import ContextCase, numeric_summary
from genomic_watermarks.sequential import (
    PATH_SAMPLING_SCHEME,
    PUBLIC_EVALUATION_SCHEME,
    evaluation_partition_domains,
    public_evaluation_material_sha256,
)
from genomic_watermarks.sequential_report import validate_sequential_report


def context_case(case_id: str, sequence: str) -> ContextCase:
    return ContextCase(
        case_id,
        sequence,
        cohort_id="cohort",
        organism="Example organism",
        accession="NC_1.1",
        start=1,
        stop=len(sequence),
        sequence_sha256=hashlib.sha256(sequence.encode("ascii")).hexdigest(),
    )


def valid_report(cases: tuple[ContextCase, ...]) -> dict[str, object]:
    masses = (0.5, 0.75)
    information = tuple(information_bits_per_base(mass) for mass in masses)
    states: list[dict[str, object]] = []
    prompt_summaries: list[dict[str, object]] = []
    for case in cases:
        prompt_rows: list[dict[str, object]] = []
        for state_index in range(2):
            row: dict[str, object] = {
                "case_id": case.case_id,
                "state_index": state_index,
                "context_bases": len(case.sequence) + 6 * state_index,
                "entropy_bits": 1.0 + state_index,
                "effective_support": 2.0 + state_index,
                "top1_mass": 0.5,
                "partition_masses": list(masses),
                "information_bits_per_base": list(information),
            }
            states.append(row)
            prompt_rows.append(row)
        prompt_summaries.append(
            {
                "case_id": case.case_id,
                "prompt_sequence_sha256": case.sequence_sha256,
                "information_bits_per_base": numeric_summary(
                    value
                    for row in prompt_rows
                    for value in row["information_bits_per_base"]  # type: ignore[union-attr]
                ),
            }
        )
    policy = POLICIES["G_bp"].policy
    return {
        "schema_version": 1,
        "classification": "engineering_pilot_not_paper_evidence",
        "complete": True,
        "policy_id": "G_bp",
        "model_id": policy.model_id,
        "revision": policy.revision,
        "cohort_id": "cohort",
        "case_count": len(cases),
        "case_ids": [case.case_id for case in cases],
        "states_per_prompt": 2,
        "state_count": len(states),
        "generated_bases_per_prompt": 12,
        "temperature": 1.0,
        "truncation": "none",
        "device": "mps",
        "dtype": "float32",
        "path_sampling": {
            "scheme": PATH_SAMPLING_SCHEME,
            "base_seed": 1729,
            "watermarked": False,
        },
        "partition_evaluation": {
            "scheme": PUBLIC_EVALUATION_SCHEME,
            "public_material_sha256": public_evaluation_material_sha256(),
            "domains": list(evaluation_partition_domains("cohort", "G_bp", 2)),
            "partitions_per_state": 2,
            "paired_and_reused_across_states": True,
        },
        "summary": {
            "entropy_bits": numeric_summary(float(row["entropy_bits"]) for row in states),
            "effective_support": numeric_summary(float(row["effective_support"]) for row in states),
            "top1_mass": numeric_summary(float(row["top1_mass"]) for row in states),
            "information_bits_per_base": numeric_summary(
                value
                for row in states
                for value in row["information_bits_per_base"]  # type: ignore[union-attr]
            ),
        },
        "prompt_summaries": prompt_summaries,
        "states": states,
    }


class SequentialReportValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = (
            context_case("one", "ATCGGC" * 2),
            context_case("two", "GCGCAT" * 2),
        )

    def test_accepts_complete_derived_report(self) -> None:
        validation = validate_sequential_report(
            valid_report(self.cases),
            self.cases,
            expected_states_per_prompt=2,
            expected_partitions_per_state=2,
        )
        self.assertTrue(validation["valid"])
        self.assertEqual(validation["state_count"], 4)

    def test_rejects_information_that_does_not_match_partition_mass(self) -> None:
        report = valid_report(self.cases)
        report["states"][0]["information_bits_per_base"][0] = 0.0  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "does not match its partition mass"):
            validate_sequential_report(
                report,
                self.cases,
                expected_states_per_prompt=2,
                expected_partitions_per_state=2,
            )

    def test_rejects_raw_sequence_field(self) -> None:
        report = copy.deepcopy(valid_report(self.cases))
        report["sequence"] = "ATCG"
        with self.assertRaisesRegex(ValueError, "forbidden raw field"):
            validate_sequential_report(
                report,
                self.cases,
                expected_states_per_prompt=2,
                expected_partitions_per_state=2,
            )


if __name__ == "__main__":
    unittest.main()
