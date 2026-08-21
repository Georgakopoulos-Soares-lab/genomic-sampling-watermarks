"""Prompt-cluster uncertainty summaries for sequential capacity reports."""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptClusterAnalysis:
    cluster_means: Mapping[str, float]
    overall_mean: float
    interval_lower: float
    interval_upper: float
    leave_one_out_means: Mapping[str, float]
    maximum_leave_one_out_change: float

    @property
    def interval_width(self) -> float:
        return self.interval_upper - self.interval_lower


def _percentile(sorted_values: Sequence[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("percentile values must not be empty")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("percentile probability must lie in [0, 1]")
    position = probability * (len(sorted_values) - 1)
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return float(sorted_values[lower_index])
    fraction = position - lower_index
    lower = float(sorted_values[lower_index])
    upper = float(sorted_values[upper_index])
    return lower + fraction * (upper - lower)


def analyze_prompt_clusters(
    values_by_prompt: Mapping[str, Sequence[float]],
    *,
    bootstrap_replicates: int,
    bootstrap_seed: int,
    confidence_level: float = 0.95,
) -> PromptClusterAnalysis:
    """Bootstrap prompt means without treating states or partitions as independent clusters."""

    if len(values_by_prompt) < 2:
        raise ValueError("at least two prompt clusters are required")
    if bootstrap_replicates <= 0:
        raise ValueError("bootstrap_replicates must be positive")
    if bootstrap_seed < 0:
        raise ValueError("bootstrap_seed must be non-negative")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must lie in (0, 1)")

    cluster_means: dict[str, float] = {}
    for prompt_id, values in values_by_prompt.items():
        resolved = tuple(float(value) for value in values)
        if not resolved:
            raise ValueError(f"prompt cluster {prompt_id!r} must not be empty")
        if any(not math.isfinite(value) for value in resolved):
            raise ValueError(f"prompt cluster {prompt_id!r} contains a non-finite value")
        cluster_means[prompt_id] = statistics.fmean(resolved)

    prompt_ids = tuple(cluster_means)
    means = tuple(cluster_means[prompt_id] for prompt_id in prompt_ids)
    overall_mean = statistics.fmean(means)
    rng = random.Random(bootstrap_seed)
    bootstrap_means = sorted(
        statistics.fmean(means[rng.randrange(len(means))] for _ in means)
        for _ in range(bootstrap_replicates)
    )
    tail = (1.0 - confidence_level) / 2.0
    lower = _percentile(bootstrap_means, tail)
    upper = _percentile(bootstrap_means, 1.0 - tail)
    leave_one_out = {
        prompt_id: statistics.fmean(
            mean for other_id, mean in cluster_means.items() if other_id != prompt_id
        )
        for prompt_id in prompt_ids
    }
    maximum_change = max(abs(mean - overall_mean) for mean in leave_one_out.values())
    return PromptClusterAnalysis(
        cluster_means=cluster_means,
        overall_mean=overall_mean,
        interval_lower=lower,
        interval_upper=upper,
        leave_one_out_means=leave_one_out,
        maximum_leave_one_out_change=maximum_change,
    )
