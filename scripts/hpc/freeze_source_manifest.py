#!/usr/bin/env python3
"""Freeze or verify the exact source bytes used by the TACC validation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

SCIENTIFIC_SCRIPTS = (
    "scripts/analyze_carbon_large_sequences.py",
    "scripts/compare_synthid_detectors.py",
    "scripts/plot_carbon_large_validation.py",
    "scripts/prepare_carbon_large_validation.py",
    "scripts/render_carbon_large_report.py",
    "scripts/run_carbon_large_detection.py",
    "scripts/run_carbon_large_distribution.py",
    "scripts/run_carbon_large_generation.py",
    "scripts/summarize_carbon_large_generation.py",
    "scripts/validate_carbon_large_validation.py",
    "scripts/analyze_generator_large_sequences.py",
    "scripts/compare_generator_synthid_detectors.py",
    "scripts/plot_generator_large_validation.py",
    "scripts/prepare_generator_large_validation.py",
    "scripts/render_generator_large_report.py",
    "scripts/run_generator_large_detection.py",
    "scripts/run_generator_large_distribution.py",
    "scripts/run_generator_large_generation.py",
    "scripts/run_generator_parallel_generation.py",
    "scripts/run_generator_synthid_position_independent.py",
    "scripts/summarize_generator_large_generation.py",
    "scripts/validate_generator_large_validation.py",
    "scripts/validate_generator_synthid_position_independent.py",
)
ROOT_INPUTS = (
    "configs/carbon_synthid_validation_hpc_v1.toml",
    "configs/generator_synthid_validation_hpc_v1.toml",
    "docs/research/generator_synthid_position_independent_validation_protocol.md",
    "docs/research/generator_synthid_validation_v1_protocol.md",
    "data/public_prompt_cohort_large_v1.yaml",
    "data/public_prompt_cohort_large_v1_sources.yaml",
    "environment/tacc-cu128-requirements.txt",
    "environment/tacc_watermark.yml",
    "pyproject.toml",
    "sources.yaml",
    "uv.lock",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def source_paths() -> tuple[Path, ...]:
    paths = list((ROOT / "src").rglob("*.py"))
    paths.extend(ROOT / relative for relative in SCIENTIFIC_SCRIPTS)
    paths.extend((ROOT / "scripts/hpc").glob("*.py"))
    paths.extend((ROOT / "scripts/hpc").glob("*.sh"))
    paths.extend((ROOT / "scripts/hpc").glob("*.sbatch"))
    paths.extend(ROOT / relative for relative in ROOT_INPUTS)
    resolved = tuple(sorted(set(paths)))
    missing = [path for path in resolved if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing[0])
    return resolved


def git_value(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def build_manifest() -> dict[str, Any]:
    files = {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source_paths()
    }
    tree = hashlib.sha256()
    for relative, digest in files.items():
        tree.update(relative.encode("utf-8"))
        tree.update(b"\x00")
        tree.update(digest.encode("ascii"))
        tree.update(b"\n")
    status = git_value("status", "--porcelain")
    return {
        "schema_version": 1,
        "classification": "source_provenance_not_admitted_evidence",
        "git_commit": git_value("rev-parse", "HEAD"),
        "dirty_worktree": bool(status),
        "dirty_status_sha256": hashlib.sha256(status.encode()).hexdigest(),
        "source_tree_sha256": tree.hexdigest(),
        "file_count": len(files),
        "files": files,
    }


def atomic_write(path: Path, payload: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"refusing to replace different source manifest: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    args = parse_args()
    current = build_manifest()
    if args.verify:
        expected = json.loads(args.output.read_text(encoding="utf-8"))
        if current != expected:
            raise RuntimeError(
                "scientific source differs from the submission manifest; use a new output root"
            )
        print(json.dumps({"verified": True, "source_tree_sha256": current["source_tree_sha256"]}))
        return 0
    payload = json.dumps(current, indent=2, sort_keys=True) + "\n"
    atomic_write(args.output, payload)
    print(payload, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
