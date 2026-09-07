#!/usr/bin/env python3
"""Resume and supervise the frozen Carbon SynthID validation workload.

The scientific runners remain the source of truth. This supervisor only keeps
the benchmarked number of independent MPS jobs active, records their commands,
and advances to the next stage after immutable completion artifacts exist.
Rerunning the supervisor is therefore the supported whole-workload resume path.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "outputs/carbon_synthid_validation_v1"
COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_large_v1/prompts.jsonl"


@dataclass(frozen=True, slots=True)
class Job:
    name: str
    command: tuple[str, ...]
    completion_paths: tuple[Path, ...]

    @property
    def complete(self) -> bool:
        return all(path.is_file() for path in self.completion_paths)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--generation-workers",
        type=int,
        choices=(1, 2),
        default=2,
        help="concurrent MPS generation jobs; two is the benchmarked default",
    )
    parser.add_argument(
        "--draw-count",
        type=int,
        choices=(2,),
        default=2,
        help="the frozen design uses two fixture-key draws",
    )
    parser.add_argument(
        "--detach",
        action="store_true",
        help="launch a caffeinated supervisor detached from the current terminal",
    )
    parser.add_argument("--internal-run", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def python_command(script: str, *arguments: str) -> tuple[str, ...]:
    return (sys.executable, str(ROOT / "scripts" / script), *arguments)


def generation_job(output_root: Path, draw_id: int) -> Job:
    generation = output_root / "generation"
    return Job(
        name=f"generation_draw_{draw_id:02d}",
        command=python_command(
            "run_carbon_large_generation.py",
            "--output-root",
            str(output_root),
            "--cohort-jsonl",
            str(COHORT),
            "--draw-index",
            str(draw_id),
            "--steps",
            "512",
            "--experiment-label",
            "carbon-synthid-validation-v1",
            "--tournament-depth",
            "30",
            "--context-tokens",
            "4",
            "--context-history-size",
            "1024",
            "--device",
            "mps",
            "--dtype",
            "bfloat16",
            "--cache-dir",
            str(ROOT / ".cache/huggingface"),
            "--local-files-only",
            "--finalize",
            "--expected-case-count",
            "256",
        ),
        completion_paths=(
            generation / f"draw_{draw_id:02d}_sequences.jsonl",
            generation / f"draw_{draw_id:02d}_generation.json",
        ),
    )


def jobs(output_root: Path, *, draw_count: int) -> dict[str, Job]:
    generation = output_root / "generation"
    distribution = output_root / "distribution"
    sequence = output_root / "sequence_comparison"
    detection = output_root / "detection"
    figures = output_root / "figures"
    draw_arguments = tuple(
        argument for draw_id in range(draw_count) for argument in ("--draw-index", str(draw_id))
    )
    return {
        "prepare": Job(
            "prepare",
            python_command(
                "prepare_carbon_large_validation.py",
                "--output-root",
                str(output_root),
                "--cohort-jsonl",
                str(COHORT),
                "--cohort-manifest",
                str(ROOT / "data/public_prompt_cohort_large_v1.yaml"),
                "--config",
                str(ROOT / "configs/carbon_synthid_validation_v1.toml"),
            ),
            (
                output_root / "cohort_manifest.yaml",
                output_root / "prompts.jsonl",
                output_root / "resolved_config.toml",
            ),
        ),
        "generation_summary": Job(
            "generation_summary",
            python_command(
                "summarize_carbon_large_generation.py",
                "--output-root",
                str(output_root),
                "--cohort-jsonl",
                str(COHORT),
                *draw_arguments,
                "--expected-case-count",
                "256",
            ),
            (generation / "generation_summary.json",),
        ),
        "distribution": Job(
            "distribution",
            python_command(
                "run_carbon_large_distribution.py",
                "--output-root",
                str(output_root),
                "--cohort-jsonl",
                str(COHORT),
                "--draw-zero-sequences",
                str(generation / "draw_00_sequences.jsonl"),
                "--state-token-index",
                "64",
                "--draws",
                "5000",
                "--replicates",
                "999",
                "--gof-seed",
                "2718",
                "--negative-control-states",
                "8",
                "--experiment-label",
                "carbon-synthid-validation-v1/distribution",
                "--tournament-depth",
                "30",
                "--context-tokens",
                "4",
                "--context-history-size",
                "1024",
                "--key-average-replicates",
                "64",
                "--device",
                "mps",
                "--dtype",
                "bfloat16",
                "--cache-dir",
                str(ROOT / ".cache/huggingface"),
                "--local-files-only",
                "--bootstrap-replicates",
                "20000",
                "--permutation-replicates",
                "100000",
                "--analysis-seed",
                "2718",
                "--finalize",
                "--expected-state-count",
                "256",
            ),
            (
                distribution / "state_manifest.jsonl",
                distribution / "fixed_state_trials.parquet",
                distribution / "distribution_summary.json",
            ),
        ),
        "sequence_comparison": Job(
            "sequence_comparison",
            python_command(
                "analyze_carbon_large_sequences.py",
                "--output-root",
                str(output_root),
                "--cohort-jsonl",
                str(COHORT),
                *draw_arguments,
                "--device",
                "mps",
                "--dtype",
                "bfloat16",
                "--cache-dir",
                str(ROOT / ".cache/huggingface"),
                "--local-files-only",
                "--bootstrap-replicates",
                "20000",
                "--permutation-replicates",
                "100000",
                "--analysis-seed",
                "2718",
                "--finalize",
                "--expected-sequence-count",
                str(256 * draw_count * 2),
            ),
            (
                sequence / "sequence_metrics.parquet",
                sequence / "sequence_comparison_summary.json",
            ),
        ),
        "detection": Job(
            "detection",
            python_command(
                "run_carbon_large_detection.py",
                "--output-root",
                str(output_root),
                "--cohort-jsonl",
                str(COHORT),
                *draw_arguments,
                "--token-lengths",
                "64",
                "128",
                "256",
                "512",
                "--target-fpr",
                "0.01",
                "--threshold-source",
                "analytic",
                "--calibration-prompts",
                "64",
                "--experiment-label",
                "carbon-synthid-validation-v1",
                "--tournament-depth",
                "30",
                "--context-tokens",
                "4",
                "--context-history-size",
                "1024",
                "--bootstrap-replicates",
                "20000",
                "--permutation-replicates",
                "100000",
                "--analysis-seed",
                "2718",
                "--finalize",
                "--expected-pair-count",
                str(256 * draw_count),
            ),
            (
                detection / "calibration_trials.parquet",
                detection / "evaluation_trials.parquet",
                detection / "detection_summary.json",
            ),
        ),
        "detector_comparison": Job(
            "detector_comparison",
            python_command(
                "compare_synthid_detectors.py",
                "--output-root",
                str(output_root),
                "--draw-index",
                "0",
                "--draw-index",
                "1",
                "--token-lengths",
                "64",
                "512",
                "--tournament-depth",
                "30",
                "--context-tokens",
                "4",
                "--context-history-size",
                "1024",
            ),
            (detection / "detector_comparison.json",),
        ),
        "figures": Job(
            "figures",
            python_command(
                "plot_carbon_large_validation.py",
                "--output-root",
                str(output_root),
            ),
            (figures / "manifest.json",),
        ),
        "report": Job(
            "report",
            python_command(
                "render_carbon_large_report.py",
                "--output-root",
                str(output_root),
            ),
            (output_root / "report.md",),
        ),
        "validation": Job(
            "validation",
            python_command(
                "validate_carbon_large_validation.py",
                "--output-root",
                str(output_root),
                "--expected-prompts",
                "256",
                "--expected-draws",
                str(draw_count),
                "--expected-generated-tokens",
                "512",
                "--expected-states",
                "256",
                "--calibration-prompts",
                "64",
                "--require-figures",
                "--require-report",
            ),
            (output_root / "artifact_digests.json",),
        ),
    }


def process_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def detach(args: argparse.Namespace) -> int:
    output_root = args.output_root.resolve()
    orchestration = output_root / "orchestration"
    orchestration.mkdir(parents=True, exist_ok=True)
    pid_path = orchestration / "supervisor.pid"
    if pid_path.is_file():
        existing_pid = int(pid_path.read_text(encoding="utf-8").strip())
        if process_is_alive(existing_pid):
            raise RuntimeError(f"supervisor is already active with pid {existing_pid}")
    log_path = orchestration / "supervisor.log"
    log_handle = log_path.open("ab")
    command = (
        "/usr/bin/caffeinate",
        "-dimsu",
        sys.executable,
        str(Path(__file__).resolve()),
        "--output-root",
        str(output_root),
        "--generation-workers",
        str(args.generation_workers),
        "--draw-count",
        str(args.draw_count),
        "--internal-run",
    )
    environment = os.environ.copy()
    environment["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )
    log_handle.close()
    pid_path.write_text(f"{process.pid}\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "detached",
                "pid": process.pid,
                "log": str(log_path),
                "draw_count": args.draw_count,
                "generation_workers": args.generation_workers,
            },
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


def atomic_state(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def append_event(state_path: Path, event: dict[str, Any]) -> None:
    state: dict[str, Any] = {"schema_version": 1, "events": []}
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    state.setdefault("events", []).append({"utc": datetime.now(UTC).isoformat(), **event})
    atomic_state(state_path, state)


def run_group(
    selected: list[Job],
    *,
    output_root: Path,
    state_path: Path,
    dry_run: bool,
) -> None:
    pending = [job for job in selected if not job.complete]
    for job in selected:
        if job.complete:
            print(json.dumps({"job": job.name, "status": "skipped_complete"}), flush=True)
    if not pending:
        return
    if dry_run:
        for job in pending:
            print(json.dumps({"job": job.name, "command": shlex.join(job.command)}), flush=True)
        return
    log_dir = output_root / "orchestration" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
    running: list[tuple[Job, subprocess.Popen[bytes], Any]] = []
    try:
        for job in pending:
            log_path = log_dir / f"{job.name}.log"
            log_handle = log_path.open("ab")
            header = (f"\n[{datetime.now(UTC).isoformat()}] {shlex.join(job.command)}\n").encode()
            log_handle.write(header)
            log_handle.flush()
            process = subprocess.Popen(
                job.command,
                cwd=ROOT,
                env=environment,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
            )
            running.append((job, process, log_handle))
            append_event(
                state_path,
                {"job": job.name, "status": "started", "pid": process.pid, "log": str(log_path)},
            )
            print(
                json.dumps({"job": job.name, "status": "started", "pid": process.pid}), flush=True
            )
        last_progress = 0.0
        while any(process.poll() is None for _, process, _ in running):
            now = time.monotonic()
            if now - last_progress >= 60.0:
                shard_counts = {
                    f"draw_{draw_id:02d}": len(
                        tuple(
                            (output_root / "generation" / "shards" / f"draw_{draw_id:02d}").glob(
                                "*.json"
                            )
                        )
                    )
                    for draw_id in range(2)
                }
                print(
                    json.dumps(
                        {
                            "status": "running",
                            "jobs": [
                                {"job": job.name, "pid": process.pid, "returncode": process.poll()}
                                for job, process, _ in running
                            ],
                            "generation_shards": shard_counts,
                        }
                    ),
                    flush=True,
                )
                last_progress = now
            time.sleep(5.0)
    except KeyboardInterrupt:
        for _, process, _ in running:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
        for _, process, _ in running:
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.terminate()
        raise
    finally:
        for _, _, log_handle in running:
            log_handle.close()
    failures: list[str] = []
    for job, process, _ in running:
        status = "completed" if process.returncode == 0 and job.complete else "failed"
        append_event(
            state_path,
            {"job": job.name, "status": status, "returncode": process.returncode},
        )
        print(
            json.dumps({"job": job.name, "status": status, "returncode": process.returncode}),
            flush=True,
        )
        if status == "failed":
            failures.append(job.name)
    if failures:
        raise RuntimeError(f"supervised job(s) failed: {', '.join(failures)}")


def main() -> int:
    args = parse_args()
    if args.detach and not args.internal_run:
        return detach(args)
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    state_path = output_root / "orchestration" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    all_jobs = jobs(output_root, draw_count=args.draw_count)
    run_group(
        [all_jobs["prepare"]],
        output_root=output_root,
        state_path=state_path,
        dry_run=args.dry_run,
    )
    generation = [generation_job(output_root, draw_id) for draw_id in range(args.draw_count)]
    for start in range(0, args.draw_count, args.generation_workers):
        run_group(
            generation[start : start + args.generation_workers],
            output_root=output_root,
            state_path=state_path,
            dry_run=args.dry_run,
        )
    run_group(
        [all_jobs["generation_summary"]],
        output_root=output_root,
        state_path=state_path,
        dry_run=args.dry_run,
    )
    run_group(
        [all_jobs["distribution"], all_jobs["sequence_comparison"]],
        output_root=output_root,
        state_path=state_path,
        dry_run=args.dry_run,
    )
    for name in (
        "detection",
        "detector_comparison",
        "figures",
        "report",
        "validation",
    ):
        run_group(
            [all_jobs[name]],
            output_root=output_root,
            state_path=state_path,
            dry_run=args.dry_run,
        )
    print(json.dumps({"status": "complete", "output_root": str(output_root)}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
