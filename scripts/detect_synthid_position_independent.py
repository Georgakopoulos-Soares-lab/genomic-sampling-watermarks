#!/usr/bin/env python3
"""Detect a SynthID tournament watermark without a prompt or known alignment.

The secret key is read from an environment variable and is never printed.  A
single plain-DNA or FASTA record is read from a file, or from standard input
when ``--input`` is omitted.  Output contains only detector statistics and
coordinates, never the input DNA.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.dna import normalize_dna  # noqa: E402
from genomic_watermarks.synthid_position_independent import (  # noqa: E402
    PositionIndependentSynthIDConfig,
    detect_synthid_position_independent,
)

DEFAULT_KEY_ENV = "GENOMIC_SYNTHID_KEY"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        help="plain-DNA or single-record FASTA input; omit to read standard input",
    )
    parser.add_argument("--domain", required=True, help="public domain used at generation")
    parser.add_argument("--key-env", default=DEFAULT_KEY_ENV)
    parser.add_argument(
        "--window-base-lengths",
        type=int,
        nargs="+",
        default=(384, 768, 1536, 3072),
    )
    parser.add_argument("--target-fpr", type=float, default=0.01)
    parser.add_argument("--depth", type=int, default=30)
    parser.add_argument("--context-tokens", type=int, default=4)
    parser.add_argument("--context-history-size", type=int, default=1024)
    return parser.parse_args()


def parse_single_sequence(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("input does not contain a DNA sequence")
    if not lines[0].startswith(">"):
        if any(line.startswith(">") for line in lines):
            raise ValueError("FASTA header must be the first non-empty line")
        return normalize_dna("".join(lines))
    headers = [index for index, line in enumerate(lines) if line.startswith(">")]
    if len(headers) != 1:
        raise ValueError("input must contain exactly one FASTA record")
    if len(lines) == 1:
        raise ValueError("FASTA record does not contain a DNA sequence")
    return normalize_dna("".join(lines[1:]))


def resolve_key(environment_name: str) -> bytes:
    raw = os.environ.get(environment_name)
    if not raw:
        raise RuntimeError(f"set {environment_name} to hex-encoded secret key material")
    try:
        key = bytes.fromhex(raw.strip())
    except ValueError as error:
        raise RuntimeError(f"{environment_name} must contain a hexadecimal value") from error
    if len(key) < 16:
        raise RuntimeError(f"{environment_name} must contain at least 16 key bytes")
    return key


def main() -> int:
    args = parse_args()
    text = args.input.read_text(encoding="utf-8") if args.input else sys.stdin.read()
    sequence = parse_single_sequence(text)
    config = PositionIndependentSynthIDConfig(
        window_base_lengths=tuple(args.window_base_lengths),
        target_false_positive_rate=args.target_fpr,
        depth=args.depth,
        context_tokens=args.context_tokens,
        context_history_size=args.context_history_size,
    )
    result = detect_synthid_position_independent(
        sequence,
        key=resolve_key(args.key_env),
        domain=args.domain,
        config=config,
    )
    payload = asdict(result)
    payload["read_base_length"] = len(sequence)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
