"""Matched inverse-transform and exponential watermark baselines.

Two alternative exact-marginal sampling watermarks, built to be directly
comparable with `partition_mc`: the same canonical support, the same
position-indexed keyed randomness, and the same model-free verifier contract of
DNA plus a runtime key plus public configuration.

Inverse transform (`its`)
    A keyed permutation orders the support and a keyed uniform selects a point on
    the resulting cumulative distribution. The emitted token's normalized rank
    under that permutation lands near the uniform, so the verifier scores how close
    the two are.

Exponential (`exp`)
    One keyed uniform per candidate token, and the emitted token is the argmax of
    ``u^(1/p)``. The winner tends to be a token whose keyed uniform was large, so
    the verifier scores ``-log(1 - u)`` at the observed token.

Both preserve the declared one-step marginal exactly, by the inverse-transform and
Gumbel identities respectively. Both are scored without a model. Neither is claimed
as novel; they exist so the partition construction can be compared against the
published alternatives on the same corpus and the same detector discipline.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from genomic_watermarks.metrics import normalized_probabilities

ITS_SCHEME = "its-v1"
EXP_SCHEME = "exp-v1"

NextDistribution = Callable[[str], tuple[Sequence[str], Sequence[float]]]

_STREAM_LABEL = b"genomic-sampling-watermarks/baselines/v1\x00"
_UNIFORM_PURPOSE = b"inverse-transform-uniform\x00"
_PERMUTATION_PURPOSE = b"inverse-transform-permutation\x00"
_TOKEN_UNIFORM_PURPOSE = b"exponential-token-uniform\x00"

# 2**-53, so a digest maps into [0, 1) without ever reaching 1.
_UNIFORM_SCALE = 1.0 / (1 << 53)

# Mean of |A - B| for independent uniforms on [0, 1). The inverse-transform score
# is centred on this so that its null expectation is exactly zero.
_MEAN_ABSOLUTE_UNIFORM_GAP = 1.0 / 3.0


def _index_bytes(index: int) -> bytes:
    if index < 0:
        raise ValueError("stream index must be non-negative")
    if index >= 1 << 64:
        raise ValueError("stream index must fit in 64 bits")
    return index.to_bytes(8, "big")


def _digest_to_unit_interval(digest: bytes) -> float:
    return (int.from_bytes(digest[:7], "big") >> 3) * _UNIFORM_SCALE


@dataclass(frozen=True, slots=True, eq=False)
class KeyedBaselineStream:
    """Position-indexed keyed randomness for the inverse-transform and exponential baselines.

    The key is held only for the lifetime of the process and is excluded from
    ``repr`` so that logging a surrounding structure cannot leak it.
    """

    key: bytes = field(repr=False)
    domain: str

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("stream key must not be empty")
        if not self.domain:
            raise ValueError("stream domain must not be empty")

    def _digest(self, purpose: bytes, index: int, token: str = "") -> bytes:
        message = (
            _STREAM_LABEL
            + purpose
            + self.domain.encode("utf-8")
            + b"\x00"
            + _index_bytes(index)
            + token.encode("ascii")
        )
        return hmac.new(self.key, message, hashlib.sha256).digest()

    def uniform(self, index: int) -> float:
        """The keyed uniform on [0, 1) that selects a point on the cumulative distribution."""

        return _digest_to_unit_interval(self._digest(_UNIFORM_PURPOSE, index))

    def permutation(self, items: Sequence[str], index: int) -> tuple[str, ...]:
        """A keyed ordering of the support for one stream position."""

        if not items:
            raise ValueError("items must not be empty")
        if len(set(items)) != len(items):
            raise ValueError("items must be unique")
        digest = self._digest(_PERMUTATION_PURPOSE, index)
        return tuple(
            sorted(
                items,
                key=lambda item: (
                    hmac.new(digest, item.encode("ascii"), hashlib.sha256).digest(),
                    item,
                ),
            )
        )

    def token_uniform(self, index: int, token: str) -> float:
        """The keyed uniform on [0, 1) attached to one candidate token at one position."""

        return _digest_to_unit_interval(self._digest(_TOKEN_UNIFORM_PURPOSE, index, token))


def sample_inverse_transform(
    items: Sequence[str],
    probabilities: Sequence[float],
    permutation: Sequence[str],
    uniform: float,
) -> str:
    """Draw one token by inverse transform over a keyed ordering of the support.

    The marginal is exactly the declared law: the cumulative distribution is walked
    in the permuted order and a uniform point selects one interval, whose width is
    that token's probability.
    """

    if not 0.0 <= uniform < 1.0:
        raise ValueError("uniform must lie in [0, 1)")
    probs = normalized_probabilities(probabilities)
    if len(items) != len(probs):
        raise ValueError("items and probabilities must have the same length")
    if len(permutation) != len(items) or set(permutation) != set(items):
        raise ValueError("the permutation must be a reordering of the items")
    weight = dict(zip(items, probs, strict=True))
    cumulative = 0.0
    for token in permutation:
        cumulative += weight[token]
        if uniform < cumulative:
            return token
    return permutation[-1]


def inverse_transform_score(rank: int, support_size: int, uniform: float) -> float:
    """Score one observed token for the inverse-transform baseline.

    ``rank`` is the token's position in the keyed permutation. The normalized rank
    lands near the keyed uniform when the key wrote the sequence, so the score is
    the shortfall of their absolute gap below its null mean of one third. The null
    expectation is therefore exactly zero.
    """

    if support_size <= 0:
        raise ValueError("support size must be positive")
    if not 0 <= rank < support_size:
        raise ValueError("rank must lie in [0, support size)")
    if not 0.0 <= uniform < 1.0:
        raise ValueError("uniform must lie in [0, 1)")
    normalized_rank = (rank + 0.5) / support_size
    return _MEAN_ABSOLUTE_UNIFORM_GAP - abs(normalized_rank - uniform)


def sample_exponential(
    items: Sequence[str],
    probabilities: Sequence[float],
    token_uniforms: Sequence[float],
) -> str:
    """Draw one token by the exponential, or Gumbel, trick.

    With independent uniforms ``u_v``, the argmax of ``u_v ** (1 / p_v)`` is
    distributed exactly as ``p``. Zero-probability tokens can never win.
    """

    probs = normalized_probabilities(probabilities)
    if len(items) != len(probs) or len(items) != len(token_uniforms):
        raise ValueError("items, probabilities, and uniforms must have the same length")
    best_token: str | None = None
    best_score = -math.inf
    for token, probability, uniform in zip(items, probs, token_uniforms, strict=True):
        if not 0.0 <= uniform < 1.0:
            raise ValueError("uniforms must lie in [0, 1)")
        if probability <= 0.0:
            continue
        # log(u) / p is monotone in u ** (1 / p) and avoids underflow for small p.
        score = math.log(uniform) / probability if uniform > 0.0 else -math.inf
        if score > best_score:
            best_score = score
            best_token = token
    if best_token is None:
        raise RuntimeError("the declared law has no token with positive probability")
    return best_token


def exponential_score(uniform: float) -> float:
    """Score one observed token for the exponential baseline.

    ``-log(1 - u)`` at the observed token. Under the null the uniform is
    independent of the token, so the score is a unit exponential with mean one; the
    emitted token tends to be one whose uniform was large, so the mean rises.
    """

    if not 0.0 <= uniform < 1.0:
        raise ValueError("uniform must lie in [0, 1)")
    return -math.log1p(-uniform)


EXPONENTIAL_NULL_MEAN = 1.0
INVERSE_TRANSFORM_NULL_MEAN = 0.0


@dataclass(frozen=True, slots=True)
class BaselineStep:
    """One emitted position, without distribution or key material."""

    index: int
    stream_index: int
    token: str
    score: float


@dataclass(frozen=True, slots=True)
class BaselineResult:
    """Tokens from one baseline generation path plus its per-step scores."""

    scheme: str
    tokens: tuple[str, ...]
    steps: tuple[BaselineStep, ...]

    @property
    def dna(self) -> str:
        return "".join(self.tokens)

    @property
    def total_score(self) -> float:
        return math.fsum(step.score for step in self.steps)

    @property
    def mean_score(self) -> float:
        return self.total_score / len(self.steps) if self.steps else 0.0


def generate_inverse_transform(
    next_distribution: NextDistribution,
    context: str,
    *,
    steps: int,
    stream: KeyedBaselineStream,
    stream_offset: int = 0,
) -> BaselineResult:
    """Generate autoregressively with the inverse-transform watermark.

    This path is fully determined by the key: it draws no auxiliary randomness at
    all, which is the structural difference from partition coupling.
    """

    if steps <= 0:
        raise ValueError("steps must be positive")
    if stream_offset < 0:
        raise ValueError("stream_offset must be non-negative")
    tokens: list[str] = []
    records: list[BaselineStep] = []
    current = context
    for index in range(steps):
        stream_index = stream_offset + index
        items, probabilities = next_distribution(current)
        permutation = stream.permutation(items, stream_index)
        uniform = stream.uniform(stream_index)
        token = sample_inverse_transform(items, probabilities, permutation, uniform)
        rank = permutation.index(token)
        records.append(
            BaselineStep(
                index=index,
                stream_index=stream_index,
                token=token,
                score=inverse_transform_score(rank, len(permutation), uniform),
            )
        )
        tokens.append(token)
        current += token
    return BaselineResult(scheme=ITS_SCHEME, tokens=tuple(tokens), steps=tuple(records))


def generate_exponential(
    next_distribution: NextDistribution,
    context: str,
    *,
    steps: int,
    stream: KeyedBaselineStream,
    stream_offset: int = 0,
) -> BaselineResult:
    """Generate autoregressively with the exponential watermark.

    Like the inverse-transform path, this is fully determined by the key.
    """

    if steps <= 0:
        raise ValueError("steps must be positive")
    if stream_offset < 0:
        raise ValueError("stream_offset must be non-negative")
    tokens: list[str] = []
    records: list[BaselineStep] = []
    current = context
    for index in range(steps):
        stream_index = stream_offset + index
        items, probabilities = next_distribution(current)
        uniforms = [stream.token_uniform(stream_index, token) for token in items]
        token = sample_exponential(items, probabilities, uniforms)
        records.append(
            BaselineStep(
                index=index,
                stream_index=stream_index,
                token=token,
                score=exponential_score(stream.token_uniform(stream_index, token)),
            )
        )
        tokens.append(token)
        current += token
    return BaselineResult(scheme=EXP_SCHEME, tokens=tuple(tokens), steps=tuple(records))


def score_inverse_transform(
    tokens: Sequence[str],
    support: Sequence[str],
    stream: KeyedBaselineStream,
    *,
    stream_offset: int = 0,
) -> tuple[float, ...]:
    """Recompute inverse-transform scores from tokens and the key alone."""

    if not tokens:
        raise ValueError("tokens must not be empty")
    if stream_offset < 0:
        raise ValueError("stream_offset must be non-negative")
    support_set = set(support)
    missing = [token for token in tokens if token not in support_set]
    if missing:
        raise ValueError(f"support is missing {len(missing)} observed token(s)")
    scores: list[float] = []
    for index, token in enumerate(tokens):
        stream_index = stream_offset + index
        permutation = stream.permutation(support, stream_index)
        scores.append(
            inverse_transform_score(
                permutation.index(token), len(permutation), stream.uniform(stream_index)
            )
        )
    return tuple(scores)


def score_exponential(
    tokens: Sequence[str],
    support: Sequence[str],
    stream: KeyedBaselineStream,
    *,
    stream_offset: int = 0,
) -> tuple[float, ...]:
    """Recompute exponential scores from tokens and the key alone."""

    if not tokens:
        raise ValueError("tokens must not be empty")
    if stream_offset < 0:
        raise ValueError("stream_offset must be non-negative")
    support_set = set(support)
    missing = [token for token in tokens if token not in support_set]
    if missing:
        raise ValueError(f"support is missing {len(missing)} observed token(s)")
    return tuple(
        exponential_score(stream.token_uniform(stream_offset + index, token))
        for index, token in enumerate(tokens)
    )


def generate_ordinary_baseline(
    next_distribution: NextDistribution,
    context: str,
    *,
    steps: int,
    rng: random.Random,
) -> BaselineResult:
    """Matched ordinary control that records no score."""

    from genomic_watermarks.sampling.partition import sample_categorical

    if steps <= 0:
        raise ValueError("steps must be positive")
    tokens: list[str] = []
    current = context
    for _ in range(steps):
        items, probabilities = next_distribution(current)
        token = sample_categorical(items, probabilities, rng)
        tokens.append(token)
        current += token
    return BaselineResult(scheme="ordinary-categorical-v1", tokens=tuple(tokens), steps=())
