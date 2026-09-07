#!/usr/bin/env python3
"""Run resumable GENERator SynthID generation across local worker processes."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.pilot import load_context_cases_jsonl  # noqa: E402

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_large_v1/prompts.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--threads-per-worker", type=int, default=4)
    parser.add_argument("--steps", type=int, default=512)
    parser.add_argument("--device", choices=("cpu", "mps"), default="cpu")
    parser.add_argument("--dtype", choices=("float32", "bfloat16", "float16"), default="float32")
    parser.add_argument("--cache-dir", default=".cache/huggingface")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def generation_command(
    args: argparse.Namespace,
    *,
    draw_id: int,
    case_ids: list[str],
) -> list[str]:
    command = [
        sys.executable,
        str(ROOT / "scripts/run_generator_large_generation.py"),
        "--output-root",
        str(args.output_root),
        "--cohort-jsonl",
        str(args.cohort_jsonl),
        "--draw-index",
        str(draw_id),
        "--steps",
        str(args.steps),
        "--experiment-label",
        "generator-synthid-validation-v1",
        "--tournament-depth",
        "30",
        "--context-tokens",
        "4",
        "--context-history-size",
        "1024",
        "--device",
        args.device,
        "--dtype",
        args.dtype,
        "--cache-dir",
        args.cache_dir,
        "--local-files-only",
    ]
    for case_id in case_ids:
        command.extend(("--case-id", case_id))
    return command


def main() -> int:
    args = parse_args()
    if args.workers < 2 or args.workers % 2:
        raise ValueError("workers must be an even number of at least two")
    if args.threads_per_worker <= 0 or args.steps <= 0:
        raise ValueError("threads-per-worker and steps must be positive")
    cases = load_context_cases_jsonl(args.cohort_jsonl)
    per_draw = args.workers // 2
    commands: list[tuple[int, int, list[str]]] = []
    for draw_id in (0, 1):
        partitions = [[] for _ in range(per_draw)]
        for index, case in enumerate(cases):
            partitions[index % per_draw].append(case.case_id)
        for worker_id, case_ids in enumerate(partitions):
            commands.append(
                (
                    draw_id,
                    worker_id,
                    generation_command(args, draw_id=draw_id, case_ids=case_ids),
                )
            )
    if args.dry_run:
        print(
            json.dumps(
                [
                    {
                        "draw_id": draw_id,
                        "worker_id": worker_id,
                        "case_count": sum(part == "--case-id" for part in command),
                        "command": command,
                    }
                    for draw_id, worker_id, command in commands
                ],
                indent=2,
            )
        )
        return 0

    log_dir = args.output_root / "orchestration/logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment["OMP_NUM_THREADS"] = str(args.threads_per_worker)
    environment["HF_HUB_DISABLE_TELEMETRY"] = "1"
    environment["TOKENIZERS_PARALLELISM"] = "false"
    environment["PYTHONNOUSERSITE"] = "1"
    running: list[tuple[int, int, subprocess.Popen[bytes], Any]] = []
    for draw_id, worker_id, command in commands:
        log = (log_dir / f"cpu_generation_draw_{draw_id:02d}_worker_{worker_id:02d}.log").open(
            "ab"
        )
        process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log, stderr=log)
        running.append((draw_id, worker_id, process, log))
    failures: list[tuple[int, int, int]] = []
    for draw_id, worker_id, process, log in running:
        return_code = process.wait()
        log.close()
        if return_code:
            failures.append((draw_id, worker_id, return_code))
    if failures:
        raise RuntimeError(f"generation worker failures: {failures}")

    for draw_id in (0, 1):
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/run_generator_large_generation.py"),
                "--output-root",
                str(args.output_root),
                "--cohort-jsonl",
                str(args.cohort_jsonl),
                "--draw-index",
                str(draw_id),
                "--steps",
                str(args.steps),
                "--experiment-label",
                "generator-synthid-validation-v1",
                "--device",
                args.device,
                "--dtype",
                args.dtype,
                "--cache-dir",
                args.cache_dir,
                "--local-files-only",
                "--finalize",
                "--finalize-only",
                "--expected-case-count",
                str(len(cases)),
            ],
            cwd=ROOT,
            env=environment,
            check=True,
        )
    print(json.dumps({"complete": True, "workers": args.workers, "cases": len(cases)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
