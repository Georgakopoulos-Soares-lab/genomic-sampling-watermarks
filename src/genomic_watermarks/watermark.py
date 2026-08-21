"""The `partition_mc` watermarked generation path and its matched ordinary control.

The construction at position ``i`` is:

1. derive a keyed equal-cardinality partition ``P_i`` of the policy support;
2. derive a keyed latent bit ``c_i`` that is uniform to anyone without the key;
3. draw the token by maximal coupling of ``c_i`` to the partition group of the
   declared policy distribution;
4. draw the token inside the selected group from the conditional policy law.

Step 4 keeps the one-step marginal exactly equal to the declared policy law. Step
2 is what a keyed verifier can recompute from DNA alone, so the group agreement
rate is the detector statistic.

Secret material is accepted only as a runtime argument. Nothing in this module
writes a key, a key digest, or any key-derived identifier to a file.
"""

from __future__ import annotations

import hashlib
import hmac
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from genomic_watermarks.sampling.partition import (
    CoupledSample,
    keyed_balanced_partition,
    sample_categorical,
    sample_partition_coupling,
)

PARTITION_MC_SCHEME = "partition-mc-v1"
ORDINARY_SCHEME = "ordinary-categorical-v1"

NextDistribution = Callable[[str], tuple[Sequence[str], Sequence[float]]]

_STREAM_LABEL = b"genomic-sampling-watermarks/partition-mc/v1\x00"
_LATENT_BIT_PURPOSE = b"latent-bit\x00"
_PARTITION_PURPOSE = b"partition\x00"


_REPLAY_SEED_LABEL = b"genomic-sampling-watermarks/public-replay-seed/v1\x00"


def public_replay_seed(*parts: str) -> int:
    """Derive a reproducible, entirely public RNG seed from experiment labels.

    This exists so that a generation run can be replayed. It is not secret
    material, is never mixed with a key, and must not be used where
    cryptographic randomness is required.
    """

    if not parts:
        raise ValueError("at least one seed part is required")
    if any(not part for part in parts):
        raise ValueError("seed parts must not be empty")
    digest = hashlib.sha256(_REPLAY_SEED_LABEL + "\x00".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:16], "big")


def _index_bytes(index: int) -> bytes:
    if index < 0:
        raise ValueError("stream index must be non-negative")
    if index >= 1 << 64:
        raise ValueError("stream index must fit in 64 bits")
    return index.to_bytes(8, "big")


@dataclass(frozen=True, slots=True, eq=False)
class KeyedPartitionStream:
    """Position-indexed keyed partitions and latent bits for `partition_mc`.

    The key is held only for the lifetime of the process. ``repr`` deliberately
    excludes it so that logging or accidental serialization of a surrounding
    structure cannot leak secret material.
    """

    key: bytes = field(repr=False)
    domain: str

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("stream key must not be empty")
        if not self.domain:
            raise ValueError("stream domain must not be empty")

    def _digest(self, purpose: bytes, index: int) -> bytes:
        message = (
            _STREAM_LABEL + purpose + self.domain.encode("utf-8") + b"\x00" + _index_bytes(index)
        )
        return hmac.new(self.key, message, hashlib.sha256).digest()

    def latent_bit(self, index: int) -> bool:
        """Return the keyed latent bit for one stream position."""

        return bool(self._digest(_LATENT_BIT_PURPOSE, index)[0] & 1)

    def partition(self, items: Sequence[str], index: int) -> dict[str, bool]:
        """Return the keyed equal-cardinality partition for one stream position."""

        subkey = self._digest(_PARTITION_PURPOSE, index)
        return keyed_balanced_partition(
            items,
            subkey,
            domain=f"{PARTITION_MC_SCHEME}/{self.domain}/{index}",
        )


@dataclass(frozen=True, slots=True)
class WatermarkStep:
    """One watermarked position, without any distribution or key material."""

    index: int
    stream_index: int
    token: str
    group: bool
    latent_bit: bool
    group_one_mass: float

    @property
    def agrees(self) -> bool:
        return self.group == self.latent_bit


@dataclass(frozen=True, slots=True)
class GenerationResult:
    """Tokens produced by one generation path plus its per-step watermark record."""

    scheme: str
    tokens: tuple[str, ...]
    steps: tuple[WatermarkStep, ...]

    @property
    def dna(self) -> str:
        return "".join(self.tokens)

    @property
    def bases(self) -> int:
        return sum(len(token) for token in self.tokens)

    @property
    def agreement_count(self) -> int:
        return sum(step.agrees for step in self.steps)

    @property
    def agreement_rate(self) -> float:
        return self.agreement_count / len(self.steps) if self.steps else 0.0

    @property
    def expected_agreement_rate(self) -> float:
        """Mean per-step agreement probability implied by the realized masses.

        Maximal coupling of a fair bit to a Bernoulli(q) group agrees with
        probability ``1 - |q - 1/2|``.
        """

        if not self.steps:
            return 0.0
        return sum(1.0 - abs(step.group_one_mass - 0.5) for step in self.steps) / len(self.steps)


def generate_partition_mc(
    next_distribution: NextDistribution,
    context: str,
    *,
    steps: int,
    stream: KeyedPartitionStream,
    rng: random.Random,
    stream_offset: int = 0,
) -> GenerationResult:
    """Generate autoregressively with the `partition_mc` watermark.

    ``next_distribution`` maps a DNA context to a ``(tokens, probabilities)``
    pair, so this loop stays model-independent. ``rng`` supplies only the
    residual randomization that keeps the marginal exact; it is not secret
    material and must not be derived from the key.
    """

    if not callable(next_distribution):
        raise TypeError("next_distribution must be callable")
    if steps <= 0:
        raise ValueError("steps must be positive")
    if stream_offset < 0:
        raise ValueError("stream_offset must be non-negative")
    tokens: list[str] = []
    records: list[WatermarkStep] = []
    current = context
    for index in range(steps):
        stream_index = stream_offset + index
        items, probabilities = next_distribution(current)
        if len(items) != len(probabilities):
            raise ValueError("items and probabilities must have the same length")
        partition = stream.partition(items, stream_index)
        latent_bit = stream.latent_bit(stream_index)
        sample: CoupledSample = sample_partition_coupling(
            items,
            probabilities,
            partition,
            latent_bit,
            rng,
        )
        records.append(
            WatermarkStep(
                index=index,
                stream_index=stream_index,
                token=sample.token,
                group=sample.group,
                latent_bit=sample.latent_bit,
                group_one_mass=sample.group_one_mass,
            )
        )
        tokens.append(sample.token)
        current += sample.token
    return GenerationResult(
        scheme=PARTITION_MC_SCHEME,
        tokens=tuple(tokens),
        steps=tuple(records),
    )


def generate_ordinary(
    next_distribution: NextDistribution,
    context: str,
    *,
    steps: int,
    rng: random.Random,
) -> GenerationResult:
    """Generate the matched ordinary control from the same declared policy law."""

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
    return GenerationResult(scheme=ORDINARY_SCHEME, tokens=tuple(tokens), steps=())


def stream_agreements(
    tokens: Sequence[str],
    support: Sequence[str],
    stream: KeyedPartitionStream,
    *,
    stream_offset: int = 0,
) -> tuple[bool, ...]:
    """Recompute per-position group agreement from tokens and the key alone.

    This is the model-free inverse of the generation loop: it needs the emitted
    tokens, the public support, the key, and the stream offset. It never touches
    a model distribution.
    """

    if not tokens:
        raise ValueError("tokens must not be empty")
    if stream_offset < 0:
        raise ValueError("stream_offset must be non-negative")
    support_set = set(support)
    missing = [token for token in tokens if token not in support_set]
    if missing:
        raise ValueError(f"support is missing {len(missing)} observed token(s)")
    agreements: list[bool] = []
    for index, token in enumerate(tokens):
        stream_index = stream_offset + index
        partition = stream.partition(support, stream_index)
        agreements.append(partition[token] == stream.latent_bit(stream_index))
    return tuple(agreements)
