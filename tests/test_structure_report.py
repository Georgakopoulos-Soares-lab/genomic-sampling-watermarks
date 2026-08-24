"""Validation tests for the E15 order-sensitive proxy report.

The result of E15 is the paired sign-flip p-value, not the relative shift, so the
tests that matter here tamper with the p-value and with the reference model's
independence. A report whose magnitudes were right and whose p-values were wrong
would invert the conclusion from "unpriced" to "priced".
"""

from __future__ import annotations

import copy
import statistics
import unittest

from genomic_watermarks.attacks import BLOCK_SHUFFLE_ATTACK, SHUFFLE_ATTACK, SPLICE_ATTACK
from genomic_watermarks.pilot import ContextCase, numeric_summary
from genomic_watermarks.sequence_proxies import PROXY_METRICS, exact_sign_flip_test
from genomic_watermarks.structure_proxies import STRUCTURE_METRICS
from genomic_watermarks.structure_report import validate_structure_report
from genomic_watermarks.watermark import PARTITION_MC_SCHEME

# Six scored prompts, because the exact sign-flip null over n prompts cannot reach
# 0.05 below n = 6: with four prompts the smallest attainable p-value is 0.125.
SCORED = ("case_0", "case_1", "case_2", "case_3", "case_4", "case_5")
HELD_OUT = ("case_6", "case_7", "case_8", "case_9")
ORDERS = (3,)
WIDTHS = (2, 8)
DONORS = (2,)
BOUNDARY = (
    "A change in a chance reading frame is NOT evidence of functional consequences, and the "
    "reference is not an independent biological model."
)


def build_cases() -> tuple[ContextCase, ...]:
    return tuple(
        ContextCase(case_id=name, sequence="ATCGGC" * 16, cohort_id="fixture_cohort")
        for name in SCORED + HELD_OUT
    )


def metrics(longest_orf: float, score: float) -> dict[str, float]:
    return {
        "longest_orf_bases": longest_orf,
        "orf_count": 12.0,
        "orf_coding_fraction": 0.5,
        "independent_model_mean_log2_probability": score,
    }


def composition(gc: float) -> dict[str, float]:
    return {metric: (gc if metric == "gc_fraction" else 0.5) for metric in PROXY_METRICS}


def row(
    attack: str,
    parameter: object,
    case_id: str,
    reference_case_id: str,
    orf_before: float,
    orf_after: float,
) -> dict[str, object]:
    entry: dict[str, object] = {
        "attack": attack,
        "parameter": parameter,
        "case_id": case_id,
        "reference_case_id": reference_case_id,
    }
    for order in ORDERS:
        key = f"structure_order_{order}"
        after = metrics(orf_after, -1.97)
        before = metrics(orf_before, -1.96)
        entry[key] = after
        entry[f"{key}_reference"] = before
        entry[f"{key}_relative_shift"] = {
            metric: abs(after[metric] - before[metric]) / (abs(before[metric]) or 1.0)
            for metric in STRUCTURE_METRICS
        }
    entry["composition_relative_shift"] = {
        metric: (0.02 if metric != "longest_homopolymer_run" else 0.15) for metric in PROXY_METRICS
    }
    return entry


def build_report() -> dict[str, object]:
    rows: list[dict[str, object]] = []
    # A full shuffle where every prompt moves the same way: a directional effect.
    for index, case_id in enumerate(SCORED):
        rows.append(row(SHUFFLE_ATTACK, None, case_id, case_id, 400.0, 400.0 - 50.0 - index))
    # Block shuffles where the direction alternates: magnitude without direction.
    for width in WIDTHS:
        for index, case_id in enumerate(SCORED):
            delta = 60.0 if index % 2 == 0 else -60.0
            rows.append(row(BLOCK_SHUFFLE_ATTACK, width, case_id, case_id, 400.0, 400.0 + delta))
    for donors in DONORS:
        for index, case_id in enumerate(SCORED):
            rows.append(
                row(SPLICE_ATTACK, donors, f"splice_{donors}_{index}", case_id, 400.0, 470.0)
            )

    summaries: list[dict[str, object]] = []
    for attack, parameter in (
        [(SHUFFLE_ATTACK, None)]
        + [(BLOCK_SHUFFLE_ATTACK, width) for width in WIDTHS]
        + [(SPLICE_ATTACK, donors) for donors in DONORS]
    ):
        selected = [r for r in rows if r["attack"] == attack and r["parameter"] == parameter]
        entry: dict[str, object] = {
            "attack": attack,
            "parameter": parameter,
            "trials": len(selected),
        }
        comp = {
            metric: numeric_summary(r["composition_relative_shift"][metric] for r in selected)
            for metric in PROXY_METRICS
        }
        entry["composition_relative_shift"] = comp
        largest = max(PROXY_METRICS, key=lambda m: comp[m]["mean"])
        entry["largest_composition_metric"] = largest
        entry["largest_composition_shift"] = comp[largest]["mean"]
        for order in ORDERS:
            key = f"structure_order_{order}"
            block: dict[str, object] = {
                "relative_shift": {
                    metric: numeric_summary(r[f"{key}_relative_shift"][metric] for r in selected)
                    for metric in STRUCTURE_METRICS
                }
            }
            if attack != SPLICE_ATTACK:
                block["sign_flip"] = {
                    metric: exact_sign_flip_test(
                        [r[key][metric] - r[f"{key}_reference"][metric] for r in selected]
                    )
                    for metric in STRUCTURE_METRICS
                }
            entry[key] = block
        summaries.append(entry)

    return {
        "schema_version": 1,
        "classification": "engineering_pilot_not_paper_evidence",
        "complete": True,
        "policy_id": "C_tok",
        "cohort_id": "fixture_cohort",
        "experiment_label": "fixture-e4",
        "watermark_method": PARTITION_MC_SCHEME,
        "case_count": len(SCORED),
        "case_ids": list(SCORED),
        "attacks": [SHUFFLE_ATTACK, BLOCK_SHUFFLE_ATTACK, SPLICE_ATTACK],
        "block_widths": list(WIDTHS),
        "donor_counts": list(DONORS),
        "splice_draws_per_donor_count": 1,
        "markov_orders": list(ORDERS),
        "minimum_orf_codons": 25,
        "composition_metrics": list(PROXY_METRICS),
        "structure_metrics": list(STRUCTURE_METRICS),
        "reference_model": {
            "kind": "order-k Markov over DNA with Laplace smoothing",
            "fitted_on": "cohort prompts not used by any detection experiment",
            "held_out_prompt_count": len(HELD_OUT),
            "held_out_prompt_ids": list(HELD_OUT),
            "overlaps_scored_prompts": False,
            "contexts_by_order": {"3": 64},
        },
        "sequences": {"path": "fixture.jsonl", "sha256": "0" * 64},
        "cohort": {"prompts_path": "fixture.jsonl"},
        "row_count": len(rows),
        "rows": rows,
        "summaries": summaries,
        "interpretation_boundary": BOUNDARY,
        "boundary": "Prices attacks whose detection outcome was measured elsewhere.",
    }


class StructureReportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.report = build_report()
        self.cases = build_cases()

    def validate(self, report: dict) -> dict:
        return validate_structure_report(report, self.cases)

    def test_a_consistent_report_validates(self) -> None:
        result = self.validate(self.report)
        self.assertTrue(result["valid"])
        self.assertTrue(result["reference_held_out"])
        self.assertEqual(result["reference_prompt_count"], len(HELD_OUT))

    def test_the_fixture_separates_direction_from_magnitude(self) -> None:
        """The distinction the whole experiment turns on."""

        conditions = {
            (c["attack"], c["parameter"]): c for c in self.validate(self.report)["conditions"]
        }
        full = conditions[(SHUFFLE_ATTACK, None)]
        block = conditions[(BLOCK_SHUFFLE_ATTACK, 2)]
        # The block shuffle has the larger magnitude and no direction.
        self.assertGreater(block["longest_orf_relative_shift"], full["longest_orf_relative_shift"])
        self.assertLessEqual(full["longest_orf_sign_flip_p_value"], 0.05)
        self.assertGreater(block["longest_orf_sign_flip_p_value"], 0.05)
        self.assertEqual(self.validate(self.report)["conditions_with_directional_orf_effect"], 1)

    def test_a_reference_fitted_on_a_scored_prompt_is_rejected(self) -> None:
        """Otherwise the independent-model score is circular."""

        tampered = copy.deepcopy(self.report)
        tampered["reference_model"]["held_out_prompt_ids"] = [*HELD_OUT, SCORED[0]]
        with self.assertRaisesRegex(ValueError, "saw scored prompt"):
            self.validate(tampered)

    def test_an_unflagged_overlap_claim_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        tampered["reference_model"]["overlaps_scored_prompts"] = True
        with self.assertRaisesRegex(ValueError, "does not overlap"):
            self.validate(tampered)

    def test_a_tampered_sign_flip_p_value_is_rejected(self) -> None:
        """The p-value is the result, so it is recomputed rather than trusted."""

        tampered = copy.deepcopy(self.report)
        for summary in tampered["summaries"]:
            if summary["attack"] == BLOCK_SHUFFLE_ATTACK:
                summary["structure_order_3"]["sign_flip"]["longest_orf_bases"]["p_value"] = 0.001
                break
        with self.assertRaisesRegex(ValueError, "sign-flip p-value"):
            self.validate(tampered)

    def test_a_tampered_relative_shift_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        tampered["rows"][0]["structure_order_3_relative_shift"]["longest_orf_bases"] = 9.0
        with self.assertRaisesRegex(ValueError, "relative shift for longest_orf_bases"):
            self.validate(tampered)

    def test_a_missing_paired_test_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        for summary in tampered["summaries"]:
            if summary["attack"] == BLOCK_SHUFFLE_ATTACK:
                del summary["structure_order_3"]["sign_flip"]
                break
        with self.assertRaisesRegex(ValueError, "missing its paired test"):
            self.validate(tampered)

    def test_a_paired_test_on_a_splice_is_rejected(self) -> None:
        """A splice has no single source, so a paired test would be meaningless."""

        tampered = copy.deepcopy(self.report)
        for summary in tampered["summaries"]:
            if summary["attack"] == SPLICE_ATTACK:
                summary["structure_order_3"]["sign_flip"] = {
                    metric: {"p_value": 0.01} for metric in STRUCTURE_METRICS
                }
                break
        with self.assertRaisesRegex(ValueError, "paired test is not defined"):
            self.validate(tampered)

    def test_a_missing_interpretation_boundary_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        tampered["interpretation_boundary"] = "reading frames were measured"
        with self.assertRaisesRegex(ValueError, "interpretation boundary must state"):
            self.validate(tampered)

    def test_a_raw_sequence_field_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        tampered["rows"][0]["generated_dna"] = "ACGTAC"
        with self.assertRaisesRegex(ValueError, "forbidden raw field"):
            self.validate(tampered)

    def test_the_largest_composition_metric_must_be_right(self) -> None:
        tampered = copy.deepcopy(self.report)
        tampered["summaries"][0]["largest_composition_metric"] = "gc_fraction"
        with self.assertRaisesRegex(ValueError, "wrong largest composition metric"):
            self.validate(tampered)

    def test_the_independent_model_shift_is_reported(self) -> None:
        result = self.validate(self.report)
        expected = statistics.fmean([abs(-1.97 - -1.96) / 1.96])
        self.assertAlmostEqual(result["largest_independent_model_shift"], expected, places=9)


if __name__ == "__main__":
    unittest.main()
