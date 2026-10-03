"""Offline checks for the cross-cohort strength summary derivation."""

from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import derive_strength_summary as summary  # noqa: E402


def row(case_id: str, draw_id: int, condition: str, strength: float) -> dict:
    return {
        "case_id": case_id,
        "draw_id": draw_id,
        "condition": condition,
        "family": "watermarked_correct_key",
        "minimum_local_log_p_value": -strength * math.log(10.0),
    }


class CorrectKeyStrengthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.saved = summary.EVALUATION_PROMPTS
        summary.EVALUATION_PROMPTS = 2

    def tearDown(self) -> None:
        summary.EVALUATION_PROMPTS = self.saved

    def grid(self) -> list[dict]:
        rows = []
        for index, condition in enumerate(summary.CONDITIONS):
            for case in ("a", "b"):
                for draw in (0, 1):
                    rows.append(row(case, draw, condition, 100.0 * (index + 1) + draw))
        rows.append({**row("a", 0, "clean", 1.0), "family": "ordinary_corresponding_key"})
        return rows

    def test_strength_uses_negative_log10_of_local_tail(self) -> None:
        values = summary.correct_key_strengths(self.grid())
        self.assertAlmostEqual(summary.summarize(values["clean"])["median"], 100.5)
        self.assertAlmostEqual(summary.summarize(values["deletion_1nt"])["minimum"], 400.0)
        self.assertEqual(summary.summarize(values["clean"])["reads"], 4)

    def test_incomplete_grid_is_rejected(self) -> None:
        rows = [r for r in self.grid() if not (r["case_id"] == "b" and r["draw_id"] == 1)]
        with self.assertRaises(ValueError):
            summary.correct_key_strengths(rows)

    def test_duplicate_trial_is_rejected(self) -> None:
        rows = self.grid()
        rows.append(row("a", 0, "clean", 5.0))
        with self.assertRaises(ValueError):
            summary.correct_key_strengths(rows)


class EditRateAgreementTests(unittest.TestCase):
    def write(self, directory: Path, name: str, detected: dict) -> Path:
        cells = [
            {
                "family": "watermarked_correct_key",
                "edit_kind": "clean",
                "edit_rate": 0.0,
                "detected": 10,
                "reads": 10,
                "rate": 1.0,
            }
        ]
        for (kind, rate), count in detected.items():
            cells.append(
                {
                    "family": "watermarked_correct_key",
                    "edit_kind": kind,
                    "edit_rate": rate,
                    "detected": count,
                    "reads": 10,
                    "rate": count / 10,
                }
            )
        path = directory / name
        path.write_text(json.dumps({"cells": cells}), encoding="utf-8")
        return path

    def test_largest_difference_and_location(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            left = self.write(directory, "l.json", {("indel", 0.05): 9, ("substitution", 0.1): 2})
            right = self.write(directory, "r.json", {("indel", 0.05): 8, ("substitution", 0.1): 5})
            result = summary.edit_rate_agreement(left, right)
        self.assertAlmostEqual(result["maximum_absolute_difference"], 0.3)
        self.assertEqual(result["at"], {"edit_kind": "substitution", "edit_rate": 0.1})
        self.assertEqual(result["cells_compared"], 2)

    def test_mismatched_grids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            left = self.write(directory, "l.json", {("indel", 0.05): 9})
            right = self.write(directory, "r.json", {("deletion", 0.05): 9})
            with self.assertRaises(ValueError):
                summary.edit_rate_agreement(left, right)


if __name__ == "__main__":
    unittest.main()
