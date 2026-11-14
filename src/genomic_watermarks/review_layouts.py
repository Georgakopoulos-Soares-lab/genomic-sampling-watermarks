"""Deterministic read layouts for the v5 review studies.

Protocol: ``docs/research/synthid_v5_review_studies_protocol_2026_11_12.md``.
Every choice here comes from a public SHA-256 stream over read identity.  Nothing
in this module consults a detector, a key, or a score.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass

from genomic_watermarks.dna import KMER_SIZE, normalize_dna, reverse_complement

REVIEW_LABEL = "synthid-review-v5"
PROMPT_BASES = 384
CONTINUATION_BASES = 3072
EMBEDDED_READ_BASES = 6144
EMBEDDED_LEFT_FLANK_BASES = 1536
REGION_LENGTHS = (384, 576, 768, 1152, 1536, 2304, 3072)
PHASE_STRAND_REGION_LENGTHS = (768, 3072)
FLANK_LENGTHS = (0, 384, 1536, 4608)
PLACEMENT_REGION_BASES = 768
PLACEMENT_STARTS = (0, 1344, 2688, 4032, 5376)
CROP_LENGTHS = (768, 1536, 2304)
REFERENCE_CELL = "A_l3072"


@dataclass(frozen=True, slots=True)
class LayoutRead:
    """One read as supplied to a detector, with the region's true location.

    ``region_start`` and ``region_length`` are in the coordinates of ``sequence``
    as supplied (after any reverse complementation) and describe the bases that
    came from the model continuation.  ``region_on_forward_strand`` is false
    when the read was reverse-complemented.
    """

    cell: str
    sequence: str
    region_start: int
    region_length: int
    region_on_forward_strand: bool


def _digest(*parts: object) -> bytes:
    return hashlib.sha256("\x00".join(str(part) for part in parts).encode()).digest()


class NaturalPool:
    """Public source spans used as non-generated flanking DNA."""

    def __init__(self, spans: Mapping[str, str]) -> None:
        if not spans:
            raise ValueError("the natural pool must not be empty")
        self._ids = tuple(sorted(spans))
        self._spans = {span_id: normalize_dna(spans[span_id]) for span_id in self._ids}
        for span_id, sequence in self._spans.items():
            if not sequence or set(sequence) - set("ACGT"):
                raise ValueError(f"span {span_id} is empty or has a non-canonical base")

    def __len__(self) -> int:
        return len(self._ids)

    def flank(self, *, cell: str, case_id: str, draw_id: int, side: str, length: int) -> str:
        """Return ``length`` bases of natural DNA, never from the read's own span."""

        if length < 0 or side not in {"left", "right"}:
            raise ValueError("invalid flank request")
        if length == 0:
            return ""
        if len(self._ids) < 2:
            raise ValueError("flanks need a span other than the read's own")
        pieces: list[str] = []
        total = 0
        piece = 0
        while total < length:
            digest = _digest(
                REVIEW_LABEL, "flank", cell, case_id, f"draw={draw_id}", side, f"piece={piece}"
            )
            piece += 1
            span_id = self._ids[int.from_bytes(digest[:8], "big") % len(self._ids)]
            if span_id == case_id:
                continue
            span = self._spans[span_id]
            if not pieces:
                span = span[int.from_bytes(digest[8:16], "big") % len(span) :]
            pieces.append(span)
            total += len(span)
        return "".join(pieces)[:length]


@dataclass(frozen=True, slots=True)
class LayoutCell:
    """One cell of the layout study."""

    cell: str
    series: str
    region_bases: int
    left_flank_bases: int = 0
    right_flank_bases: int = 0
    uses_prompt: bool = False
    reverse_complemented: bool = False
    crop_bases: int = 0

    @property
    def flank_identity(self) -> str:
        """Name used in flank hashes: a forward cell and its reverse-complement twin share it."""

        return self.cell.removesuffix("_fw").removesuffix("_rc")


def layout_cells() -> tuple[LayoutCell, ...]:
    """The 54 protocol cells, in a fixed order."""

    cells: list[LayoutCell] = []
    for length in REGION_LENGTHS:
        cells.append(LayoutCell(f"A_l{length:04d}", "A", length, uses_prompt=True))
    for length in REGION_LENGTHS:
        right = EMBEDDED_READ_BASES - EMBEDDED_LEFT_FLANK_BASES - length
        cells.append(LayoutCell(f"B_l{length:04d}", "B", length, EMBEDDED_LEFT_FLANK_BASES, right))
    for length in PHASE_STRAND_REGION_LENGTHS:
        for offset in range(KMER_SIZE):
            for reverse in (False, True):
                strand = "rc" if reverse else "fw"
                cells.append(
                    LayoutCell(
                        f"C_l{length:04d}_o{offset}_{strand}",
                        "C",
                        length,
                        PROMPT_BASES + offset,
                        PROMPT_BASES,
                        reverse_complemented=reverse,
                    )
                )
    for length in PHASE_STRAND_REGION_LENGTHS:
        for flank in FLANK_LENGTHS:
            cells.append(LayoutCell(f"D_l{length:04d}_f{flank:04d}", "D", length, flank, flank))
    for start in PLACEMENT_STARTS:
        right = EMBEDDED_READ_BASES - start - PLACEMENT_REGION_BASES
        cells.append(LayoutCell(f"E_s{start:04d}", "E", PLACEMENT_REGION_BASES, start, right))
    for crop in CROP_LENGTHS:
        cells.append(
            LayoutCell(f"F_c{crop:04d}", "F", CONTINUATION_BASES, uses_prompt=True, crop_bases=crop)
        )
    return tuple(cells)


def cell_by_name(name: str) -> LayoutCell:
    for cell in layout_cells():
        if cell.cell == name:
            return cell
    raise KeyError(name)


def build_read(
    cell: LayoutCell,
    *,
    prompt: str,
    continuation: str,
    pool: NaturalPool,
    case_id: str,
    draw_id: int,
) -> LayoutRead:
    """Build one read.  The same call with an ordinary continuation gives the control."""

    prompt_dna = normalize_dna(prompt)
    region_source = normalize_dna(continuation)
    if len(prompt_dna) != PROMPT_BASES or len(region_source) != CONTINUATION_BASES:
        raise ValueError("prompt and continuation must have their protocol lengths")
    if cell.region_bases % KMER_SIZE or not 0 < cell.region_bases <= CONTINUATION_BASES:
        raise ValueError("region length must be a positive multiple of six")
    region = region_source[: cell.region_bases]

    if cell.uses_prompt:
        left, right = prompt_dna, ""
    else:
        left = pool.flank(
            cell=cell.flank_identity,
            case_id=case_id,
            draw_id=draw_id,
            side="left",
            length=cell.left_flank_bases,
        )
        right = pool.flank(
            cell=cell.flank_identity,
            case_id=case_id,
            draw_id=draw_id,
            side="right",
            length=cell.right_flank_bases,
        )
    sequence = left + region + right
    start, length = len(left), len(region)

    if cell.crop_bases:
        if not 0 < cell.crop_bases <= len(sequence):
            raise ValueError("crop does not fit the read")
        digest = _digest(REVIEW_LABEL, "crop", cell.cell, case_id, f"draw={draw_id}")
        crop_start = int.from_bytes(digest[:8], "big") % (len(sequence) - cell.crop_bases + 1)
        crop_stop = crop_start + cell.crop_bases
        kept_start = max(start, crop_start)
        kept_stop = min(start + length, crop_stop)
        sequence = sequence[crop_start:crop_stop]
        length = max(0, kept_stop - kept_start)
        start = kept_start - crop_start if length else 0

    forward = True
    if cell.reverse_complemented:
        sequence = reverse_complement(sequence)
        start = len(sequence) - start - length
        forward = False
    return LayoutRead(cell.cell, sequence, start, length, forward)
