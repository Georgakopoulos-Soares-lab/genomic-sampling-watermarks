from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from genomic_watermarks.pilot import (
    ContextCase,
    capacity_points,
    capacity_points_for_partitions,
    cohort_case_digest,
    cohort_content_digest,
    deterministic_public_dna,
    load_context_cases_jsonl,
    numeric_summary,
    select_spanning_cases,
    synthetic_context_cases,
)


class PilotTest(unittest.TestCase):
    def test_public_dna_is_deterministic_and_canonical(self) -> None:
        first = deterministic_public_dna("fixture", 18)
        self.assertEqual(first, deterministic_public_dna("fixture", 18))
        self.assertEqual(len(first), 18)
        self.assertLessEqual(set(first), set("ATCG"))

    def test_context_cases_are_unique_and_phase_aligned(self) -> None:
        cases = synthetic_context_cases()
        self.assertEqual(len(cases), 8)
        self.assertEqual(len({case.case_id for case in cases}), len(cases))
        self.assertTrue(all(len(case.sequence) % 6 == 0 for case in cases))

    def test_capacity_points_cover_requested_partitions(self) -> None:
        points = capacity_points(
            ("AAAAAA", "TTTTTT"),
            (0.75, 0.25),
            fixture_material=b"public-fixture",
            domains=("a", "b", "c"),
        )
        self.assertEqual(len(points), 3)
        self.assertTrue(all(0.0 <= point.partition_mass <= 1.0 for point in points))
        self.assertTrue(
            all(0.0 <= point.information_bits_per_base <= 1.0 / 6.0 for point in points)
        )

    def test_prebuilt_partitions_match_domain_built_points(self) -> None:
        tokens = ("AAAAAA", "TTTTTT")
        probabilities = (0.75, 0.25)
        direct = capacity_points(
            tokens,
            probabilities,
            fixture_material=b"public-fixture",
            domains=("a", "b"),
        )
        from genomic_watermarks.sampling.partition import keyed_balanced_partition

        partitions = tuple(
            keyed_balanced_partition(tokens, b"public-fixture", domain=domain)
            for domain in ("a", "b")
        )
        self.assertEqual(
            capacity_points_for_partitions(tokens, probabilities, partitions),
            direct,
        )

    def test_numeric_summary(self) -> None:
        self.assertEqual(
            numeric_summary((1.0, 2.0, 9.0)),
            {"minimum": 1.0, "median": 2.0, "mean": 4.0, "maximum": 9.0},
        )

    def test_spanning_case_selection_includes_pseudorandom_extremes(self) -> None:
        selected = select_spanning_cases(synthetic_context_cases(), 4)
        self.assertEqual(
            tuple(case.case_id for case in selected),
            ("balanced_repeat", "a_rich", "public_pseudorandom_96", "public_pseudorandom_384"),
        )

    def test_public_cohort_loader_validates_metadata_and_checksum(self) -> None:
        sequence = "ATCGGC" * 2
        checksum = __import__("hashlib").sha256(sequence.encode("ascii")).hexdigest()
        row = (
            '{"prompt_id":"one","sequence":"'
            + sequence
            + '","cohort_id":"cohort","organism":"Example organism",'
            + '"accession":"NC_1.1","start":10,"stop":21,"sequence_sha256":"'
            + checksum
            + '"}\n'
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "prompts.jsonl"
            path.write_text(row, encoding="utf-8")
            cases = load_context_cases_jsonl(path)
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0].organism, "Example organism")
        self.assertEqual(cases[0].accession, "NC_1.1")

    def test_cohort_content_digest_is_order_sensitive_and_deterministic(self) -> None:
        first = cohort_content_digest((("one", "aa"), ("two", "bb")))
        self.assertEqual(first, cohort_content_digest((("one", "aa"), ("two", "bb"))))
        self.assertNotEqual(first, cohort_content_digest((("two", "bb"), ("one", "aa"))))
        self.assertNotEqual(first, cohort_content_digest((("one", "aa"), ("two", "bc"))))
        with self.assertRaisesRegex(ValueError, "at least one prompt"):
            cohort_content_digest(())
        with self.assertRaisesRegex(ValueError, "prompt ID and sequence checksum"):
            cohort_content_digest((("one", ""),))

    def test_cohort_case_digest_matches_the_id_and_checksum_pairs(self) -> None:
        import hashlib

        sequences = {"one": "ATCGGC" * 2, "two": "GCGCGC" * 2}
        cases = tuple(
            ContextCase(
                case_id=case_id,
                sequence=sequence,
                sequence_sha256=hashlib.sha256(sequence.encode("ascii")).hexdigest(),
            )
            for case_id, sequence in sequences.items()
        )
        expected = cohort_content_digest(
            (case.case_id, str(case.sequence_sha256)) for case in cases
        )
        self.assertEqual(cohort_case_digest(cases), expected)

    def test_cohort_case_digest_requires_every_checksum(self) -> None:
        cases = (ContextCase(case_id="one", sequence="ATCGGC"),)
        with self.assertRaisesRegex(ValueError, "requires a checksum"):
            cohort_case_digest(cases)

    def test_public_cohort_loader_rejects_checksum_mismatch(self) -> None:
        row = (
            '{"prompt_id":"one","sequence":"ATCGGC","cohort_id":"cohort",'
            '"organism":"Example","accession":"NC_1.1","start":1,"stop":6,'
            '"sequence_sha256":"wrong"}\n'
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "prompts.jsonl"
            path.write_text(row, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid public prompt"):
                load_context_cases_jsonl(path)


if __name__ == "__main__":
    unittest.main()
