#!/usr/bin/env python3
"""Compute reproducible content digests for completed artifacts.

A file digest pins the stored bytes; it cannot be reproduced by re-running the
command, because timings and host fields differ every time. A content digest is
taken over the artifact with those volatile fields removed, so a reviewer can
re-run the recorded command and compare the number instead of trusting it.

With ``--expect`` the script verifies a previously recorded table instead of
printing a new one, which is how a rerun is checked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.content_digest import (  # noqa: E402
    VOLATILE_FIELDS,
    content_digest,
    volatile_fields_present,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, nargs="+", required=True)
    parser.add_argument(
        "--expect",
        type=Path,
        help="a previously written digest table to verify instead of printing a new one",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output is not None and args.output.exists():
        raise FileExistsError(f"refusing to replace existing output: {args.output}")

    rows = []
    for path in sorted(args.input):
        payload = path.read_bytes()
        report = json.loads(payload)
        rows.append(
            {
                "artifact": str(path.resolve().relative_to(ROOT)),
                "file_sha256": hashlib.sha256(payload).hexdigest(),
                "content_sha256": content_digest(report),
                "volatile_fields_present": list(volatile_fields_present(report)),
            }
        )
        del payload, report

    table = {
        "schema_version": 1,
        "classification": "engineering_analysis_pending_evidence_review",
        "purpose": (
            "the content digest is reproducible by re-running the recorded command; the file "
            "digest pins the stored bytes and is not"
        ),
        "volatile_fields_excluded": sorted(VOLATILE_FIELDS),
        "artifacts": rows,
    }

    if args.expect is not None:
        expected = {
            row["artifact"]: row["content_sha256"]
            for row in json.loads(args.expect.read_text(encoding="utf-8"))["artifacts"]
        }
        mismatched = [
            row["artifact"]
            for row in rows
            if row["artifact"] in expected and expected[row["artifact"]] != row["content_sha256"]
        ]
        absent = [row["artifact"] for row in rows if row["artifact"] not in expected]
        print(
            json.dumps(
                {
                    "checked": len(rows),
                    "matched": len(rows) - len(mismatched) - len(absent),
                    "mismatched": mismatched,
                    "not_in_expected_table": absent,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1 if mismatched else 0

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(table, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"artifacts": len(rows), "output": str(args.output) if args.output else None},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
