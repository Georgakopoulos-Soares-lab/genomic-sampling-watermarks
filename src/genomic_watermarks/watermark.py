"""Ordinary sampling controls shared by the Carbon SynthID experiments.

This module does not implement a watermark. It holds only the matched ordinary
sampler and the public replay-seed helper used by the retained SynthID runs.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from genomic_watermarks.sampling.partition import sample_categorical

ORDINARY_SCHEME = "ordinary-categorical-v1"
NextDistribution = Callable[[str], tuple[Sequence[str], Sequence[float]]]

_REPLAY_SEED_LABEL = b"genomic-sampling-watermarks/public-replay-seed/v1\x00"


def public_replay_seed(*parts: str) -> int:
    """Derive a reproducible public random seed from experiment labels."""

    if not parts:
        raise ValueError("at least one seed part is required")
    if any(not part for part in parts):
        raise ValueError("seed parts must not be empty")
    digest = hashlib.sha256(_REPLAY_SEED_LABEL + "\x00".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:16], "big")


@dataclass(frozen=True, slots=True)
class GenerationResult:
    """Tokens produced by the matched ordinary generation path."""

    scheme: str
    tokens: tuple[str, ...]
    steps: tuple[()] = ()

    @property
    def dna(self) -> str:
        return "".join(self.tokens)

    @property
    def bases(self) -> int:
        return sum(len(token) for token in self.tokens)


def generate_ordinary(
    next_distribution: NextDistribution,
    context: str,
    *,
    steps: int,
    rng: random.Random,
) -> GenerationResult:
    """Generate the ordinary control from the same declared model distribution."""

    if not callable(next_distribution):
        raise TypeError("next_distribution must be callable")
    if steps <= 0:
        raise ValueError("steps must be positive")
    tokens: list[str] = []
    current = context
    for _ in range(steps):
        items, probabilities = next_distribution(current)
        if len(items) != len(probabilities):
            raise ValueError("items and probabilities must have the same length")
        token = sample_categorical(items, probabilities, rng)
        tokens.append(token)
        current += token
    return GenerationResult(scheme=ORDINARY_SCHEME, tokens=tuple(tokens))
