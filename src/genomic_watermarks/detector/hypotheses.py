"""Detector scoring and explicit strand/phase hypothesis enumeration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from genomic_watermarks.dna import TokenizationHypothesis, enumerate_hypotheses


@dataclass(frozen=True, slots=True)
class PartitionScore:
    matches: int
    total: int

    @property
    def rate(self) -> float:
        return self.matches / self.total if self.total else 0.0


def score_partition_agreement(
    tokens: Sequence[str],
    partition: Mapping[str, bool],
    target_bits: Sequence[bool],
) -> PartitionScore:
    """Count group/target agreement for one already-aligned hypothesis."""

    if len(tokens) != len(target_bits):
        raise ValueError("tokens and target_bits must have the same length")
    missing = [token for token in tokens if token not in partition]
    if missing:
        raise ValueError(f"partition is missing {len(missing)} observed token(s)")
    matches = sum(
        partition[token] == bool(target) for token, target in zip(tokens, target_bits, strict=True)
    )
    return PartitionScore(matches=matches, total=len(tokens))


def search_orientation_and_phase(sequence: str) -> tuple[TokenizationHypothesis, ...]:
    """Return the 12 fixed hypotheses that null calibration must reproduce."""

    return enumerate_hypotheses(sequence)
