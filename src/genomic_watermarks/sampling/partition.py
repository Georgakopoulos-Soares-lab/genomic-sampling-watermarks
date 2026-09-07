"""Reproducible categorical sampling used by SynthID and its ordinary control.

The historical filename is retained so completed SynthID runs keep their exact import path.
"""

from __future__ import annotations

import random
from collections.abc import Sequence

from genomic_watermarks.metrics import normalized_probabilities


def sample_categorical(
    items: Sequence[str],
    probabilities: Sequence[float],
    rng: random.Random,
) -> str:
    """Draw from a categorical distribution using one reproducible random value."""

    probs = normalized_probabilities(probabilities)
    if len(items) != len(probs):
        raise ValueError("items and probabilities must have the same length")
    threshold = rng.random()
    cumulative = 0.0
    for item, probability in zip(items, probs, strict=True):
        cumulative += probability
        if threshold < cumulative:
            return item
    return items[-1]
