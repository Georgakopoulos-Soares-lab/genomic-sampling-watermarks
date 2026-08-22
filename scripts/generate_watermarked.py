#!/usr/bin/env python3
"""Generate matched `partition_mc` and ordinary continuations from a pinned policy.

The secret key is read only from the environment at runtime. The report records a
caller-supplied experiment label and never a key, a key digest, or any
key-derived value. Generated DNA is written to a separate sequences file so the
report stays small.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import random
import resource
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.models.huggingface import load_adapter  # noqa: E402
from genomic_watermarks.pilot import load_context_cases_jsonl, numeric_summary  # noqa: E402
from genomic_watermarks.watermark import (  # noqa: E402
    ORDINARY_SCHEME,
    PARTITION_MC_SCHEME,
    KeyedPartitionStream,
    generate_ordinary,
    generate_partition_mc,
    public_replay_seed,
    stream_agreements,
)

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl"
DEFAULT_DTYPES = {"C_tok": "bfloat16", "G_tok": "float32", "G_bp": "float32"}
DEFAULT_KEY_ENV = "GENOMIC_WATERMARK_KEY"
PUBLIC_FIXTURE_KEY = b"genomic-sampling-watermarks/public-generation-fixture/v1"
FIXTURE_KEY_LABEL = "genomic-sampling-watermarks/public-generation-fixture/v1/index"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=tuple(DEFAULT_DTYPES), required=True)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--steps", type=int, default=64, help="6-mer tokens per continuation")
    parser.add_argument("--stream-offset", type=int, default=0)
    parser.add_argument(
        "--experiment-label",
        required=True,
        help="public run label; must not be derived from the key",
    )
    parser.add_argument("--key-env", default=DEFAULT_KEY_ENV)
    parser.add_argument(
        "--public-fixture-key",
        action="store_true",
        help="use the published non-secret fixture key for a smoke run",
    )
    parser.add_argument(
        "--fixture-key-index",
        type=int,
        default=0,
        help=(
            "which published fixture key to use; 0 is the original one and any positive index "
            "derives an independent published key, so a study can average over keys"
        ),
    )
    parser.add_argument(
        "--arms",
        choices=("both", "watermarked"),
        default="both",
        help="generate both arms, or only the watermarked arm when the control already exists",
    )
    parser.add_argument("--device", choices=("mps", "cpu"), default="mps")
    parser.add_argument("--dtype", choices=("bfloat16", "float16", "float32"))
    parser.add_argument("--cache-dir", default=".cache/huggingface")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sequences-output", type=Path, required=True)
    return parser.parse_args()


def process_peak_rss_gib() -> float:
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    bytes_used = value if sys.platform == "darwin" else value * 1024.0
    return bytes_used / (1024.0**3)


def resolve_key(args: argparse.Namespace) -> tuple[bytes, str]:
    """Return runtime key material and a non-reversible description of its source."""

    if args.public_fixture_key:
        if args.fixture_key_index < 0:
            raise RuntimeError("fixture-key-index must be non-negative")
        if args.fixture_key_index == 0:
            return PUBLIC_FIXTURE_KEY, "public_fixture"
        derived = hashlib.sha256(
            f"{FIXTURE_KEY_LABEL}/{args.fixture_key_index:04d}".encode()
        ).digest()
        return derived, f"public_fixture_index_{args.fixture_key_index}"
    raw = os.environ.get(args.key_env)
    if not raw:
        raise RuntimeError(
            f"set {args.key_env} to hex key material at runtime, "
            "or pass --public-fixture-key for a non-secret smoke run"
        )
    try:
        key = bytes.fromhex(raw.strip())
    except ValueError as error:
        raise RuntimeError(f"{args.key_env} must contain hex-encoded key material") from error
    if len(key) < 16:
        raise RuntimeError(f"{args.key_env} must supply at least 16 bytes of key material")
    return key, "runtime_environment"


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


def main() -> int:
    args = parse_args()
    if args.steps <= 0:
        raise ValueError("steps must be positive")
    if args.stream_offset < 0:
        raise ValueError("stream-offset must be non-negative")
    if not args.experiment_label.strip():
        raise ValueError("experiment-label must not be empty")
    for path in (args.output, args.sequences_output):
        if path.exists():
            raise FileExistsError(f"refusing to replace existing output: {path}")

    cases = selected_cases(load_context_cases_jsonl(args.cohort_jsonl), args.case_id)
    cohort_id = cases[0].cohort_id
    dtype = args.dtype or DEFAULT_DTYPES[args.policy]
    key, key_source = resolve_key(args)
    stream_domain = f"{args.experiment_label}/{cohort_id}/{args.policy}"
    stream = KeyedPartitionStream(key=key, domain=stream_domain)

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
    support = adapter.canonical_tokens
    model_id = adapter.policy.model_id
    model_revision = adapter.policy.revision

    def next_distribution(context: str) -> tuple[tuple[str, ...], tuple[float, ...]]:
        state = adapter.next_distribution(context)
        return tuple(state.tokens), tuple(state.probabilities)

    rows: list[dict[str, Any]] = []
    sequence_records: list[dict[str, Any]] = []
    watermarked_seconds = 0.0
    ordinary_seconds = 0.0
    for case in cases:
        watermarked_started = time.perf_counter()
        watermarked = generate_partition_mc(
            next_distribution,
            case.sequence,
            steps=args.steps,
            stream=stream,
            rng=random.Random(
                public_replay_seed(
                    args.experiment_label, args.policy, case.case_id, PARTITION_MC_SCHEME
                )
            ),
            stream_offset=args.stream_offset,
        )
        watermarked_seconds += time.perf_counter() - watermarked_started

        ordinary_started = time.perf_counter()
        ordinary = None
        if args.arms == "both":
            ordinary = generate_ordinary(
                next_distribution,
                case.sequence,
                steps=args.steps,
                rng=random.Random(
                    public_replay_seed(
                        args.experiment_label, args.policy, case.case_id, ORDINARY_SCHEME
                    )
                ),
            )
        ordinary_seconds += time.perf_counter() - ordinary_started

        recovered = stream_agreements(
            watermarked.tokens,
            support,
            stream,
            stream_offset=args.stream_offset,
        )
        generation_agreements = tuple(step.agrees for step in watermarked.steps)
        rows.append(
            {
                "case_id": case.case_id,
                "organism": case.organism,
                "accession": case.accession,
                "prompt_sequence_sha256": case.sequence_sha256,
                "prompt_bases": len(case.sequence),
                "generated_tokens": args.steps,
                "generated_bases": watermarked.bases,
                "watermarked_sequence_sha256": hashlib.sha256(
                    watermarked.dna.encode("ascii")
                ).hexdigest(),
                "ordinary_sequence_sha256": (
                    hashlib.sha256(ordinary.dna.encode("ascii")).hexdigest()
                    if ordinary is not None
                    else None
                ),
                "agreement_count": watermarked.agreement_count,
                "agreement_rate": watermarked.agreement_rate,
                "expected_agreement_rate": watermarked.expected_agreement_rate,
                "keyed_recomputation_matches_generation": recovered == generation_agreements,
                "group_one_mass": numeric_summary(
                    step.group_one_mass for step in watermarked.steps
                ),
            }
        )
        emitted = [(PARTITION_MC_SCHEME, watermarked)]
        if ordinary is not None:
            emitted.append((ORDINARY_SCHEME, ordinary))
        for scheme, result in emitted:
            sequence_records.append(
                {
                    "case_id": case.case_id,
                    "cohort_id": cohort_id,
                    "policy_id": args.policy,
                    "scheme": scheme,
                    "experiment_label": args.experiment_label,
                    "stream_offset": args.stream_offset if scheme == PARTITION_MC_SCHEME else None,
                    "generated_dna": result.dna,
                }
            )

    mps_memory: dict[str, float] = {}
    if args.device == "mps":
        mps_memory = {
            "mps_current_allocated_gib": float(torch.mps.current_allocated_memory()) / (1024.0**3),
            "mps_driver_allocated_gib": float(torch.mps.driver_allocated_memory()) / (1024.0**3),
        }
    adapter = None
    gc.collect()
    if args.device == "mps":
        torch.mps.empty_cache()

    all_recovered = all(row["keyed_recomputation_matches_generation"] for row in rows)
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
        "watermark_method": PARTITION_MC_SCHEME,
        "control_method": ORDINARY_SCHEME,
        "experiment_label": args.experiment_label,
        "key_source": key_source,
        "fixture_key_index": args.fixture_key_index,
        "arms": args.arms,
        "stream_domain": stream_domain,
        "stream_offset": args.stream_offset,
        "generated_tokens_per_case": args.steps,
        "generated_bases_per_case": args.steps * 6,
        "temperature": 1.0,
        "truncation": "none",
        "device": args.device,
        "dtype": dtype,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "model_load_seconds": model_load_seconds,
        "watermarked_seconds": watermarked_seconds,
        "ordinary_seconds": ordinary_seconds,
        "wall_seconds": time.perf_counter() - run_started,
        "process_peak_rss_gib": process_peak_rss_gib(),
        **mps_memory,
        "keyed_recomputation_matches_generation": all_recovered,
        "summary": {
            "agreement_rate": numeric_summary(row["agreement_rate"] for row in rows),
            "expected_agreement_rate": numeric_summary(
                row["expected_agreement_rate"] for row in rows
            ),
        },
        "cases": rows,
        "sequences_path": str(args.sequences_output),
        "boundary": (
            "Agreement rates here are generator-side diagnostics. They are not detector results "
            "and carry no calibrated false-positive rate."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.sequences_output.parent.mkdir(parents=True, exist_ok=True)
    args.sequences_output.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in sequence_records),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sequences_output": str(args.sequences_output),
                "policy_id": args.policy,
                "case_count": len(cases),
                "generated_bases_per_case": args.steps * 6,
                "keyed_recomputation_matches_generation": all_recovered,
                "mean_agreement_rate": report["summary"]["agreement_rate"]["mean"],
                "mean_expected_agreement_rate": report["summary"]["expected_agreement_rate"][
                    "mean"
                ],
                "wall_seconds": report["wall_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
