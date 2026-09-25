"""Offline checks for the retained-trial strength derivation."""

from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from derive_cross_model_strength_analysis import (  # noqa: E402
    selected_clean_trials,
    summarize_trials,
    weakest_window_counterfactual,
)

from genomic_watermarks.synthid_position_independent import (  # noqa: E402
    fair_binomial_log_survival_probability,
)


def trial(case_id: str, draw_id: int, *, excluded: int = 0) -> dict:
    scored = 60 - excluded
    total = scored * 30
    ones = round(total * 0.65)
    log_p = fair_binomial_log_survival_probability(ones, total)
    return {
        "case_id": case_id,
        "draw_id": draw_id,
        "condition": "clean",
        "family": "watermarked_correct_key",
        "minimum_local_log_p_value": log_p,
        "best_hypothesis": {
            "window_base_length": 384,
            "scored_tokens": scored,
            "repeated_contexts": excluded,
            "g_ones": ones,
            "g_total": total,
            "local_log_p_value": log_p,
        },
    }


class CrossModelStrengthTest(unittest.TestCase):
    def test_rejects_incorrect_repetition_accounting_and_tails(self) -> None:
        rows = [trial(f"p{i}", draw_id, excluded=i % 3) for i in range(192) for draw_id in (0, 1)]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trials.jsonl"

            def write() -> None:
                path.write_text("".join(json.dumps(row) + "\n" for row in rows))

            write()
            selected = selected_clean_trials(path)
            self.assertEqual(len(selected), 384)
            self.assertEqual(summarize_trials(selected)["prompts"], 192)

            rows[0]["best_hypothesis"]["repeated_contexts"] = 1
            write()
            with self.assertRaisesRegex(ValueError, "do not cover"):
                selected_clean_trials(path)

            rows[0] = trial("p0", 0)
            rows[0]["best_hypothesis"]["local_log_p_value"] += 0.1
            write()
            with self.assertRaisesRegex(ValueError, "exact binomial tail"):
                selected_clean_trials(path)

    def test_counterfactual_is_only_a_count_sensitivity(self) -> None:
        carbon = [trial("c", 0)]
        generator = [trial("g", 0, excluded=20)]
        result = weakest_window_counterfactual(carbon, generator)
        self.assertEqual(result["counterfactual_full_scored_tokens"], 60)
        self.assertEqual(result["generator_weakest_scored_tokens"], 40)
        self.assertGreater(result["scored_token_count_sensitivity"], 0)
        self.assertTrue(math.isfinite(result["counterfactual_strength"]))
        self.assertIn("not a causal attribution", result["interpretation"])


if __name__ == "__main__":
    unittest.main()
