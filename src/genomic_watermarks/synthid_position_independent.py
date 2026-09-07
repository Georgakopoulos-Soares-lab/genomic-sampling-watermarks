"""Position-independent standalone detection for the SynthID tournament watermark.

The generator in :mod:`genomic_watermarks.synthid` is already position
independent: its PRF input is local token content, not an absolute token index.
This module completes that protocol on the verification side.  It accepts only
DNA, a key, and public configuration; searches both orientations, every
nucleotide start, and every declared window length; and returns one globally
corrected decision.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from genomic_watermarks.dna import KMER_SIZE, normalize_dna, reverse_complement
from genomic_watermarks.synthid import (
    DEFAULT_CONTEXT_HISTORY_SIZE,
    DEFAULT_CONTEXT_TOKENS,
    DEFAULT_DEPTH,
    KeyedTournament,
)
from genomic_watermarks.synthid_boundary import (
    BoundaryWindowScore,
    score_synthid_unknown_boundaries,
)

POSITION_INDEPENDENT_SYNTHID_DETECTOR = "synthid-position-independent-detector-v1"
FORWARD = "forward"
REVERSE_COMPLEMENT = "reverse_complement"
SUPPORTED_ORIENTATIONS = (FORWARD, REVERSE_COMPLEMENT)


@dataclass(frozen=True, slots=True)
class PositionIndependentSynthIDConfig:
    """Public parameters defining one complete detector hypothesis family."""

    window_base_lengths: tuple[int, ...] = (384, 768, 1536, 3072)
    orientations: tuple[str, ...] = SUPPORTED_ORIENTATIONS
    target_false_positive_rate: float = 0.01
    depth: int = DEFAULT_DEPTH
    context_tokens: int = DEFAULT_CONTEXT_TOKENS
    context_history_size: int = DEFAULT_CONTEXT_HISTORY_SIZE

    def __post_init__(self) -> None:
        if not self.window_base_lengths:
            raise ValueError("at least one window length is required")
        if len(set(self.window_base_lengths)) != len(self.window_base_lengths):
            raise ValueError("window lengths must be unique")
        if any(length <= 0 or length % KMER_SIZE for length in self.window_base_lengths):
            raise ValueError("window lengths must be positive multiples of six")
        if not self.orientations:
            raise ValueError("at least one orientation is required")
        if len(set(self.orientations)) != len(self.orientations):
            raise ValueError("orientations must be unique")
        if any(orientation not in SUPPORTED_ORIENTATIONS for orientation in self.orientations):
            raise ValueError("unsupported orientation")
        if not 0.0 < self.target_false_positive_rate < 1.0:
            raise ValueError("target false-positive rate must lie in (0, 1)")
        if not 0 < self.depth <= 256:
            raise ValueError("depth must lie in [1, 256]")
        if self.context_tokens <= 0 or self.context_history_size <= 0:
            raise ValueError("context and history sizes must be positive")
        minimum_tokens = min(self.window_base_lengths) // KMER_SIZE
        if minimum_tokens <= self.context_tokens:
            raise ValueError("every window must contain a scored token after context warm-up")
        maximum_scored = max(self.window_base_lengths) // KMER_SIZE - self.context_tokens
        if maximum_scored > self.context_history_size:
            raise ValueError("window exceeds the declared repetition-history size")


@dataclass(frozen=True, slots=True)
class PositionIndependentHypothesis:
    """The strongest local region, with coordinates in both read orientations."""

    orientation: str
    oriented_start: int
    original_start: int
    original_stop: int
    window_base_length: int
    statistic: float
    local_exact_p_value: float
    local_log_p_value: float
    g_ones: int
    g_total: int
    scored_tokens: int
    repeated_contexts: int


@dataclass(frozen=True, slots=True)
class PositionIndependentDetection:
    """One globally corrected position-independent SynthID decision."""

    detector_id: str
    detected: bool
    sequence_p_value: float
    sequence_log_p_value: float
    minimum_local_p_value: float
    minimum_local_log_p_value: float
    target_false_positive_rate: float
    hypotheses_searched: int
    orientations_searched: tuple[str, ...]
    window_base_lengths_searched: tuple[int, ...]
    best_hypothesis: PositionIndependentHypothesis


def _logaddexp(left: float, right: float) -> float:
    if left == -math.inf:
        return right
    if right == -math.inf:
        return left
    upper = max(left, right)
    return upper + math.log1p(math.exp(min(left, right) - upper))


@lru_cache(maxsize=32)
def _fair_binomial_log_survival_table(total: int) -> tuple[float, ...]:
    """Return log ``P[Binomial(total, 1/2) >= k]`` for every integer ``k``.

    Working from the all-successes endpoint in log space preserves extremely
    small positive tails which would underflow in ordinary floating point.
    The table is dependency-free and costs O(total) once for every distinct
    repetition-masked total encountered.
    """

    if total <= 0:
        raise ValueError("binomial total must be positive")
    survival = [-math.inf] * (total + 1)
    log_probability = -total * math.log(2.0)
    log_running = -math.inf
    for successes in range(total, -1, -1):
        log_running = _logaddexp(log_running, log_probability)
        survival[successes] = min(0.0, log_running)
        if successes:
            log_probability += math.log(successes) - math.log(total - successes + 1)
    survival[0] = 0.0
    return tuple(survival)


def fair_binomial_survival_probability(successes: int, total: int) -> float:
    """Exact one-sided local null p-value for a SynthID mean-g score."""

    if not 0 <= successes <= total:
        raise ValueError("successes must lie in [0, total]")
    return math.exp(fair_binomial_log_survival_probability(successes, total))


def fair_binomial_log_survival_probability(successes: int, total: int) -> float:
    """Natural log of the exact local tail, retained below float underflow."""

    if not 0 <= successes <= total:
        raise ValueError("successes must lie in [0, total]")
    if total <= 0:
        raise ValueError("binomial total must be positive")
    return _fair_binomial_log_survival_table(total)[successes]


def _orient(sequence: str, orientation: str) -> str:
    if orientation == FORWARD:
        return sequence
    if orientation == REVERSE_COMPLEMENT:
        return reverse_complement(sequence)
    raise ValueError("unsupported orientation")


def _original_interval(
    *,
    read_length: int,
    orientation: str,
    oriented_start: int,
    window_length: int,
) -> tuple[int, int]:
    if orientation == FORWARD:
        return oriented_start, oriented_start + window_length
    return read_length - oriented_start - window_length, read_length - oriented_start


def _hypothesis(
    score: BoundaryWindowScore,
    *,
    read_length: int,
    orientation: str,
    window_length: int,
    local_p_value: float,
    local_log_p_value: float,
) -> PositionIndependentHypothesis:
    original_start, original_stop = _original_interval(
        read_length=read_length,
        orientation=orientation,
        oriented_start=score.base_start,
        window_length=window_length,
    )
    return PositionIndependentHypothesis(
        orientation=orientation,
        oriented_start=score.base_start,
        original_start=original_start,
        original_stop=original_stop,
        window_base_length=window_length,
        statistic=score.statistic,
        local_exact_p_value=local_p_value,
        local_log_p_value=local_log_p_value,
        g_ones=score.g_ones,
        g_total=score.g_total,
        scored_tokens=score.scored_tokens,
        repeated_contexts=score.repeated_contexts,
    )


def detect_synthid_position_independent(
    sequence: str,
    *,
    key: bytes,
    domain: str,
    config: PositionIndependentSynthIDConfig | None = None,
) -> PositionIndependentDetection:
    """Detect SynthID without a prompt, boundary, phase, strand, or token offset.

    Oversized configured windows are skipped based only on public read length.
    The returned p-value applies one Bonferroni correction across every
    orientation, nucleotide start, and evaluated length.  No prompt score or
    empirical calibration sample selects the threshold.
    """

    dna = normalize_dna(sequence)
    if not dna:
        raise ValueError("sequence must not be empty")
    resolved = config or PositionIndependentSynthIDConfig()
    lengths = tuple(length for length in resolved.window_base_lengths if length <= len(dna))
    if not lengths:
        raise ValueError("sequence is shorter than every configured window")
    tournament = KeyedTournament(
        key=key,
        domain=domain,
        depth=resolved.depth,
        context_tokens=resolved.context_tokens,
        context_history_size=resolved.context_history_size,
    )

    candidates: list[PositionIndependentHypothesis] = []
    for orientation in resolved.orientations:
        oriented = _orient(dna, orientation)
        by_length = score_synthid_unknown_boundaries(
            oriented,
            base_lengths=lengths,
            tournament=tournament,
        )
        for window_length in lengths:
            for score in by_length[window_length]:
                local_log_p = fair_binomial_log_survival_probability(
                    score.g_ones,
                    score.g_total,
                )
                local_p = math.exp(local_log_p)
                candidates.append(
                    _hypothesis(
                        score,
                        read_length=len(dna),
                        orientation=orientation,
                        window_length=window_length,
                        local_p_value=local_p,
                        local_log_p_value=local_log_p,
                    )
                )
    if not candidates:
        raise RuntimeError("the declared position-independent search scored no hypothesis")
    best = min(
        candidates,
        key=lambda candidate: (
            candidate.local_log_p_value,
            -candidate.statistic,
            resolved.orientations.index(candidate.orientation),
            candidate.window_base_length,
            candidate.oriented_start,
        ),
    )
    hypotheses = len(candidates)
    sequence_log_p = min(0.0, math.log(hypotheses) + best.local_log_p_value)
    sequence_p = math.exp(sequence_log_p)
    return PositionIndependentDetection(
        detector_id=POSITION_INDEPENDENT_SYNTHID_DETECTOR,
        detected=sequence_log_p <= math.log(resolved.target_false_positive_rate),
        sequence_p_value=sequence_p,
        sequence_log_p_value=sequence_log_p,
        minimum_local_p_value=best.local_exact_p_value,
        minimum_local_log_p_value=best.local_log_p_value,
        target_false_positive_rate=resolved.target_false_positive_rate,
        hypotheses_searched=hypotheses,
        orientations_searched=resolved.orientations,
        window_base_lengths_searched=lengths,
        best_hypothesis=best,
    )
