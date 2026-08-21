#!/usr/bin/env python3
"""Compare one model distribution between Apple MPS and CPU."""

from __future__ import annotations

import argparse
import gc
import json
import platform
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.metrics import (  # noqa: E402
    jensen_shannon_divergence_bits,
    top_k_overlap_fraction,
    total_variation_distance,
)
from genomic_watermarks.models.huggingface import POLICIES, load_adapter  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=sorted(POLICIES), required=True)
    parser.add_argument(
        "--mps-dtype",
        choices=("bfloat16", "float16", "float32"),
        default="bfloat16",
    )
    parser.add_argument("--context-kmers", type=int, default=16)
    parser.add_argument("--cache-dir", default=".cache/huggingface")
    parser.add_argument("--local-files-only", action="store_true")
    return parser.parse_args()


def process_peak_rss_gib() -> float:
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    bytes_used = value if sys.platform == "darwin" else value * 1024.0
    return bytes_used / (1024.0**3)


def main() -> int:
    args = parse_args()
    if args.context_kmers <= 0:
        raise ValueError("context-kmers must be positive")

    try:
        import torch
    except ImportError as error:
        raise RuntimeError("install the optional 'models' dependencies first") from error
    if not torch.backends.mps.is_available():
        raise RuntimeError("MPS is unavailable; run this command outside a restricted sandbox")

    context = "ATCGGC" * args.context_kmers
    common = {
        "cache_dir": args.cache_dir,
        "local_files_only": args.local_files_only,
        "allow_cpu_fallback": False,
    }

    mps_load_started = time.perf_counter()
    mps_adapter = load_adapter(args.policy, device="mps", dtype=args.mps_dtype, **common)
    mps_load_seconds = time.perf_counter() - mps_load_started
    mps_probe_started = time.perf_counter()
    mps_state = mps_adapter.next_distribution(context)
    mps_probe_seconds = time.perf_counter() - mps_probe_started
    del mps_adapter
    gc.collect()
    torch.mps.empty_cache()

    cpu_load_started = time.perf_counter()
    cpu_adapter = load_adapter(args.policy, device="cpu", dtype="float32", **common)
    cpu_load_seconds = time.perf_counter() - cpu_load_started
    cpu_probe_started = time.perf_counter()
    cpu_state = cpu_adapter.next_distribution(context)
    cpu_probe_seconds = time.perf_counter() - cpu_probe_started

    if mps_state.tokens != cpu_state.tokens:
        raise RuntimeError("MPS and CPU adapters returned different canonical token orders")
    mps_top = max(range(len(mps_state.probabilities)), key=mps_state.probabilities.__getitem__)
    cpu_top = max(range(len(cpu_state.probabilities)), key=cpu_state.probabilities.__getitem__)

    report = {
        "policy_id": cpu_adapter.policy.policy_id,
        "model_id": cpu_adapter.policy.model_id,
        "revision": cpu_adapter.policy.revision,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "context_bases": len(context),
        "canonical_count": len(cpu_state.tokens),
        "mps_dtype": mps_state.metadata["dtype"],
        "cpu_dtype": cpu_state.metadata["dtype"],
        "top1_token_same": mps_top == cpu_top,
        "top10_overlap_fraction": top_k_overlap_fraction(
            mps_state.probabilities, cpu_state.probabilities, 10
        ),
        "top100_overlap_fraction": top_k_overlap_fraction(
            mps_state.probabilities, cpu_state.probabilities, 100
        ),
        "total_variation_distance": total_variation_distance(
            mps_state.probabilities, cpu_state.probabilities
        ),
        "jensen_shannon_divergence_bits": jensen_shannon_divergence_bits(
            mps_state.probabilities, cpu_state.probabilities
        ),
        "maximum_absolute_probability_delta": max(
            abs(left - right)
            for left, right in zip(
                mps_state.probabilities,
                cpu_state.probabilities,
                strict=True,
            )
        ),
        "mps_model_load_seconds": mps_load_seconds,
        "cpu_model_load_seconds": cpu_load_seconds,
        "mps_distribution_seconds": mps_probe_seconds,
        "cpu_distribution_seconds": cpu_probe_seconds,
        "process_peak_rss_gib": process_peak_rss_gib(),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
