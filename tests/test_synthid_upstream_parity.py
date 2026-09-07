"""Differential test against DeepMind's released ``synthid-text`` implementation.

The tournament formula is the one piece of this construction that is not ours:
it is reproduced from the released code pinned in ``sources.yaml`` as
``synthid_text_code``.  Asserting our probability-space update against upstream's
log-space ``update_scores`` is what distinguishes an implementation of SynthID
from an implementation merely inspired by it.

The upstream tree is not vendored, so these tests skip unless
``GSW_SYNTHID_UPSTREAM`` points at a clone. Obtain it with::

    git clone https://github.com/google-deepmind/synthid-text
    git -C synthid-text checkout addb4a158143c7c6851a1308f78b89fceed59683
    export GSW_SYNTHID_UPSTREAM=$PWD/synthid-text
"""

from __future__ import annotations

import importlib.util
import os
import random
import sys
import types
import unittest
from pathlib import Path

PINNED_REVISION = "addb4a158143c7c6851a1308f78b89fceed59683"


def _load_upstream():
    """Import upstream ``logits_processing`` with its unused deps stubbed."""

    root = os.environ.get("GSW_SYNTHID_UPSTREAM")
    if not root:
        return None
    module_path = Path(root) / "src/synthid_text/logits_processing.py"
    if not module_path.is_file():
        return None
    # ``update_scores`` needs only torch.  Transformers and the hashing helper
    # are imported at upstream module scope, and the module defines a
    # ``LogitsProcessor`` subclass at import time, so the base class must exist.
    for name in ("transformers", "synthid_text", "synthid_text.hashing_function"):
        sys.modules.setdefault(name, types.ModuleType(name))
    if not hasattr(sys.modules["transformers"], "LogitsProcessor"):
        sys.modules["transformers"].LogitsProcessor = type("LogitsProcessor", (), {})
    spec = importlib.util.spec_from_file_location("upstream_logits_processing", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    import numpy
    import torch
except ImportError:  # pragma: no cover - optional extras
    numpy = None
    torch = None

UPSTREAM = _load_upstream() if torch is not None else None

from genomic_watermarks.synthid import (  # noqa: E402
    TournamentDistribution,
    update_tournament_probabilities,
)


@unittest.skipIf(UPSTREAM is None, "set GSW_SYNTHID_UPSTREAM to a pinned upstream clone")
class UpstreamTournamentParityTest(unittest.TestCase):
    """Our update must equal upstream's on identical inputs."""

    def _upstream_probabilities(self, probabilities, g_values):
        scores = torch.log(torch.tensor([probabilities], dtype=torch.float64))
        g_tensor = torch.tensor([g_values], dtype=torch.float64)
        updated = UPSTREAM.update_scores(scores, g_tensor)
        probabilities = torch.exp(updated)[0].numpy()
        return probabilities / probabilities.sum()

    def _assert_parity(self, probabilities, g_values, places=12):
        ours: TournamentDistribution = update_tournament_probabilities(probabilities, g_values)
        theirs = self._upstream_probabilities(probabilities, g_values)
        for index, (mine, upstream_value) in enumerate(
            zip(ours.probabilities, theirs, strict=True)
        ):
            self.assertAlmostEqual(mine, float(upstream_value), places=places, msg=f"index {index}")

    def test_matches_upstream_on_random_laws(self) -> None:
        rng = random.Random(20260829)
        for vocabulary, depth in ((4, 1), (8, 3), (16, 30), (64, 30), (256, 30)):
            weights = [rng.expovariate(1.0) for _ in range(vocabulary)]
            total = sum(weights)
            probabilities = [weight / total for weight in weights]
            g_values = [[rng.randint(0, 1) for _ in range(depth)] for _ in range(vocabulary)]
            self._assert_parity(probabilities, g_values)

    def test_matches_upstream_on_peaked_and_flat_laws(self) -> None:
        vocabulary, depth = 32, 30
        rng = random.Random(7)
        g_values = [[rng.randint(0, 1) for _ in range(depth)] for _ in range(vocabulary)]
        flat = [1.0 / vocabulary] * vocabulary
        peaked = [1e-9] * vocabulary
        peaked[3] = 1.0 - 1e-9 * (vocabulary - 1)
        for probabilities in (flat, peaked):
            self._assert_parity(probabilities, probabilities and g_values)

    def test_matches_upstream_when_a_layer_is_constant(self) -> None:
        """All-ones and all-zeros layers are the formula's degenerate cases."""

        vocabulary = 16
        probabilities = [1.0 / vocabulary] * vocabulary
        for constant in (0, 1):
            g_values = [[constant, 1 - constant, constant] for _ in range(vocabulary)]
            self._assert_parity(probabilities, g_values)

    def test_upstream_clone_is_the_pinned_revision(self) -> None:
        import subprocess

        root = os.environ["GSW_SYNTHID_UPSTREAM"]
        head = subprocess.run(
            ["git", "-C", root, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        self.assertEqual(head, PINNED_REVISION, "upstream clone is not at the sources.yaml pin")
