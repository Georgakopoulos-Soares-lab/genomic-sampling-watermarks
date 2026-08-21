#!/usr/bin/env python3
"""Dependency-free structural checks for the research evidence ledger."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_FILE = ROOT / "evidence" / "measurements.yaml"
FORBIDDEN_PATTERNS = (
    re.compile(r"(?i)^\s*(secret_key|private_key|hf_token|access_token)\s*:"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def main() -> int:
    errors: list[str] = []
    seen_ids: dict[str, Path] = {}

    if not EVIDENCE_FILE.is_file():
        errors.append(f"missing {EVIDENCE_FILE.relative_to(ROOT)}")
        text = ""
    else:
        text = EVIDENCE_FILE.read_text(encoding="utf-8")
        if "schema_version:" not in text or "measurements:" not in text:
            errors.append(f"invalid top-level structure in {EVIDENCE_FILE.relative_to(ROOT)}")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                errors.append(f"possible secret material in {EVIDENCE_FILE.relative_to(ROOT)}")
        for match in re.finditer(r"^\s*-\s+id:\s+([A-Za-z0-9_.-]+)\s*$", text, re.MULTILINE):
            item_id = match.group(1)
            if item_id in seen_ids:
                errors.append(f"duplicate measurement id {item_id}")
            seen_ids[item_id] = EVIDENCE_FILE

        statuses = re.findall(r"^\s+status:\s+(\S+)\s*$", text, re.MULTILINE)
        invalid = [value for value in statuses if value not in {"V", "A"}]
        if invalid:
            errors.append(f"invalid evidence statuses: {', '.join(sorted(set(invalid)))}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"evidence ledger OK ({len(seen_ids)} measurements)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
