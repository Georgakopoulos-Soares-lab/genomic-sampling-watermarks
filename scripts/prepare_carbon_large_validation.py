#!/usr/bin/env python3
"""Prepare a new Carbon large-validation output root without overwriting files."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_large_v1/prompts.jsonl"
DEFAULT_MANIFEST = ROOT / "data/public_prompt_cohort_large_v1.yaml"
DEFAULT_CONFIG = ROOT / "configs/carbon_synthid_validation_v1.toml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--cohort-manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def copy_if_identical_or_new(source: Path, destination: Path) -> None:
    payload = source.read_bytes()
    if destination.exists():
        if destination.read_bytes() != payload:
            raise FileExistsError(f"refusing to replace different output: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)


def main() -> int:
    args = parse_args()
    for source in (args.cohort_jsonl, args.cohort_manifest, args.config):
        if not source.is_file():
            raise FileNotFoundError(source)
    args.output_root.mkdir(parents=True, exist_ok=True)
    copy_if_identical_or_new(args.cohort_manifest, args.output_root / "cohort_manifest.yaml")
    copy_if_identical_or_new(args.cohort_jsonl, args.output_root / "prompts.jsonl")
    copy_if_identical_or_new(args.config, args.output_root / "resolved_config.toml")
    for name in ("generation", "distribution", "sequence_comparison", "detection", "figures"):
        (args.output_root / name).mkdir(exist_ok=True)
    artifacts = {
        "cohort_manifest.yaml": hashlib.sha256(
            (args.output_root / "cohort_manifest.yaml").read_bytes()
        ).hexdigest(),
        "prompts.jsonl": hashlib.sha256(
            (args.output_root / "prompts.jsonl").read_bytes()
        ).hexdigest(),
        "resolved_config.toml": hashlib.sha256(
            (args.output_root / "resolved_config.toml").read_bytes()
        ).hexdigest(),
    }
    print(
        json.dumps(
            {"output_root": str(args.output_root), "prepared": True, "artifacts": artifacts},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
