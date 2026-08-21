from __future__ import annotations

import unittest

from genomic_watermarks.detector.hypotheses import (
    score_partition_agreement,
    search_orientation_and_phase,
)


class DetectorTest(unittest.TestCase):
    def test_partition_agreement(self) -> None:
        score = score_partition_agreement(
            ("AAAAAA", "TTTTTT", "CCCCCC"),
            {"AAAAAA": True, "TTTTTT": False, "CCCCCC": True},
            (True, True, True),
        )
        self.assertEqual(score.matches, 2)
        self.assertEqual(score.total, 3)
        self.assertAlmostEqual(score.rate, 2.0 / 3.0)

    def test_search_preserves_declared_multiplicity(self) -> None:
        hypotheses = search_orientation_and_phase("AAAAAA" * 3)
        self.assertEqual(len(hypotheses), 12)

    def test_target_length_mismatch_fails(self) -> None:
        with self.assertRaises(ValueError):
            score_partition_agreement(("AAAAAA",), {"AAAAAA": True}, ())


if __name__ == "__main__":
    unittest.main()
