"""Pure policy transformations shared by model adapters and offline tests."""

from __future__ import annotations

import math
from collections.abc import Sequence

from genomic_watermarks.dna import BASES, KMER_SIZE
from genomic_watermarks.metrics import normalized_probabilities


def canonical_softmax(logits: Sequence[float], canonical_ids: Sequence[int]) -> tuple[float, ...]:
    """Mask to canonical IDs and normalize their logits with a stable softmax."""

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
    weights = tuple(math.exp(value - maximum) for value in selected)
    return normalized_probabilities(weights)


def base_marginals(
    tokens: Sequence[str], probabilities: Sequence[float], *, k: int = KMER_SIZE
) -> tuple[tuple[float, ...], ...]:
    """Marginalize a canonical k-mer distribution to k distributions over A/T/C/G."""

    if len(tokens) != len(probabilities):
        raise ValueError("tokens and probabilities must have the same length")
    probs = normalized_probabilities(probabilities)
    base_to_index = {base: index for index, base in enumerate(BASES)}
    marginals = [[0.0] * len(BASES) for _ in range(k)]
    for token, probability in zip(tokens, probs, strict=True):
        if len(token) != k or any(base not in base_to_index for base in token):
            raise ValueError(f"non-canonical {k}-mer: {token!r}")
        for position, base in enumerate(token):
            marginals[position][base_to_index[base]] += probability
    return tuple(normalized_probabilities(row) for row in marginals)


def independent_base_product_distribution(
    tokens: Sequence[str], probabilities: Sequence[float], *, k: int = KMER_SIZE
) -> tuple[float, ...]:
    """Return the k-mer law induced by independent draws from base marginals.

    This is the stochastic distribution implemented by the audited GENERator-v2
    base-marginal processor when ``do_sample=True``.
    """

    marginals = base_marginals(tokens, probabilities, k=k)
    return product_distribution_from_base_marginals(tokens, marginals, k=k)


def product_distribution_from_base_marginals(
    tokens: Sequence[str],
    marginals: Sequence[Sequence[float]],
    *,
    k: int = KMER_SIZE,
) -> tuple[float, ...]:
    """Construct the canonical k-mer law induced by supplied base marginals."""

    if len(marginals) != k:
        raise ValueError(f"expected {k} base-marginal rows")
    normalized_marginals = tuple(normalized_probabilities(row) for row in marginals)
    if any(len(row) != len(BASES) for row in normalized_marginals):
        raise ValueError(f"each base-marginal row must contain {len(BASES)} values")
    base_to_index = {base: index for index, base in enumerate(BASES)}
    product_weights = tuple(
        math.prod(
            normalized_marginals[position][base_to_index[base]]
            for position, base in enumerate(token)
        )
        for token in tokens
    )
    return normalized_probabilities(product_weights)


def apply_generation_policy(
    policy_id: str,
    tokens: Sequence[str],
    probabilities: Sequence[float],
) -> tuple[float, ...]:
    """Apply the declared direct-token or stochastic base-marginal policy."""

    direct = {"C_tok", "G_tok"}
    base_product = {"C_bp", "G_bp"}
    if policy_id in direct:
        return normalized_probabilities(probabilities)
    if policy_id in base_product:
        if not tokens:
            raise ValueError("tokens must not be empty")
        return independent_base_product_distribution(tokens, probabilities, k=len(tokens[0]))
    raise ValueError(f"unsupported next-distribution policy: {policy_id}")
