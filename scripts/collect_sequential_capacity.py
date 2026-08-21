#!/usr/bin/env python3
"""Collect the frozen sequential E2 capacity pilot without watermarking the path."""

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
    shannon_entropy_bits,
    top1_mass,
)
from genomic_watermarks.models.huggingface import load_adapter  # noqa: E402
from genomic_watermarks.pilot import (  # noqa: E402
    capacity_points_for_partitions,
    load_context_cases_jsonl,
    numeric_summary,
)
from genomic_watermarks.sampling.partition import sample_categorical  # noqa: E402
from genomic_watermarks.sequential import (  # noqa: E402
    PATH_SAMPLING_SCHEME,
    PUBLIC_EVALUATION_SCHEME,
    build_evaluation_partitions,
    evaluation_partition_domains,
    path_rng,
    public_evaluation_material_sha256,
)

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_v1/prompts.jsonl"
DEFAULT_DTYPES = {"C_tok": "bfloat16", "G_tok": "float32", "G_bp": "float32"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=tuple(DEFAULT_DTYPES), required=True)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument(
        "--case-id",
        action="append",
        help="collect only this prompt ID; repeat for multiple prompts",
    )
    parser.add_argument("--states-per-prompt", type=int, default=128)
    parser.add_argument("--partitions-per-state", type=int, default=32)
    parser.add_argument("--seed", type=int, default=1729)
    parser.add_argument("--device", choices=("mps", "cpu"), default="mps")
    parser.add_argument("--dtype", choices=("bfloat16", "float16", "float32"))
    parser.add_argument("--cache-dir", default=".cache/huggingface")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def process_peak_rss_gib() -> float:
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    bytes_used = value if sys.platform == "darwin" else value * 1024.0
    return bytes_used / (1024.0**3)


def selected_cases(cases: tuple[Any, ...], requested_ids: list[str] | None) -> tuple[Any, ...]:
    if not requested_ids:
        return cases
    if len(set(requested_ids)) != len(requested_ids):
        raise ValueError("case-id values must be unique")
    by_id = {case.case_id: case for case in cases}
    missing = [case_id for case_id in requested_ids if case_id not in by_id]
    if missing:
        raise ValueError(f"unknown case-id value(s): {', '.join(missing)}")
    return tuple(by_id[case_id] for case_id in requested_ids)


def aggregate(rows: list[dict[str, Any]], name: str) -> dict[str, float]:
    return numeric_summary(float(row[name]) for row in rows)


def main() -> int:
    args = parse_args()
    if args.states_per_prompt <= 0:
        raise ValueError("states-per-prompt must be positive")
    if args.partitions_per_state <= 0:
        raise ValueError("partitions-per-state must be positive")
    if args.seed < 0:
        raise ValueError("seed must be non-negative")
    if args.output.exists():
        raise FileExistsError(f"refusing to replace existing output: {args.output}")

    cases = selected_cases(load_context_cases_jsonl(args.cohort_jsonl), args.case_id)
    cohort_id = cases[0].cohort_id
    dtype = args.dtype or DEFAULT_DTYPES[args.policy]

    try:
        import torch
    except ImportError as error:
        raise RuntimeError("install the optional 'models' dependencies first") from error
    if args.device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS is unavailable; run this command outside a restricted sandbox")

    run_started = time.perf_counter()
    load_started = time.perf_counter()
    adapter = load_adapter(
        args.policy,
        device=args.device,
        dtype=dtype,
        allow_cpu_fallback=False,
        cache_dir=args.cache_dir,
        local_files_only=args.local_files_only,
    )
    model_load_seconds = time.perf_counter() - load_started
    model_id = adapter.policy.model_id
    model_revision = adapter.policy.revision

    partition_started = time.perf_counter()
    partitions = build_evaluation_partitions(
        adapter.canonical_tokens,
        cohort_id=cohort_id,
        policy_id=args.policy,
        count=args.partitions_per_state,
    )
    partition_build_seconds = time.perf_counter() - partition_started

    rows: list[dict[str, Any]] = []
    prompt_summaries: list[dict[str, Any]] = []
    total_distribution_seconds = 0.0
    total_capacity_seconds = 0.0
    for case in cases:
        context = case.sequence
        rng = path_rng(args.seed, args.policy, case.case_id)
        prompt_rows: list[dict[str, Any]] = []
        generated_digest = hashlib.sha256()
        for state_index in range(args.states_per_prompt):
            distribution_started = time.perf_counter()
            state = adapter.next_distribution(context)
            distribution_seconds = time.perf_counter() - distribution_started
            total_distribution_seconds += distribution_seconds

            capacity_started = time.perf_counter()
            points = capacity_points_for_partitions(
                state.tokens,
                state.probabilities,
                partitions,
            )
            capacity_seconds = time.perf_counter() - capacity_started
            total_capacity_seconds += capacity_seconds

            sampled_token = sample_categorical(state.tokens, state.probabilities, rng)
            generated_digest.update(sampled_token.encode("ascii"))
            row = {
                "case_id": case.case_id,
                "state_index": state_index,
                "context_bases": len(context),
                "entropy_bits": shannon_entropy_bits(state.probabilities),
                "effective_support": inverse_simpson_support(state.probabilities),
                "top1_mass": top1_mass(state.probabilities),
                "partition_masses": [point.partition_mass for point in points],
                "information_bits_per_base": [point.information_bits_per_base for point in points],
                "distribution_seconds": distribution_seconds,
                "capacity_seconds": capacity_seconds,
            }
            rows.append(row)
            prompt_rows.append(row)
            context += sampled_token

        prompt_summaries.append(
            {
                "case_id": case.case_id,
                "organism": case.organism,
                "accession": case.accession,
                "prompt_sequence_sha256": case.sequence_sha256,
                "generated_bases": args.states_per_prompt * 6,
                "generated_sequence_sha256": generated_digest.hexdigest(),
                "information_bits_per_base": numeric_summary(
                    value for row in prompt_rows for value in row["information_bits_per_base"]
                ),
                "top1_mass": aggregate(prompt_rows, "top1_mass"),
            }
        )

    mps_memory: dict[str, float] = {}
    if args.device == "mps":
        mps_memory = {
            "mps_current_allocated_gib": float(torch.mps.current_allocated_memory()) / (1024.0**3),
            "mps_driver_allocated_gib": float(torch.mps.driver_allocated_memory()) / (1024.0**3),
        }
    del adapter
    gc.collect()
    if args.device == "mps":
        torch.mps.empty_cache()

    report: dict[str, Any] = {
        "schema_version": 1,
        "classification": "engineering_pilot_not_paper_evidence",
        "complete": True,
        "policy_id": args.policy,
        "model_id": model_id,
        "revision": model_revision,
        "cohort_id": cohort_id,
        "case_count": len(cases),
        "case_ids": [case.case_id for case in cases],
        "states_per_prompt": args.states_per_prompt,
        "state_count": len(rows),
        "generated_bases_per_prompt": args.states_per_prompt * 6,
        "temperature": 1.0,
        "truncation": "none",
        "path_sampling": {
            "scheme": PATH_SAMPLING_SCHEME,
            "base_seed": args.seed,
            "watermarked": False,
        },
        "partition_evaluation": {
            "scheme": PUBLIC_EVALUATION_SCHEME,
            "public_material_sha256": public_evaluation_material_sha256(),
            "domains": list(
                evaluation_partition_domains(
                    cohort_id,
                    args.policy,
                    args.partitions_per_state,
                )
            ),
            "partitions_per_state": args.partitions_per_state,
            "paired_and_reused_across_states": True,
        },
        "device": args.device,
        "dtype": dtype,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "model_load_seconds": model_load_seconds,
        "partition_build_seconds": partition_build_seconds,
        "total_distribution_seconds": total_distribution_seconds,
        "total_capacity_seconds": total_capacity_seconds,
        "states_per_second": len(rows) / total_distribution_seconds,
        "wall_seconds": time.perf_counter() - run_started,
        "process_peak_rss_gib": process_peak_rss_gib(),
        **mps_memory,
        "summary": {
            "entropy_bits": aggregate(rows, "entropy_bits"),
            "effective_support": aggregate(rows, "effective_support"),
            "top1_mass": aggregate(rows, "top1_mass"),
            "information_bits_per_base": numeric_summary(
                value for row in rows for value in row["information_bits_per_base"]
            ),
        },
        "prompt_summaries": prompt_summaries,
        "states": rows,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "policy_id": args.policy,
                "case_count": len(cases),
                "state_count": len(rows),
                "states_per_second": report["states_per_second"],
                "wall_seconds": report["wall_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
