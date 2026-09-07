"""Probability transformations used by the retained direct-token adapters."""

from __future__ import annotations

import math
from collections.abc import Sequence

from genomic_watermarks.metrics import normalized_probabilities


def canonical_softmax(logits: Sequence[float], canonical_ids: Sequence[int]) -> tuple[float, ...]:
    """Restrict logits to canonical DNA-token IDs and apply a stable softmax."""

    if not canonical_ids:
        raise ValueError("canonical_ids must not be empty")
    if len(set(canonical_ids)) != len(canonical_ids):
        raise ValueError("canonical_ids must be unique")
    if min(canonical_ids) < 0 or max(canonical_ids) >= len(logits):
        raise ValueError("canonical token ID lies outside the logits vector")
    selected = tuple(float(logits[index]) for index in canonical_ids)
    if any(not math.isfinite(value) for value in selected):
        raise ValueError("canonical logits must be finite")
    maximum = max(selected)
    return normalized_probabilities(math.exp(value - maximum) for value in selected)


def apply_generation_policy(
    policy_id: str,
    tokens: Sequence[str],
    probabilities: Sequence[float],
) -> tuple[float, ...]:
    """Return a retained direct canonical 6-mer distribution."""

    if policy_id not in {"C_tok", "G_tok"}:
        raise ValueError(f"unsupported next-distribution policy: {policy_id}")
    if len(tokens) != len(probabilities):
        raise ValueError("tokens and probabilities must have the same length")
    return normalized_probabilities(probabilities)
