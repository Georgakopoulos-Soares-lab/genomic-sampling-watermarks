"""Tests for the edit-rate channel used by the L1-07 pilot.

The channel must be a public replay: reproducible from its label and identity alone,
independent of any detector score, and never silently a no-op.
"""

from __future__ import annotations

import unittest

from genomic_watermarks.synthid_boundary import (
    deterministic_multi_base_edit,
    deterministic_single_base_edit,
)

SEQUENCE = "ACGTTGCA" * 384  # 3072 bases
LABEL = "test-edit-rate/v1"


def _edit(**overrides):
    kwargs = dict(
        edit_rate=0.01,
        edit_kind="substitution",
        case_id="case-1",
        draw_id=0,
        label=LABEL,
    )
    kwargs.update(overrides)
    return deterministic_multi_base_edit(SEQUENCE, **kwargs)


class MultiBaseEditTest(unittest.TestCase):
    def test_replays_from_identity_alone(self) -> None:
        self.assertEqual(_edit().sequence, _edit().sequence)

    def test_identity_separates_channels(self) -> None:
        base = _edit().sequence
        self.assertNotEqual(base, _edit(draw_id=1).sequence)
        self.assertNotEqual(base, _edit(case_id="case-2").sequence)
        self.assertNotEqual(base, _edit(label="other/v1").sequence)

    def test_count_follows_declared_rate(self) -> None:
        for rate, expected in ((0.0, 0), (0.001, 3), (0.01, 31), (0.05, 154)):
            self.assertEqual(_edit(edit_rate=rate).edit_count, expected)

    def test_a_positive_rate_is_never_a_no_op(self) -> None:
        # Rounding must not silently drop the only event on a short sequence.
        edit = deterministic_multi_base_edit(
            "ACGTAC", edit_rate=0.0001, edit_kind="substitution",
            case_id="c", draw_id=0, label=LABEL,
        )
        self.assertEqual(edit.edit_count, 1)
        self.assertNotEqual(edit.sequence, "ACGTAC")

    def test_zero_rate_is_identity(self) -> None:
        edit = _edit(edit_rate=0.0)
        self.assertEqual(edit.sequence, SEQUENCE)
        self.assertEqual(edit.positions, ())

    def test_substitutions_preserve_length_and_change_exactly_k_bases(self) -> None:
        edit = _edit(edit_rate=0.01, edit_kind="substitution")
        self.assertEqual(len(edit.sequence), len(SEQUENCE))
        changed = sum(1 for a, b in zip(SEQUENCE, edit.sequence) if a != b)
        self.assertEqual(changed, edit.edit_count)

    def test_positions_are_distinct(self) -> None:
        edit = _edit(edit_rate=0.05)
        self.assertEqual(len(set(edit.positions)), len(edit.positions))

    def test_direction_pure_kinds_move_length_one_way(self) -> None:
        self.assertGreater(len(_edit(edit_kind="insertion").sequence), len(SEQUENCE))
        self.assertLess(len(_edit(edit_kind="deletion").sequence), len(SEQUENCE))

    def test_single_edit_channel_is_unchanged(self) -> None:
        # The declared threat model still rests on the single-edit channel; adding the
        # rate channel must not perturb it.
        single = deterministic_single_base_edit(
            SEQUENCE, condition="substitution_1nt", case_id="case-1", draw_id=0
        )
        self.assertEqual(len(single.sequence), len(SEQUENCE))
        changed = sum(1 for a, b in zip(SEQUENCE, single.sequence) if a != b)
        self.assertEqual(changed, 1)

    def test_rejects_invalid_arguments(self) -> None:
        for bad in (
            {"edit_kind": "transposition"},
            {"edit_rate": -0.1},
            {"edit_rate": 1.5},
            {"case_id": ""},
            {"draw_id": -1},
        ):
            with self.assertRaises(ValueError):
                _edit(**bad)


if __name__ == "__main__":
    unittest.main()
