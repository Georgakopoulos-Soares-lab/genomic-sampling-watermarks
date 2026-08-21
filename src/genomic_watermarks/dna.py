"""Canonical DNA normalization and fixed-block 6-mer hypotheses."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

BASES = "ATCG"
KMER_SIZE = 6
_COMPLEMENT = str.maketrans({"A": "T", "T": "A", "C": "G", "G": "C"})


@dataclass(frozen=True, slots=True)
class TokenizationHypothesis:
    """One strand-orientation and fixed-block phase hypothesis."""

    orientation: str
    phase: int
    tokens: tuple[str, ...]


def canonical_kmers(k: int = KMER_SIZE) -> tuple[str, ...]:
    """Return all canonical DNA k-mers in the audited A/T/C/G product order."""

    if k <= 0:
        raise ValueError("k must be positive")
    return tuple("".join(chars) for chars in product(BASES, repeat=k))


def normalize_dna(sequence: str) -> str:
    """Remove whitespace, uppercase, and reject non-canonical DNA symbols."""

    normalized = "".join(sequence.split()).upper()
    invalid = sorted(set(normalized).difference(BASES))
    if invalid:
        raise ValueError(f"non-canonical DNA symbols: {''.join(invalid)}")
    return normalized


def reverse_complement(sequence: str) -> str:
    """Return the reverse complement of canonical DNA."""

    normalized = normalize_dna(sequence)
    return normalized.translate(_COMPLEMENT)[::-1]


def tokenize_fixed(
    sequence: str,
    *,
    phase: int = 0,
    k: int = KMER_SIZE,
) -> tuple[str, ...]:
    """Split complete, non-overlapping k-mers after skipping ``phase`` bases.

    Incomplete trailing material is deliberately excluded. Tokenizer-specific
    padding behavior belongs in model adapters, not the standalone detector.
    """

    if k <= 0:
        raise ValueError("k must be positive")
    if not 0 <= phase < k:
        raise ValueError(f"phase must be in [0, {k - 1}]")
    normalized = normalize_dna(sequence)
    usable_end = phase + ((len(normalized) - phase) // k) * k
    if usable_end <= phase:
        return ()
    return tuple(normalized[index : index + k] for index in range(phase, usable_end, k))


def enumerate_hypotheses(
    sequence: str,
    *,
    k: int = KMER_SIZE,
) -> tuple[TokenizationHypothesis, ...]:
    """Enumerate both strands and all fixed-block phases.

    Palindromic or short inputs may produce identical token sequences. They
    remain separate hypotheses because detector multiplicity is defined by the
    search procedure, not by data-dependent deduplication.
    """

    forward = normalize_dna(sequence)
    orientations = (
        ("forward", forward),
        ("reverse_complement", reverse_complement(forward)),
    )
    return tuple(
        TokenizationHypothesis(
            orientation=orientation,
            phase=phase,
            tokens=tokenize_fixed(oriented_sequence, phase=phase, k=k),
        )
        for orientation, oriented_sequence in orientations
        for phase in range(k)
    )
