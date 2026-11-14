"""Comparison baselines for the S2 detector study of the v5 review protocol.

Protocol: ``docs/research/synthid_v5_review_studies_protocol_2026_11_12.md``, Section 6.

These three detectors are analysis baselines only.  They do not replace or modify
``synthid-position-independent-detector-v1`` (the verifier in
:mod:`genomic_watermarks.synthid_position_independent`) and exist only for the S2
comparison in the v5 protocol.  No other result may use them.

All three use exactly the verifier's window statistic: the same keyed mark bits, four
context tokens, the first-occurrence repeated-context rule inside a window, the exact
fair-binomial upper tail ``fair_binomial_log_survival_probability``, and the same
sequence-level target.  Each corrects for the number of windows it searched, in log
space: ``log(M) + min log p <= log(target)``.

* :func:`detect_aligned_oracle` is told the strand, region start, and region length and
  scores one window (``M = 1``).
* :func:`detect_phase_only` searches both strands and six phases with one window per
  frame, the whole read from that phase (``M = 12`` for a read long enough).
* :func:`detect_fine_grid` searches both strands, every base start, and every window
  length ``384 + 96 j`` that fits the read.

Windows may not score more tokens than the context history holds.  That is the
verifier's own rule, and beyond it ``score_synthid_tokens`` (a bounded history) and the
verifier's first-occurrence rule would no longer agree, so these functions raise
instead of changing semantics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from genomic_watermarks.dna import KMER_SIZE, normalize_dna, reverse_complement, tokenize_fixed
from genomic_watermarks.synthid import KeyedTournament, score_synthid_tokens
from genomic_watermarks.synthid_boundary import score_synthid_unknown_boundaries
from genomic_watermarks.synthid_position_independent import (
    FORWARD,
    REVERSE_COMPLEMENT,
    PositionIndependentSynthIDConfig,
    fair_binomial_log_survival_probability,
)

ALIGNED_ORACLE_DETECTOR = "aligned-oracle-baseline"
PHASE_ONLY_DETECTOR = "phase-only-baseline"
FINE_GRID_DETECTOR = "fine-grid-baseline"
FINE_GRID_MINIMUM_BASES = 384
FINE_GRID_STEP_BASES = 96


@dataclass(frozen=True, slots=True)
class BaselineWindow:
    """The strongest window a baseline scored.

    ``oriented_start`` is in the read as searched (reverse-complemented when
    ``orientation`` is ``reverse_complement``); ``original_start`` and
    ``original_stop`` are in the read as supplied.
    """

    orientation: str
    oriented_start: int
    original_start: int
    original_stop: int
    window_base_length: int
    g_ones: int
    g_total: int
    scored_tokens: int
    repeated_contexts: int


@dataclass(frozen=True, slots=True)
class BaselineDetection:
    """One corrected baseline decision.

    ``sequence_log_p_value`` is capped at zero like the verifier's.
    ``uncapped_sequence_log_p_value`` is ``log(M) + min log p`` before the cap, so
    corrected strength ``-log10 P`` can be reported for reads whose corrected P is 1.
    """

    detector_id: str
    detected: bool
    sequence_log_p_value: float
    uncapped_sequence_log_p_value: float
    minimum_local_log_p_value: float
    hypotheses_searched: int
    target_false_positive_rate: float
    best_window: BaselineWindow


def _original_interval(
    *, read_length: int, orientation: str, oriented_start: int, window_length: int
) -> tuple[int, int]:
    if orientation == FORWARD:
        return oriented_start, oriented_start + window_length
    return read_length - oriented_start - window_length, read_length - oriented_start


def _orient(dna: str, orientation: str) -> str:
    if orientation == FORWARD:
        return dna
    if orientation == REVERSE_COMPLEMENT:
        return reverse_complement(dna)
    raise ValueError("unsupported orientation")


def _resolve(
    config: PositionIndependentSynthIDConfig | None,
) -> PositionIndependentSynthIDConfig:
    return config or PositionIndependentSynthIDConfig()


def _tournament(
    key: bytes, domain: str, config: PositionIndependentSynthIDConfig
) -> KeyedTournament:
    return KeyedTournament(
        key=key,
        domain=domain,
        depth=config.depth,
        context_tokens=config.context_tokens,
        context_history_size=config.context_history_size,
    )


def _check_window_tokens(tokens: int, config: PositionIndependentSynthIDConfig) -> None:
    scored = tokens - config.context_tokens
    if scored < 1:
        raise ValueError("window has no scored token after context warm-up")
    if scored > config.context_history_size:
        raise ValueError(
            f"a window scoring {scored} tokens exceeds the {config.context_history_size}-context "
            "history; the baselines support reads of at most "
            f"{(config.context_history_size + config.context_tokens + 1) * KMER_SIZE - 1} bases"
        )


def _finish(
    detector_id: str,
    *,
    hypotheses: int,
    best_log_p: float,
    window: BaselineWindow,
    config: PositionIndependentSynthIDConfig,
) -> BaselineDetection:
    uncapped = math.log(hypotheses) + best_log_p
    return BaselineDetection(
        detector_id=detector_id,
        detected=uncapped <= math.log(config.target_false_positive_rate),
        sequence_log_p_value=min(0.0, uncapped),
        uncapped_sequence_log_p_value=uncapped,
        minimum_local_log_p_value=best_log_p,
        hypotheses_searched=hypotheses,
        target_false_positive_rate=config.target_false_positive_rate,
        best_window=window,
    )


def _score_frame(
    oriented: str,
    *,
    phase: int,
    base_length: int,
    orientation: str,
    read_length: int,
    tournament: KeyedTournament,
) -> tuple[float, float, BaselineWindow]:
    """Score ``oriented[phase:phase + base_length]``; return (log p, statistic, window)."""

    tokens = tokenize_fixed(oriented[phase : phase + base_length])
    score = score_synthid_tokens(tokens, tournament)
    log_p = fair_binomial_log_survival_probability(score.g_ones, score.g_total)
    original_start, original_stop = _original_interval(
        read_length=read_length,
        orientation=orientation,
        oriented_start=phase,
        window_length=base_length,
    )
    window = BaselineWindow(
        orientation=orientation,
        oriented_start=phase,
        original_start=original_start,
        original_stop=original_stop,
        window_base_length=base_length,
        g_ones=score.g_ones,
        g_total=score.g_total,
        scored_tokens=score.scored_tokens,
        repeated_contexts=score.repeated_contexts,
    )
    return log_p, score.statistic, window


def detect_aligned_oracle(
    sequence: str,
    *,
    key: bytes,
    domain: str,
    region_start: int,
    region_length: int,
    region_on_forward_strand: bool,
    config: PositionIndependentSynthIDConfig | None = None,
) -> BaselineDetection:
    """Score the told region from its first base, floored to a multiple of six.

    ``region_start`` and ``region_length`` are in the read as supplied.  A read that
    was reverse-complemented is oriented back first, so the region is read 5' to 3'
    as generated.  One window, so no correction beyond ``M = 1``.
    """

    resolved = _resolve(config)
    dna = normalize_dna(sequence)
    if region_length <= 0 or region_start < 0 or region_start + region_length > len(dna):
        raise ValueError("the told region must lie inside the read")
    window_length = (region_length // KMER_SIZE) * KMER_SIZE
    _check_window_tokens(window_length // KMER_SIZE, resolved)
    orientation = FORWARD if region_on_forward_strand else REVERSE_COMPLEMENT
    oriented = _orient(dna, orientation)
    oriented_start = (
        region_start if region_on_forward_strand else len(dna) - region_start - region_length
    )
    log_p, _statistic, window = _score_frame(
        oriented,
        phase=oriented_start,
        base_length=window_length,
        orientation=orientation,
        read_length=len(dna),
        tournament=_tournament(key, domain, resolved),
    )
    return _finish(
        ALIGNED_ORACLE_DETECTOR, hypotheses=1, best_log_p=log_p, window=window, config=resolved
    )


def detect_phase_only(
    sequence: str,
    *,
    key: bytes,
    domain: str,
    config: PositionIndependentSynthIDConfig | None = None,
) -> BaselineDetection:
    """One window per (orientation, phase): the whole read from that phase offset.

    Each window is floored to a multiple of six.  ``M`` is the number of frames
    scored (12 for the two verifier orientations and six phases on a read long enough
    to leave a scored token in every frame).
    """

    resolved = _resolve(config)
    dna = normalize_dna(sequence)
    if not dna:
        raise ValueError("sequence must not be empty")
    tournament = _tournament(key, domain, resolved)
    best: tuple[tuple[float, float, int, int], BaselineWindow] | None = None
    frames = 0
    for orientation_index, orientation in enumerate(resolved.orientations):
        oriented = _orient(dna, orientation)
        for phase in range(KMER_SIZE):
            tokens = (len(dna) - phase) // KMER_SIZE
            if tokens <= resolved.context_tokens:
                continue
            _check_window_tokens(tokens, resolved)
            log_p, statistic, window = _score_frame(
                oriented,
                phase=phase,
                base_length=tokens * KMER_SIZE,
                orientation=orientation,
                read_length=len(dna),
                tournament=tournament,
            )
            frames += 1
            candidate = ((log_p, -statistic, orientation_index, phase), window)
            if best is None or candidate[0] < best[0]:
                best = candidate
    if best is None:
        raise ValueError("the read is too short to score any phase frame")
    return _finish(
        PHASE_ONLY_DETECTOR,
        hypotheses=frames,
        best_log_p=best[0][0],
        window=best[1],
        config=resolved,
    )


def fine_grid_lengths(read_bases: int) -> tuple[int, ...]:
    """Every length ``384 + 96 j`` that fits a read of ``read_bases`` bases."""

    return tuple(range(FINE_GRID_MINIMUM_BASES, read_bases + 1, FINE_GRID_STEP_BASES))


def expected_fine_grid_windows(read_bases: int, *, orientations: int = 2) -> int:
    """Closed-form window count of the fine-grid search."""

    return orientations * sum(read_bases - length + 1 for length in fine_grid_lengths(read_bases))


def detect_fine_grid(
    sequence: str,
    *,
    key: bytes,
    domain: str,
    config: PositionIndependentSynthIDConfig | None = None,
    window_base_lengths: tuple[int, ...] | None = None,
) -> BaselineDetection:
    """Search both strands, every base start, and every length ``384 + 96 j``.

    The scoring is :func:`score_synthid_unknown_boundaries`, the routine the verifier
    uses, so a window of a given start and length scores identically in both.  The
    ``config`` supplies depth, context, history, orientations, and the target; its
    ``window_base_lengths`` are ignored.  ``window_base_lengths`` replaces the
    generated length grid; it exists so a test can run this search on the verifier's
    four lengths and compare with the verifier.
    """

    resolved = _resolve(config)
    dna = normalize_dna(sequence)
    if not dna:
        raise ValueError("sequence must not be empty")
    lengths = tuple(window_base_lengths) if window_base_lengths else fine_grid_lengths(len(dna))
    if not lengths:
        raise ValueError("the read is shorter than the shortest fine-grid window")
    for length in lengths:
        _check_window_tokens(length // KMER_SIZE, resolved)
    tournament = _tournament(key, domain, resolved)

    hypotheses = 0
    best_key: tuple[float, float, int, int, int] | None = None
    best_score = None
    best_orientation = FORWARD
    for orientation_index, orientation in enumerate(resolved.orientations):
        by_length = score_synthid_unknown_boundaries(
            _orient(dna, orientation), base_lengths=lengths, tournament=tournament
        )
        for length in lengths:
            for score in by_length[length]:
                hypotheses += 1
                log_p = fair_binomial_log_survival_probability(score.g_ones, score.g_total)
                if best_key is not None and log_p > best_key[0]:
                    continue
                candidate = (log_p, -score.statistic, orientation_index, length, score.base_start)
                if best_key is None or candidate < best_key:
                    best_key, best_score, best_orientation = candidate, score, orientation
    if best_key is None or best_score is None:
        raise RuntimeError("the fine-grid search scored no window")
    length = best_key[3]
    original_start, original_stop = _original_interval(
        read_length=len(dna),
        orientation=best_orientation,
        oriented_start=best_score.base_start,
        window_length=length,
    )
    window = BaselineWindow(
        orientation=best_orientation,
        oriented_start=best_score.base_start,
        original_start=original_start,
        original_stop=original_stop,
        window_base_length=length,
        g_ones=best_score.g_ones,
        g_total=best_score.g_total,
        scored_tokens=best_score.scored_tokens,
        repeated_contexts=best_score.repeated_contexts,
    )
    return _finish(
        FINE_GRID_DETECTOR,
        hypotheses=hypotheses,
        best_log_p=best_key[0],
        window=window,
        config=resolved,
    )
