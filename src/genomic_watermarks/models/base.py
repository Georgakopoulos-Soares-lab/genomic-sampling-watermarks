"""Dependency-light interface implemented by Carbon and GENERator adapters."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ModelPolicy:
    policy_id: str
    model_id: str
    revision: str
    tokenizer_revision: str


@dataclass(frozen=True, slots=True)
class DistributionState:
    tokens: tuple[str, ...]
    probabilities: tuple[float, ...]
    metadata: Mapping[str, str | int | float | bool]

    def __post_init__(self) -> None:
        if not self.tokens or len(self.tokens) != len(self.probabilities):
            raise ValueError("tokens and probabilities must have the same non-zero length")
        if len(set(self.tokens)) != len(self.tokens):
            raise ValueError("tokens must be unique")
        if any(not math.isfinite(value) or value < 0.0 for value in self.probabilities):
            raise ValueError("probabilities must be finite and non-negative")
        if not math.isclose(math.fsum(self.probabilities), 1.0, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError("probabilities must sum to one")


@runtime_checkable
class GenomicModelAdapter(Protocol):
    """Minimal model interface needed by sampling and channel experiments."""

    @property
    def policy(self) -> ModelPolicy: ...

    @property
    def canonical_tokens(self) -> Sequence[str]: ...

    def next_distribution(self, dna_context: str) -> DistributionState: ...
