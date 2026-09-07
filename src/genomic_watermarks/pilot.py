"""Public prompt records and compact summaries used by SynthID experiments."""

from __future__ import annotations

import hashlib
import json
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from genomic_watermarks.dna import BASES, KMER_SIZE, normalize_dna


@dataclass(frozen=True, slots=True)
class ContextCase:
    case_id: str
    sequence: str
    cohort_id: str = "synthetic_public_v1"
    organism: str | None = None
    accession: str | None = None
    start: int | None = None
    stop: int | None = None
    sequence_sha256: str | None = None

    def __post_init__(self) -> None:
        normalized = normalize_dna(self.sequence)
        if normalized != self.sequence:
            raise ValueError("pilot contexts must already be normalized")
        if not normalized or len(normalized) % KMER_SIZE:
            raise ValueError("pilot context length must be a positive multiple of six")
        observed_sha256 = hashlib.sha256(normalized.encode("ascii")).hexdigest()
        if self.sequence_sha256 is not None and self.sequence_sha256 != observed_sha256:
            raise ValueError("pilot context checksum does not match its sequence")
        if (self.start is None) != (self.stop is None):
            raise ValueError("pilot context coordinates must be supplied together")
        if self.start is not None and self.stop - self.start + 1 != len(normalized):
            raise ValueError("pilot context coordinates do not match its sequence length")


def cohort_content_digest(entries: Iterable[tuple[str, str]]) -> str:
    """Digest a cohort by prompt ID and sequence checksum, independent of file formatting."""

    digest = hashlib.sha256()
    count = 0
    for prompt_id, sequence_sha256 in entries:
        if not prompt_id or not sequence_sha256:
            raise ValueError("cohort digest requires a prompt ID and sequence checksum")
        digest.update(prompt_id.encode())
        digest.update(b"\x00")
        digest.update(sequence_sha256.encode())
        digest.update(b"\n")
        count += 1
    if not count:
        raise ValueError("cohort digest requires at least one prompt")
    return digest.hexdigest()


def cohort_case_digest(cases: Sequence[ContextCase]) -> str:
    """Return the cohort content digest for loaded prompt cases."""

    missing = [case.case_id for case in cases if case.sequence_sha256 is None]
    if missing:
        raise ValueError(f"cohort digest requires a checksum for {len(missing)} prompt(s)")
    return cohort_content_digest((case.case_id, str(case.sequence_sha256)) for case in cases)


def load_context_cases_jsonl(path: Path) -> tuple[ContextCase, ...]:
    """Load a checked public prompt JSONL file without retaining unrelated fields."""

    cases: list[ContextCase] = []
    seen_ids: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            case = ContextCase(
                case_id=str(row["prompt_id"]),
                sequence=str(row["sequence"]),
                cohort_id=str(row["cohort_id"]),
                organism=str(row["organism"]),
                accession=str(row["accession"]),
                start=int(row["start"]),
                stop=int(row["stop"]),
                sequence_sha256=str(row["sequence_sha256"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"invalid public prompt at line {line_number}") from error
        if case.case_id in seen_ids:
            raise ValueError(f"duplicate public prompt ID: {case.case_id}")
        seen_ids.add(case.case_id)
        cases.append(case)
    if not cases:
        raise ValueError("public prompt cohort must not be empty")
    if len({case.cohort_id for case in cases}) != 1:
        raise ValueError("public prompts must belong to one cohort")
    return tuple(cases)


def deterministic_public_dna(label: str, length: int) -> str:
    """Create reproducible synthetic DNA without reading a dataset or private sequence."""

    if length <= 0:
        raise ValueError("length must be positive")
    output: list[str] = []
    counter = 0
    while len(output) < length:
        digest = hashlib.sha256(f"{label}/{counter}".encode()).digest()
        for value in digest:
            for shift in (0, 2, 4, 6):
                output.append(BASES[(value >> shift) & 0b11])
                if len(output) == length:
                    return "".join(output)
        counter += 1
    raise AssertionError("unreachable")


def synthetic_context_cases() -> tuple[ContextCase, ...]:
    """Return a compact, composition-diverse set of public pilot contexts."""

    return (
        ContextCase("balanced_repeat", "ATCGGC" * 16),
        ContextCase("a_rich", "AAAAAT" * 16),
        ContextCase("t_rich", "TTTTTC" * 16),
        ContextCase("gc_repeat", "GCGCGC" * 16),
        ContextCase("at_repeat", "ATATAT" * 16),
        ContextCase("homopolymer_a", "AAAAAA" * 16),
        ContextCase("public_pseudorandom_96", deterministic_public_dna("pilot-96-v1", 96)),
        ContextCase("public_pseudorandom_384", deterministic_public_dna("pilot-384-v1", 384)),
    )


def select_spanning_cases(
    cases: Sequence[ContextCase],
    count: int,
) -> tuple[ContextCase, ...]:
    """Select a small parity subset spanning the fixture list's two ends."""

    if not 0 <= count <= len(cases):
        raise ValueError("count must lie between zero and the context count")
    if count <= 2:
        return tuple(cases[:count])
    return tuple(cases[: count - 2]) + tuple(cases[-2:])


def numeric_summary(values: Iterable[float]) -> dict[str, float]:
    """Return the compact summary used by the streamed pilot report."""

    resolved = tuple(float(value) for value in values)
    if not resolved:
        raise ValueError("summary values must not be empty")
    return {
        "minimum": min(resolved),
        "median": statistics.median(resolved),
        "mean": statistics.fmean(resolved),
        "maximum": max(resolved),
    }
