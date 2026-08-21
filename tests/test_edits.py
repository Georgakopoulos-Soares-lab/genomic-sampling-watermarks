from __future__ import annotations

import random
import unittest

from genomic_watermarks.edits.channel import crop, delete_bases, insert_bases, substitute_bases


class EditChannelTest(unittest.TestCase):
    def test_zero_rate_is_identity(self) -> None:
        sequence = "ATCGATCG"
        self.assertEqual(substitute_bases(sequence, 0.0, random.Random(1)), sequence)
        self.assertEqual(delete_bases(sequence, 0.0, random.Random(1)), sequence)
        self.assertEqual(insert_bases(sequence, 0.0, random.Random(1)), sequence)

    def test_full_substitution_changes_every_base(self) -> None:
        sequence = "ATCGATCG"
        edited = substitute_bases(sequence, 1.0, random.Random(4))
        self.assertEqual(len(edited), len(sequence))
        self.assertTrue(all(left != right for left, right in zip(sequence, edited, strict=True)))

    def test_full_deletion_and_insertion_lengths(self) -> None:
        sequence = "ATCGATCG"
        self.assertEqual(delete_bases(sequence, 1.0, random.Random(2)), "")
        self.assertEqual(len(insert_bases(sequence, 1.0, random.Random(2))), 2 * len(sequence))

    def test_crop(self) -> None:
        self.assertEqual(crop("AAAATTTTCCCC", 4, 4), "TTTT")
        self.assertEqual(crop("AAAATTTTCCCC", 8), "CCCC")


if __name__ == "__main__":
    unittest.main()
