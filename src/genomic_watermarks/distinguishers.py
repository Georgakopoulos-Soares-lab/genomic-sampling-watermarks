"""Held-out unkeyed distinguishers for the observer in the threat model.

The threat model's third goal is that a one-output classifier *without* the key
should not reliably tell an exact-marginal watermarked sequence from an ordinary
one under matched conditions. These are deliberately simple, cheap, model-free
distinguishers: if a construction is distinguishable by a 3-mer centroid or a
compressor, it is distinguishable, and no elaborate classifier is needed to say so.

Failing to distinguish with these does **not** establish undetectability. It rules
out the crude attacks, which is the honest scope.

The task is a paired two-alternative forced choice: given one watermarked and one
ordinary sequence from the *same* prompt, say which is watermarked. Pairing
controls for prompt, and chance is exactly one half. Every distinguisher is fit on
training prompts and evaluated on a held-out prompt, so nothing is scored on data
it was fit to.
"""

from __future__ import annotations

import itertools
import math
import zlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from genomic_watermarks.dna import normalize_dna
from genomic_watermarks.sequence_proxies import PROXY_METRICS, kmer_distribution, proxy_metrics

FeatureFn = Callable[[str], tuple[float, ...]]


def proxy_features(sequence: str) -> tuple[float, ...]:
    """The nine declared sequence proxies, in a fixed order."""

    metrics = proxy_metrics(sequence)
    return tuple(metrics[name] for name in PROXY_METRICS)


def trimer_features(sequence: str) -> tuple[float, ...]:
    """The 64 overlapping 3-mer frequencies."""

    return kmer_distribution(sequence, 3)


def compression_features(sequence: str) -> tuple[float, ...]:
    """Compressed length per base, at maximum zlib effort."""

    normalized = normalize_dna(sequence)
    packed = zlib.compress(normalized.encode("ascii"), level=9)
    return (len(packed) / len(normalized),)


DISTINGUISHERS: dict[str, FeatureFn] = {
    "proxy_centroid": proxy_features,
    "trimer_centroid": trimer_features,
    "compression": compression_features,
}


@dataclass(frozen=True, slots=True)
class ForcedChoiceResult:
    """Held-out paired forced-choice accuracy for one distinguisher."""

    distinguisher: str
    decisions: int
    correct: int
    accuracy_by_prompt: Mapping[str, float]

    @property
    def accuracy(self) -> float:
        return self.correct / self.decisions if self.decisions else 0.0


def _standardize(
    vectors: Sequence[tuple[float, ...]],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Return per-feature mean and a scale that never divides by zero."""

    if not vectors:
        raise ValueError("at least one training vector is required")
    width = len(vectors[0])
    if any(len(vector) != width for vector in vectors):
        raise ValueError("training vectors must have equal width")
    means = tuple(
        math.fsum(vector[index] for vector in vectors) / len(vectors) for index in range(width)
    )
    scales = []
    for index in range(width):
        variance = math.fsum((vector[index] - means[index]) ** 2 for vector in vectors) / len(
            vectors
        )
        scales.append(math.sqrt(variance) or 1.0)
    return means, tuple(scales)


def _direction(
    watermarked: Sequence[tuple[float, ...]],
    ordinary: Sequence[tuple[float, ...]],
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    """Fit the standardizer and the watermarked-minus-ordinary centroid direction."""

    means, scales = _standardize([*watermarked, *ordinary])

    def centroid(rows: Sequence[tuple[float, ...]]) -> tuple[float, ...]:
        return tuple(
            math.fsum((row[index] - means[index]) / scales[index] for row in rows) / len(rows)
            for index in range(len(means))
        )

    watermarked_centroid = centroid(watermarked)
    ordinary_centroid = centroid(ordinary)
    direction = tuple(
        watermarked_centroid[index] - ordinary_centroid[index] for index in range(len(means))
    )
    return means, scales, direction


def _score(
    vector: tuple[float, ...],
    means: tuple[float, ...],
    scales: tuple[float, ...],
    direction: tuple[float, ...],
) -> float:
    return math.fsum(
        ((vector[index] - means[index]) / scales[index]) * direction[index]
        for index in range(len(means))
    )


def exact_cluster_sign_flip_p_value(
    correct_by_prompt: Mapping[str, int],
    draws_per_prompt: int,
) -> dict[str, float]:
    """Exact two-sided p-value for forced-choice accuracy, respecting prompt clusters.

    Under the null the two members of a pair are exchangeable, so relabelling a
    whole prompt maps ``k`` correct decisions to ``draws - k``. Enumerating all
    ``2**prompts`` relabellings gives an exact test that keeps decisions inside a
    prompt together.

    This exists because a bootstrap over per-prompt accuracies is *not* a valid
    test here: it treats each prompt's accuracy as known when it is estimated from
    only a handful of decisions, so it ignores within-prompt noise and can exclude
    chance when the pooled count is unremarkable.
    """

    if draws_per_prompt <= 0:
        raise ValueError("draws per prompt must be positive")
    prompts = tuple(sorted(correct_by_prompt))
    if not prompts:
        raise ValueError("at least one prompt is required")
    if len(prompts) > 20:
        raise ValueError("exact enumeration is limited to 20 prompts")
    counts = [int(correct_by_prompt[prompt]) for prompt in prompts]
    if any(not 0 <= count <= draws_per_prompt for count in counts):
        raise ValueError("each prompt's correct count must lie in [0, draws]")
    total = len(prompts) * draws_per_prompt
    observed = abs(sum(counts) - total / 2.0)
    exceedances = 0
    enumerated = 0
    for flips in itertools.product((False, True), repeat=len(counts)):
        enumerated += 1
        flipped = sum(
            draws_per_prompt - count if flip else count
            for count, flip in zip(counts, flips, strict=True)
        )
        if abs(flipped - total / 2.0) >= observed - 1e-12:
            exceedances += 1
    return {
        "correct": float(sum(counts)),
        "decisions": float(total),
        "accuracy": sum(counts) / total,
        "chance_accuracy": 0.5,
        "p_value": exceedances / enumerated,
        "prompts": float(len(prompts)),
        "draws_per_prompt": float(draws_per_prompt),
        "relabellings": float(enumerated),
        "exact": 1.0,
    }


def matched_draw_forced_choice(
    pairs_by_draw: Mapping[str, Mapping[str, tuple[str, str]]],
    distinguisher: str,
) -> ForcedChoiceResult:
    """Forced choice where each pair comes from the same generation draw.

    Pairing a watermarked sequence against a control from a *different* draw lets a
    distinguisher learn that control's realization instead of the watermark. Here
    every decision compares two sequences produced in the same run, differing only
    in whether the watermark was applied, and the distinguisher is still fit on
    other prompts only.
    """

    if distinguisher not in DISTINGUISHERS:
        raise ValueError(f"unknown distinguisher {distinguisher}")
    if not pairs_by_draw:
        raise ValueError("at least one draw is required")
    draw_labels = tuple(sorted(pairs_by_draw))
    case_ids = tuple(sorted(pairs_by_draw[draw_labels[0]]))
    if len(case_ids) < 3:
        raise ValueError("leave-one-prompt-out needs at least three prompts")
    for label in draw_labels:
        if tuple(sorted(pairs_by_draw[label])) != case_ids:
            raise ValueError(f"draw {label} does not cover the same prompts")
        for case_id in case_ids:
            pair = pairs_by_draw[label][case_id]
            if len(pair) != 2:
                raise ValueError(f"draw {label} prompt {case_id} must hold exactly two sequences")

    features = DISTINGUISHERS[distinguisher]
    vectors = {
        label: {
            case_id: (
                features(pairs_by_draw[label][case_id][0]),
                features(pairs_by_draw[label][case_id][1]),
            )
            for case_id in case_ids
        }
        for label in draw_labels
    }

    correct = 0
    decisions = 0
    per_prompt: dict[str, float] = {}
    for held_out in case_ids:
        training = [case_id for case_id in case_ids if case_id != held_out]
        train_watermarked = [
            vectors[label][case_id][0] for label in draw_labels for case_id in training
        ]
        train_ordinary = [
            vectors[label][case_id][1] for label in draw_labels for case_id in training
        ]
        means, scales, direction = _direction(train_watermarked, train_ordinary)
        prompt_correct = 0
        for label in draw_labels:
            watermarked_vector, ordinary_vector = vectors[label][held_out]
            if _score(watermarked_vector, means, scales, direction) > _score(
                ordinary_vector, means, scales, direction
            ):
                prompt_correct += 1
        correct += prompt_correct
        decisions += len(draw_labels)
        per_prompt[held_out] = prompt_correct / len(draw_labels)
    return ForcedChoiceResult(
        distinguisher=distinguisher,
        decisions=decisions,
        correct=correct,
        accuracy_by_prompt=per_prompt,
    )


def leave_one_prompt_out_forced_choice(
    watermarked_by_key: Mapping[str, Mapping[str, str]],
    ordinary: Mapping[str, str],
    distinguisher: str,
) -> ForcedChoiceResult:
    """Score a distinguisher by leave-one-prompt-out paired forced choice.

    For each held-out prompt, the distinguisher is fit on every *other* prompt's
    sequences and then asked, for each key, which member of that prompt's pair is
    watermarked. A tie counts as a miss rather than a coin flip, so the reported
    accuracy is never inflated by ties.
    """

    if distinguisher not in DISTINGUISHERS:
        raise ValueError(f"unknown distinguisher {distinguisher}")
    if not watermarked_by_key:
        raise ValueError("at least one key is required")
    case_ids = tuple(sorted(ordinary))
    if len(case_ids) < 3:
        raise ValueError("leave-one-prompt-out needs at least three prompts")
    for label, arm in watermarked_by_key.items():
        if set(arm) != set(case_ids):
            raise ValueError(f"key {label} does not cover the same prompts as the control")

    features = DISTINGUISHERS[distinguisher]
    watermarked_vectors = {
        label: {case_id: features(arm[case_id]) for case_id in case_ids}
        for label, arm in watermarked_by_key.items()
    }
    ordinary_vectors = {case_id: features(ordinary[case_id]) for case_id in case_ids}

    correct = 0
    decisions = 0
    per_prompt: dict[str, float] = {}
    for held_out in case_ids:
        training = [case_id for case_id in case_ids if case_id != held_out]
        train_watermarked = [
            watermarked_vectors[label][case_id]
            for label in watermarked_vectors
            for case_id in training
        ]
        train_ordinary = [ordinary_vectors[case_id] for case_id in training]
        means, scales, direction = _direction(train_watermarked, train_ordinary)
        prompt_correct = 0
        prompt_total = 0
        for label in watermarked_vectors:
            watermarked_score = _score(
                watermarked_vectors[label][held_out], means, scales, direction
            )
            ordinary_score = _score(ordinary_vectors[held_out], means, scales, direction)
            prompt_total += 1
            if watermarked_score > ordinary_score:
                prompt_correct += 1
        correct += prompt_correct
        decisions += prompt_total
        per_prompt[held_out] = prompt_correct / prompt_total
    return ForcedChoiceResult(
        distinguisher=distinguisher,
        decisions=decisions,
        correct=correct,
        accuracy_by_prompt=per_prompt,
    )
