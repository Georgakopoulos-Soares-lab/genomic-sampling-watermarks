#!/usr/bin/env python3
"""Check the figure manifest against the ledger and the figure files on disk.

A figure is only auditable if three things line up: the manifest names measurements
that exist, every figure file it claims exists, and the manifest was regenerated
after the ledger last changed. This checks all three and fails loudly, so a stale
figure cannot sit in a manuscript looking current.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "evidence/measurements.yaml"
MANIFEST = ROOT / "paper/figures/manifest.json"


def main() -> int:
    if not MANIFEST.exists():
        print("figure manifest is missing; run paper/scripts/make_figures.py")
        return 1
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ledger = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
    known = {m["id"] for m in ledger["measurements"]}
    superseded = {m["id"] for m in ledger["measurements"] if m.get("supersedes")}
    del superseded

    problems: list[str] = []

    declared: set[str] = set()
    for figure in manifest["figures"]:
        name = figure["name"]
        for measurement_id in figure["measurement_ids"]:
            declared.add(measurement_id)
            if measurement_id not in known:
                problems.append(f"{name} cites unknown measurement {measurement_id}")
        path = ROOT / figure["figure"]
        if not path.exists():
            problems.append(f"{name} names a missing file {figure['figure']}")
        if not figure.get("caption_claim"):
            problems.append(f"{name} has no caption claim")
        if not figure.get("sign"):
            problems.append(f"{name} does not declare which direction its axis points")

    used = set(manifest["measurement_ids_used"])
    if declared - used:
        problems.append(
            f"{len(declared - used)} measurement(s) cited by a figure but absent from the "
            "manifest's used list"
        )
    for measurement_id in sorted(used):
        if measurement_id not in known:
            problems.append(f"the manifest's used list names unknown measurement {measurement_id}")

    # A manifest older than the ledger describes figures drawn from different numbers.
    if MANIFEST.stat().st_mtime < LEDGER.stat().st_mtime:
        problems.append(
            "the manifest is older than the ledger; regenerate with paper/scripts/make_figures.py"
        )

    if problems:
        for problem in problems:
            print(f"FAIL {problem}")
        return 1
    print(
        f"figures OK ({len(manifest['figures'])} figures, {len(used)} measurements, "
        f"{len(known)} in the ledger)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
