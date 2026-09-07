"""SynthID-Text-style non-distortionary tournament sampling for DNA tokens.

This is a model-independent adaptation of the tournament construction in
DeepMind's ``synthid-text`` implementation.  For each unique recent-token
context, a keyed PRF assigns ``depth`` binary g-values to every candidate.  A
two-way tournament layer transforms a categorical law ``p`` as

``p'(x) = p(x) * (1 + g(x) - sum_y p(y) g(y))``.

Applying the transform once per layer is distributionally equivalent to the
binary tournament, without materialising its ``2**depth`` conceptual leaves.
The released SynthID-Text defaults are used here: four context tokens and 30
layers.  Repeated contexts are sampled ordinarily and excluded from detection,
as in the reference implementation.

The construction is non-distortionary over fresh pseudorandom g-functions.  A
fixed key and fixed context intentionally induce a reweighted conditional law;
callers must not describe that key-conditional law as equal to the model law.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import random
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from genomic_watermarks.metrics import normalized_probabilities
from genomic_watermarks.sampling.partition import sample_categorical

SYNTHID_SCHEME = "synthid-tournament-v1"
DEFAULT_CONTEXT_TOKENS = 4
DEFAULT_DEPTH = 30
DEFAULT_CONTEXT_HISTORY_SIZE = 1024

NextDistribution = Callable[[str], tuple[Sequence[str], Sequence[float]]]

_PRF_LABEL = b"genomic-sampling-watermarks/synthid-tournament/v1\x00"

_SHA256_BLOCK_SIZE = 64
_NUMPY_UNRESOLVED = "unresolved"
_numpy_module: object = _NUMPY_UNRESOLVED


def _numpy():
    """Return NumPy when importable, else ``None``.

    The core package declares no dependencies, so the vectorised path is an
    optional accelerator.  Both paths compute the same construction; the pure
    Python reference stays authoritative and is exercised against the fast
    path in the test suite.
    """

    global _numpy_module
    if _numpy_module is _NUMPY_UNRESOLVED:
        try:
            import numpy
        except ImportError:  # pragma: no cover - exercised on minimal installs
            _numpy_module = None
        else:
            _numpy_module = numpy
    return _numpy_module


def _length_prefixed(value: bytes) -> bytes:
    if len(value) >= 1 << 32:
        raise ValueError("encoded value is too long")
    return len(value).to_bytes(4, "big") + value


_suffix_cache: dict[tuple[str, ...], tuple[bytes, ...]] = {}
_SUFFIX_CACHE_LIMIT = 4


def _candidate_suffixes(candidates: Sequence[str]) -> tuple[bytes, ...]:
    """Return the encoded PRF tail of each candidate, cached by vocabulary.

    The candidate set is the fixed canonical vocabulary, so its encoding is
    recomputed on every generated token for no reason.  Caching it removes two
    allocations per candidate per token without altering a single PRF byte.
    """

    key = tuple(candidates)
    cached = _suffix_cache.get(key)
    if cached is None:
        for candidate in key:
            if not candidate:
                raise ValueError("context and candidate tokens must not be empty")
        cached = tuple(_length_prefixed(candidate.encode("ascii")) for candidate in key)
        if len(_suffix_cache) >= _SUFFIX_CACHE_LIMIT:
            _suffix_cache.clear()
        _suffix_cache[key] = cached
    return cached


@dataclass(frozen=True, slots=True, eq=False)
class KeyedTournament:
    """Context-keyed binary g-values for a SynthID-style tournament.

    One HMAC-SHA-256 output supplies the layer bits for a candidate.  Under the
    PRF assumption these bits are computationally indistinguishable from the
    independent Bernoulli(1/2) values required by the tournament construction.
    The secret key is excluded from ``repr``.
    """

    key: bytes = field(repr=False)
    domain: str
    depth: int = DEFAULT_DEPTH
    context_tokens: int = DEFAULT_CONTEXT_TOKENS
    context_history_size: int = DEFAULT_CONTEXT_HISTORY_SIZE
    _pads: tuple[object, object] = field(
        init=False, repr=False, compare=False, hash=False, default=()
    )

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("tournament key must not be empty")
        if not self.domain:
            raise ValueError("tournament domain must not be empty")
        if not 0 < self.depth <= 256:
            raise ValueError("tournament depth must lie in [1, 256]")
        if self.context_tokens <= 0:
            raise ValueError("context_tokens must be positive")
        if self.context_history_size <= 0:
            raise ValueError("context_history_size must be positive")
        # RFC 2104 pads, primed once so that the per-candidate work is one
        # inner and one outer compression rather than a full re-keying.  This
        # is the same function as ``hmac.new(key, msg, sha256)``; the test
        # suite asserts digest equality against ``hmac`` directly.
        block = self.key
        if len(block) > _SHA256_BLOCK_SIZE:
            block = hashlib.sha256(block).digest()
        block = block.ljust(_SHA256_BLOCK_SIZE, b"\x00")
        inner = hashlib.sha256(bytes(byte ^ 0x36 for byte in block))
        outer = hashlib.sha256(bytes(byte ^ 0x5C for byte in block))
        object.__setattr__(self, "_pads", (inner, outer))

    def _context_prefix(self, context: Sequence[str]) -> bytes:
        """Return the PRF message bytes shared by every candidate."""

        resolved = tuple(str(token) for token in context)
        if len(resolved) != self.context_tokens:
            raise ValueError(
                f"tournament context must contain exactly {self.context_tokens} tokens"
            )
        if any(not token for token in resolved):
            raise ValueError("context and candidate tokens must not be empty")
        message = bytearray(_PRF_LABEL)
        message.extend(_length_prefixed(self.domain.encode("utf-8")))
        for token in resolved:
            message.extend(_length_prefixed(token.encode("ascii")))
        return bytes(message)

    def candidate_digests(
        self,
        context: Sequence[str],
        candidates: Sequence[str],
    ) -> bytes:
        """Return the concatenated 32-byte PRF digest of every candidate.

        The inner state is advanced through the context-dependent prefix once
        and copied per candidate, so a 4,096-way vocabulary costs one inner
        and one outer compression each instead of re-hashing the prefix.
        """

        inner_pad, outer_pad = self._pads
        base = inner_pad.copy()
        base.update(self._context_prefix(context))
        copy_inner = base.copy
        copy_outer = outer_pad.copy
        digests = bytearray()
        for suffix in _candidate_suffixes(candidates):
            inner = copy_inner()
            inner.update(suffix)
            outer = copy_outer()
            outer.update(inner.digest())
            digests.extend(outer.digest())
        return bytes(digests)

    def candidate_g_bits(
        self,
        context: Sequence[str],
        candidates: Sequence[str],
    ):
        """Return a ``candidate x layer`` uint8 g-value array, or ``None``.

        ``None`` signals that NumPy is unavailable and the caller must use the
        pure Python path.  ``numpy.unpackbits`` is big-endian within each byte,
        which is precisely the bit order ``g_values`` reads out of the digest.
        """

        numpy = _numpy()
        if numpy is None:
            return None
        digests = self.candidate_digests(context, candidates)
        raw = numpy.frombuffer(digests, dtype=numpy.uint8).reshape(len(candidates), 32)
        return numpy.unpackbits(raw, axis=1)[:, : self.depth]

    def _digest(self, context: Sequence[str], candidate: str) -> bytes:
        resolved = tuple(str(token) for token in context)
        if len(resolved) != self.context_tokens:
            raise ValueError(
                f"tournament context must contain exactly {self.context_tokens} tokens"
            )
        if any(not token for token in resolved) or not candidate:
            raise ValueError("context and candidate tokens must not be empty")
        message = bytearray(_PRF_LABEL)
        message.extend(_length_prefixed(self.domain.encode("utf-8")))
        for token in resolved:
            message.extend(_length_prefixed(token.encode("ascii")))
        message.extend(_length_prefixed(candidate.encode("ascii")))
        return hmac.new(self.key, bytes(message), hashlib.sha256).digest()

    def g_mask(self, context: Sequence[str], candidate: str) -> int:
        """Return the candidate's first ``depth`` PRF bits as an integer mask."""

        digest = self._digest(context, candidate)
        return int.from_bytes(digest, "big") >> (256 - self.depth)

    def g_values(self, context: Sequence[str], candidate: str) -> tuple[int, ...]:
        """Return one binary g-value per tournament layer."""

        mask = self.g_mask(context, candidate)
        return tuple((mask >> (self.depth - 1 - layer)) & 1 for layer in range(self.depth))

    def candidate_g_values(
        self,
        context: Sequence[str],
        candidates: Sequence[str],
    ) -> tuple[tuple[int, ...], ...]:
        """Return a ``candidate × layer`` binary g-value matrix."""

        return tuple(self.g_values(context, candidate) for candidate in candidates)


@dataclass(frozen=True, slots=True)
class TournamentDistribution:
    """The exact categorical law after all declared tournament layers."""

    probabilities: tuple[float, ...]
    g_masses: tuple[float, ...]


def update_tournament_probabilities(
    probabilities: Sequence[float],
    g_values: Sequence[Sequence[int | bool]],
) -> TournamentDistribution:
    """Apply the non-distortionary binary tournament probability update.

    ``g_values`` is indexed by candidate and then layer.  This function mirrors
    ``synthid_text.logits_processing.update_scores`` in probability space.
    """

    probs = list(normalized_probabilities(probabilities))
    rows = tuple(tuple(int(value) for value in row) for row in g_values)
    if len(rows) != len(probs):
        raise ValueError("g-value rows must match the probability vector")
    if not rows:
        raise ValueError("at least one candidate is required")
    depth = len(rows[0])
    if depth <= 0 or any(len(row) != depth for row in rows):
        raise ValueError("g-value rows must have one common positive depth")
    if any(value not in (0, 1) for row in rows for value in row):
        raise ValueError("g-values must be binary")

    masses: list[float] = []
    for layer in range(depth):
        mass = math.fsum(
            probability for probability, row in zip(probs, rows, strict=True) if row[layer]
        )
        masses.append(mass)
        probs = [
            probability * (1.0 + row[layer] - mass)
            for probability, row in zip(probs, rows, strict=True)
        ]
        # The transform sums to one algebraically.  Normalization controls only
        # floating-point drift over the released default's 30 layers.
        probs = list(normalized_probabilities(probs))
    return TournamentDistribution(probabilities=tuple(probs), g_masses=tuple(masses))


def _validate_tournament_inputs(
    items: Sequence[str],
    probabilities: Sequence[float],
) -> None:
    if len(items) != len(probabilities):
        raise ValueError("items and probabilities must have the same length")
    if not items or len(set(items)) != len(items):
        raise ValueError("items must be non-empty and unique")


def tournament_distribution_reference(
    items: Sequence[str],
    probabilities: Sequence[float],
    context: Sequence[str],
    tournament: KeyedTournament,
) -> TournamentDistribution:
    """Pure Python tournament law.  Authoritative definition of the construction.

    This path has no third-party dependency and is the oracle the vectorised
    path is tested against.  It keeps one compact PRF mask per candidate rather
    than a ``4,096 x 30`` Python integer matrix.
    """

    _validate_tournament_inputs(items, probabilities)
    probs = list(normalized_probabilities(probabilities))
    masks = tuple(tournament.g_mask(context, item) for item in items)
    masses: list[float] = []
    for layer in range(tournament.depth):
        bit = 1 << (tournament.depth - 1 - layer)
        mass = math.fsum(
            probability for probability, mask in zip(probs, masks, strict=True) if mask & bit
        )
        masses.append(mass)
        probs = [
            probability * (2.0 - mass if mask & bit else 1.0 - mass)
            for probability, mask in zip(probs, masks, strict=True)
        ]
        probs = list(normalized_probabilities(probs))
    return TournamentDistribution(probabilities=tuple(probs), g_masses=tuple(masses))


def _tournament_probabilities_numpy(
    items: Sequence[str],
    probabilities: Sequence[float],
    context: Sequence[str],
    tournament: KeyedTournament,
    numpy,
):
    """Return ``(probability array, g masses)`` using the vectorised path.

    The layer recurrence is inherently sequential -- ``mass`` depends on the
    probabilities the previous layer produced -- so the win is per-layer width,
    not depth.  ``p * (2 - mass)`` when ``g`` is set and ``p * (1 - mass)``
    otherwise is exactly ``p * (1 - mass + g)``, which needs no branch.
    """

    probs = numpy.asarray(probabilities, dtype=numpy.float64)
    if not numpy.isfinite(probs).all() or (probs < 0.0).any():
        raise ValueError("probabilities must be finite and non-negative")
    total = probs.sum()
    if total <= 0.0:
        raise ValueError("probability vector must have positive mass")
    probs = probs / total
    bits = tournament.candidate_g_bits(context, items)
    columns = bits.astype(numpy.float64)
    masses: list[float] = []
    for layer in range(tournament.depth):
        column = columns[:, layer]
        mass = float(probs @ column)
        masses.append(mass)
        probs = probs * (1.0 - mass + column)
        # Algebraically the transform already sums to one; this only bounds
        # floating-point drift across the released default's 30 layers.
        total = probs.sum()
        if total <= 0.0:
            raise ValueError("probability vector must have positive mass")
        probs = probs / total
    return probs, tuple(masses), bits


def tournament_distribution(
    items: Sequence[str],
    probabilities: Sequence[float],
    context: Sequence[str],
    tournament: KeyedTournament,
) -> TournamentDistribution:
    """Return the key- and context-conditional tournament law.

    Dispatches to the vectorised path when NumPy is importable and to
    :func:`tournament_distribution_reference` otherwise.  Both compute the same
    construction from the same bit-identical PRF digests.
    """

    _validate_tournament_inputs(items, probabilities)
    numpy = _numpy()
    if numpy is None:
        return tournament_distribution_reference(items, probabilities, context, tournament)
    probs, masses, _bits = _tournament_probabilities_numpy(
        items, probabilities, context, tournament, numpy
    )
    return TournamentDistribution(probabilities=tuple(probs.tolist()), g_masses=masses)


def _sample_index_numpy(probabilities, rng: random.Random, numpy) -> int:
    """Pick an index with exactly one uniform variate.

    Mirrors :func:`sample_categorical`: ``numpy.cumsum`` accumulates in the same
    sequential order as the reference loop, and ``searchsorted(..., "right")``
    returns the first index whose running total exceeds the variate, which is
    the reference's ``threshold < cumulative``.
    """

    total = probabilities.sum()
    if total <= 0.0:
        raise ValueError("probability vector must have positive mass")
    normalized = probabilities / total
    threshold = rng.random()
    cumulative = numpy.cumsum(normalized)
    index = int(numpy.searchsorted(cumulative, threshold, side="right"))
    return min(index, int(probabilities.shape[0]) - 1)


def _tournament_step(
    items: Sequence[str],
    probabilities: Sequence[float],
    context: Sequence[str],
    tournament: KeyedTournament,
    rng: random.Random,
) -> tuple[str, tuple[int, ...]]:
    """Sample one watermarked token and return it with its layer g-values."""

    _validate_tournament_inputs(items, probabilities)
    numpy = _numpy()
    if numpy is None:
        updated = tournament_distribution_reference(items, probabilities, context, tournament)
        token = sample_categorical(items, updated.probabilities, rng)
        return token, tournament.g_values(context, token)
    probs, _masses, bits = _tournament_probabilities_numpy(
        items, probabilities, context, tournament, numpy
    )
    index = _sample_index_numpy(probs, rng, numpy)
    token = items[index]
    return token, tuple(int(value) for value in bits[index])


@dataclass(frozen=True, slots=True)
class TournamentStep:
    """One generated token and the detector-visible tournament trace."""

    index: int
    token: str
    applied: bool
    repeated_context: bool
    g_values: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class SynthIDGenerationResult:
    """An autoregressive SynthID-style continuation."""

    scheme: str
    tokens: tuple[str, ...]
    steps: tuple[TournamentStep, ...]

    @property
    def dna(self) -> str:
        return "".join(self.tokens)

    @property
    def scored_tokens(self) -> int:
        return sum(step.applied for step in self.steps)

    @property
    def repeated_contexts(self) -> int:
        return sum(step.repeated_context for step in self.steps)

    @property
    def g_ones(self) -> int:
        return sum(sum(step.g_values) for step in self.steps if step.applied)

    @property
    def g_total(self) -> int:
        return sum(len(step.g_values) for step in self.steps if step.applied)

    @property
    def mean_g_value(self) -> float:
        return self.g_ones / self.g_total if self.g_total else 0.0


def _remember_context(
    context: tuple[str, ...],
    history: deque[tuple[str, ...]],
    seen: set[tuple[str, ...]],
    limit: int,
) -> bool:
    repeated = context in seen
    if len(history) == limit:
        removed = history.popleft()
        if removed not in history:
            seen.remove(removed)
    history.append(context)
    seen.add(context)
    return repeated


def generate_synthid(
    next_distribution: NextDistribution,
    context: str,
    *,
    steps: int,
    tournament: KeyedTournament,
    rng: random.Random,
) -> SynthIDGenerationResult:
    """Generate with the clean SynthID-style tournament path.

    The first ``context_tokens`` output tokens are ordinary samples.  This
    makes every scored n-gram reconstructable from output DNA alone, without
    giving the detector the prompt.
    """

    if not callable(next_distribution):
        raise TypeError("next_distribution must be callable")
    if steps <= 0:
        raise ValueError("steps must be positive")
    tokens: list[str] = []
    records: list[TournamentStep] = []
    history: deque[tuple[str, ...]] = deque()
    seen: set[tuple[str, ...]] = set()
    current = context
    for index in range(steps):
        items, probabilities = next_distribution(current)
        items = tuple(items)
        probabilities = tuple(probabilities)
        if len(items) != len(probabilities):
            raise ValueError("items and probabilities must have the same length")
        if index < tournament.context_tokens:
            token = sample_categorical(items, probabilities, rng)
            record = TournamentStep(
                index=index,
                token=token,
                applied=False,
                repeated_context=False,
                g_values=(),
            )
        else:
            recent = tuple(tokens[-tournament.context_tokens :])
            repeated = _remember_context(
                recent,
                history,
                seen,
                tournament.context_history_size,
            )
            if repeated:
                token = sample_categorical(items, probabilities, rng)
                record = TournamentStep(
                    index=index,
                    token=token,
                    applied=False,
                    repeated_context=True,
                    g_values=(),
                )
            else:
                token, values = _tournament_step(items, probabilities, recent, tournament, rng)
                record = TournamentStep(
                    index=index,
                    token=token,
                    applied=True,
                    repeated_context=False,
                    g_values=values,
                )
        tokens.append(token)
        records.append(record)
        current += token
    return SynthIDGenerationResult(
        scheme=SYNTHID_SCHEME,
        tokens=tuple(tokens),
        steps=tuple(records),
    )


@dataclass(frozen=True, slots=True)
class SynthIDScore:
    """Aligned clean detector score from output tokens and a key."""

    statistic: float
    mean_g_value: float
    g_ones: int
    g_total: int
    scored_tokens: int
    repeated_contexts: int


def score_synthid_tokens(
    tokens: Sequence[str],
    tournament: KeyedTournament,
) -> SynthIDScore:
    """Score known-forward, phase-zero output with no alignment search."""

    resolved = tuple(str(token) for token in tokens)
    if len(resolved) <= tournament.context_tokens:
        raise ValueError("not enough tokens to form a scored tournament n-gram")
    history: deque[tuple[str, ...]] = deque()
    seen: set[tuple[str, ...]] = set()
    ones = 0
    total = 0
    scored = 0
    repeated_count = 0
    for index in range(tournament.context_tokens, len(resolved)):
        recent = resolved[index - tournament.context_tokens : index]
        repeated = _remember_context(
            recent,
            history,
            seen,
            tournament.context_history_size,
        )
        if repeated:
            repeated_count += 1
            continue
        values = tournament.g_values(recent, resolved[index])
        ones += sum(values)
        total += len(values)
        scored += 1
    if total <= 0:
        raise ValueError("all available tournament contexts were masked")
    return SynthIDScore(
        statistic=(2.0 * ones - total) / math.sqrt(total),
        mean_g_value=ones / total,
        g_ones=ones,
        g_total=total,
        scored_tokens=scored,
        repeated_contexts=repeated_count,
    )
