"""Offline checks for the generation-path sampler-fidelity test (no model downloads)."""

from __future__ import annotations

import itertools
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

try:
    import numpy
except ImportError:  # pragma: no cover - the generation path needs NumPy
    numpy = None

import run_sampler_fidelity_v4 as fidelity  # noqa: E402

from genomic_watermarks.synthid import KeyedTournament  # noqa: E402

ITEMS = tuple("".join(p) for p in itertools.product("ACGT", repeat=3))  # 64 toy tokens


def toy_law(seed: int) -> tuple[float, ...]:
    rng = random.Random(seed)
    weights = [rng.random() ** 3 for _ in ITEMS]
    total = sum(weights)
    return tuple(w / total for w in weights)


TOURNAMENT = KeyedTournament(
    key=b"\x01" * 32, domain="test/v4", depth=30, context_tokens=4, context_history_size=1024
)


@unittest.skipIf(numpy is None, "NumPy is required for the generation sampling path")
class EvaluateStateTests(unittest.TestCase):
    def run_state(self, **overrides):
        kwargs = dict(
            items=ITEMS,
            probabilities=toy_law(3),
            recent=("AAA", "CCG", "TTA", "GAC"),
            tournament=TOURNAMENT,
            seed_parts=("C_tok", "case-1"),
            draws=4000,
            replicates=199,
            key_replicates=64,
            negative_control=True,
            integration_draws=100,
            numpy=numpy,
        )
        kwargs.update(overrides)
        return fidelity.evaluate_state(**kwargs)

    def test_numpy_and_reference_laws_agree(self):
        self.assertLessEqual(
            self.run_state()["numpy_vs_reference_max_abs"], fidelity.EXACTNESS_TOLERANCE
        )

    def test_efficient_path_reproduces_tournament_step_draw_for_draw(self):
        self.assertTrue(self.run_state()["integration"]["identical"])

    def test_correct_samplers_pass_and_the_wrong_one_is_rejected(self):
        record = self.run_state()
        self.assertGreater(record["marked"]["p_value"], 0.001)
        self.assertGreater(record["ordinary"]["p_value"], 0.001)
        self.assertLessEqual(record["negative_control"]["p_value"], 0.01)

    def test_key_average_moves_towards_the_model_law(self):
        tv = self.run_state()["key_average"]["total_variation_by_keys"]
        self.assertLess(tv["64"], tv["1"])

    def test_draws_are_reproducible(self):
        self.assertEqual(self.run_state()["marked"]["counts"], self.run_state()["marked"]["counts"])


class SelectionAndSummaryTests(unittest.TestCase):
    def test_states_come_from_evaluation_prompts_only(self):
        case_ids = [f"case_{i:04d}" for i in range(400)]
        chosen, negatives, integrations = fidelity.select_states(
            case_ids, states=100, negative=8, integration=32
        )
        split = fidelity.deterministic_prompt_split(
            case_ids, calibration_prompts=64, label=fidelity.CALIBRATION_SPLIT_LABEL
        )
        self.assertEqual(len(chosen), 100)
        self.assertTrue(all(split[c] == "evaluation" for c in chosen))
        self.assertTrue(negatives <= set(chosen) and len(negatives) == 8)
        self.assertTrue(integrations <= set(chosen) and len(integrations) == 32)
        self.assertEqual(
            chosen, fidelity.select_states(case_ids, states=100, negative=8, integration=32)[0]
        )

    def test_binomial_tail_and_bh(self):
        self.assertAlmostEqual(fidelity.binomial_upper_tail(0, 10, 0.05), 1.0)
        self.assertLess(fidelity.binomial_upper_tail(10, 100, 0.05), 0.05)
        self.assertEqual(fidelity.benjamini_hochberg_rejections([0.001, 0.002, 0.5, 0.9], 0.05), 2)
        self.assertEqual(fidelity.benjamini_hochberg_rejections([0.2, 0.5], 0.05), 0)


if __name__ == "__main__":
    unittest.main()
