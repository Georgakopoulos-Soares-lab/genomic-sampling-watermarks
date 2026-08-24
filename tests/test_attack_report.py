"""Validation tests for the E11/E12 key-reuse attack report.

The two checks specific to this experiment are the ones tampered with hardest: the
threshold must come from unattacked nulls, and the report must state which
direction each family's detection rate points. A spoofing rate of 1.000 and a
genuine rate of 1.000 mean opposite things, and a report that does not say so
invites a reader to average them.
"""

from __future__ import annotations

import copy
import math
import unittest

from genomic_watermarks.attack_report import validate_attack_report
from genomic_watermarks.attacks import BLOCK_SHUFFLE_ATTACK, SHUFFLE_ATTACK, SPLICE_ATTACK
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
LENGTHS = (32,)
PROMPTS = ("case_0", "case_1", "case_2", "case_3")
DONORS = (2, 4)
WIDTHS = (2, 8)
REPLICATES = 200
SEED = 11
MIN_WINDOW = 8
PROXIES = ("gc_fraction", "cpg_fraction")


def hypotheses_at(token_length: int) -> int:
    scorable = sum(
        1 for phase in range(6) if (token_length if phase == 0 else token_length - 1) >= MIN_WINDOW
    )
    return len(ORIENTATIONS) * scorable * OFFSETS


def build_cases() -> tuple[ContextCase, ...]:
    return tuple(
        ContextCase(case_id=name, sequence="ATCGGC" * 16, cohort_id="fixture_cohort")
        for name in PROMPTS
    )


def trial(
    family: str,
    cluster: str,
    length: int,
    matches: int,
    *,
    attack: str | None = None,
    parameter: object = None,
    key_index: int | None = None,
    displaced: float | None = None,
    replicate: int | None = None,
) -> dict[str, object]:
    return {
        "family": family,
        "attack": attack,
        "parameter": parameter,
        "cluster": cluster,
        "key_index": key_index,
        "replicate": replicate,
        "token_length": length,
        "base_length": length * 6,
        "statistic": standardized_agreement(matches, length),
        "matches": matches,
        "total": length,
        "displaced_fraction": displaced,
        "orientation": ORIENTATIONS[0],
        "phase": 0,
        "stream_offset": 0,
        "hypotheses_searched": hypotheses_at(length),
    }


def build_report() -> dict[str, object]:
    trials: list[dict[str, object]] = []
    for length in LENGTHS:
        for index, case_id in enumerate(PROMPTS):
            trials.append(trial("genuine", case_id, length, length - index % 2))
            # Forgeries score like genuine output: that is the vulnerability.
            for donors in DONORS:
                trials.append(
                    trial(
                        "spoof",
                        case_id,
                        length,
                        length - index % 2,
                        attack=SPLICE_ATTACK,
                        parameter=donors,
                        replicate=index,
                    )
                )
            trials.append(
                trial(
                    "removal",
                    case_id,
                    length,
                    length // 2,
                    attack=SHUFFLE_ATTACK,
                    displaced=0.99,
                )
            )
            for width in WIDTHS:
                trials.append(
                    trial(
                        "removal",
                        case_id,
                        length,
                        length // 2 + (0 if width > 4 else 6),
                        attack=BLOCK_SHUFFLE_ATTACK,
                        parameter=width,
                        displaced=0.5 if width == 2 else 0.9,
                    )
                )
            for family in ("fixed_key_many_query_ordinary", "fixed_key_many_query_public_dna"):
                trials.append(trial(family, case_id, length, length // 2 + 1))
            for key_index in range(NULL_KEYS):
                base = length // 2 + (index + key_index) % 3
                trials.append(
                    trial("wrong_key_watermarked", case_id, length, base, key_index=key_index)
                )
                trials.append(trial("any_key_ordinary", case_id, length, base, key_index=key_index))

    lengths_report: list[dict[str, object]] = []
    for length in LENGTHS:
        rows = [row for row in trials if row["token_length"] == length]
        pooled = [
            float(row["statistic"])
            for row in rows
            if row["family"] in {"wrong_key_watermarked", "any_key_ordinary"}
        ]
        calibration = calibrate_threshold(pooled, TARGET_FPR)
        cells: list[dict[str, object]] = []
        keys = [("genuine", None, None)]
        keys.extend(("spoof", SPLICE_ATTACK, donors) for donors in DONORS)
        keys.append(("removal", SHUFFLE_ATTACK, None))
        keys.extend(("removal", BLOCK_SHUFFLE_ATTACK, width) for width in WIDTHS)
        keys.extend(
            (family, None, None)
            for family in (
                "fixed_key_many_query_ordinary",
                "fixed_key_many_query_public_dna",
                "wrong_key_watermarked",
                "any_key_ordinary",
            )
        )
        for family, attack, parameter in keys:
            selected = [
                row
                for row in rows
                if row["family"] == family
                and row["attack"] == attack
                and row["parameter"] == parameter
            ]
            values = [float(row["statistic"]) for row in selected]
            by_cluster: dict[str, list[float]] = {}
            for row in selected:
                by_cluster.setdefault(str(row["cluster"]), []).append(float(row["statistic"]))
            entry: dict[str, object] = {
                "family": family,
                "attack": attack,
                "parameter": parameter,
                "trials": len(values),
                "detection_rate": detection_rate(values, calibration.threshold),
                "statistic": numeric_summary(values),
                "maximum_empirical_global_p_value": max(
                    empirical_p_value(value, pooled) for value in values
                ),
            }
            displaced = [
                row["displaced_fraction"]
                for row in selected
                if row["displaced_fraction"] is not None
            ]
            if displaced:
                entry["displaced_fraction"] = numeric_summary(displaced)
            if len(by_cluster) >= 2:
                entry["detection_rate_joint_interval"] = joint_detection_rate_interval(
                    by_cluster, pooled, TARGET_FPR, replicates=REPLICATES, seed=SEED
                )
            cells.append(entry)
        lengths_report.append(
            {
                "token_length": length,
                "base_length": length * 6,
                "hypotheses_searched": hypotheses_at(length),
                "calibration": {
                    "pooled_null_families": ["wrong_key_watermarked", "any_key_ordinary"],
                    "pooled_null_trials": len(pooled),
                    "target_false_positive_rate": TARGET_FPR,
                    "achieved_false_positive_rate": calibration.achieved_false_positive_rate,
                    "attainable_false_positive_rate": calibration.attainable_false_positive_rate,
                    "target_is_attainable": calibration.is_attainable,
                    "threshold": calibration.threshold,
                },
                "cells": cells,
            }
        )

    utility = [
        {
            "attack": attack,
            "parameter": parameter,
            "proxies": {"gc_fraction": 0.5, "cpg_fraction": 0.02},
            "reference_proxies": {"gc_fraction": 0.51, "cpg_fraction": 0.021},
        }
        for attack, parameter in (
            (SPLICE_ATTACK, 2),
            (SHUFFLE_ATTACK, None),
            (BLOCK_SHUFFLE_ATTACK, 2),
        )
    ]

    return {
        "schema_version": 1,
        "classification": "engineering_pilot_not_paper_evidence",
        "complete": True,
        "policy_id": "C_tok",
        "cohort_id": "fixture_cohort",
        "experiment_label": "fixture-e4",
        "watermark_method": PARTITION_MC_SCHEME,
        "control_method": ORDINARY_SCHEME,
        "decision_rule": DECISION_RULE,
        "attacks": [SPLICE_ATTACK, SHUFFLE_ATTACK, BLOCK_SHUFFLE_ATTACK],
        "attacker_knowledge": (
            "generated DNA and the public configuration only. The attacker never queries the "
            "model, never observes a probability, and never observes the key."
        ),
        "key_source": "public_fixture",
        "null_key_source": "public_fixture_labels",
        "null_keys": NULL_KEYS,
        "case_count": len(PROMPTS),
        "case_ids": list(PROMPTS),
        "outputs_available_to_attacker": len(PROMPTS),
        "donor_counts": list(DONORS),
        "block_widths": list(WIDTHS),
        "splice_draws_per_donor_count": 1,
        "token_lengths": list(LENGTHS),
        "detector_search": {
            "orientations": list(ORIENTATIONS),
            "phases": list(range(6)),
            "window_tokens": "full_sequence_only",
            "window_stride_tokens": 0,
            "stream_offsets": list(range(OFFSETS)),
            "minimum_window_tokens": MIN_WINDOW,
        },
        "support_size": 4096,
        "sequences": {"path": "fixture.jsonl", "sha256": "0" * 64},
        "cohort": {"prompts_path": "fixture.jsonl"},
        "interval_method": "joint resample",
        "bootstrap_replicates": REPLICATES,
        "bootstrap_seed": SEED,
        "proxy_metrics": list(PROXIES),
        "utility_rows": utility,
        "trial_count": len(trials),
        "trials": trials,
        "lengths": lengths_report,
        "sign_of_the_result": (
            "For the spoofing attack a HIGH detection rate is a vulnerability, not a success."
        ),
    }


class AttackReportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.report = build_report()
        self.cases = build_cases()

    def validate(self, report: dict) -> dict:
        return validate_attack_report(
            report,
            self.cases,
            expected_offsets=OFFSETS,
            expected_null_keys=NULL_KEYS,
            expected_target_fpr=TARGET_FPR,
        )

    def test_a_consistent_report_validates(self) -> None:
        result = self.validate(self.report)
        self.assertTrue(result["valid"])
        self.assertTrue(result["threshold_calibrated_on_unattacked_nulls"])
        entry = result["lengths"][0]
        self.assertEqual(entry["genuine_detection_rate"], 1.0)
        self.assertTrue(entry["spoof_matches_genuine"])

    def test_each_family_carries_the_direction_of_its_rate(self) -> None:
        """A spoof rate and a genuine rate must never read as the same thing."""

        cells = {
            (c["family"], c["attack"], c["parameter"]): c
            for c in self.validate(self.report)["lengths"][0]["cells"]
        }
        self.assertEqual(cells[("spoof", SPLICE_ATTACK, 2)]["high_rate_means"], "vulnerability")
        self.assertEqual(cells[("genuine", None, None)]["high_rate_means"], "intended detection")
        self.assertEqual(
            cells[("removal", SHUFFLE_ATTACK, None)]["high_rate_means"], "failed attack"
        )
        self.assertEqual(
            cells[("wrong_key_watermarked", None, None)]["high_rate_means"], "false positive"
        )

    def test_a_threshold_calibrated_on_attacked_material_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        tampered["lengths"][0]["calibration"]["pooled_null_families"] = [
            "wrong_key_watermarked",
            "any_key_ordinary",
            "removal",
        ]
        with self.assertRaisesRegex(ValueError, "unattacked null families only"):
            self.validate(tampered)

    def test_a_report_that_hides_the_sign_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        tampered["sign_of_the_result"] = "detection rates are reported per attack"
        with self.assertRaisesRegex(ValueError, "high spoofing detection rate is a vulnerability"):
            self.validate(tampered)

    def test_an_overstated_attacker_model_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        tampered["attacker_knowledge"] = "the attacker queries the model and observes the key"
        with self.assertRaisesRegex(ValueError, "attacker model must state"):
            self.validate(tampered)

    def test_a_statistic_inconsistent_with_its_matches_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        for row in tampered["trials"]:
            if row["family"] == "spoof":
                row["statistic"] = float(row["statistic"]) + 1.0
                break
        with self.assertRaisesRegex(ValueError, "stored match count"):
            self.validate(tampered)

    def test_a_donor_count_beyond_the_attackers_outputs_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        tampered["donor_counts"] = [2, 99]
        with self.assertRaisesRegex(ValueError, "exceeds the available output count"):
            self.validate(tampered)

    def test_a_key_index_on_a_non_null_family_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        for row in tampered["trials"]:
            if row["family"] == "genuine":
                row["key_index"] = 0
                break
        with self.assertRaisesRegex(ValueError, "only the wrong-key null families"):
            self.validate(tampered)

    def test_a_missing_utility_column_is_rejected(self) -> None:
        """Removal without a utility column is not a result."""

        tampered = copy.deepcopy(self.report)
        tampered["utility_rows"] = []
        with self.assertRaisesRegex(ValueError, "utility rows are required"):
            self.validate(tampered)

    def test_a_raw_sequence_field_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        tampered["utility_rows"][0]["generated_dna"] = "ACGTAC"
        with self.assertRaisesRegex(ValueError, "forbidden raw field"):
            self.validate(tampered)

    def test_a_detection_rate_inconsistent_with_the_trials_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.report)
        tampered["lengths"][0]["cells"][0]["detection_rate"] = 0.5
        with self.assertRaisesRegex(ValueError, "detection rate is inconsistent"):
            self.validate(tampered)

    def test_the_fixture_separates_spoof_from_removal(self) -> None:
        """A fixture where every attack scored alike could not catch a mix-up."""

        cells = {
            (c["family"], c["attack"], c["parameter"]): c
            for c in self.validate(self.report)["lengths"][0]["cells"]
        }
        self.assertGreater(
            cells[("spoof", SPLICE_ATTACK, 2)]["mean_statistic"],
            cells[("removal", SHUFFLE_ATTACK, None)]["mean_statistic"],
        )
        self.assertTrue(math.isfinite(cells[("genuine", None, None)]["mean_statistic"]))


if __name__ == "__main__":
    unittest.main()
