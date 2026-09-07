"""The on-device canonical gather must be a transfer optimisation only.

``next_distribution`` used to move the model's entire vocabulary to Python and
index it there.  Gathering the canonical IDs on the model's device first is
worth roughly thirty times less marshalling on Carbon's 155,776-token
vocabulary, but it is only admissible if the probabilities are unchanged, so
this module pins the old and new expressions against each other.
"""

from __future__ import annotations

import unittest

try:
    import torch
except ImportError:  # pragma: no cover - torch is an optional extra
    torch = None

from genomic_watermarks.models.policy_math import canonical_softmax


@unittest.skipIf(torch is None, "requires the optional 'models' extra")
class CanonicalGatherEquivalenceTest(unittest.TestCase):
    def _compare(self, row, ids) -> None:
        index = torch.tensor(ids, dtype=torch.long, device=row.device)
        previous = row.detach().float().cpu().tolist()
        gathered = row.detach().index_select(0, index).float().cpu().tolist()
        self.assertEqual(gathered, [previous[identifier] for identifier in ids])
        self.assertEqual(
            canonical_softmax(gathered, tuple(range(len(ids)))),
            canonical_softmax(previous, ids),
        )

    def test_gather_is_bit_identical_across_dtypes(self) -> None:
        generator = torch.Generator().manual_seed(20260829)
        vocabulary = 4096
        ids = tuple(range(7, 7 + 512))
        for dtype in (torch.float32, torch.bfloat16, torch.float16):
            row = torch.randn(vocabulary, generator=generator).to(dtype) * 8.0
            self._compare(row, ids)

    def test_gather_handles_non_contiguous_and_unordered_ids(self) -> None:
        generator = torch.Generator().manual_seed(11)
        row = torch.randn(2048, generator=generator).to(torch.bfloat16)
        ids = (1999, 3, 1024, 0, 777, 2047, 5)
        self._compare(row, ids)

    def test_gather_preserves_extreme_logits(self) -> None:
        row = torch.tensor(
            [-3.0e38, 0.0, 3.0e38, -1.0, 1.0, 12345.678, -0.0],
            dtype=torch.float32,
        )
        self._compare(row, (0, 2, 4, 6))
