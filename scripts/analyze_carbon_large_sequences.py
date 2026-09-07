#!/usr/bin/env python3
"""Compute Carbon likelihood and paired sequence proxies for the large corpus."""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import resource
import statistics
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.large_validation import (  # noqa: E402
    benjamini_hochberg,
    bonferroni_adjusted,
    paired_cluster_summary,
    sequence_identity,
    sha256_file,
)
from genomic_watermarks.models.huggingface import load_adapter  # noqa: E402
from genomic_watermarks.pilot import load_context_cases_jsonl  # noqa: E402
from genomic_watermarks.sequence_proxies import (  # noqa: E402
    PROXY_METRICS,
    kmer_divergence_bits,
    proxy_metrics,
)
from genomic_watermarks.synthid import SYNTHID_SCHEME  # noqa: E402
from genomic_watermarks.watermark import (  # noqa: E402
    ORDINARY_SCHEME,
    public_replay_seed,
)

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_large_v1/prompts.jsonl"
METRICS = (
    *PROXY_METRICS,
    "js_divergence_from_prompt_k1_bits",
    "js_divergence_from_prompt_k2_bits",
    "js_divergence_from_prompt_k3_bits",
    "mean_negative_log_likelihood_per_token",
    "perplexity",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--draw-index", type=int, action="append")
    parser.add_argument("--device", choices=("mps", "cuda", "cpu"), default="mps")
    parser.add_argument("--dtype", choices=("bfloat16", "float16", "float32"), default="bfloat16")
    parser.add_argument("--cache-dir", default=".cache/huggingface")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--bootstrap-replicates", type=int, default=20_000)
    parser.add_argument("--permutation-replicates", type=int, default=100_000)
    parser.add_argument("--analysis-seed", type=int, default=2718)
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--expected-sequence-count", type=int)
    return parser.parse_args()


def process_peak_rss_gib() -> float:
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    bytes_used = value if sys.platform == "darwin" else value * 1024.0
    return bytes_used / (1024.0**3)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to replace completed shard: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def shard_name(record: dict[str, Any]) -> str:
    scheme = "watermarked" if record["scheme"] == SYNTHID_SCHEME else "ordinary"
    return f"{record['case_id']}__draw_{int(record['draw_id']):02d}__{scheme}.json"


def validate_shard(shard: dict[str, Any], record: dict[str, Any], args: argparse.Namespace) -> None:
    expected = {
        "complete": True,
        "case_id": record["case_id"],
        "draw_id": int(record["draw_id"]),
        "scheme": record["scheme"],
        "sequence_sha256": record["sequence_sha256"],
        "policy_id": "C_tok",
        "device": args.device,
        "dtype": args.dtype,
    }
    for field, value in expected.items():
        if shard.get(field) != value:
            raise ValueError(f"metric shard has inconsistent {field}")
    metrics = shard.get("metrics")
    if not isinstance(metrics, dict) or set(metrics) != set(METRICS):
        raise ValueError("metric shard does not contain the frozen metric suite")
    if int(shard["likelihood_token_count"]) != int(record["generated_tokens"]):
        raise ValueError("metric shard likelihood includes the wrong token count")


def arm_summary(rows: list[dict[str, Any]], metric: str) -> dict[str, float]:
    values = [float(row["metrics"][metric]) for row in rows]
    return {"mean": statistics.fmean(values), "median": statistics.median(values)}


def compare_metric(
    *,
    rows: list[dict[str, Any]],
    metric: str,
    draw_filter: int | None,
    bootstrap_replicates: int,
    permutation_replicates: int,
    seed: int,
) -> dict[str, Any]:
    filtered = [row for row in rows if draw_filter is None or int(row["draw_id"]) == draw_filter]
    by_identity = {
        (str(row["case_id"]), int(row["draw_id"]), str(row["scheme"])): row for row in filtered
    }
    prompts = sorted({str(row["case_id"]) for row in filtered})
    draws = sorted({int(row["draw_id"]) for row in filtered})
    differences: dict[str, tuple[float, ...]] = {}
    for case_id in prompts:
        values: list[float] = []
        for draw_id in draws:
            wm = by_identity[(case_id, draw_id, SYNTHID_SCHEME)]
            ordinary = by_identity[(case_id, draw_id, ORDINARY_SCHEME)]
            values.append(float(wm["metrics"][metric]) - float(ordinary["metrics"][metric]))
        differences[case_id] = tuple(values)
    result = paired_cluster_summary(
        differences,
        bootstrap_replicates=bootstrap_replicates,
        permutation_replicates=permutation_replicates,
        seed=seed,
    )
    watermarked = [row for row in filtered if row["scheme"] == SYNTHID_SCHEME]
    ordinary = [row for row in filtered if row["scheme"] == ORDINARY_SCHEME]
    return {
        "metric": metric,
        "draw_id": draw_filter,
        "watermarked": arm_summary(watermarked, metric),
        "ordinary": arm_summary(ordinary, metric),
        "paired": asdict(result),
    }


def finalize(
    *,
    args: argparse.Namespace,
    records: list[dict[str, Any]],
    shards_dir: Path,
    input_artifacts: list[dict[str, str]],
) -> dict[str, Any]:
    expected = args.expected_sequence_count or len(records)
    paths = sorted(shards_dir.glob("*.json"))
    if len(paths) != expected:
        raise ValueError(f"found {len(paths)} completed metric shards, expected {expected}")
    rows = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    identities = [sequence_identity(row) for row in rows]
    if len(set(identities)) != len(identities):
        raise ValueError("metric shards contain duplicate sequence identities")
    expected_records = {sequence_identity(record): record for record in records}
    if set(identities) != set(expected_records):
        raise ValueError("metric shards do not match the selected generation corpus")
    for row in rows:
        validate_shard(row, expected_records[sequence_identity(row)], args)
    sequence_dir = args.output_root / "sequence_comparison"
    parquet_path = sequence_dir / "sequence_metrics.parquet"
    summary_path = sequence_dir / "sequence_comparison_summary.json"
    try:
        import pandas as pd
    except ImportError as error:
        raise RuntimeError("install the optional 'analysis' dependencies first") from error
    flat_rows = [
        {
            "case_id": row["case_id"],
            "draw_id": row["draw_id"],
            "scheme": row["scheme"],
            "fixture_key_index": row["fixture_key_index"],
            "sequence_sha256": row["sequence_sha256"],
            "likelihood_token_count": row["likelihood_token_count"],
            **row["metrics"],
        }
        for row in rows
    ]
    if parquet_path.exists():
        raise FileExistsError(f"refusing to replace existing output: {parquet_path}")
    pd.DataFrame(flat_rows).sort_values(["case_id", "draw_id", "scheme"]).to_parquet(
        parquet_path, index=False
    )
    main: dict[str, dict[str, Any]] = {}
    for metric in METRICS:
        main[metric] = compare_metric(
            rows=rows,
            metric=metric,
            draw_filter=None,
            bootstrap_replicates=args.bootstrap_replicates,
            permutation_replicates=args.permutation_replicates,
            seed=public_replay_seed(
                "carbon-synthid-validation-v1/sequence-comparison",
                metric,
                str(args.analysis_seed),
            ),
        )
    p_values = {metric: value["paired"]["p_value"] for metric, value in main.items()}
    bh = benjamini_hochberg(p_values)
    bonferroni = bonferroni_adjusted(p_values)
    for metric in METRICS:
        main[metric]["paired"]["benjamini_hochberg_p_value"] = bh[metric]
        main[metric]["paired"]["bonferroni_p_value"] = bonferroni[metric]
    per_draw: dict[str, dict[str, Any]] = {}
    for draw_id in sorted({int(row["draw_id"]) for row in rows}):
        per_draw[str(draw_id)] = {
            metric: compare_metric(
                rows=rows,
                metric=metric,
                draw_filter=draw_id,
                bootstrap_replicates=args.bootstrap_replicates,
                permutation_replicates=args.permutation_replicates,
                seed=public_replay_seed(
                    "carbon-synthid-validation-v1/sequence-comparison/per-draw",
                    str(draw_id),
                    metric,
                    str(args.analysis_seed),
                ),
            )
            for metric in METRICS
        }
    summary = {
        "schema_version": 1,
        "classification": "validation_artifact_not_admitted_evidence",
        "complete": True,
        "experiment_id": "carbon_synthid_validation_v1",
        "question": "matched full-sequence Carbon behavior",
        "policy_id": "C_tok",
        "model_id": "HuggingFaceBio/Carbon-500M",
        "revision": "9796b752108258c1d365089f842e62e6c0547704",
        "sequence_count": len(rows),
        "pair_count": len(rows) // 2,
        "prompt_count": len({row["case_id"] for row in rows}),
        "draw_indices": sorted({int(row["draw_id"]) for row in rows}),
        "statistical_cluster": "case_id",
        "likelihood": {
            "definition": (
                "teacher-forced mean negative log-likelihood per generated canonical 6-mer "
                "under the same frozen C_tok law, conditioned on the original prompt"
            ),
            "prompt_tokens_in_loss": False,
            "model_forward_calls": len(rows),
        },
        "multiple_testing_family": list(METRICS),
        "main_key_averaged": main,
        "per_fixture_key_draw": per_draw,
        "inputs": input_artifacts,
        "artifacts": {
            "sequence_metrics": {
                "path": str(parquet_path),
                "sha256": sha256_file(str(parquet_path)),
            }
        },
        "boundary": (
            "These are sequence-level model scores and biological proxies, not biological "
            "function, viability, or safety measurements. Statistical significance is reported "
            "with effect size and does not by itself establish practical importance."
        ),
    }
    serialized = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if summary_path.exists() and summary_path.read_text(encoding="utf-8") != serialized:
        raise FileExistsError(f"refusing to replace different output: {summary_path}")
    if not summary_path.exists():
        summary_path.write_text(serialized, encoding="utf-8")
    return {
        "summary": str(summary_path),
        "summary_sha256": sha256_file(str(summary_path)),
        "sequence_metrics": str(parquet_path),
        "sequence_count": len(rows),
    }


def main() -> int:
    args = parse_args()
    draw_indices = tuple(sorted(set(args.draw_index or range(2))))
    if any(draw not in range(2) for draw in draw_indices):
        raise ValueError("draw indices must lie in 0..1")
    cases = load_context_cases_jsonl(args.cohort_jsonl)
    cases_by_id = {case.case_id: case for case in cases}
    selected_ids = set(args.case_id or cases_by_id)
    if not selected_ids <= set(cases_by_id):
        raise ValueError("an unknown case-id was requested")
    records: list[dict[str, Any]] = []
    input_artifacts: list[dict[str, str]] = []
    for draw_id in draw_indices:
        path = args.output_root / "generation" / f"draw_{draw_id:02d}_sequences.jsonl"
        if not path.is_file():
            raise FileNotFoundError(f"missing finalized generation draw: {path}")
        input_artifacts.append({"path": str(path), "sha256": sha256_file(str(path))})
        for record in load_jsonl(path):
            if str(record["case_id"]) in selected_ids:
                records.append(record)
    expected_identities = len(selected_ids) * len(draw_indices) * 2
    if len(records) != expected_identities or len(
        {sequence_identity(row) for row in records}
    ) != len(records):
        raise ValueError("selected generation records are incomplete or duplicated")
    shards_dir = args.output_root / "sequence_comparison" / "metric_shards"
    sessions_dir = args.output_root / "sequence_comparison" / "sessions"
    shards_dir.mkdir(parents=True, exist_ok=True)
    pending: list[dict[str, Any]] = []
    for record in records:
        path = shards_dir / shard_name(record)
        if path.exists():
            validate_shard(json.loads(path.read_text(encoding="utf-8")), record, args)
        else:
            pending.append(record)
    if pending:
        try:
            import torch
        except ImportError as error:
            raise RuntimeError("install the optional 'models' dependencies first") from error
        if args.device == "mps" and not torch.backends.mps.is_available():
            raise RuntimeError("MPS is unavailable")
        if args.device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable")
        if args.device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        run_started = time.perf_counter()
        load_started = time.perf_counter()
        adapter = load_adapter(
            "C_tok",
            device=args.device,
            dtype=args.dtype,
            allow_cpu_fallback=False,
            cache_dir=args.cache_dir,
            local_files_only=args.local_files_only,
        )
        model_load_seconds = time.perf_counter() - load_started
        for completed, record in enumerate(pending, start=1):
            case = cases_by_id[str(record["case_id"])]
            sequence = str(record["generated_dna"])
            started = time.perf_counter()
            metrics = proxy_metrics(sequence)
            for k in (1, 2, 3):
                metrics[f"js_divergence_from_prompt_k{k}_bits"] = kmer_divergence_bits(
                    sequence, case.sequence, k
                )
            likelihood = adapter.continuation_likelihood(case.sequence, sequence)
            metrics["mean_negative_log_likelihood_per_token"] = (
                likelihood.mean_negative_log_likelihood
            )
            metrics["perplexity"] = likelihood.perplexity
            shard = {
                "schema_version": 1,
                "classification": "validation_artifact_not_admitted_evidence",
                "complete": True,
                "policy_id": "C_tok",
                "case_id": record["case_id"],
                "draw_id": int(record["draw_id"]),
                "scheme": record["scheme"],
                "fixture_key_index": int(record["fixture_key_index"]),
                "prompt_sequence_sha256": case.sequence_sha256,
                "sequence_sha256": record["sequence_sha256"],
                "generated_bases": len(sequence),
                "device": args.device,
                "dtype": args.dtype,
                "likelihood_token_count": likelihood.token_count,
                "metrics": metrics,
                "wall_seconds": time.perf_counter() - started,
            }
            atomic_write_json(shards_dir / shard_name(record), shard)
            print(
                json.dumps(
                    {
                        "case_id": record["case_id"],
                        "draw_id": record["draw_id"],
                        "scheme": record["scheme"],
                        "completed_in_session": completed,
                        "pending_in_session": len(pending) - completed,
                        "mean_nll": likelihood.mean_negative_log_likelihood,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        mps_memory: dict[str, float] = {}
        if args.device == "mps":
            mps_memory = {
                "mps_current_allocated_gib": float(torch.mps.current_allocated_memory())
                / (1024.0**3),
                "mps_driver_allocated_gib": float(torch.mps.driver_allocated_memory())
                / (1024.0**3),
            }
        cuda_memory: dict[str, float | str | list[int]] = {}
        if args.device == "cuda":
            cuda_memory = {
                "cuda_device_name": torch.cuda.get_device_name(),
                "cuda_device_capability": list(torch.cuda.get_device_capability()),
                "cuda_peak_allocated_gib": float(torch.cuda.max_memory_allocated()) / (1024.0**3),
                "cuda_peak_reserved_gib": float(torch.cuda.max_memory_reserved()) / (1024.0**3),
                "torch_version": torch.__version__,
                "torch_cuda_version": str(torch.version.cuda),
            }
        session = {
            "schema_version": 1,
            "sequence_count": len(pending),
            "model_load_seconds": model_load_seconds,
            "wall_seconds": time.perf_counter() - run_started,
            "process_peak_rss_gib": process_peak_rss_gib(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "device": args.device,
            "dtype": args.dtype,
            **mps_memory,
            **cuda_memory,
        }
        sessions_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(
            sessions_dir / f"session_{time.time_ns()}_{os.getpid()}.json",
            session,
        )
        adapter = None
        gc.collect()
        if args.device == "mps":
            torch.mps.empty_cache()
        elif args.device == "cuda":
            torch.cuda.empty_cache()
    result: dict[str, Any] = {
        "selected_sequences": len(records),
        "computed_now": len(pending),
        "resumed_sequences": len(records) - len(pending),
        "metric_shards": str(shards_dir),
    }
    if args.finalize:
        result["finalized"] = finalize(
            args=args,
            records=records,
            shards_dir=shards_dir,
            input_artifacts=input_artifacts,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
