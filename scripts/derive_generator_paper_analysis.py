#!/usr/bin/env python3
"""Derive missing manuscript panels from admitted GENERator v1 artifacts on CPU.

The output is immutable: use --check to verify it, or a new filename/identity
for a changed analysis. Neither generation nor detection is rerun.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shlex
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from validate_generator_synthid_position_independent import (  # noqa: E402
    exact_interval,
    validate_trial,
)

from genomic_watermarks.paper_analysis import detection_summary, quality_summary  # noqa: E402

ANALYSIS_ID = "generator_v1_paper_analysis_2026_09_11"
DEFAULT_OUTPUT = ROOT / "evidence/derived/generator_v1_paper_analysis_2026_09_11.json"
SOURCES = {
    "quality": (
        "outputs/generator_synthid_e16_v1/sequence_comparison_summary.json",
        "d8e3c03b2d0e3a2639c521889ea29dd804e8a741d3cf43818cb79f31ae821401",
    ),
    "trials": (
        "outputs/generator_synthid_position_independent_v1/trials.jsonl",
        "3de1d8f7b8a946d3a5149f48ac30e357ceb2fa812eddbe6a11a5e836c7106d99",
    ),
    "detection": (
        "outputs/generator_synthid_position_independent_v1/summary.json",
        "ac28bf5ed078fccd1eac5a97cabdd4f2a4e67f07a75d291aa3c5e0abd15830f7",
    ),
}
CODE_FILES = (
    "scripts/derive_generator_paper_analysis.py",
    "src/genomic_watermarks/paper_analysis.py",
    "scripts/validate_generator_synthid_position_independent.py",
    "src/genomic_watermarks/synthid_position_independent.py",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derive() -> dict[str, Any]:
    """Verify source hashes, every stored trial, intervals, and paired summaries."""
    for relative, expected in SOURCES.values():
        if digest(ROOT / relative) != expected:
            raise ValueError(f"source digest mismatch: {relative}")
    quality = json.loads((ROOT / SOURCES["quality"][0]).read_text())
    source = json.loads((ROOT / SOURCES["detection"][0]).read_text())
    trials = [json.loads(line) for line in (ROOT / SOURCES["trials"][0]).read_text().splitlines()]
    if (quality["prompt_count"], quality["pair_count"]) != (256, 512):
        raise ValueError("unexpected quality cohort size")
    if source["evaluation_prompts"] != 192 or len(trials) != 4608:
        raise ValueError("unexpected detection cohort size")
    for row in trials:
        validate_trial(row)
    # Preserve the source intervals after independently recomputing their endpoints.
    for cell in source["rates"]:
        for field in ("prompt_both_draws", "prompt_any_draw"):
            record = cell[field]
            recomputed = exact_interval(record["detections"], record["trials"])
            if any(
                abs(a - b) > 1e-12
                for a, b in zip(
                    recomputed,
                    record["exact_95_interval"],
                    strict=True,
                )
            ):
                raise ValueError("stored prompt interval failed independent recomputation")
    return {
        "quality": quality_summary(quality),
        "detection": detection_summary(trials, source),
        "model": quality["model_id"],
        "revision": quality["revision"],
        "policy": quality["policy_id"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="verify without writing")
    args = parser.parse_args()
    if not args.check and args.output.exists():
        raise FileExistsError(f"immutable output exists; use --check: {args.output}")
    start = time.perf_counter()
    data = derive()
    sources = {name: {"path": path, "sha256": sha} for name, (path, sha) in SOURCES.items()}
    code = {relative: digest(ROOT / relative) for relative in CODE_FILES}
    if args.check:
        retained = json.loads(args.output.read_text())
        if retained["analysis_id"] != ANALYSIS_ID or retained["data"] != data:
            raise ValueError("retained derived values differ from verified source data")
        if retained["sources"] != sources or retained["provenance"]["code_sha256"] != code:
            raise ValueError("retained source or analysis-code provenance differs")
    else:
        git_revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
        ).strip()
        record = {
            "schema_version": 1,
            "analysis_id": ANALYSIS_ID,
            "status": "A",
            "generation_rerun": False,
            "detection_rerun": False,
            "sources": sources,
            "data": data,
            "provenance": {
                "git_base_revision": git_revision,
                "code_sha256": code,
                "command": shlex.join([sys.executable, *sys.argv]),
                "python": platform.python_version(),
                "system": platform.system(),
                "machine": platform.machine(),
                "macos": platform.mac_ver()[0],
                "device": "cpu",
                "scipy": version("scipy"),
                "original_execution": "docs/research/generator_synthid_execution_2026_09_03.md",
                "amendment": "docs/research/generator_v1_analysis_amendment_2026_09_11.md",
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "status": "verified" if args.check else "derived",
                "analysis_id": ANALYSIS_ID,
                "output": str(args.output.relative_to(ROOT)),
                "sha256": digest(args.output),
                "seconds": time.perf_counter() - start,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
