"""Order-sensitive sequence proxies: reading frames and an independent-model score.

The nine metrics in `sequence_proxies` are composition and complexity statistics.
They are blind to a rearrangement of whole 6-mers by construction, because such a
rearrangement preserves the 6-mer multiset exactly. That blindness is a real
limitation: the E12 removal attack is a 6-mer permutation, so those proxies price it
at almost nothing while it plainly destroys the sequence's long-range structure.

The two measures here are the instruments `docs/baseline_definition.md` declared for
exactly this purpose, and both are order-sensitive.

Open reading frames
    Standard start and stop codons read in all six frames. An ORF spans a junction,
    so shuffling 6-mers destroys long ORFs even though it moves no base composition.
    These are structural sequence statistics and carry no claim about translation,
    expression, function, viability, or safety.

Independent-model score
    Mean log-probability of the sequence under an order-`k` Markov model fitted on
    held-out public DNA. "Independent" means fitted without the generator, the key,
    or the sequence being scored --- it is not an independent *biological* model, and
    a low score means "unlike the reference cohort's local statistics" and nothing
    more. Because the model conditions on the preceding `k` bases, it is sensitive to
    the junctions a rearrangement creates while a composition statistic is not.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence

from genomic_watermarks.dna import BASES, normalize_dna, reverse_complement

STRUCTURE_METRICS = (
    "longest_orf_bases",
    "orf_count",
    "orf_coding_fraction",
    "independent_model_mean_log2_probability",
)

START_CODON = "ATG"
STOP_CODONS = ("TAA", "TAG", "TGA")
# An ORF shorter than this is common by chance in random DNA and carries no signal.
MINIMUM_ORF_CODONS = 25


def _codons(sequence: str, frame: int) -> list[str]:
    usable = (len(sequence) - frame) // 3 * 3
    return [sequence[i : i + 3] for i in range(frame, frame + usable, 3)]


def open_reading_frames(
    sequence: str,
    *,
    minimum_codons: int = MINIMUM_ORF_CODONS,
    both_strands: bool = True,
) -> tuple[tuple[int, int], ...]:
    """Return (start base, length in bases) for every ORF found, longest first.

    An ORF is a start codon followed by an in-frame stop codon with no intervening
    stop, at least ``minimum_codons`` long including both. All three frames are read
    on the forward strand and, unless disabled, all three on the reverse complement.
    Coordinates for reverse-strand frames are reported on the reverse-complemented
    sequence, so they locate a span rather than a strand-resolved position.
    """

    if minimum_codons < 2:
        raise ValueError("an ORF must span at least a start and a stop codon")
    normalized = normalize_dna(sequence)
    strands = [normalized]
    if both_strands:
        strands.append(reverse_complement(normalized))
    found: list[tuple[int, int]] = []
    for strand in strands:
        for frame in range(3):
            codons = _codons(strand, frame)
            open_at: int | None = None
            for index, codon in enumerate(codons):
                if open_at is None:
                    if codon == START_CODON:
                        open_at = index
                    continue
                if codon in STOP_CODONS:
                    span = index - open_at + 1
                    if span >= minimum_codons:
                        found.append((frame + open_at * 3, span * 3))
                    open_at = None
    found.sort(key=lambda item: (-item[1], item[0]))
    return tuple(found)


def orf_summary(sequence: str, *, minimum_codons: int = MINIMUM_ORF_CODONS) -> dict[str, float]:
    """Longest ORF, ORF count, and the fraction of bases inside some ORF."""

    normalized = normalize_dna(sequence)
    if not normalized:
        raise ValueError("sequence must not be empty")
    orfs = open_reading_frames(normalized, minimum_codons=minimum_codons)
    covered = 0
    if orfs:
        # Union of spans on the forward coordinate system, so overlapping frames are
        # not double counted.
        spans = sorted((start, start + length) for start, length in orfs)
        current_start, current_end = spans[0]
        for start, end in spans[1:]:
            if start > current_end:
                covered += current_end - current_start
                current_start, current_end = start, end
            else:
                current_end = max(current_end, end)
        covered += current_end - current_start
    return {
        "longest_orf_bases": float(orfs[0][1]) if orfs else 0.0,
        "orf_count": float(len(orfs)),
        "orf_coding_fraction": min(1.0, covered / len(normalized)),
    }


class MarkovReference:
    """An order-`k` Markov model over DNA, fitted on reference sequences.

    Laplace smoothing keeps every context scorable, so an unseen junction costs
    log-probability rather than producing an infinity. The model never sees the
    generator, the key, or the sequence it will score.
    """

    __slots__ = ("_counts", "_order", "_totals", "_vocabulary")

    def __init__(self, order: int = 3) -> None:
        if not 1 <= order <= 6:
            raise ValueError("order must lie in [1, 6]")
        self._order = order
        self._counts: dict[str, dict[str, int]] = {}
        self._totals: dict[str, int] = {}
        self._vocabulary = tuple(BASES)

    @property
    def order(self) -> int:
        return self._order

    @property
    def contexts(self) -> int:
        return len(self._counts)

    def fit(self, sequences: Iterable[str]) -> MarkovReference:
        fitted = 0
        for sequence in sequences:
            normalized = normalize_dna(sequence)
            if len(normalized) <= self._order:
                continue
            fitted += 1
            for index in range(self._order, len(normalized)):
                context = normalized[index - self._order : index]
                base = normalized[index]
                if base not in self._vocabulary:
                    continue
                row = self._counts.setdefault(context, {})
                row[base] = row.get(base, 0) + 1
                self._totals[context] = self._totals.get(context, 0) + 1
        if not fitted:
            raise ValueError("no reference sequence was long enough to fit the model")
        return self

    def mean_log2_probability(self, sequence: str) -> float:
        """Mean base-2 log probability per scored base, with Laplace smoothing."""

        if not self._counts:
            raise ValueError("the reference model has not been fitted")
        normalized = normalize_dna(sequence)
        if len(normalized) <= self._order:
            raise ValueError("sequence is shorter than the model order")
        size = len(self._vocabulary)
        total = 0.0
        scored = 0
        for index in range(self._order, len(normalized)):
            context = normalized[index - self._order : index]
            base = normalized[index]
            if base not in self._vocabulary:
                continue
            row = self._counts.get(context, {})
            numerator = row.get(base, 0) + 1
            denominator = self._totals.get(context, 0) + size
            total += math.log2(numerator / denominator)
            scored += 1
        if not scored:
            raise ValueError("no base could be scored")
        return total / scored


def structure_metrics(
    sequence: str,
    reference: MarkovReference,
    *,
    minimum_codons: int = MINIMUM_ORF_CODONS,
) -> dict[str, float]:
    """Every order-sensitive proxy for one sequence."""

    summary = orf_summary(sequence, minimum_codons=minimum_codons)
    summary["independent_model_mean_log2_probability"] = reference.mean_log2_probability(sequence)
    missing = set(STRUCTURE_METRICS) - set(summary)
    if missing:
        raise ValueError(f"structure metrics are incomplete: {', '.join(sorted(missing))}")
    return summary


def relative_shift(
    attacked: Mapping[str, float],
    reference_metrics: Mapping[str, float],
) -> dict[str, float]:
    """Relative change per metric, matching how the composition proxies are compared."""

    shifts: dict[str, float] = {}
    for metric in STRUCTURE_METRICS:
        if metric not in attacked or metric not in reference_metrics:
            raise ValueError(f"metric {metric} is missing from a comparison")
        base = abs(float(reference_metrics[metric])) or 1.0
        shifts[metric] = abs(float(attacked[metric]) - float(reference_metrics[metric])) / base
    return shifts


def fit_reference(sequences: Sequence[str], *, order: int = 3) -> MarkovReference:
    """Fit the independent reference model on held-out public DNA."""

    return MarkovReference(order=order).fit(sequences)
