"""Sequence-level proxy metrics and an exact paired sign-flip test.

These are composition and complexity statistics computed from DNA alone. They are
proxies for "does the watermarked output look like the unwatermarked output" and
nothing more. Closeness on them is not biological equivalence, and no functional,
viability, or safety inference may be drawn from them.

The comparison is paired: for one prompt and one policy, the watermarked and
ordinary continuations start from the same context and have the same length, so
their difference is the quantity of interest. With a small number of prompts the
sign-flip permutation null can be enumerated exactly, which avoids relying on an
asymptotic approximation at n = 8.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Mapping, Sequence

from genomic_watermarks.dna import BASES, normalize_dna
from genomic_watermarks.metrics import (
    jensen_shannon_divergence_bits,
    normalized_probabilities,
    shannon_entropy_bits,
)

PROXY_METRICS = (
    "gc_fraction",
    "base_entropy_bits",
    "dinucleotide_entropy_bits",
    "trinucleotide_entropy_bits",
    "distinct_hexamer_fraction",
    "longest_homopolymer_run",
    "mean_homopolymer_run",
    "purine_fraction",
    "cpg_fraction",
)


def kmer_counts(sequence: str, k: int) -> dict[str, int]:
    """Count overlapping k-mers over the canonical alphabet."""

    if k <= 0:
        raise ValueError("k must be positive")
    normalized = normalize_dna(sequence)
    if len(normalized) < k:
        raise ValueError("sequence is shorter than k")
    counts = {"".join(item): 0 for item in itertools.product(BASES, repeat=k)}
    for index in range(len(normalized) - k + 1):
        counts[normalized[index : index + k]] += 1
    return counts


def kmer_distribution(sequence: str, k: int) -> tuple[float, ...]:
    """Return the overlapping k-mer distribution in fixed canonical order."""

    counts = kmer_counts(sequence, k)
    return normalized_probabilities(tuple(counts[key] for key in sorted(counts)))


def homopolymer_runs(sequence: str) -> tuple[int, ...]:
    """Return the lengths of maximal single-base runs."""

    normalized = normalize_dna(sequence)
    if not normalized:
        raise ValueError("sequence must not be empty")
    runs: list[int] = []
    current = 1
    for previous, base in zip(normalized, normalized[1:], strict=False):
        if base == previous:
            current += 1
        else:
            runs.append(current)
            current = 1
    runs.append(current)
    return tuple(runs)


def proxy_metrics(sequence: str) -> dict[str, float]:
    """Compute every declared sequence proxy for one DNA string."""

    normalized = normalize_dna(sequence)
    if len(normalized) < 6:
        raise ValueError("proxy metrics need at least six bases")
    length = len(normalized)
    gc = sum(base in "GC" for base in normalized) / length
    purine = sum(base in "AG" for base in normalized) / length
    runs = homopolymer_runs(normalized)
    hexamers = {normalized[index : index + 6] for index in range(length - 5)}
    dinucleotides = kmer_counts(normalized, 2)
    return {
        "gc_fraction": gc,
        "base_entropy_bits": shannon_entropy_bits(kmer_distribution(normalized, 1)),
        "dinucleotide_entropy_bits": shannon_entropy_bits(kmer_distribution(normalized, 2)),
        "trinucleotide_entropy_bits": shannon_entropy_bits(kmer_distribution(normalized, 3)),
        "distinct_hexamer_fraction": len(hexamers) / (length - 5),
        "longest_homopolymer_run": float(max(runs)),
        "mean_homopolymer_run": sum(runs) / len(runs),
        "purine_fraction": purine,
        "cpg_fraction": dinucleotides["CG"] / (length - 1),
    }


def kmer_divergence_bits(left: str, right: str, k: int) -> float:
    """Jensen-Shannon divergence in bits between two overlapping k-mer distributions."""

    return jensen_shannon_divergence_bits(
        kmer_distribution(left, k),
        kmer_distribution(right, k),
    )


def exact_sign_flip_test(differences: Sequence[float]) -> dict[str, float]:
    """Two-sided exact sign-flip permutation test on paired differences.

    Enumerates all ``2**n`` sign assignments, so it is exact rather than
    asymptotic. The statistic is the absolute mean difference. Use only for small
    ``n``; this raises above 20 pairs rather than silently sampling.
    """

    values = tuple(float(value) for value in differences)
    if len(values) < 2:
        raise ValueError("at least two pairs are required")
    if len(values) > 20:
        raise ValueError("exact enumeration is limited to 20 pairs")
    if any(not math.isfinite(value) for value in values):
        raise ValueError("paired differences must be finite")
    observed = abs(math.fsum(values) / len(values))
    exceedances = 0
    total = 0
    for signs in itertools.product((1.0, -1.0), repeat=len(values)):
        total += 1
        candidate = abs(
            math.fsum(sign * value for sign, value in zip(signs, values, strict=True)) / len(values)
        )
        if candidate >= observed - 1e-12:
            exceedances += 1
    return {
        "mean_difference": math.fsum(values) / len(values),
        "absolute_mean_difference": observed,
        "p_value": exceedances / total,
        "pairs": float(len(values)),
        "permutations": float(total),
        "exact": 1.0,
    }


def paired_proxy_comparison(
    watermarked: Mapping[str, str],
    ordinary: Mapping[str, str],
) -> dict[str, dict[str, float]]:
    """Compare matched arms per prompt and test each proxy with the exact paired test."""

    if set(watermarked) != set(ordinary):
        raise ValueError("both arms must cover the same prompts")
    if len(watermarked) < 2:
        raise ValueError("at least two prompts are required")
    case_ids = tuple(sorted(watermarked))
    for case_id in case_ids:
        if len(normalize_dna(watermarked[case_id])) != len(normalize_dna(ordinary[case_id])):
            raise ValueError(f"arms must have equal length for {case_id}")
    watermarked_metrics = {case_id: proxy_metrics(watermarked[case_id]) for case_id in case_ids}
    ordinary_metrics = {case_id: proxy_metrics(ordinary[case_id]) for case_id in case_ids}
    comparison: dict[str, dict[str, float]] = {}
    for metric in PROXY_METRICS:
        differences = [
            watermarked_metrics[case_id][metric] - ordinary_metrics[case_id][metric]
            for case_id in case_ids
        ]
        test = exact_sign_flip_test(differences)
        comparison[metric] = {
            **test,
            "watermarked_mean": math.fsum(
                watermarked_metrics[case_id][metric] for case_id in case_ids
            )
            / len(case_ids),
            "ordinary_mean": math.fsum(ordinary_metrics[case_id][metric] for case_id in case_ids)
            / len(case_ids),
        }
    return comparison
