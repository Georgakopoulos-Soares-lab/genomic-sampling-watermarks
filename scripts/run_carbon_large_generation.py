#!/usr/bin/env python3
"""Resumable matched SynthID tournament generation for one Carbon draw.

Each completed prompt is an immutable JSON shard containing both arms.  A crash
can therefore lose at most the current prompt.  Finalization deterministically
assembles the requested ``draw_XX_sequences.jsonl`` without overwriting an
existing completed artifact.
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
import shlex
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.large_validation import fixture_key, sha256_file  # noqa: E402
from genomic_watermarks.models.huggingface import load_adapter  # noqa: E402
from genomic_watermarks.pilot import (  # noqa: E402
    cohort_case_digest,
    load_context_cases_jsonl,
    numeric_summary,
)
from genomic_watermarks.synthid import (  # noqa: E402
    DEFAULT_CONTEXT_HISTORY_SIZE,
    DEFAULT_CONTEXT_TOKENS,
    DEFAULT_DEPTH,
    SYNTHID_SCHEME,
    KeyedTournament,
    generate_synthid,
    score_synthid_tokens,
)
from genomic_watermarks.watermark import (  # noqa: E402
    ORDINARY_SCHEME,
    generate_ordinary,
    public_replay_seed,
)

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_large_v1/prompts.jsonl"
DEFAULT_LABEL = "carbon-synthid-validation-v1"
EXPERIMENT_ID = "carbon_synthid_validation_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--draw-index", type=int, required=True, choices=(0, 1))
    parser.add_argument("--steps", type=int, default=512)
    parser.add_argument("--experiment-label", default=DEFAULT_LABEL)
    parser.add_argument("--tournament-depth", type=int, default=DEFAULT_DEPTH)
    parser.add_argument("--context-tokens", type=int, default=DEFAULT_CONTEXT_TOKENS)
    parser.add_argument("--context-history-size", type=int, default=DEFAULT_CONTEXT_HISTORY_SIZE)
    parser.add_argument("--device", choices=("mps", "cuda", "cpu"), default="mps")
    parser.add_argument("--dtype", choices=("bfloat16", "float16", "float32"), default="bfloat16")
    parser.add_argument("--cache-dir", default=".cache/huggingface")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--finalize-only", action="store_true")
    parser.add_argument("--expected-case-count", type=int)
    return parser.parse_args()


def process_peak_rss_gib() -> float:
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    bytes_used = value if sys.platform == "darwin" else value * 1024.0
    return bytes_used / (1024.0**3)


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


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to replace completed shard: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    if temporary.exists():
        raise FileExistsError(f"temporary output already exists: {temporary}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def validate_shard(
    shard: dict[str, Any],
    *,
    case: Any,
    draw_index: int,
    steps: int,
    experiment_label: str,
    cohort_id: str,
    device: str,
    dtype: str,
) -> None:
    expected = {
        "case_id": case.case_id,
        "draw_id": draw_index,
        "fixture_key_index": draw_index,
        "policy_id": "C_tok",
        "cohort_id": cohort_id,
        "experiment_label": experiment_label,
        "generated_tokens": steps,
        "prompt_sequence_sha256": case.sequence_sha256,
        "device": device,
        "dtype": dtype,
    }
    for field, value in expected.items():
        if shard.get(field) != value:
            raise ValueError(f"generation shard {case.case_id} has inconsistent {field}")
    if not bool(shard.get("complete")):
        raise ValueError(f"generation shard {case.case_id} is not complete")
    arms = shard.get("arms")
    if not isinstance(arms, list) or len(arms) != 2:
        raise ValueError(f"generation shard {case.case_id} does not contain two arms")
    schemes = {str(arm.get("scheme")) for arm in arms}
    if schemes != {SYNTHID_SCHEME, ORDINARY_SCHEME}:
        raise ValueError(f"generation shard {case.case_id} has wrong arms")
    for arm in arms:
        dna = str(arm["generated_dna"])
        if len(dna) != steps * 6 or set(dna) - set("ACGT"):
            raise ValueError(f"generation shard {case.case_id} has invalid DNA")
        if hashlib.sha256(dna.encode("ascii")).hexdigest() != str(arm["sequence_sha256"]):
            raise ValueError(f"generation shard {case.case_id} has a sequence checksum mismatch")


def shard_records(shard: dict[str, Any]) -> list[dict[str, Any]]:
    common = {
        "case_id": shard["case_id"],
        "draw_id": shard["draw_id"],
        "cohort_id": shard["cohort_id"],
        "policy_id": shard["policy_id"],
        "experiment_label": shard["experiment_label"],
        "fixture_key_index": shard["fixture_key_index"],
        "fixture_key_label": f"public_fixture_index_{shard['fixture_key_index']}",
        "stream_domain": shard["stream_domain"],
        "prompt_sequence_sha256": shard["prompt_sequence_sha256"],
        "generated_tokens": shard["generated_tokens"],
        "generated_bases": shard["generated_tokens"] * 6,
    }
    records: list[dict[str, Any]] = []
    for arm in shard["arms"]:
        records.append(
            {
                **common,
                "scheme": arm["scheme"],
                "sequence_sha256": arm["sequence_sha256"],
                "generated_dna": arm["generated_dna"],
            }
        )
    return records


def next_session_path(sessions_dir: Path, draw_index: int) -> Path:
    sessions_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(sessions_dir.glob(f"draw_{draw_index:02d}_session_*.json"))
    return sessions_dir / f"draw_{draw_index:02d}_session_{len(existing):03d}.json"


def finalize(
    *,
    args: argparse.Namespace,
    all_cases: tuple[Any, ...],
    selected: tuple[Any, ...],
    shards_dir: Path,
    sessions_dir: Path,
) -> dict[str, Any]:
    expected_count = args.expected_case_count or len(selected)
    if expected_count <= 0:
        raise ValueError("expected-case-count must be positive")
    cases_by_id = {case.case_id: case for case in all_cases}
    loaded: dict[str, dict[str, Any]] = {}
    for path in sorted(shards_dir.glob("*.json")):
        shard = json.loads(path.read_text(encoding="utf-8"))
        case_id = str(shard.get("case_id"))
        case = cases_by_id.get(case_id)
        if case is None:
            raise ValueError(f"generation shard references unknown case {case_id}")
        validate_shard(
            shard,
            case=case,
            draw_index=args.draw_index,
            steps=args.steps,
            experiment_label=args.experiment_label,
            cohort_id=all_cases[0].cohort_id,
            device=args.device,
            dtype=args.dtype,
        )
        if case_id in loaded:
            raise ValueError(f"duplicate generation shard for {case_id}")
        loaded[case_id] = shard
    if len(loaded) != expected_count:
        raise ValueError(
            f"cannot finalize draw {args.draw_index}: found {len(loaded)} shards, "
            f"expected {expected_count}"
        )
    ordered_ids = [case.case_id for case in all_cases if case.case_id in loaded]
    sequences_path = args.output_root / "generation" / f"draw_{args.draw_index:02d}_sequences.jsonl"
    report_path = args.output_root / "generation" / f"draw_{args.draw_index:02d}_generation.json"
    records = [record for case_id in ordered_ids for record in shard_records(loaded[case_id])]
    serialized = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    if sequences_path.exists():
        if sequences_path.read_text(encoding="utf-8") != serialized:
            raise FileExistsError(f"refusing to replace different output: {sequences_path}")
    else:
        sequences_path.parent.mkdir(parents=True, exist_ok=True)
        sequences_path.write_text(serialized, encoding="utf-8")
    sessions = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(sessions_dir.glob(f"draw_{args.draw_index:02d}_session_*.json"))
    ]
    mean_g_values = [float(loaded[case_id]["mean_g_value"]) for case_id in ordered_ids]
    sequence_count = len(records)
    total_generated_bases = sequence_count * args.steps * 6
    known_wall_seconds = sum(float(row["wall_seconds"]) for row in sessions)
    watermarked_generation_seconds = sum(
        float(loaded[case_id]["watermarked_seconds"]) for case_id in ordered_ids
    )
    ordinary_generation_seconds = sum(
        float(loaded[case_id]["ordinary_seconds"]) for case_id in ordered_ids
    )
    model_generation_seconds = watermarked_generation_seconds + ordinary_generation_seconds
    report = {
        "schema_version": 1,
        "classification": "validation_artifact_not_admitted_evidence",
        "complete": True,
        "experiment_id": EXPERIMENT_ID,
        "experiment_label": args.experiment_label,
        "policy_id": "C_tok",
        "model_id": "HuggingFaceBio/Carbon-500M",
        "revision": "9796b752108258c1d365089f842e62e6c0547704",
        "cohort_id": all_cases[0].cohort_id,
        "cohort_content_sha256": cohort_case_digest(all_cases),
        "draw_id": args.draw_index,
        "fixture_key_index": args.draw_index,
        "key_source": f"public_fixture_index_{args.draw_index}",
        "watermark_method": SYNTHID_SCHEME,
        "control_method": ORDINARY_SCHEME,
        "stream_domain": f"{args.experiment_label}/{all_cases[0].cohort_id}/C_tok",
        "tournament": {
            "kind": "non-distortionary binary tournament",
            "depth": args.tournament_depth,
            "context_tokens": args.context_tokens,
            "context_history_size": args.context_history_size,
            "repeated_contexts_masked": True,
            "first_context_tokens_unwatermarked": True,
        },
        "replay_seed_parts": [
            "experiment_label",
            "policy_id",
            "case_id",
            "draw=<draw_id>",
            "scheme",
        ],
        "case_count": len(loaded),
        "case_ids": ordered_ids,
        "sequence_count": sequence_count,
        "generated_tokens_per_sequence": args.steps,
        "generated_bases_per_sequence": args.steps * 6,
        "total_generated_bases": total_generated_bases,
        "temperature": 1.0,
        "truncation": "none",
        "device": args.device,
        "dtype": args.dtype,
        "sessions": sessions,
        "known_successful_session_wall_seconds": known_wall_seconds,
        "known_model_load_seconds": sum(float(row["model_load_seconds"]) for row in sessions),
        "watermarked_generation_seconds": watermarked_generation_seconds,
        "ordinary_generation_seconds": ordinary_generation_seconds,
        "model_generation_seconds": model_generation_seconds,
        "sequences_per_second": sequence_count / model_generation_seconds,
        "generated_bp_per_second": total_generated_bases / model_generation_seconds,
        "job_wall_sequences_per_second": sequence_count / known_wall_seconds,
        "job_wall_generated_bp_per_second": total_generated_bases / known_wall_seconds,
        "peak_rss_gib": max((float(row["process_peak_rss_gib"]) for row in sessions), default=0.0),
        "peak_mps_current_allocated_gib": max(
            (float(row.get("mps_current_allocated_gib", 0.0)) for row in sessions), default=0.0
        ),
        "peak_mps_driver_allocated_gib": max(
            (float(row.get("mps_driver_allocated_gib", 0.0)) for row in sessions), default=0.0
        ),
        "peak_cuda_allocated_gib": max(
            (float(row.get("cuda_peak_allocated_gib", 0.0)) for row in sessions), default=0.0
        ),
        "peak_cuda_reserved_gib": max(
            (float(row.get("cuda_peak_reserved_gib", 0.0)) for row in sessions), default=0.0
        ),
        "mean_g_value": numeric_summary(mean_g_values),
        "all_keyed_recomputations_match": all(
            bool(loaded[case_id]["keyed_recomputation_matches_generation"])
            for case_id in ordered_ids
        ),
        "sequences": {"path": str(sequences_path), "sha256": sha256_file(str(sequences_path))},
        "shard_count": len(loaded),
        "boundary": (
            "The two fixture keys are public reproducibility fixtures, not deployment secrets. "
            "A draw changes the key and residual replay seed but not the declared PRF domain."
        ),
    }
    serialized_report = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if report_path.exists():
        if report_path.read_text(encoding="utf-8") != serialized_report:
            raise FileExistsError(f"refusing to replace different output: {report_path}")
    else:
        report_path.write_text(serialized_report, encoding="utf-8")
    return {
        "draw_id": args.draw_index,
        "case_count": len(loaded),
        "sequence_count": len(records),
        "sequences": str(sequences_path),
        "sequences_sha256": report["sequences"]["sha256"],
        "report": str(report_path),
        "report_sha256": sha256_file(str(report_path)),
    }


def main() -> int:
    args = parse_args()
    if args.steps <= 0:
        raise ValueError("steps must be positive")
    if args.finalize_only and not args.finalize:
        args.finalize = True
    all_cases = load_context_cases_jsonl(args.cohort_jsonl)
    selected = selected_cases(all_cases, args.case_id)
    cohort_id = all_cases[0].cohort_id
    generation_dir = args.output_root / "generation"
    shards_dir = generation_dir / "shards" / f"draw_{args.draw_index:02d}"
    sessions_dir = generation_dir / "sessions"
    shards_dir.mkdir(parents=True, exist_ok=True)
    cases_pending: list[Any] = []
    for case in selected:
        path = shards_dir / f"{case.case_id}.json"
        if path.exists():
            validate_shard(
                json.loads(path.read_text(encoding="utf-8")),
                case=case,
                draw_index=args.draw_index,
                steps=args.steps,
                experiment_label=args.experiment_label,
                cohort_id=cohort_id,
                device=args.device,
                dtype=args.dtype,
            )
        else:
            cases_pending.append(case)

    if cases_pending and args.finalize_only:
        raise ValueError("--finalize-only cannot run while selected generation shards are missing")

    if cases_pending:
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
        stream_domain = f"{args.experiment_label}/{cohort_id}/C_tok"
        tournament = KeyedTournament(
            key=fixture_key(args.draw_index),
            domain=stream_domain,
            depth=args.tournament_depth,
            context_tokens=args.context_tokens,
            context_history_size=args.context_history_size,
        )

        def next_distribution(context: str) -> tuple[tuple[str, ...], tuple[float, ...]]:
            state = adapter.next_distribution(context)
            return tuple(state.tokens), tuple(state.probabilities)

        for completed, case in enumerate(cases_pending, start=1):
            watermarked_started = time.perf_counter()
            watermarked = generate_synthid(
                next_distribution,
                case.sequence,
                steps=args.steps,
                tournament=tournament,
                rng=random.Random(
                    public_replay_seed(
                        args.experiment_label,
                        "C_tok",
                        case.case_id,
                        f"draw={args.draw_index}",
                        SYNTHID_SCHEME,
                    )
                ),
            )
            watermarked_seconds = time.perf_counter() - watermarked_started
            ordinary_started = time.perf_counter()
            ordinary = generate_ordinary(
                next_distribution,
                case.sequence,
                steps=args.steps,
                rng=random.Random(
                    public_replay_seed(
                        args.experiment_label,
                        "C_tok",
                        case.case_id,
                        f"draw={args.draw_index}",
                        ORDINARY_SCHEME,
                    )
                ),
            )
            ordinary_seconds = time.perf_counter() - ordinary_started
            recovered = score_synthid_tokens(watermarked.tokens, tournament)
            shard = {
                "schema_version": 1,
                "classification": "validation_artifact_not_admitted_evidence",
                "complete": True,
                "experiment_id": EXPERIMENT_ID,
                "experiment_label": args.experiment_label,
                "policy_id": "C_tok",
                "model_id": adapter.policy.model_id,
                "revision": adapter.policy.revision,
                "cohort_id": cohort_id,
                "case_id": case.case_id,
                "draw_id": args.draw_index,
                "fixture_key_index": args.draw_index,
                "prompt_sequence_sha256": case.sequence_sha256,
                "stream_domain": stream_domain,
                "tournament_depth": args.tournament_depth,
                "context_tokens": args.context_tokens,
                "context_history_size": args.context_history_size,
                "generated_tokens": args.steps,
                "device": args.device,
                "dtype": args.dtype,
                "watermarked_seconds": watermarked_seconds,
                "ordinary_seconds": ordinary_seconds,
                "scored_tokens": watermarked.scored_tokens,
                "repeated_contexts": watermarked.repeated_contexts,
                "g_ones": watermarked.g_ones,
                "g_total": watermarked.g_total,
                "mean_g_value": watermarked.mean_g_value,
                "keyed_recomputation_matches_generation": (
                    recovered.g_ones == watermarked.g_ones
                    and recovered.g_total == watermarked.g_total
                    and recovered.scored_tokens == watermarked.scored_tokens
                    and recovered.repeated_contexts == watermarked.repeated_contexts
                ),
                "arms": [
                    {
                        "scheme": SYNTHID_SCHEME,
                        "sequence_sha256": hashlib.sha256(
                            watermarked.dna.encode("ascii")
                        ).hexdigest(),
                        "generated_dna": watermarked.dna,
                    },
                    {
                        "scheme": ORDINARY_SCHEME,
                        "sequence_sha256": hashlib.sha256(ordinary.dna.encode("ascii")).hexdigest(),
                        "generated_dna": ordinary.dna,
                    },
                ],
            }
            atomic_write_json(shards_dir / f"{case.case_id}.json", shard)
            print(
                json.dumps(
                    {
                        "draw_id": args.draw_index,
                        "case_id": case.case_id,
                        "completed_in_session": completed,
                        "pending_in_session": len(cases_pending) - completed,
                        "watermarked_seconds": watermarked_seconds,
                        "ordinary_seconds": ordinary_seconds,
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
                "cuda_current_allocated_gib": float(torch.cuda.memory_allocated()) / (1024.0**3),
                "cuda_peak_allocated_gib": float(torch.cuda.max_memory_allocated()) / (1024.0**3),
                "cuda_current_reserved_gib": float(torch.cuda.memory_reserved()) / (1024.0**3),
                "cuda_peak_reserved_gib": float(torch.cuda.max_memory_reserved()) / (1024.0**3),
                "torch_version": torch.__version__,
                "torch_cuda_version": str(torch.version.cuda),
            }
        session = {
            "schema_version": 1,
            "draw_id": args.draw_index,
            "started_utc": datetime.now(UTC).isoformat(),
            "command": shlex.join([sys.executable, *sys.argv]),
            "case_count": len(cases_pending),
            "case_ids": [case.case_id for case in cases_pending],
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
        atomic_write_json(next_session_path(sessions_dir, args.draw_index), session)
        adapter = None
        gc.collect()
        if args.device == "mps":
            torch.mps.empty_cache()
        elif args.device == "cuda":
            torch.cuda.empty_cache()

    result: dict[str, Any] = {
        "draw_id": args.draw_index,
        "requested_cases": len(selected),
        "generated_now": len(cases_pending),
        "resumed_cases": len(selected) - len(cases_pending),
        "shards_dir": str(shards_dir),
    }
    if args.finalize:
        result["finalized"] = finalize(
            args=args,
            all_cases=all_cases,
            selected=selected,
            shards_dir=shards_dir,
            sessions_dir=sessions_dir,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
