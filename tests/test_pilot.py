from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from genomic_watermarks.pilot import (
    ContextCase,
    cohort_case_digest,
    cohort_content_digest,
    deterministic_public_dna,
    load_context_cases_jsonl,
    numeric_summary,
)


class PublicPromptUtilitiesTest(unittest.TestCase):
    def test_public_dna_is_deterministic_and_canonical(self) -> None:
        first = deterministic_public_dna("fixture", 18)
        self.assertEqual(first, deterministic_public_dna("fixture", 18))
        self.assertEqual(len(first), 18)
        self.assertLessEqual(set(first), set("ATCG"))

    def test_numeric_summary(self) -> None:
        self.assertEqual(
            numeric_summary((1.0, 2.0, 9.0)),
            {"minimum": 1.0, "median": 2.0, "mean": 4.0, "maximum": 9.0},
        )

    def test_public_cohort_loader_checks_metadata_and_checksum(self) -> None:
        sequence = "ATCGGC" * 2
        checksum = hashlib.sha256(sequence.encode("ascii")).hexdigest()
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
        self.assertEqual(cases[0].organism, "Example organism")

    def test_cohort_digest_uses_prompt_order_and_checksums(self) -> None:
        first = cohort_content_digest((("one", "aa"), ("two", "bb")))
        self.assertNotEqual(first, cohort_content_digest((("two", "bb"), ("one", "aa"))))
        sequence = "ATCGGC"
        checksum = hashlib.sha256(sequence.encode("ascii")).hexdigest()
        cases = (ContextCase("one", sequence, sequence_sha256=checksum),)
        self.assertEqual(cohort_case_digest(cases), cohort_content_digest((("one", checksum),)))


if __name__ == "__main__":
    unittest.main()
