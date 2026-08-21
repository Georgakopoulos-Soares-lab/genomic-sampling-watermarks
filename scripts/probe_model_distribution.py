#!/usr/bin/env python3
"""Run one fixed, non-generating distribution probe against a local model."""

from __future__ import annotations

import argparse
import json
import platform
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.metrics import (  # noqa: E402
    inverse_simpson_support,
    shannon_entropy_bits,
    top1_mass,
)
from genomic_watermarks.models.huggingface import POLICIES, load_adapter  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=sorted(POLICIES), required=True)
    parser.add_argument("--device", choices=("auto", "mps", "cpu"), default="auto")
    parser.add_argument(
        "--dtype",
        choices=("auto", "bfloat16", "float16", "float32"),
        default="auto",
    )
    parser.add_argument("--context-kmers", type=int, default=16)
    parser.add_argument("--cache-dir", default=".cache/huggingface")
    parser.add_argument("--local-files-only", action="store_true")
    return parser.parse_args()


def process_peak_rss_gib() -> float:
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    # macOS reports bytes; Linux reports KiB.
    bytes_used = value if sys.platform == "darwin" else value * 1024.0
    return bytes_used / (1024.0**3)


def main() -> int:
    args = parse_args()
    if args.context_kmers <= 0:
        raise ValueError("context-kmers must be positive")

    # Public, deterministic, phase-aligned synthetic context. It is never emitted.
    context = "ATCGGC" * args.context_kmers
    load_started = time.perf_counter()
    adapter = load_adapter(
        args.policy,
        device=args.device,
        dtype=args.dtype,
        cache_dir=args.cache_dir,
        local_files_only=args.local_files_only,
    )
    load_seconds = time.perf_counter() - load_started

    probe_started = time.perf_counter()
    state = adapter.next_distribution(context)
    probe_seconds = time.perf_counter() - probe_started
    vocabulary = adapter.canonical_vocabulary

    report = {
        "policy_id": adapter.policy.policy_id,
        "model_id": adapter.policy.model_id,
        "revision": adapter.policy.revision,
        "device": state.metadata["device"],
        "dtype": state.metadata["dtype"],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "context_bases": len(context),
        "canonical_count": len(state.tokens),
        "canonical_first_id": vocabulary.first_id,
        "canonical_last_id": vocabulary.last_id,
        "probability_sum": sum(state.probabilities),
        "entropy_bits": shannon_entropy_bits(state.probabilities),
        "effective_support": inverse_simpson_support(state.probabilities),
        "top1_mass": top1_mass(state.probabilities),
        "model_load_seconds": load_seconds,
        "distribution_seconds": probe_seconds,
        "process_peak_rss_gib": process_peak_rss_gib(),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
