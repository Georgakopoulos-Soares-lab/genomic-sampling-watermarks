#!/usr/bin/env python3
"""Fixed-state distribution-preservation audit for `partition_mc`.

For each selected prompt the model state is computed once. Many watermarked
draws are then taken at that frozen state, each with a fresh keyed partition and
latent bit, and compared with the declared policy law by a parametric Monte Carlo
goodness-of-fit test. A matched ordinary control is tested the same way.

This audits the one-step marginal at the tested states. It is not evidence of
sequence-level indistinguishability.
"""

from __future__ import annotations

import argparse
import gc
import json
import platform
import random
import resource
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.gof import (  # noqa: E402
    summarize_p_values,
    token_goodness_of_fit,
)
from genomic_watermarks.metrics import (  # noqa: E402
    inverse_simpson_support,
    shannon_entropy_bits,
    top1_mass,
)
from genomic_watermarks.models.huggingface import load_adapter  # noqa: E402
from genomic_watermarks.pilot import load_context_cases_jsonl  # noqa: E402
from genomic_watermarks.sampling.partition import (  # noqa: E402
    sample_categorical,
    sample_partition_coupling,
)
from genomic_watermarks.watermark import (  # noqa: E402
    ORDINARY_SCHEME,
    PARTITION_MC_SCHEME,
    KeyedPartitionStream,
    public_replay_seed,
)

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl"
DEFAULT_DTYPES = {"C_tok": "bfloat16", "G_tok": "float32", "G_bp": "float32"}
PUBLIC_FIXTURE_KEY = b"genomic-sampling-watermarks/public-preservation-fixture/v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=tuple(DEFAULT_DTYPES), required=True)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--draws", type=int, default=2000, help="draws per state and arm")
    parser.add_argument("--replicates", type=int, default=999)
    parser.add_argument("--gof-seed", type=int, default=2718)
    parser.add_argument("--experiment-label", required=True)
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


def main() -> int:
    args = parse_args()
    if args.draws <= 0:
        raise ValueError("draws must be positive")
    if args.replicates <= 0:
        raise ValueError("replicates must be positive")
    if not args.experiment_label.strip():
        raise ValueError("experiment-label must not be empty")
    if args.output.exists():
        raise FileExistsError(f"refusing to replace existing output: {args.output}")

    cases = selected_cases(load_context_cases_jsonl(args.cohort_jsonl), args.case_id)
    cohort_id = cases[0].cohort_id
    dtype = args.dtype or DEFAULT_DTYPES[args.policy]
    stream_domain = f"{args.experiment_label}/{cohort_id}/{args.policy}"
    stream = KeyedPartitionStream(key=PUBLIC_FIXTURE_KEY, domain=stream_domain)

    try:
        import torch
    except ImportError as error:
        raise RuntimeError("install the optional 'models' dependencies first") from error
    if args.device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS is unavailable; run this command outside a restricted sandbox")

    run_started = time.perf_counter()
    adapter = load_adapter(
        args.policy,
        device=args.device,
        dtype=dtype,
        allow_cpu_fallback=False,
        cache_dir=args.cache_dir,
        local_files_only=args.local_files_only,
    )
    model_id = adapter.policy.model_id
    model_revision = adapter.policy.revision

    rows: list[dict[str, Any]] = []
    watermarked_p_values: dict[str, float] = {}
    ordinary_p_values: dict[str, float] = {}
    for case in cases:
        state = adapter.next_distribution(case.sequence)
        items = tuple(state.tokens)
        probabilities = tuple(float(value) for value in state.probabilities)

        watermarked_rng = random.Random(
            public_replay_seed(
                args.experiment_label, args.policy, case.case_id, PARTITION_MC_SCHEME
            )
        )
        ordinary_rng = random.Random(
            public_replay_seed(args.experiment_label, args.policy, case.case_id, ORDINARY_SCHEME)
        )
        watermarked_tokens: list[str] = []
        agreements = 0
        sample_started = time.perf_counter()
        for index in range(args.draws):
            partition = stream.partition(items, index)
            latent_bit = stream.latent_bit(index)
            sample = sample_partition_coupling(
                items, probabilities, partition, latent_bit, watermarked_rng
            )
            watermarked_tokens.append(sample.token)
            agreements += sample.agrees_with_latent
        watermarked_seconds = time.perf_counter() - sample_started

        ordinary_started = time.perf_counter()
        ordinary_tokens = [
            sample_categorical(items, probabilities, ordinary_rng) for _ in range(args.draws)
        ]
        ordinary_seconds = time.perf_counter() - ordinary_started

        watermarked_gof = token_goodness_of_fit(
            watermarked_tokens,
            items,
            probabilities,
            replicates=args.replicates,
            seed=args.gof_seed,
        )
        ordinary_gof = token_goodness_of_fit(
            ordinary_tokens,
            items,
            probabilities,
            replicates=args.replicates,
            seed=args.gof_seed,
        )
        watermarked_p_values[case.case_id] = watermarked_gof.p_value
        ordinary_p_values[case.case_id] = ordinary_gof.p_value
        rows.append(
            {
                "case_id": case.case_id,
                "organism": case.organism,
                "accession": case.accession,
                "prompt_sequence_sha256": case.sequence_sha256,
                "context_bases": len(case.sequence),
                "entropy_bits": shannon_entropy_bits(probabilities),
                "effective_support": inverse_simpson_support(probabilities),
                "top1_mass": top1_mass(probabilities),
                "draws_per_arm": args.draws,
                "watermarked_agreement_rate": agreements / args.draws,
                "watermarked": {
                    "statistic": watermarked_gof.statistic,
                    "p_value": watermarked_gof.p_value,
                    "replicate_statistic_mean": watermarked_gof.replicate_statistic_mean,
                    "distinct_tokens": len(set(watermarked_tokens)),
                },
                "ordinary": {
                    "statistic": ordinary_gof.statistic,
                    "p_value": ordinary_gof.p_value,
                    "replicate_statistic_mean": ordinary_gof.replicate_statistic_mean,
                    "distinct_tokens": len(set(ordinary_tokens)),
                },
                "support_categories": watermarked_gof.support_categories,
                "categories": watermarked_gof.categories,
                "watermarked_sampling_seconds": watermarked_seconds,
                "ordinary_sampling_seconds": ordinary_seconds,
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
        "key_source": "public_fixture",
        "stream_domain": stream_domain,
        "test": {
            "name": "parametric Monte Carlo categorical goodness-of-fit on the G statistic",
            "draws_per_state_and_arm": args.draws,
            "replicates": args.replicates,
            "seed": args.gof_seed,
            "reference": "the declared policy law at the same frozen model state",
        },
        "temperature": 1.0,
        "truncation": "none",
        "device": args.device,
        "dtype": dtype,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "wall_seconds": time.perf_counter() - run_started,
        "process_peak_rss_gib": process_peak_rss_gib(),
        **mps_memory,
        "watermarked_p_value_family": summarize_p_values(watermarked_p_values),
        "ordinary_p_value_family": summarize_p_values(ordinary_p_values),
        "states": rows,
        "boundary": (
            "This audits the one-step marginal at the tested states. It is not evidence of "
            "sequence-level indistinguishability, and the p-value family summary is not a "
            "single global test."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "policy_id": args.policy,
                "case_count": len(cases),
                "draws_per_arm": args.draws,
                "watermarked_minimum_p_value": report["watermarked_p_value_family"][
                    "minimum_p_value"
                ],
                "watermarked_rejections_at_alpha": report["watermarked_p_value_family"][
                    "rejections_at_alpha"
                ],
                "ordinary_minimum_p_value": report["ordinary_p_value_family"]["minimum_p_value"],
                "ordinary_rejections_at_alpha": report["ordinary_p_value_family"][
                    "rejections_at_alpha"
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
