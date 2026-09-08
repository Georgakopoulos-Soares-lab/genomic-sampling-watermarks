#!/usr/bin/env python3
"""Resumable one-step audit of the GENERATOR SynthID tournament sampler."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import random
import resource
import struct
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.gof import monte_carlo_goodness_of_fit, summarize_p_values  # noqa: E402
from genomic_watermarks.large_validation import (  # noqa: E402
    benjamini_hochberg,
    bonferroni_adjusted,
    paired_cluster_summary,
    sha256_file,
)
from genomic_watermarks.metrics import (  # noqa: E402
    inverse_simpson_support,
    jensen_shannon_divergence_bits,
    shannon_entropy_bits,
    top1_mass,
    total_variation_distance,
)
from genomic_watermarks.models.huggingface import load_adapter  # noqa: E402
from genomic_watermarks.pilot import load_context_cases_jsonl, numeric_summary  # noqa: E402
from genomic_watermarks.synthid import (  # noqa: E402
    DEFAULT_CONTEXT_HISTORY_SIZE,
    DEFAULT_CONTEXT_TOKENS,
    DEFAULT_DEPTH,
    SYNTHID_SCHEME,
    KeyedTournament,
    tournament_distribution,
)
from genomic_watermarks.watermark import (  # noqa: E402
    ORDINARY_SCHEME,
    public_replay_seed,
)

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_large_v1/prompts.jsonl"
PUBLIC_PRESERVATION_FIXTURE = b"genomic-sampling-watermarks/public-preservation-fixture/v1"
BROKEN_SCHEME = "broken-skip-tournament-negative-control-v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--draw-zero-sequences", type=Path, required=True)
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--state-token-index", type=int, default=64)
    parser.add_argument("--draws", type=int, default=5_000)
    parser.add_argument("--replicates", type=int, default=999)
    parser.add_argument("--gof-seed", type=int, default=2718)
    parser.add_argument("--negative-control-states", type=int, default=8)
    parser.add_argument(
        "--experiment-label", default="generator-synthid-validation-v1/distribution"
    )
    parser.add_argument("--tournament-depth", type=int, default=DEFAULT_DEPTH)
    parser.add_argument("--context-tokens", type=int, default=DEFAULT_CONTEXT_TOKENS)
    parser.add_argument("--context-history-size", type=int, default=DEFAULT_CONTEXT_HISTORY_SIZE)
    parser.add_argument("--key-average-replicates", type=int, default=64)
    parser.add_argument("--device", choices=("mps", "cuda", "cpu"), default="mps")
    parser.add_argument("--dtype", choices=("bfloat16", "float16", "float32"), default="bfloat16")
    parser.add_argument("--cache-dir", default=".cache/huggingface")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--expected-state-count", type=int)
    parser.add_argument("--bootstrap-replicates", type=int, default=20_000)
    parser.add_argument("--permutation-replicates", type=int, default=100_000)
    parser.add_argument("--analysis-seed", type=int, default=2718)
    return parser.parse_args()


def process_peak_rss_gib() -> float:
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    bytes_used = value if sys.platform == "darwin" else value * 1024.0
    return bytes_used / (1024.0**3)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def selected_cases(cases: tuple[Any, ...], requested: list[str] | None) -> tuple[Any, ...]:
    if not requested:
        return cases
    if len(set(requested)) != len(requested):
        raise ValueError("case-id values must be unique")
    by_id = {case.case_id: case for case in cases}
    missing = [case_id for case_id in requested if case_id not in by_id]
    if missing:
        raise ValueError(f"unknown case-id value(s): {', '.join(missing)}")
    return tuple(by_id[case_id] for case_id in requested)


def distribution_sha256(items: tuple[str, ...], probabilities: tuple[float, ...]) -> str:
    digest = hashlib.sha256()
    for item, probability in zip(items, probabilities, strict=True):
        digest.update(item.encode("ascii"))
        digest.update(struct.pack(">d", probability))
    return digest.hexdigest()


def empirical_metrics(counts: list[int], probabilities: tuple[float, ...]) -> dict[str, float]:
    total = sum(counts)
    empirical = tuple(count / total for count in counts)
    return {
        "total_variation_distance": total_variation_distance(empirical, probabilities),
        "jensen_shannon_divergence_bits": jensen_shannon_divergence_bits(empirical, probabilities),
        "maximum_absolute_frequency_error": max(
            abs(observed - declared)
            for observed, declared in zip(empirical, probabilities, strict=True)
        ),
    }


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to replace completed shard: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def validate_shard(
    shard: dict[str, Any],
    *,
    case: Any,
    args: argparse.Namespace,
    negative_control: bool,
) -> None:
    expected = {
        "complete": True,
        "policy_id": "G_tok",
        "case_id": case.case_id,
        "draw_id": 0,
        "prompt_sequence_sha256": case.sequence_sha256,
        "state_token_index": args.state_token_index,
        "draws_per_arm": args.draws,
        "replicates": args.replicates,
        "tournament_depth": args.tournament_depth,
        "context_tokens": args.context_tokens,
        "context_history_size": args.context_history_size,
        "key_average_replicates": args.key_average_replicates,
        "negative_control_included": negative_control,
        "device": args.device,
        "dtype": args.dtype,
    }
    for field, value in expected.items():
        if shard.get(field) != value:
            raise ValueError(f"distribution shard {case.case_id} has inconsistent {field}")
    items = shard.get("items")
    model_probabilities = shard.get("model_probabilities")
    tournament_probabilities = shard.get("tournament_probabilities")
    if (
        not isinstance(items, list)
        or not isinstance(model_probabilities, list)
        or not isinstance(tournament_probabilities, list)
        or len(items) != 4096
    ):
        raise ValueError("distribution shard does not freeze a 4,096-way law")
    if len(model_probabilities) != len(items) or len(tournament_probabilities) != len(items):
        raise ValueError("distribution shard has a malformed probability vector")
    if (
        distribution_sha256(tuple(items), tuple(model_probabilities))
        != shard["model_distribution_sha256"]
    ):
        raise ValueError("model distribution checksum does not match")
    if (
        distribution_sha256(tuple(items), tuple(tournament_probabilities))
        != shard["tournament_distribution_sha256"]
    ):
        raise ValueError("tournament distribution checksum does not match")
    for arm in ("watermarked", "ordinary"):
        counts = shard[arm]["counts"]
        if len(counts) != 4096 or sum(counts) != args.draws:
            raise ValueError(f"distribution shard has invalid {arm} counts")
    if negative_control:
        counts = shard["negative_control"]["counts"]
        if len(counts) != 4096 or sum(counts) != args.draws:
            raise ValueError("distribution shard has invalid negative-control counts")


def p_value_summary(p_values: dict[str, float]) -> dict[str, Any]:
    base = summarize_p_values(p_values)
    bh = benjamini_hochberg(p_values)
    bonferroni = bonferroni_adjusted(p_values)
    return {
        **base,
        "benjamini_hochberg_rejections": sum(value < 0.05 for value in bh.values()),
        "benjamini_hochberg_adjusted": bh,
        "bonferroni_adjusted": bonferroni,
    }


def finalize(
    *,
    args: argparse.Namespace,
    all_cases: tuple[Any, ...],
    selected: tuple[Any, ...],
    shards_dir: Path,
    negative_ids: set[str],
) -> dict[str, Any]:
    expected = args.expected_state_count or len(selected)
    if expected <= 0:
        raise ValueError("expected-state-count must be positive")
    by_id = {case.case_id: case for case in all_cases}
    shards: dict[str, dict[str, Any]] = {}
    for path in sorted(shards_dir.glob("*.json")):
        shard = json.loads(path.read_text(encoding="utf-8"))
        case_id = str(shard.get("case_id"))
        case = by_id.get(case_id)
        if case is None:
            raise ValueError(f"unknown case in distribution shard: {case_id}")
        validate_shard(
            shard,
            case=case,
            args=args,
            negative_control=case_id in negative_ids,
        )
        if case_id in shards:
            raise ValueError(f"duplicate distribution shard for {case_id}")
        shards[case_id] = shard
    if len(shards) != expected:
        raise ValueError(f"found {len(shards)} completed states, expected {expected}")
    ordered = [case.case_id for case in all_cases if case.case_id in shards]
    distribution_dir = args.output_root / "distribution"
    manifest_path = distribution_dir / "state_manifest.jsonl"
    parquet_path = distribution_dir / "fixed_state_trials.parquet"
    summary_path = distribution_dir / "distribution_summary.json"
    manifest_rows: list[dict[str, Any]] = []
    parquet_rows: list[dict[str, Any]] = []
    watermarked_p: dict[str, float] = {}
    ordinary_p: dict[str, float] = {}
    broken_p: dict[str, float] = {}
    for case_id in ordered:
        shard = shards[case_id]
        watermarked_p[case_id] = float(shard["watermarked"]["p_value"])
        ordinary_p[case_id] = float(shard["ordinary"]["p_value"])
        if shard["negative_control_included"]:
            broken_p[case_id] = float(shard["negative_control"]["p_value"])
        manifest_rows.append(
            {
                key: shard[key]
                for key in (
                    "case_id",
                    "draw_id",
                    "prompt_sequence_sha256",
                    "ordinary_prefix_sha256",
                    "state_context_sha256",
                    "state_token_index",
                    "context_bases",
                    "model_distribution_sha256",
                    "tournament_distribution_sha256",
                    "entropy_bits",
                    "top1_mass",
                    "effective_support",
                    "key_conditional_total_variation_distance",
                    "key_conditional_jensen_shannon_divergence_bits",
                    "key_averaged_total_variation_distance",
                    "key_averaged_jensen_shannon_divergence_bits",
                    "key_averaged_maximum_absolute_error",
                    "key_average_replicates",
                    "negative_control_included",
                )
            }
        )
        parquet_rows.append(
            {
                "case_id": case_id,
                "draw_id": 0,
                "state_token_index": args.state_token_index,
                "model_distribution_sha256": shard["model_distribution_sha256"],
                "tournament_distribution_sha256": shard["tournament_distribution_sha256"],
                "tokens": shard["items"],
                "model_probabilities": shard["model_probabilities"],
                "tournament_probabilities": shard["tournament_probabilities"],
                "watermarked_counts": shard["watermarked"]["counts"],
                "ordinary_counts": shard["ordinary"]["counts"],
                "negative_control_counts": (
                    shard["negative_control"]["counts"]
                    if shard["negative_control_included"]
                    else None
                ),
                "watermarked_g_statistic": shard["watermarked"]["g_statistic"],
                "watermarked_p_value": shard["watermarked"]["p_value"],
                "ordinary_g_statistic": shard["ordinary"]["g_statistic"],
                "ordinary_p_value": shard["ordinary"]["p_value"],
                "negative_control_g_statistic": (
                    shard["negative_control"]["g_statistic"]
                    if shard["negative_control_included"]
                    else None
                ),
                "negative_control_p_value": (
                    shard["negative_control"]["p_value"]
                    if shard["negative_control_included"]
                    else None
                ),
            }
        )
    manifest_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in manifest_rows)
    if manifest_path.exists() and manifest_path.read_text(encoding="utf-8") != manifest_text:
        raise FileExistsError(f"refusing to replace different output: {manifest_path}")
    if not manifest_path.exists():
        manifest_path.write_text(manifest_text, encoding="utf-8")
    try:
        import pandas as pd
    except ImportError as error:
        raise RuntimeError("install the optional 'analysis' dependencies first") from error
    if parquet_path.exists():
        raise FileExistsError(f"refusing to replace existing output: {parquet_path}")
    pd.DataFrame(parquet_rows).to_parquet(parquet_path, index=False)
    error_comparisons: dict[str, Any] = {}
    for metric in (
        "total_variation_distance",
        "jensen_shannon_divergence_bits",
        "maximum_absolute_frequency_error",
        "g_statistic",
    ):
        differences = {
            case_id: (
                float(shards[case_id]["watermarked"][metric])
                - float(shards[case_id]["ordinary"][metric]),
            )
            for case_id in ordered
        }
        result = paired_cluster_summary(
            differences,
            bootstrap_replicates=args.bootstrap_replicates,
            permutation_replicates=args.permutation_replicates,
            seed=public_replay_seed(args.experiment_label, metric, str(args.analysis_seed)),
        )
        error_comparisons[metric] = asdict(result)
    comparison_p = {name: value["p_value"] for name, value in error_comparisons.items()}
    comparison_bh = benjamini_hochberg(comparison_p)
    for metric in error_comparisons:
        error_comparisons[metric]["benjamini_hochberg_p_value"] = comparison_bh[metric]
    summary = {
        "schema_version": 1,
        "classification": "validation_artifact_not_admitted_evidence",
        "complete": True,
        "experiment_id": "generator_synthid_validation_v1",
        "question": "one-step tournament implementation and finite-key marginal audit",
        "policy_id": "G_tok",
        "model_id": "GenerTeam/GENERator-v2-eukaryote-1.2b-base",
        "revision": "c41b0018da9ee13b9e96ee54647de8da381ccd72",
        "cohort_id": all_cases[0].cohort_id,
        "state_selection": (
            "declared G_tok law after the first 64 tokens of draw-0's ordinary trajectory"
        ),
        "state_token_index": args.state_token_index,
        "state_count": len(ordered),
        "model_forward_calls": len(ordered),
        "draws_per_state_per_arm": args.draws,
        "monte_carlo_replicates": args.replicates,
        "tournament": {
            "scheme": SYNTHID_SCHEME,
            "depth": args.tournament_depth,
            "context_tokens": args.context_tokens,
            "context_history_size": args.context_history_size,
            "key_average_replicates_per_state": args.key_average_replicates,
        },
        "key_conditional_divergence": {
            "total_variation_distance": numeric_summary(
                float(shards[case_id]["key_conditional_total_variation_distance"])
                for case_id in ordered
            ),
            "jensen_shannon_divergence_bits": numeric_summary(
                float(shards[case_id]["key_conditional_jensen_shannon_divergence_bits"])
                for case_id in ordered
            ),
        },
        "finite_key_averaged_divergence": {
            "total_variation_distance": numeric_summary(
                float(shards[case_id]["key_averaged_total_variation_distance"])
                for case_id in ordered
            ),
            "jensen_shannon_divergence_bits": numeric_summary(
                float(shards[case_id]["key_averaged_jensen_shannon_divergence_bits"])
                for case_id in ordered
            ),
            "maximum_absolute_error": numeric_summary(
                float(shards[case_id]["key_averaged_maximum_absolute_error"]) for case_id in ordered
            ),
        },
        "watermarked_p_values": p_value_summary(watermarked_p),
        "ordinary_p_values": p_value_summary(ordinary_p),
        "negative_control": {
            "scheme": BROKEN_SCHEME,
            "state_selection": "lowest SHA-256 rank of public case_id under the frozen label",
            "state_count": len(broken_p),
            "p_values": p_value_summary(broken_p) if broken_p else None,
        },
        "paired_watermarked_minus_ordinary_error": error_comparisons,
        "artifacts": {
            "state_manifest": {
                "path": str(manifest_path),
                "sha256": sha256_file(str(manifest_path)),
            },
            "fixed_state_trials": {
                "path": str(parquet_path),
                "sha256": sha256_file(str(parquet_path)),
            },
        },
        "boundary": (
            "The watermarked arm is tested against its exact fixed-key tournament law, while the "
            "ordinary arm is tested against G_tok. A fixed key and context intentionally reweight "
            "the law; finite public-key averaging is reported separately and is not a proof of "
            "cryptographic pseudorandomness or sequence-level equality."
        ),
    }
    serialized_summary = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if summary_path.exists() and summary_path.read_text(encoding="utf-8") != serialized_summary:
        raise FileExistsError(f"refusing to replace different output: {summary_path}")
    if not summary_path.exists():
        summary_path.write_text(serialized_summary, encoding="utf-8")
    return {
        "summary": str(summary_path),
        "summary_sha256": sha256_file(str(summary_path)),
        "state_count": len(ordered),
        "fixed_state_trials": str(parquet_path),
    }


def main() -> int:
    args = parse_args()
    if args.state_token_index < args.context_tokens:
        raise ValueError("state-token-index must cover the tournament context")
    if args.draws <= 0 or args.replicates <= 0:
        raise ValueError("draws and replicates must be positive")
    if args.gof_seed < 0 or args.negative_control_states < 0:
        raise ValueError("seeds and control-state count must be non-negative")
    if args.key_average_replicates <= 0:
        raise ValueError("key-average-replicates must be positive")
    all_cases = load_context_cases_jsonl(args.cohort_jsonl)
    selected = selected_cases(all_cases, args.case_id)
    sequence_rows = load_jsonl(args.draw_zero_sequences)
    ordinary = {
        str(row["case_id"]): str(row["generated_dna"])
        for row in sequence_rows
        if int(row["draw_id"]) == 0 and str(row["scheme"]) == ORDINARY_SCHEME
    }
    missing = [case.case_id for case in selected if case.case_id not in ordinary]
    if missing:
        raise ValueError(f"draw-zero ordinary sequences are missing {len(missing)} selected cases")
    if any(len(ordinary[case.case_id]) < args.state_token_index * 6 for case in selected):
        raise ValueError("an ordinary continuation is shorter than the frozen state position")
    # Ranking the selected set keeps the same eight-of-256 rule in the full
    # run while guaranteeing that a reduced smoke run actually exercises the
    # deliberately wrong sampler.
    ranked = sorted(
        (case.case_id for case in selected),
        key=lambda case_id: hashlib.sha256(
            f"generator-synthid-validation-v1/distribution-negative-control\x00{case_id}".encode()
        ).digest(),
    )
    negative_ids = set(ranked[: min(args.negative_control_states, len(ranked))])
    distribution_dir = args.output_root / "distribution"
    shards_dir = distribution_dir / "state_shards"
    sessions_dir = distribution_dir / "sessions"
    shards_dir.mkdir(parents=True, exist_ok=True)
    pending: list[Any] = []
    for case in selected:
        path = shards_dir / f"{case.case_id}.json"
        if path.exists():
            validate_shard(
                json.loads(path.read_text(encoding="utf-8")),
                case=case,
                args=args,
                negative_control=case.case_id in negative_ids,
            )
        else:
            pending.append(case)

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
            "G_tok",
            device=args.device,
            dtype=args.dtype,
            allow_cpu_fallback=False,
            cache_dir=args.cache_dir,
            local_files_only=args.local_files_only,
        )
        model_load_seconds = time.perf_counter() - load_started
        stream_domain = f"{args.experiment_label}/{all_cases[0].cohort_id}/G_tok"
        tournament = KeyedTournament(
            key=PUBLIC_PRESERVATION_FIXTURE,
            domain=stream_domain,
            depth=args.tournament_depth,
            context_tokens=args.context_tokens,
            context_history_size=args.context_history_size,
        )
        for completed, case in enumerate(pending, start=1):
            prefix = ordinary[case.case_id][: args.state_token_index * 6]
            context = case.sequence + prefix
            state_started = time.perf_counter()
            state = adapter.next_distribution(context)
            items = tuple(state.tokens)
            probabilities = tuple(float(value) for value in state.probabilities)
            recent = tuple(
                prefix[index : index + 6]
                for index in range(len(prefix) - args.context_tokens * 6, len(prefix), 6)
            )
            tournament_law = tournament_distribution(items, probabilities, recent, tournament)
            tournament_probabilities = tournament_law.probabilities

            averaged_probabilities = [0.0] * len(items)
            for key_index in range(args.key_average_replicates):
                derived_key = hashlib.sha256(
                    PUBLIC_PRESERVATION_FIXTURE
                    + b"\x00key-average\x00"
                    + case.case_id.encode()
                    + key_index.to_bytes(8, "big")
                ).digest()
                key_tournament = KeyedTournament(
                    key=derived_key,
                    domain=stream_domain,
                    depth=args.tournament_depth,
                    context_tokens=args.context_tokens,
                    context_history_size=args.context_history_size,
                )
                key_law = tournament_distribution(items, probabilities, recent, key_tournament)
                for token_index, probability in enumerate(key_law.probabilities):
                    averaged_probabilities[token_index] += probability / args.key_average_replicates
            key_average = tuple(averaged_probabilities)
            watermarked_counts = [0] * len(items)
            ordinary_counts = [0] * len(items)
            broken_counts = [0] * len(items)
            watermarked_rng = random.Random(
                public_replay_seed(args.experiment_label, case.case_id, SYNTHID_SCHEME)
            )
            ordinary_rng = random.Random(
                public_replay_seed(args.experiment_label, case.case_id, ORDINARY_SCHEME)
            )
            broken_rng = random.Random(
                public_replay_seed(args.experiment_label, case.case_id, BROKEN_SCHEME)
            )
            token_indices = range(len(items))
            for token_index in watermarked_rng.choices(
                token_indices, weights=tournament_probabilities, k=args.draws
            ):
                watermarked_counts[token_index] += 1
            for token_index in ordinary_rng.choices(
                token_indices, weights=probabilities, k=args.draws
            ):
                ordinary_counts[token_index] += 1
            if case.case_id in negative_ids:
                for token_index in broken_rng.choices(
                    token_indices, weights=probabilities, k=args.draws
                ):
                    broken_counts[token_index] += 1

            def arm_result(
                counts: list[int],
                scheme: str,
                *,
                state_case_id: str = case.case_id,
                state_probabilities: tuple[float, ...] = probabilities,
            ) -> dict[str, Any]:
                seed = public_replay_seed(
                    args.experiment_label,
                    state_case_id,
                    scheme,
                    f"gof-base-seed={args.gof_seed}",
                )
                gof = monte_carlo_goodness_of_fit(
                    counts,
                    state_probabilities,
                    replicates=args.replicates,
                    seed=seed,
                )
                return {
                    "scheme": scheme,
                    "counts": counts,
                    "g_statistic": gof.statistic,
                    "p_value": gof.p_value,
                    "gof_seed": seed,
                    "replicate_statistic_mean": gof.replicate_statistic_mean,
                    **empirical_metrics(counts, state_probabilities),
                }

            shard: dict[str, Any] = {
                "schema_version": 1,
                "classification": "validation_artifact_not_admitted_evidence",
                "complete": True,
                "policy_id": "G_tok",
                "model_id": adapter.policy.model_id,
                "revision": adapter.policy.revision,
                "cohort_id": all_cases[0].cohort_id,
                "case_id": case.case_id,
                "draw_id": 0,
                "prompt_sequence_sha256": case.sequence_sha256,
                "ordinary_prefix_sha256": hashlib.sha256(prefix.encode("ascii")).hexdigest(),
                "state_context_sha256": hashlib.sha256(context.encode("ascii")).hexdigest(),
                "state_token_index": args.state_token_index,
                "context_bases": len(context),
                "model_distribution_sha256": distribution_sha256(items, probabilities),
                "tournament_distribution_sha256": distribution_sha256(
                    items, tournament_probabilities
                ),
                "items": list(items),
                "model_probabilities": list(probabilities),
                "tournament_probabilities": list(tournament_probabilities),
                "entropy_bits": shannon_entropy_bits(probabilities),
                "top1_mass": top1_mass(probabilities),
                "effective_support": inverse_simpson_support(probabilities),
                "draws_per_arm": args.draws,
                "replicates": args.replicates,
                "tournament_depth": args.tournament_depth,
                "context_tokens": args.context_tokens,
                "context_history_size": args.context_history_size,
                "device": args.device,
                "dtype": args.dtype,
                "key_conditional_total_variation_distance": total_variation_distance(
                    tournament_probabilities, probabilities
                ),
                "key_conditional_jensen_shannon_divergence_bits": (
                    jensen_shannon_divergence_bits(tournament_probabilities, probabilities)
                ),
                "key_average_replicates": args.key_average_replicates,
                "key_averaged_total_variation_distance": total_variation_distance(
                    key_average, probabilities
                ),
                "key_averaged_jensen_shannon_divergence_bits": (
                    jensen_shannon_divergence_bits(key_average, probabilities)
                ),
                "key_averaged_maximum_absolute_error": max(
                    abs(averaged - declared)
                    for averaged, declared in zip(key_average, probabilities, strict=True)
                ),
                "watermarked": arm_result(
                    watermarked_counts,
                    SYNTHID_SCHEME,
                    state_probabilities=tournament_probabilities,
                ),
                "ordinary": arm_result(ordinary_counts, ORDINARY_SCHEME),
                "negative_control_included": case.case_id in negative_ids,
                "negative_control": (
                    arm_result(
                        broken_counts,
                        BROKEN_SCHEME,
                        state_probabilities=tournament_probabilities,
                    )
                    if case.case_id in negative_ids
                    else None
                ),
                "state_wall_seconds": time.perf_counter() - state_started,
            }
            atomic_write_json(shards_dir / f"{case.case_id}.json", shard)
            print(
                json.dumps(
                    {
                        "case_id": case.case_id,
                        "completed_in_session": completed,
                        "pending_in_session": len(pending) - completed,
                        "watermarked_p_value": shard["watermarked"]["p_value"],
                        "ordinary_p_value": shard["ordinary"]["p_value"],
                        "negative_control_p_value": (
                            shard["negative_control"]["p_value"]
                            if shard["negative_control_included"]
                            else None
                        ),
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
            "case_count": len(pending),
            "case_ids": [case.case_id for case in pending],
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
        atomic_write_json(sessions_dir / f"session_{time.time_ns()}_{os.getpid()}.json", session)
        adapter = None
        gc.collect()
        if args.device == "mps":
            torch.mps.empty_cache()
        elif args.device == "cuda":
            torch.cuda.empty_cache()

    result: dict[str, Any] = {
        "selected_states": len(selected),
        "computed_now": len(pending),
        "resumed_states": len(selected) - len(pending),
        "state_shards": str(shards_dir),
    }
    if args.finalize:
        result["finalized"] = finalize(
            args=args,
            all_cases=all_cases,
            selected=selected,
            shards_dir=shards_dir,
            negative_ids=negative_ids,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
