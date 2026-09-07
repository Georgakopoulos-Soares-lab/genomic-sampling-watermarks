"""Shared invariants and statistics for the SynthID large-validation experiments.

This module is deliberately model-independent.  It defines sequence identity,
the frozen prompt split, fixture-key labels, clustered paired inference, and
small helpers used by the experiment runners.  It does not change the sampler,
the model policy, or the detector.
"""

from __future__ import annotations

import hashlib
import math
import random
import statistics
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

LARGE_VALIDATION_ID = "carbon_synthid_validation_v1"
LARGE_COHORT_ID = "ncbi_refseq_eukaryote_windows_large_v1"
CALIBRATION_SPLIT_LABEL = f"{LARGE_VALIDATION_ID}/prompt-split/v1"
PUBLIC_GENERATION_FIXTURE = b"genomic-sampling-watermarks/public-generation-fixture/v1"
PUBLIC_GENERATION_FIXTURE_LABEL = "genomic-sampling-watermarks/public-generation-fixture/v1/index"
PUBLIC_NULL_KEY_LABEL = f"genomic-sampling-watermarks/{LARGE_VALIDATION_ID}/null-key/v1"


def fixture_key(index: int) -> bytes:
    """Return the existing published generation fixture key at ``index``."""

    if index < 0:
        raise ValueError("fixture key index must be non-negative")
    if index == 0:
        return PUBLIC_GENERATION_FIXTURE
    return hashlib.sha256(f"{PUBLIC_GENERATION_FIXTURE_LABEL}/{index:04d}".encode()).digest()


def null_key(index: int) -> bytes:
    """Return a published, experiment-specific independent null fixture key."""

    if index < 0:
        raise ValueError("null key index must be non-negative")
    return hashlib.sha256(f"{PUBLIC_NULL_KEY_LABEL}/{index:04d}".encode()).digest()


def sequence_identity(record: Mapping[str, object]) -> tuple[str, int, str]:
    """Return the required unique identity ``(case_id, draw_id, scheme)``."""

    return (str(record["case_id"]), int(record["draw_id"]), str(record["scheme"]))


def deterministic_prompt_split(
    case_ids: Sequence[str],
    *,
    calibration_prompts: int,
    label: str = CALIBRATION_SPLIT_LABEL,
) -> dict[str, str]:
    """Assign exactly ``calibration_prompts`` cases by a frozen hash ranking.

    Hash ranking, instead of a threshold on the first byte, preserves the
    requested exact 64/192 split while remaining a deterministic function only
    of the public case ID and the preregistered label.
    """

    resolved = tuple(str(case_id) for case_id in case_ids)
    if not resolved or len(set(resolved)) != len(resolved):
        raise ValueError("case IDs must be non-empty and unique")
    if not 0 < calibration_prompts < len(resolved):
        raise ValueError("calibration prompt count must lie inside the cohort size")
    if not label:
        raise ValueError("split label must not be empty")
    ranked = sorted(
        resolved,
        key=lambda case_id: (
            hashlib.sha256(f"{label}\x00{case_id}".encode()).digest(),
            case_id,
        ),
    )
    calibration = set(ranked[:calibration_prompts])
    return {
        case_id: "calibration" if case_id in calibration else "evaluation" for case_id in resolved
    }


def benjamini_hochberg(p_values: Mapping[str, float]) -> dict[str, float]:
    """Return Benjamini-Hochberg adjusted p-values keyed like the input."""

    if not p_values:
        raise ValueError("at least one p-value is required")
    resolved = {str(name): float(value) for name, value in p_values.items()}
    if any(not 0.0 <= value <= 1.0 for value in resolved.values()):
        raise ValueError("p-values must lie in [0, 1]")
    ranked = sorted(resolved.items(), key=lambda item: (item[1], item[0]))
    adjusted: dict[str, float] = {}
    running = 1.0
    count = len(ranked)
    for rank, (name, value) in reversed(tuple(enumerate(ranked, start=1))):
        running = min(running, value * count / rank)
        adjusted[name] = min(1.0, running)
    return adjusted


def bonferroni_adjusted(p_values: Mapping[str, float]) -> dict[str, float]:
    """Return Bonferroni-adjusted p-values keyed like the input."""

    if not p_values:
        raise ValueError("at least one p-value is required")
    count = len(p_values)
    adjusted: dict[str, float] = {}
    for name, raw in p_values.items():
        value = float(raw)
        if not 0.0 <= value <= 1.0:
            raise ValueError("p-values must lie in [0, 1]")
        adjusted[str(name)] = min(1.0, count * value)
    return adjusted


def poisson_binomial_two_sided_p_value(
    success_probabilities: Sequence[float], observed_successes: int
) -> float:
    """Return an equal-tailed exact p-value for non-identical Bernoulli trials.

    Dynamic programming evaluates the full Poisson-binomial mass function.  This
    is appropriate for rare-event fit checks where a nonparametric percentile
    bootstrap cannot generate more positive clusters than were observed and can
    consequently have a spuriously narrow upper endpoint.
    """

    probabilities = tuple(float(value) for value in success_probabilities)
    if not probabilities:
        raise ValueError("at least one success probability is required")
    if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in probabilities):
        raise ValueError("success probabilities must be finite and lie in [0, 1]")
    if not 0 <= observed_successes <= len(probabilities):
        raise ValueError("observed successes must lie between zero and the trial count")

    probability_mass = [1.0]
    for probability in probabilities:
        updated = [0.0] * (len(probability_mass) + 1)
        for successes, mass in enumerate(probability_mass):
            updated[successes] += mass * (1.0 - probability)
            updated[successes + 1] += mass * probability
        probability_mass = updated
    lower_tail = math.fsum(probability_mass[: observed_successes + 1])
    upper_tail = math.fsum(probability_mass[observed_successes:])
    return min(1.0, 2.0 * min(lower_tail, upper_tail))


def _cluster_means(values_by_prompt: Mapping[str, Sequence[float]]) -> tuple[float, ...]:
    if len(values_by_prompt) < 2:
        raise ValueError("at least two prompt clusters are required")
    means: list[float] = []
    for case_id, values in values_by_prompt.items():
        resolved = tuple(float(value) for value in values)
        if not resolved:
            raise ValueError(f"prompt cluster {case_id!r} must not be empty")
        if any(not math.isfinite(value) for value in resolved):
            raise ValueError(f"prompt cluster {case_id!r} contains a non-finite value")
        means.append(statistics.fmean(resolved))
    return tuple(means)


def _percentile(sorted_values: Sequence[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("percentile input must not be empty")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must lie in [0, 1]")
    position = probability * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    fraction = position - lower
    return float(sorted_values[lower]) + fraction * (
        float(sorted_values[upper]) - float(sorted_values[lower])
    )


def cluster_sign_flip_test(
    values_by_prompt: Mapping[str, Sequence[float]],
    *,
    replicates: int,
    seed: int,
) -> float:
    """Two-sided paired sign-flip test with one shared sign per prompt.

    Four draws from one prompt retain their dependence: the permutation flips
    the prompt's mean difference as one unit rather than treating all pairs as
    independent observations.
    """

    means = _cluster_means(values_by_prompt)
    if replicates <= 0:
        raise ValueError("replicates must be positive")
    if seed < 0:
        raise ValueError("seed must be non-negative")
    observed = abs(statistics.fmean(means))
    rng = random.Random(seed)
    exceedances = 0
    for _ in range(replicates):
        candidate = abs(
            math.fsum(value if rng.getrandbits(1) else -value for value in means) / len(means)
        )
        if candidate >= observed - 1e-15:
            exceedances += 1
    return (1 + exceedances) / (1 + replicates)


def cluster_bootstrap_interval(
    values_by_prompt: Mapping[str, Sequence[float]],
    *,
    replicates: int,
    seed: int,
    statistic: Callable[[Sequence[float]], float] = statistics.fmean,
    confidence_level: float = 0.95,
) -> tuple[float, float]:
    """Percentile interval that resamples prompts and retains within-prompt rows."""

    if replicates <= 0:
        raise ValueError("replicates must be positive")
    if seed < 0:
        raise ValueError("seed must be non-negative")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence level must lie in (0, 1)")
    clusters: list[tuple[float, ...]] = []
    for case_id, values in values_by_prompt.items():
        resolved = tuple(float(value) for value in values)
        if not resolved or any(not math.isfinite(value) for value in resolved):
            raise ValueError(f"invalid values for prompt cluster {case_id!r}")
        clusters.append(resolved)
    if len(clusters) < 2:
        raise ValueError("at least two prompt clusters are required")
    rng = random.Random(seed)
    sampled: list[float] = []
    for _ in range(replicates):
        rows: list[float] = []
        for _cluster in clusters:
            rows.extend(clusters[rng.randrange(len(clusters))])
        sampled.append(float(statistic(rows)))
    sampled.sort()
    tail = (1.0 - confidence_level) / 2.0
    return _percentile(sampled, tail), _percentile(sampled, 1.0 - tail)


@dataclass(frozen=True, slots=True)
class PairedClusterSummary:
    pairs: int
    prompts: int
    mean_difference: float
    median_difference: float
    interval_lower: float
    interval_upper: float
    p_value: float
    standardized_effect: float


def paired_cluster_summary(
    values_by_prompt: Mapping[str, Sequence[float]],
    *,
    bootstrap_replicates: int,
    permutation_replicates: int,
    seed: int,
) -> PairedClusterSummary:
    """Summarize paired differences using prompt clusters as the sampling unit."""

    means = _cluster_means(values_by_prompt)
    rows = tuple(float(value) for values in values_by_prompt.values() for value in values)
    lower, upper = cluster_bootstrap_interval(
        values_by_prompt,
        replicates=bootstrap_replicates,
        seed=seed,
    )
    spread = statistics.stdev(means)
    mean = statistics.fmean(means)
    standardized = (
        mean / spread if spread > 0.0 else (0.0 if mean == 0.0 else math.copysign(math.inf, mean))
    )
    return PairedClusterSummary(
        pairs=len(rows),
        prompts=len(means),
        mean_difference=mean,
        median_difference=statistics.median(rows),
        interval_lower=lower,
        interval_upper=upper,
        p_value=cluster_sign_flip_test(
            values_by_prompt,
            replicates=permutation_replicates,
            seed=seed,
        ),
        standardized_effect=standardized,
    )


def exact_mcnemar_p_value(
    watermarked: Sequence[bool], ordinary: Sequence[bool]
) -> dict[str, int | float]:
    """Return the conventional exact two-sided McNemar result for matched pairs."""

    left = tuple(bool(value) for value in watermarked)
    right = tuple(bool(value) for value in ordinary)
    if not left or len(left) != len(right):
        raise ValueError("matched decision vectors must have the same non-zero length")
    wm_only = sum(a and not b for a, b in zip(left, right, strict=True))
    ordinary_only = sum(b and not a for a, b in zip(left, right, strict=True))
    discordant = wm_only + ordinary_only
    if discordant == 0:
        p_value = 1.0
    else:
        tail = sum(math.comb(discordant, k) for k in range(min(wm_only, ordinary_only) + 1))
        p_value = min(1.0, 2.0 * tail / (2**discordant))
    return {
        "watermarked_only": wm_only,
        "ordinary_only": ordinary_only,
        "discordant_pairs": discordant,
        "p_value": p_value,
    }


def sha256_file(path: str) -> str:
    """Return the SHA-256 digest of a file without imposing a Path dependency."""

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
