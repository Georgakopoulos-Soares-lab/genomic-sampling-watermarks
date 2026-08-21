"""Simple reproducible DNA edit channels for protocol fixtures."""

from __future__ import annotations

import random

from genomic_watermarks.dna import BASES, normalize_dna


def _validate_rate(rate: float) -> None:
    if not 0.0 <= rate <= 1.0:
        raise ValueError("edit rate must lie in [0, 1]")


def substitute_bases(sequence: str, rate: float, rng: random.Random) -> str:
    """Independently substitute each selected base with a different base."""

    _validate_rate(rate)
    normalized = normalize_dna(sequence)
    output: list[str] = []
    for base in normalized:
        if rng.random() < rate:
            alternatives = tuple(candidate for candidate in BASES if candidate != base)
            output.append(alternatives[rng.randrange(len(alternatives))])
        else:
            output.append(base)
    return "".join(output)


def delete_bases(sequence: str, rate: float, rng: random.Random) -> str:
    """Independently delete each base with the specified probability."""

    _validate_rate(rate)
    normalized = normalize_dna(sequence)
    return "".join(base for base in normalized if rng.random() >= rate)


def insert_bases(sequence: str, rate: float, rng: random.Random) -> str:
    """Insert at most one uniformly chosen base before each source base."""

    _validate_rate(rate)
    normalized = normalize_dna(sequence)
    output: list[str] = []
    for base in normalized:
        if rng.random() < rate:
            output.append(BASES[rng.randrange(len(BASES))])
        output.append(base)
    return "".join(output)


def crop(sequence: str, start: int, length: int | None = None) -> str:
    """Crop a canonical sequence by a non-negative start and optional length."""

    normalized = normalize_dna(sequence)
    if start < 0:
        raise ValueError("start must be non-negative")
    if length is not None and length < 0:
        raise ValueError("length must be non-negative")
    return normalized[start:] if length is None else normalized[start : start + length]
