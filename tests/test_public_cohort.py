from __future__ import annotations

import unittest
from pathlib import Path

from genomic_watermarks.pilot import cohort_content_digest

try:
    import yaml
except ImportError:  # pragma: no cover - optional developer dependency
    yaml = None


@unittest.skipIf(yaml is None, "PyYAML is not installed")
class LargePublicCohortManifestTest(unittest.TestCase):
    def test_manifest_is_frozen_and_checksum_complete(self) -> None:
        manifest = yaml.safe_load(
            Path("data/public_prompt_cohort_large_v1.yaml").read_text(encoding="utf-8")
        )
        selection = manifest["selection"]
        self.assertEqual(manifest["cohort_id"], "ncbi_refseq_eukaryote_windows_large_v1")
        self.assertEqual(selection["prompt_count"], 256)
        self.assertEqual(selection["prompt_length_bases"], 384)
        entries = tuple(
            (window["id"], window["sequence_sha256"])
            for record in manifest["records"]
            for window in record["windows"]
        )
        self.assertEqual(len(entries), 256)
        self.assertEqual(
            cohort_content_digest(entries),
            "8f7f7bba52f26837cdef5f17b542e01ab61eb1ddf7735d43dcd6f7b8d0986308",
        )


if __name__ == "__main__":
    unittest.main()
