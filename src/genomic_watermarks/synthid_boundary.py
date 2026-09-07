"""Exhaustive unknown-boundary scoring for the SynthID tournament detector.

Every nucleotide start defines a fixed-length, phase-zero 6-mer window.  A
one-base stride therefore searches the unknown generation boundary and all six
blocking phases at once.  The implementation below is exactly equivalent to
calling ``score_synthid_tokens`` on every substring, but caches each keyed
context score and uses range sums so the model-free validation remains cheap.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

from genomic_watermarks.dna import BASES, KMER_SIZE, normalize_dna, tokenize_fixed
from genomic_watermarks.synthid import KeyedTournament


@dataclass(frozen=True, slots=True)
class BoundaryWindowScore:
    """SynthID score for one candidate nucleotide start."""

    base_start: int
    statistic: float
    mean_g_value: float
    g_ones: int
    g_total: int
    scored_tokens: int
    repeated_contexts: int


@dataclass(frozen=True, slots=True)
class SingleBaseEdit:
    """One reproducible nucleotide edit applied inside a generated continuation."""

    condition: str
    position: int
    original_base: str | None
    edited_base: str | None
    sequence: str


class _Fenwick:
    """Small integer Fenwick tree used only when a phase contains repeated contexts."""

    def __init__(self, size: int) -> None:
        self._values = [0] * (size + 1)

    def add(self, index: int, value: int) -> None:
        resolved = index + 1
        while resolved < len(self._values):
            self._values[resolved] += value
            resolved += resolved & -resolved

    def prefix(self, stop: int) -> int:
        total = 0
        resolved = stop
        while resolved > 0:
            total += self._values[resolved]
            resolved -= resolved & -resolved
        return total

    def range_sum(self, start: int, stop: int) -> int:
        return self.prefix(stop) - self.prefix(start)


@dataclass(frozen=True, slots=True)
class _PhaseTrace:
    phase: int
    tokens: tuple[str, ...]
    weights: tuple[int, ...]
    previous: tuple[int, ...]
    has_repeats: bool


def _prepare_phase(
    dna: str,
    *,
    phase: int,
    tournament: KeyedTournament,
) -> _PhaseTrace:
    tokens = tokenize_fixed(dna, phase=phase)
    context_tokens = tournament.context_tokens
    weights = [0] * len(tokens)
    previous = [-1] * len(tokens)
    last_seen: dict[tuple[str, ...], int] = {}
    has_repeats = False
    for index in range(context_tokens, len(tokens)):
        context = tokens[index - context_tokens : index]
        prior = last_seen.get(context, -1)
        previous[index] = prior
        has_repeats = has_repeats or prior >= 0
        last_seen[context] = index
        weights[index] = tournament.g_mask(context, tokens[index]).bit_count()
    return _PhaseTrace(
        phase=phase,
        tokens=tokens,
        weights=tuple(weights),
        previous=tuple(previous),
        has_repeats=has_repeats,
    )


def _phase_scores(
    trace: _PhaseTrace,
    *,
    window_tokens: int,
    tournament: KeyedTournament,
) -> tuple[BoundaryWindowScore, ...]:
    starts = len(trace.tokens) - window_tokens + 1
    if starts <= 0:
        return ()
    context_tokens = tournament.context_tokens
    if window_tokens <= context_tokens:
        raise ValueError("window must contain at least one scored SynthID token")
    scored_per_window = window_tokens - context_tokens
    if scored_per_window > tournament.context_history_size:
        raise ValueError("window exceeds the declared repetition-history size")

    results: list[BoundaryWindowScore] = []
    if not trace.has_repeats:
        prefix = [0]
        for weight in trace.weights:
            prefix.append(prefix[-1] + weight)
        total = scored_per_window * tournament.depth
        for token_start in range(starts):
            score_start = token_start + context_tokens
            stop = token_start + window_tokens
            ones = prefix[stop] - prefix[score_start]
            results.append(
                BoundaryWindowScore(
                    base_start=trace.phase + token_start * KMER_SIZE,
                    statistic=(2.0 * ones - total) / math.sqrt(total),
                    mean_g_value=ones / total,
                    g_ones=ones,
                    g_total=total,
                    scored_tokens=scored_per_window,
                    repeated_contexts=0,
                )
            )
        return tuple(results)

    # A context is scored only on its first occurrence inside a candidate
    # window.  For score range [A, B), position i is eligible exactly when
    # previous[i] < A.  Sweep A from left to right and maintain eligible
    # positions in two Fenwick trees for O(log n) range queries.
    weight_tree = _Fenwick(len(trace.tokens))
    count_tree = _Fenwick(len(trace.tokens))
    by_previous: dict[int, list[int]] = {}
    for index in range(context_tokens, len(trace.tokens)):
        by_previous.setdefault(trace.previous[index], []).append(index)
    first_score_start = context_tokens
    for prior, indices in by_previous.items():
        if prior < first_score_start:
            for index in indices:
                weight_tree.add(index, trace.weights[index])
                count_tree.add(index, 1)

    for token_start in range(starts):
        score_start = token_start + context_tokens
        stop = token_start + window_tokens
        scored = count_tree.range_sum(score_start, stop)
        ones = weight_tree.range_sum(score_start, stop)
        total = scored * tournament.depth
        if total <= 0:
            raise ValueError("all available tournament contexts were masked")
        results.append(
            BoundaryWindowScore(
                base_start=trace.phase + token_start * KMER_SIZE,
                statistic=(2.0 * ones - total) / math.sqrt(total),
                mean_g_value=ones / total,
                g_ones=ones,
                g_total=total,
                scored_tokens=scored,
                repeated_contexts=scored_per_window - scored,
            )
        )
        # Moving A to A+1 makes positions whose previous occurrence was A
        # eligible. Positions left behind remain harmless outside range queries.
        for index in by_previous.get(score_start, ()):
            weight_tree.add(index, trace.weights[index])
            count_tree.add(index, 1)
    return tuple(results)


def score_synthid_unknown_boundary(
    sequence: str,
    *,
    base_length: int,
    tournament: KeyedTournament,
) -> tuple[BoundaryWindowScore, ...]:
    """Score every complete ``base_length`` substring at a one-base stride."""

    return score_synthid_unknown_boundaries(
        sequence,
        base_lengths=(base_length,),
        tournament=tournament,
    )[base_length]


def score_synthid_unknown_boundaries(
    sequence: str,
    *,
    base_lengths: tuple[int, ...],
    tournament: KeyedTournament,
) -> dict[int, tuple[BoundaryWindowScore, ...]]:
    """Score several window lengths while reusing every keyed context value."""

    dna = normalize_dna(sequence)
    lengths = tuple(sorted(set(int(length) for length in base_lengths)))
    if not lengths:
        raise ValueError("at least one base length is required")
    for base_length in lengths:
        if base_length <= 0 or base_length % KMER_SIZE:
            raise ValueError("base lengths must be positive multiples of six")
        if base_length > len(dna):
            raise ValueError("base lengths must not exceed the observed DNA length")
        if base_length // KMER_SIZE <= tournament.context_tokens:
            raise ValueError("base length is too short for the SynthID context")
    traces = tuple(
        _prepare_phase(dna, phase=phase, tournament=tournament) for phase in range(KMER_SIZE)
    )
    resolved: dict[int, tuple[BoundaryWindowScore, ...]] = {}
    for base_length in lengths:
        window_tokens = base_length // KMER_SIZE
        scores = tuple(
            score
            for trace in traces
            for score in _phase_scores(
                trace,
                window_tokens=window_tokens,
                tournament=tournament,
            )
            if score.base_start <= len(dna) - base_length
        )
        ordered = tuple(sorted(scores, key=lambda score: score.base_start))
        expected = len(dna) - base_length + 1
        if len(ordered) != expected:
            raise RuntimeError(f"scored {len(ordered)} boundary hypotheses, expected {expected}")
        resolved[base_length] = ordered
    return resolved


def deterministic_single_base_edit(
    sequence: str,
    *,
    condition: str,
    case_id: str,
    draw_id: int,
    label: str = "carbon-synthid-unknown-boundary-single-edit/v1",
) -> SingleBaseEdit:
    """Apply one public-replay substitution, insertion, or deletion."""

    dna = normalize_dna(sequence)
    if not dna:
        raise ValueError("cannot edit an empty sequence")
    if condition not in {"substitution_1nt", "insertion_1nt", "deletion_1nt"}:
        raise ValueError("unsupported single-base edit condition")
    if not case_id or draw_id < 0 or not label:
        raise ValueError("edit identity and label must be valid")
    digest = hashlib.sha256(
        f"{label}\x00{condition}\x00{case_id}\x00draw={draw_id}".encode()
    ).digest()
    position = int.from_bytes(digest[:8], "big") % len(dna)
    original = dna[position]
    if condition == "substitution_1nt":
        choices = tuple(base for base in BASES if base != original)
        replacement = choices[digest[8] % len(choices)]
        edited = dna[:position] + replacement + dna[position + 1 :]
        return SingleBaseEdit(condition, position, original, replacement, edited)
    if condition == "insertion_1nt":
        inserted = BASES[digest[8] % len(BASES)]
        edited = dna[:position] + inserted + dna[position:]
        return SingleBaseEdit(condition, position, None, inserted, edited)
    edited = dna[:position] + dna[position + 1 :]
    return SingleBaseEdit(condition, position, original, None, edited)
