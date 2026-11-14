"""Tests for the deterministic v5 review layouts (``genomic_watermarks.review_layouts``)."""

from __future__ import annotations

import random
import unittest
from collections import Counter

from genomic_watermarks.dna import reverse_complement
from genomic_watermarks.review_layouts import (
    CONTINUATION_BASES,
    CROP_LENGTHS,
    EMBEDDED_READ_BASES,
    PLACEMENT_STARTS,
    PROMPT_BASES,
    REFERENCE_CELL,
    REGION_LENGTHS,
    LayoutCell,
    LayoutRead,
    NaturalPool,
    build_read,
    cell_by_name,
    layout_cells,
)

SPAN_BASES = 3072


def random_dna(length: int, seed: int) -> str:
    rng = random.Random(seed)
    return "".join(rng.choice("ACGT") for _ in range(length))


def make_pool(spans: int = 16, seed: int = 100) -> NaturalPool:
    return NaturalPool({f"span{i:02d}": random_dna(SPAN_BASES, seed + i) for i in range(spans)})


POOL = make_pool()
PROMPT = random_dna(PROMPT_BASES, 1)
CONTINUATION = random_dna(CONTINUATION_BASES, 2)
OTHER_CONTINUATION = random_dna(CONTINUATION_BASES, 3)
CASE = "span03"


def read_for(
    cell_name: str,
    *,
    continuation: str = CONTINUATION,
    case_id: str = CASE,
    draw_id: int = 0,
    pool: NaturalPool = POOL,
) -> LayoutRead:
    return build_read(
        cell_by_name(cell_name),
        prompt=PROMPT,
        continuation=continuation,
        pool=pool,
        case_id=case_id,
        draw_id=draw_id,
    )


def region_text(read: LayoutRead) -> str:
    """The region as it appears in the model's own orientation."""

    piece = read.sequence[read.region_start : read.region_start + read.region_length]
    return piece if read.region_on_forward_strand else reverse_complement(piece)


def crop_start_of(read: LayoutRead) -> int:
    reference = PROMPT + CONTINUATION
    start = reference.find(read.sequence)
    assert start >= 0 and reference.find(read.sequence, start + 1) < 0
    return start


class CellTableTest(unittest.TestCase):
    def test_there_are_exactly_54_cells_with_unique_names(self) -> None:
        cells = layout_cells()
        self.assertEqual(len(cells), 54)
        self.assertEqual(len({cell.cell for cell in cells}), 54)
        self.assertEqual(cells, layout_cells())

    def test_counts_per_series_match_the_protocol(self) -> None:
        counts = Counter(cell.series for cell in layout_cells())
        self.assertEqual(counts, {"A": 7, "B": 7, "C": 24, "D": 8, "E": 5, "F": 3})

    def test_series_parameters_match_the_protocol_table(self) -> None:
        by_series: dict[str, list[LayoutCell]] = {}
        for cell in layout_cells():
            by_series.setdefault(cell.series, []).append(cell)
        self.assertEqual([c.region_bases for c in by_series["A"]], list(REGION_LENGTHS))
        self.assertEqual([c.region_bases for c in by_series["B"]], list(REGION_LENGTHS))
        self.assertEqual(REGION_LENGTHS, (384, 576, 768, 1152, 1536, 2304, 3072))
        self.assertTrue(all(c.uses_prompt for c in by_series["A"]))
        self.assertTrue(all(not c.uses_prompt for c in by_series["B"]))
        self.assertTrue(all(c.left_flank_bases == 1536 for c in by_series["B"]))
        self.assertEqual({c.region_bases for c in by_series["C"]}, {768, 3072})
        self.assertEqual(
            sorted({c.left_flank_bases - PROMPT_BASES for c in by_series["C"]}), list(range(6))
        )
        self.assertTrue(all(c.right_flank_bases == 384 for c in by_series["C"]))
        self.assertEqual(sum(c.reverse_complemented for c in by_series["C"]), 12)
        self.assertEqual({c.left_flank_bases for c in by_series["D"]}, {0, 384, 1536, 4608})
        self.assertTrue(all(c.left_flank_bases == c.right_flank_bases for c in by_series["D"]))
        self.assertEqual([c.left_flank_bases for c in by_series["E"]], list(PLACEMENT_STARTS))
        self.assertTrue(all(c.region_bases == 768 for c in by_series["E"]))
        self.assertEqual([c.crop_bases for c in by_series["F"]], [768, 1536, 2304])
        self.assertTrue(all(c.crop_bases == 0 for c in layout_cells() if c.series != "F"))

    def test_every_region_length_is_a_positive_multiple_of_six(self) -> None:
        for cell in layout_cells():
            self.assertGreater(cell.region_bases, 0, cell.cell)
            self.assertEqual(cell.region_bases % 6, 0, cell.cell)

    def test_reference_cell_is_series_a_at_full_length(self) -> None:
        cell = cell_by_name(REFERENCE_CELL)
        self.assertEqual((cell.series, cell.region_bases), ("A", 3072))
        self.assertTrue(cell.uses_prompt)

    def test_cell_by_name_rejects_unknown_names(self) -> None:
        with self.assertRaises(KeyError):
            cell_by_name("A_l9999")


class ReadLengthTest(unittest.TestCase):
    def test_read_lengths_per_series(self) -> None:
        for cell in layout_cells():
            read = read_for(cell.cell)
            if cell.series == "A":
                expected = PROMPT_BASES + cell.region_bases
            elif cell.series in {"B", "E"}:
                expected = EMBEDDED_READ_BASES
            elif cell.series == "C":
                expected = PROMPT_BASES + (cell.left_flank_bases - PROMPT_BASES)
                expected += cell.region_bases + 384
            elif cell.series == "D":
                expected = cell.region_bases + 2 * cell.left_flank_bases
            else:
                expected = cell.crop_bases
            self.assertEqual(len(read.sequence), expected, cell.cell)
            self.assertEqual(set(read.sequence) - set("ACGT"), set(), cell.cell)

    def test_cell_name_is_carried_on_the_read(self) -> None:
        self.assertEqual(read_for("B_l0768").cell, "B_l0768")


class RegionTest(unittest.TestCase):
    def test_suffix_reads_are_prompt_plus_continuation_prefix(self) -> None:
        for length in REGION_LENGTHS:
            read = read_for(f"A_l{length:04d}")
            self.assertEqual(read.sequence, PROMPT + CONTINUATION[:length])
            self.assertEqual((read.region_start, read.region_length), (PROMPT_BASES, length))
            self.assertTrue(read.region_on_forward_strand)

    def test_region_slice_equals_continuation_prefix_for_uncropped_cells(self) -> None:
        for cell in layout_cells():
            if cell.crop_bases:
                continue
            read = read_for(cell.cell)
            self.assertEqual(read.region_length, cell.region_bases, cell.cell)
            self.assertEqual(region_text(read), CONTINUATION[: cell.region_bases], cell.cell)

    def test_embedded_and_placement_region_offsets(self) -> None:
        for length in REGION_LENGTHS:
            read = read_for(f"B_l{length:04d}")
            self.assertEqual(read.region_start, 1536)
        for start in PLACEMENT_STARTS:
            read = read_for(f"E_s{start:04d}")
            self.assertEqual(read.region_start, start)
            self.assertEqual(read.region_length, 768)
            self.assertEqual(len(read.sequence) - start - 768, 6144 - start - 768)

    def test_symmetric_flank_cells_center_the_region(self) -> None:
        for length in (768, 3072):
            for flank in (0, 384, 1536, 4608):
                read = read_for(f"D_l{length:04d}_f{flank:04d}")
                self.assertEqual(read.region_start, flank)

    def test_reverse_complemented_region_is_the_reverse_complement_of_its_slice(self) -> None:
        for length in (768, 3072):
            for offset in range(6):
                read = read_for(f"C_l{length:04d}_o{offset}_rc")
                self.assertFalse(read.region_on_forward_strand)
                self.assertEqual(region_text(read), CONTINUATION[:length])
                # The right flank of the forward layout becomes the left flank.
                self.assertEqual(read.region_start, 384)

    def test_crops_are_substrings_of_the_reference_read_with_correct_region_offsets(self) -> None:
        for crop in CROP_LENGTHS:
            for index in range(25):
                case_id = f"span{index:02d}"
                read = read_for(f"F_c{crop:04d}", case_id=case_id, draw_id=index % 2)
                self.assertEqual(len(read.sequence), crop)
                start = crop_start_of(read)
                kept_start = max(PROMPT_BASES, start)
                kept_stop = min(PROMPT_BASES + CONTINUATION_BASES, start + crop)
                self.assertEqual(read.region_length, kept_stop - kept_start)
                self.assertEqual(read.region_start, kept_start - start)
                self.assertEqual(
                    read.sequence[read.region_start : read.region_start + read.region_length],
                    CONTINUATION[kept_start - PROMPT_BASES : kept_stop - PROMPT_BASES],
                )
                self.assertGreaterEqual(read.region_length, crop - PROMPT_BASES)

    def test_crop_start_stays_within_valid_range_and_covers_it(self) -> None:
        reference_length = PROMPT_BASES + CONTINUATION_BASES
        for crop in CROP_LENGTHS:
            valid = reference_length - crop + 1
            starts = [
                crop_start_of(read_for(f"F_c{crop:04d}", case_id=f"case{index:04d}", draw_id=draw))
                for index in range(400)
                for draw in (0, 1)
            ]
            self.assertTrue(all(0 <= start < valid for start in starts))
            self.assertLess(min(starts), valid * 0.02)
            self.assertGreater(max(starts), valid * 0.98)
            self.assertAlmostEqual(sum(starts) / len(starts), (valid - 1) / 2, delta=valid * 0.05)
            self.assertGreater(len(set(starts)), min(len(starts), valid) * 0.25)


class DeterminismAndFlankTest(unittest.TestCase):
    def test_reads_are_deterministic(self) -> None:
        for cell in layout_cells():
            self.assertEqual(read_for(cell.cell), read_for(cell.cell), cell.cell)
        self.assertEqual(read_for("B_l0768"), read_for("B_l0768", pool=make_pool()))

    def test_flanks_depend_on_case_draw_and_side(self) -> None:
        base = read_for("D_l0768_f0384")
        self.assertNotEqual(base.sequence, read_for("D_l0768_f0384", draw_id=1).sequence)
        self.assertNotEqual(base.sequence, read_for("D_l0768_f0384", case_id="span04").sequence)
        left, right = base.sequence[:384], base.sequence[-384:]
        self.assertNotEqual(left, right)

    def test_control_read_shares_flanks_with_the_marked_read(self) -> None:
        for cell in layout_cells():
            marked = read_for(cell.cell, continuation=CONTINUATION)
            control = read_for(cell.cell, continuation=OTHER_CONTINUATION)
            self.assertEqual(len(marked.sequence), len(control.sequence), cell.cell)
            self.assertEqual(
                (marked.region_start, marked.region_length),
                (control.region_start, control.region_length),
                cell.cell,
            )
            if cell.series == "F":
                continue  # a crop is a window of the whole reference read, flank-free
            end = marked.region_start + marked.region_length
            self.assertEqual(
                marked.sequence[: marked.region_start],
                control.sequence[: control.region_start],
                cell.cell,
            )
            self.assertEqual(marked.sequence[end:], control.sequence[end:], cell.cell)
            self.assertNotEqual(
                marked.sequence[marked.region_start : end],
                control.sequence[control.region_start : end],
                cell.cell,
            )

    def test_flank_never_contains_the_read_own_span(self) -> None:
        for index in range(len(POOL)):
            case_id = f"span{index:02d}"
            own = random_dna(SPAN_BASES, 100 + index)
            for cell_name in ("B_l0768", "D_l3072_f4608", "E_s2688", "C_l0768_o3_fw"):
                read = read_for(cell_name, case_id=case_id, draw_id=index % 2)
                cell = cell_by_name(cell_name)
                flank_text = (
                    read.sequence[: read.region_start]
                    + read.sequence[read.region_start + read.region_length :]
                )
                if not cell.reverse_complemented:
                    self.assertNotIn(own[:48], flank_text, (case_id, cell_name))
                    self.assertNotIn(own[1500:1548], flank_text, (case_id, cell_name))

    def test_flank_with_a_two_span_pool_comes_only_from_the_other_span(self) -> None:
        own, other = random_dna(SPAN_BASES, 7), random_dna(SPAN_BASES, 8)
        pool = NaturalPool({"own": own, "other": other})
        for draw in range(6):
            flank = pool.flank(
                cell="D_l0768_f4608", case_id="own", draw_id=draw, side="left", length=4608
            )
            self.assertEqual(len(flank), 4608)
            offset = (other * 3).find(flank[:64])
            self.assertGreaterEqual(offset, 0)
            self.assertEqual((other * 3)[offset : offset + 4608], flank)
            self.assertNotIn(own[:48], flank)

    def test_flank_longer_than_one_span_joins_several_spans(self) -> None:
        for draw in range(8):
            flank = POOL.flank(
                cell="D_l3072_f4608", case_id=CASE, draw_id=draw, side="right", length=4608
            )
            self.assertEqual(len(flank), 4608)
            self.assertGreater(4608, SPAN_BASES)
            spans = {f"span{i:02d}": random_dna(SPAN_BASES, 100 + i) for i in range(len(POOL))}
            # The flank is not a substring of any single span: it crosses a locus boundary.
            self.assertFalse(any(flank in span * 2 for span in spans.values()))

    def test_flank_shorter_than_one_span_is_a_substring_of_one_span(self) -> None:
        flank = POOL.flank(cell="B_l0768", case_id=CASE, draw_id=0, side="left", length=1536)
        spans = [random_dna(SPAN_BASES, 100 + i) for i in range(len(POOL))]
        self.assertTrue(any(flank in span for span in spans))

    def test_zero_length_flank_is_empty_and_needs_no_pool_diversity(self) -> None:
        single = NaturalPool({"only": random_dna(SPAN_BASES, 5)})
        self.assertEqual(
            single.flank(cell="x", case_id="only", draw_id=0, side="left", length=0), ""
        )

    def test_left_flank_of_384_plus_offset_puts_region_start_at_that_phase(self) -> None:
        for length in (768, 3072):
            for offset in range(6):
                read = read_for(f"C_l{length:04d}_o{offset}_fw")
                self.assertEqual(read.region_start, PROMPT_BASES + offset)
                self.assertEqual(read.region_start % 6, offset)
                self.assertEqual(len(read.sequence) - read.region_start - read.region_length, 384)

    def test_reverse_complement_cells_mirror_forward_cell_geometry(self) -> None:
        for length in (768, 3072):
            for offset in range(6):
                forward = read_for(f"C_l{length:04d}_o{offset}_fw")
                reverse = read_for(f"C_l{length:04d}_o{offset}_rc")
                self.assertEqual(len(forward.sequence), len(reverse.sequence))
                self.assertEqual(reverse.region_length, forward.region_length)
                self.assertEqual(
                    reverse.region_start,
                    len(forward.sequence) - forward.region_start - forward.region_length,
                )
                self.assertTrue(forward.region_on_forward_strand)
                self.assertFalse(reverse.region_on_forward_strand)

    def test_reverse_complement_cell_sequence_equals_reverse_complement_of_forward_cell(
        self,
    ) -> None:
        """Known defect: the flank hash includes the full cell name, which ends in ``_fw`` or
        ``_rc``, so the two strands of one layout get different flanks.  Protocol Section 5
        check 2 (identical smallest P-value and window count for a read and its reverse
        complement) therefore cannot hold for reads built directly with ``build_read``.
        """

        for length in (768, 3072):
            for offset in range(6):
                forward = read_for(f"C_l{length:04d}_o{offset}_fw")
                reverse = read_for(f"C_l{length:04d}_o{offset}_rc")
                self.assertEqual(reverse.sequence, reverse_complement(forward.sequence))


class InvalidInputTest(unittest.TestCase):
    def test_pool_rejects_empty_and_non_canonical_spans(self) -> None:
        with self.assertRaises(ValueError):
            NaturalPool({})
        with self.assertRaises(ValueError):
            NaturalPool({"a": ""})
        with self.assertRaises(ValueError):
            NaturalPool({"a": "ACGN"})
        with self.assertRaises(ValueError):
            NaturalPool({"a": "ACG-T"})

    def test_pool_normalizes_case_and_whitespace(self) -> None:
        pool = NaturalPool({"a": "acgt\nacgt", "b": "tttt"})
        self.assertEqual(len(pool), 2)
        self.assertEqual(
            pool.flank(cell="x", case_id="a", draw_id=0, side="left", length=4), "TTTT"
        )

    def test_flank_rejects_bad_side_negative_length_and_single_span_pool(self) -> None:
        with self.assertRaises(ValueError):
            POOL.flank(cell="x", case_id=CASE, draw_id=0, side="middle", length=6)
        with self.assertRaises(ValueError):
            POOL.flank(cell="x", case_id=CASE, draw_id=0, side="left", length=-1)
        single = NaturalPool({"only": random_dna(100, 1)})
        with self.assertRaises(ValueError):
            single.flank(cell="x", case_id="only", draw_id=0, side="left", length=6)

    def test_build_read_rejects_wrong_prompt_or_continuation_length(self) -> None:
        cell = cell_by_name("A_l0768")
        kwargs = {"pool": POOL, "case_id": CASE, "draw_id": 0}
        with self.assertRaises(ValueError):
            build_read(cell, prompt=PROMPT[:-6], continuation=CONTINUATION, **kwargs)
        with self.assertRaises(ValueError):
            build_read(cell, prompt=PROMPT, continuation=CONTINUATION[:-6], **kwargs)
        with self.assertRaises(ValueError):
            build_read(cell, prompt=PROMPT, continuation=CONTINUATION + "ACGTAC", **kwargs)

    def test_build_read_rejects_non_canonical_dna(self) -> None:
        cell = cell_by_name("A_l0768")
        with self.assertRaises(ValueError):
            build_read(
                cell,
                prompt="N" * PROMPT_BASES,
                continuation=CONTINUATION,
                pool=POOL,
                case_id=CASE,
                draw_id=0,
            )

    def test_build_read_rejects_invalid_region_lengths_and_crops(self) -> None:
        kwargs = {
            "prompt": PROMPT,
            "continuation": CONTINUATION,
            "pool": POOL,
            "case_id": CASE,
            "draw_id": 0,
        }
        for bad in (0, 7, 3078, -6):
            with self.assertRaises(ValueError, msg=str(bad)):
                build_read(LayoutCell("bad", "A", bad, uses_prompt=True), **kwargs)
        with self.assertRaises(ValueError):
            build_read(
                LayoutCell("bad_crop", "F", 768, uses_prompt=True, crop_bases=10_000), **kwargs
            )


if __name__ == "__main__":
    unittest.main()
