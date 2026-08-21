#!/usr/bin/env python3
"""Run a small model-policy capacity and device-parity pilot."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import platform
import resource
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.metrics import (  # noqa: E402
    inverse_simpson_support,
    jensen_shannon_divergence_bits,
    shannon_entropy_bits,
    top1_mass,
    top_k_overlap_fraction,
    total_variation_distance,
)
from genomic_watermarks.models.huggingface import load_adapter  # noqa: E402
from genomic_watermarks.pilot import (  # noqa: E402
    capacity_points,
    load_context_cases_jsonl,
    numeric_summary,
    select_spanning_cases,
    synthetic_context_cases,
)

PUBLIC_FIXTURE_MATERIAL = hashlib.sha256(b"carbon-capacity-pilot/public-fixture/v1").digest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--policy",
        choices=("C_tok", "G_tok", "G_bp"),
        default="C_tok",
        help="declared next-token policy to evaluate",
    )
    parser.add_argument("--cache-dir", default=".cache/huggingface")
    parser.add_argument(
        "--mps-dtype",
        choices=("bfloat16", "float16", "float32"),
        default="bfloat16",
    )
    parser.add_argument("--partitions-per-state", type=int, default=8)
    parser.add_argument("--cpu-parity-cases", type=int, default=4)
    parser.add_argument("--cohort-jsonl", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--local-files-only", action="store_true")
    return parser.parse_args()


def process_peak_rss_gib() -> float:
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    bytes_used = value if sys.platform == "darwin" else value * 1024.0
    return bytes_used / (1024.0**3)


def aggregate(rows: list[dict[str, Any]], name: str) -> dict[str, float]:
    return numeric_summary(float(row[name]) for row in rows)


def main() -> int:
    args = parse_args()
    if args.partitions_per_state <= 0:
        raise ValueError("partitions-per-state must be positive")

    cases = (
        load_context_cases_jsonl(args.cohort_jsonl)
        if args.cohort_jsonl is not None
        else synthetic_context_cases()
    )
    if not 0 <= args.cpu_parity_cases <= len(cases):
        raise ValueError("cpu-parity-cases must lie between zero and the context count")

    try:
        import torch
    except ImportError as error:
        raise RuntimeError("install the optional 'models' dependencies first") from error
    if not torch.backends.mps.is_available():
        raise RuntimeError("MPS is unavailable; run this command outside a restricted sandbox")

    common = {
        "cache_dir": args.cache_dir,
        "local_files_only": args.local_files_only,
        "allow_cpu_fallback": False,
    }
    load_started = time.perf_counter()
    mps_adapter = load_adapter(args.policy, device="mps", dtype=args.mps_dtype, **common)
    mps_load_seconds = time.perf_counter() - load_started
    model_id = mps_adapter.policy.model_id
    model_revision = mps_adapter.policy.revision

    rows: list[dict[str, Any]] = []
    parity_inputs: dict[str, tuple[float, ...]] = {}
    total_inference_seconds = 0.0
    parity_cases = select_spanning_cases(cases, args.cpu_parity_cases)
    parity_case_ids = {case.case_id for case in parity_cases}
    for case in cases:
        started = time.perf_counter()
        state = mps_adapter.next_distribution(case.sequence)
        elapsed = time.perf_counter() - started
        total_inference_seconds += elapsed
        domains = (
            f"{case.case_id}/partition/{index}" for index in range(args.partitions_per_state)
        )
        capacities = capacity_points(
            state.tokens,
            state.probabilities,
            fixture_material=PUBLIC_FIXTURE_MATERIAL,
            domains=domains,
        )
        row: dict[str, Any] = {
            "case_id": case.case_id,
            "context_bases": len(case.sequence),
            "entropy_bits": shannon_entropy_bits(state.probabilities),
            "effective_support": inverse_simpson_support(state.probabilities),
            "top1_mass": top1_mass(state.probabilities),
            "partition_mass_minimum": min(point.partition_mass for point in capacities),
            "partition_mass_maximum": max(point.partition_mass for point in capacities),
            "information_bits_per_token_mean": numeric_summary(
                point.information_bits_per_token for point in capacities
            )["mean"],
            "information_bits_per_base_mean": numeric_summary(
                point.information_bits_per_base for point in capacities
            )["mean"],
            "mps_distribution_seconds": elapsed,
        }
        if case.organism is not None:
            row["source"] = {
                "cohort_id": case.cohort_id,
                "organism": case.organism,
                "accession": case.accession,
                "start": case.start,
                "stop": case.stop,
                "sequence_sha256": case.sequence_sha256,
            }
        rows.append(row)
        if case.case_id in parity_case_ids:
            parity_inputs[case.case_id] = state.probabilities

    mps_current_allocated_gib = float(torch.mps.current_allocated_memory()) / (1024.0**3)
    mps_driver_allocated_gib = float(torch.mps.driver_allocated_memory()) / (1024.0**3)
    del mps_adapter
    gc.collect()
    torch.mps.empty_cache()

    parity_rows: list[dict[str, Any]] = []
    cpu_load_seconds = 0.0
    cpu_total_inference_seconds = 0.0
    if parity_inputs:
        load_started = time.perf_counter()
        cpu_adapter = load_adapter(args.policy, device="cpu", dtype="float32", **common)
        cpu_load_seconds = time.perf_counter() - load_started
        for case in parity_cases:
            started = time.perf_counter()
            cpu_state = cpu_adapter.next_distribution(case.sequence)
            elapsed = time.perf_counter() - started
            cpu_total_inference_seconds += elapsed
            mps_probabilities = parity_inputs[case.case_id]
            mps_top = max(range(len(mps_probabilities)), key=mps_probabilities.__getitem__)
            cpu_top = max(
                range(len(cpu_state.probabilities)),
                key=cpu_state.probabilities.__getitem__,
            )
            parity_rows.append(
                {
                    "case_id": case.case_id,
                    "top1_token_same": mps_top == cpu_top,
                    "total_variation_distance": total_variation_distance(
                        mps_probabilities, cpu_state.probabilities
                    ),
                    "jensen_shannon_divergence_bits": jensen_shannon_divergence_bits(
                        mps_probabilities, cpu_state.probabilities
                    ),
                    "top10_overlap_fraction": top_k_overlap_fraction(
                        mps_probabilities, cpu_state.probabilities, 10
                    ),
                    "top100_overlap_fraction": top_k_overlap_fraction(
                        mps_probabilities, cpu_state.probabilities, 100
                    ),
                    "maximum_absolute_probability_delta": max(
                        abs(left - right)
                        for left, right in zip(
                            mps_probabilities,
                            cpu_state.probabilities,
                            strict=True,
                        )
                    ),
                    "cpu_distribution_seconds": elapsed,
                }
            )

    organism_summary: dict[str, dict[str, dict[str, float]]] = {}
    for organism in sorted({str(row["source"]["organism"]) for row in rows if "source" in row}):
        organism_rows = [row for row in rows if row.get("source", {}).get("organism") == organism]
        organism_summary[organism] = {
            "entropy_bits": aggregate(organism_rows, "entropy_bits"),
            "information_bits_per_base_mean": aggregate(
                organism_rows, "information_bits_per_base_mean"
            ),
            "top1_mass": aggregate(organism_rows, "top1_mass"),
        }

    report: dict[str, Any] = {
        "schema_version": 1,
        "classification": "engineering_pilot_not_paper_evidence",
        "input_mode": "public_cohort" if args.cohort_jsonl is not None else "synthetic",
        "cohort_id": cases[0].cohort_id,
        "policy_id": args.policy,
        "model_id": model_id,
        "revision": model_revision,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "temperature": 1.0,
        "context_count": len(rows),
        "partition_fixtures_per_state": args.partitions_per_state,
        "fixture_material": "public_nonsecret_v1",
        "mps_dtype": args.mps_dtype,
        "cpu_dtype": "float32" if parity_rows else "not_run",
        "mps_model_load_seconds": mps_load_seconds,
        "mps_total_distribution_seconds": total_inference_seconds,
        "mps_states_per_second": len(rows) / total_inference_seconds,
        "cpu_model_load_seconds": cpu_load_seconds,
        "cpu_total_distribution_seconds": cpu_total_inference_seconds,
        "cpu_states_per_second": (
            len(parity_rows) / cpu_total_inference_seconds if cpu_total_inference_seconds else 0.0
        ),
        "mps_current_allocated_gib": mps_current_allocated_gib,
        "mps_driver_allocated_gib": mps_driver_allocated_gib,
        "process_peak_rss_gib": process_peak_rss_gib(),
        "distribution_summary": {
            "entropy_bits": aggregate(rows, "entropy_bits"),
            "effective_support": aggregate(rows, "effective_support"),
            "top1_mass": aggregate(rows, "top1_mass"),
            "information_bits_per_token_mean": aggregate(rows, "information_bits_per_token_mean"),
            "information_bits_per_base_mean": aggregate(rows, "information_bits_per_base_mean"),
        },
        "organism_summary": organism_summary,
        "parity_summary": (
            {
                "case_count": len(parity_rows),
                "case_ids": [row["case_id"] for row in parity_rows],
                "top1_agreement_fraction": sum(bool(row["top1_token_same"]) for row in parity_rows)
                / len(parity_rows),
                "total_variation_distance": aggregate(parity_rows, "total_variation_distance"),
                "jensen_shannon_divergence_bits": aggregate(
                    parity_rows, "jensen_shannon_divergence_bits"
                ),
                "top10_overlap_fraction": aggregate(parity_rows, "top10_overlap_fraction"),
                "top100_overlap_fraction": aggregate(parity_rows, "top100_overlap_fraction"),
                "maximum_absolute_probability_delta": aggregate(
                    parity_rows, "maximum_absolute_probability_delta"
                ),
            }
            if parity_rows
            else {"case_count": 0}
        ),
        "contexts": rows,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
