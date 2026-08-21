from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import yaml

SCRIPT_PATH = Path("scripts/build_public_prompt_cohort.py")
SPEC = importlib.util.spec_from_file_location("build_public_prompt_cohort", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load public cohort builder")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PublicCohortTest(unittest.TestCase):
    def test_manifest_has_versioned_canonical_windows(self) -> None:
        manifest = yaml.safe_load(
            Path("data/public_prompt_cohort.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(len(manifest["records"]), 4)
        windows = [window for record in manifest["records"] for window in record["windows"]]
        self.assertEqual(len(windows), 12)
        self.assertEqual(len({window["id"] for window in windows}), 12)
        self.assertTrue(all(window["stop"] - window["start"] + 1 == 384 for window in windows))
        self.assertTrue(all(len(window["sequence_sha256"]) == 64 for window in windows))
        self.assertTrue(all("." in record["accession"] for record in manifest["records"]))

    def test_v2_manifest_retains_v1_and_adds_output_blind_chromosomes(self) -> None:
        v1 = yaml.safe_load(Path("data/public_prompt_cohort.yaml").read_text(encoding="utf-8"))
        v2 = yaml.safe_load(Path("data/public_prompt_cohort_v2.yaml").read_text(encoding="utf-8"))
        v1_windows = {
            window["id"]: window for record in v1["records"] for window in record["windows"]
        }
        v2_windows = {
            window["id"]: window for record in v2["records"] for window in record["windows"]
        }
        self.assertEqual(len(v2["records"]), 8)
        self.assertEqual(len(v2_windows), 24)
        self.assertEqual({key: v2_windows[key] for key in v1_windows}, v1_windows)
        for record in v2["records"]:
            length = record["record_length"]
            for window in record["windows"]:
                expected_start = int(window["position_fraction"] * (length - 384)) + 1
                self.assertEqual(window["start"], expected_start)
                self.assertEqual(window["stop"], expected_start + 383)

    def test_fasta_parser_and_cohort_digest(self) -> None:
        header, sequence = MODULE.parse_fasta(">NC_TEST.1 region\natcg\nATCG\n")
        self.assertEqual(header, "NC_TEST.1 region")
        self.assertEqual(sequence, "ATCGATCG")
        prompt = {"prompt_id": "one", "sequence_sha256": MODULE.sequence_sha256(sequence)}
        self.assertEqual(MODULE.cohort_sha256([prompt]), MODULE.cohort_sha256([prompt]))

    def test_fasta_parser_rejects_ambiguous_bases(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.parse_fasta(">NC_TEST.1\nATNG\n")


if __name__ == "__main__":
    unittest.main()
