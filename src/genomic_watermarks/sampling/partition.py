"""Exact-marginal partition sampling through maximal coupling."""

from __future__ import annotations

import hashlib
import hmac
import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from genomic_watermarks.metrics import normalized_probabilities, partition_mass

_PROTOCOL_LABEL = b"genomic-sampling-watermarks/partition/v1\x00"


@dataclass(frozen=True, slots=True)
class CoupledSample:
    token: str
    group: bool
    latent_bit: bool
    group_one_mass: float

    @property
    def agrees_with_latent(self) -> bool:
        return self.group == self.latent_bit


def keyed_balanced_partition(
    items: Sequence[str],
    key: bytes,
    *,
    domain: str = "default",
) -> dict[str, bool]:
    """Create a deterministic, equal-cardinality partition with HMAC-SHA-256.

    Equal cardinality does not imply equal probability mass. The realized mass
    must be measured for every next-token distribution.
    """

    if not key:
        raise ValueError("key must not be empty")
    if not items or len(items) % 2:
        raise ValueError("items must contain a non-empty even number of values")
    if len(set(items)) != len(items):
        raise ValueError("items must be unique")
    domain_bytes = domain.encode("utf-8")
    ranked = sorted(
        items,
        key=lambda item: (
            hmac.new(
                key,
                _PROTOCOL_LABEL + domain_bytes + b"\x00" + item.encode("ascii"),
                hashlib.sha256,
            ).digest(),
            item,
        ),
    )
    split = len(ranked) // 2
    return {item: rank >= split for rank, item in enumerate(ranked)}


def select_group_maximal_coupling(
    latent_bit: bool,
    group_one_mass: float,
    rng: random.Random,
) -> bool:
    """Couple a fair latent bit to a Bernoulli(q) group with maximal agreement."""

    if not math.isfinite(group_one_mass) or not 0.0 <= group_one_mass <= 1.0:
        raise ValueError("group mass must be finite and lie in [0, 1]")
    q = group_one_mass
    if q >= 0.5:
        return True if latent_bit else rng.random() < 2.0 * q - 1.0
    return rng.random() < 2.0 * q if latent_bit else False


def sample_categorical(
    items: Sequence[str],
    probabilities: Sequence[float],
    rng: random.Random,
) -> str:
    """Draw from a categorical law using exactly one reproducible uniform variate."""

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


def sample_partition_coupling(
    items: Sequence[str],
    probabilities: Sequence[float],
    partition: Mapping[str, bool],
    latent_bit: bool,
    rng: random.Random,
) -> CoupledSample:
    """Draw one exact-marginal token using the partition coupling baseline.

    ``random.Random`` makes research fixtures reproducible. It is not a claim
    that this object is a production cryptographic random generator.
    """

    probs = normalized_probabilities(probabilities)
    if len(items) != len(probs):
        raise ValueError("items and probabilities must have the same length")
    q = partition_mass(items, probs, partition)
    group = select_group_maximal_coupling(bool(latent_bit), q, rng)
    conditional_items: list[str] = []
    conditional_weights: list[float] = []
    for item, probability in zip(items, probs, strict=True):
        if partition[item] == group and probability > 0.0:
            conditional_items.append(item)
            conditional_weights.append(probability)
    if not conditional_items:
        raise RuntimeError("maximal coupling selected a zero-mass group")
    normalized_conditional = normalized_probabilities(conditional_weights)
    token = sample_categorical(conditional_items, normalized_conditional, rng)
    return CoupledSample(
        token=token,
        group=group,
        latent_bit=bool(latent_bit),
        group_one_mass=q,
    )
