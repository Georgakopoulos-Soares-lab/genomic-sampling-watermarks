"""Tests for reproducible artifact content digests."""

from __future__ import annotations

import copy
import unittest

from genomic_watermarks.content_digest import (
    EXCLUDED_FIELDS,
    PROTECTED_FIELDS,
    VOLATILE_FIELDS,
    assert_no_scientific_field_is_volatile,
    content_digest,
    strip_volatile,
    volatile_fields_present,
)

REPORT = {
    "policy_id": "C_tok",
    "wall_seconds": 391.79,
    "platform": "macOS-26.0-arm64",
    "python": "3.12.14",
    "summary": {"detection_rate": 1.0, "threshold": 3.654, "model_load_seconds": 1.2},
    "trials": [
        {"statistic": 7.5, "matches": 500, "total": 512, "wall_seconds": 0.1},
        {"statistic": 3.5, "matches": 260, "total": 512, "wall_seconds": 0.2},
    ],
}


class ContentDigestTest(unittest.TestCase):
    def test_timings_do_not_change_the_digest(self) -> None:
        """Two runs of the same command differ only in timings and host fields."""

        rerun = copy.deepcopy(REPORT)
        rerun["wall_seconds"] = 402.11
        rerun["platform"] = "macOS-26.1-arm64"
        rerun["summary"]["model_load_seconds"] = 3.4
        rerun["trials"][0]["wall_seconds"] = 0.9
        self.assertEqual(content_digest(REPORT), content_digest(rerun))

    def test_any_result_change_changes_the_digest(self) -> None:
        for path, mutate in (
            ("detection rate", lambda r: r["summary"].__setitem__("detection_rate", 0.875)),
            ("threshold", lambda r: r["summary"].__setitem__("threshold", 3.655)),
            ("statistic", lambda r: r["trials"][0].__setitem__("statistic", 7.51)),
            ("matches", lambda r: r["trials"][1].__setitem__("matches", 261)),
            ("policy", lambda r: r.__setitem__("policy_id", "G_tok")),
            ("trial count", lambda r: r["trials"].append({"statistic": 1.0})),
        ):
            changed = copy.deepcopy(REPORT)
            mutate(changed)
            with self.subTest(path=path):
                self.assertNotEqual(content_digest(REPORT), content_digest(changed))

    def test_key_order_does_not_change_the_digest(self) -> None:
        reordered = {key: REPORT[key] for key in reversed(list(REPORT))}
        self.assertEqual(content_digest(REPORT), content_digest(reordered))

    def test_volatile_fields_are_reported(self) -> None:
        self.assertEqual(
            volatile_fields_present(REPORT),
            ("model_load_seconds", "platform", "python", "wall_seconds"),
        )

    def test_stripping_removes_only_volatile_fields(self) -> None:
        stripped = strip_volatile(REPORT)
        self.assertNotIn("wall_seconds", stripped)
        self.assertEqual(stripped["summary"]["detection_rate"], 1.0)
        self.assertEqual(len(stripped["trials"]), 2)
        self.assertEqual(stripped["trials"][0]["matches"], 500)

    def test_no_result_field_may_be_declared_volatile(self) -> None:
        """The guard that stops the volatile set from swallowing a conclusion."""

        assert_no_scientific_field_is_volatile()
        self.assertFalse(EXCLUDED_FIELDS & PROTECTED_FIELDS)
        self.assertLess(len(VOLATILE_FIELDS), len(EXCLUDED_FIELDS))


class PathSpellingTest(unittest.TestCase):
    """How a path is spelled is not a result; what the file contains is."""

    BASE = {
        "cohort": {
            "prompts_path": "data/processed/cohort/prompts.jsonl",
            "prompts_file_sha256": "a" * 64,
            "manifest_path": "data/cohort.yaml",
            "manifest_sha256": "b" * 64,
        },
        "sequences": {"path": "outputs/seq.jsonl", "sha256": "c" * 64},
        "summary": {"detection_rate": 1.0},
    }

    def test_the_same_file_reached_by_a_different_path_is_the_same_run(self) -> None:
        relocated = copy.deepcopy(self.BASE)
        relocated["cohort"]["prompts_path"] = "/abs/repo/data/processed/cohort/prompts.jsonl"
        relocated["sequences"]["path"] = "/abs/repo/outputs/seq.jsonl"
        self.assertEqual(content_digest(self.BASE), content_digest(relocated))

    def test_a_different_input_still_changes_the_digest(self) -> None:
        """Excluding the spelling must not make the digest blind to the input."""

        for label, mutate in (
            ("prompts", lambda r: r["cohort"].__setitem__("prompts_file_sha256", "d" * 64)),
            ("manifest absent", lambda r: r["cohort"].__setitem__("manifest_sha256", None)),
            ("sequences", lambda r: r["sequences"].__setitem__("sha256", "e" * 64)),
        ):
            changed = copy.deepcopy(self.BASE)
            mutate(changed)
            with self.subTest(label=label):
                self.assertNotEqual(content_digest(self.BASE), content_digest(changed))


if __name__ == "__main__":
    unittest.main()
