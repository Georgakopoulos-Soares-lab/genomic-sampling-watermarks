from __future__ import annotations

import random
import unittest

from genomic_watermarks.watermark import (
    ORDINARY_SCHEME,
    generate_ordinary,
    public_replay_seed,
)


class OrdinaryControlTest(unittest.TestCase):
    @staticmethod
    def distribution(_context: str) -> tuple[tuple[str, ...], tuple[float, ...]]:
        return ("AAAAAA", "CCCCCC", "GGGGGG", "TTTTTT"), (0.25, 0.25, 0.25, 0.25)

    def test_public_seed_replays_exactly(self) -> None:
        seed = public_replay_seed("prompt", "draw-0")
        first = generate_ordinary(self.distribution, "", steps=32, rng=random.Random(seed))
        second = generate_ordinary(self.distribution, "", steps=32, rng=random.Random(seed))
        self.assertEqual(first, second)
        self.assertEqual(first.scheme, ORDINARY_SCHEME)
        self.assertEqual(first.bases, 192)

    def test_two_draw_seeds_create_different_sequences_without_a_key(self) -> None:
        first = generate_ordinary(
            self.distribution,
            "",
            steps=32,
            rng=random.Random(public_replay_seed("prompt", "draw-0")),
        )
        second = generate_ordinary(
            self.distribution,
            "",
            steps=32,
            rng=random.Random(public_replay_seed("prompt", "draw-1")),
        )
        self.assertNotEqual(first.tokens, second.tokens)


if __name__ == "__main__":
    unittest.main()
