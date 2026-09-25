#!/usr/bin/env python3
"""Benchmark the frozen position-independent detector on retained public reads.

Only aggregate timings and source digests are written. Each condition is an
immutable checkpoint, so rerunning this command skips completed conditions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.large_validation import fixture_key  # noqa: E402
from genomic_watermarks.synthid_position_independent import (  # noqa: E402
    PositionIndependentSynthIDConfig,
    detect_synthid_position_independent,
)

COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_large_v1/prompts.jsonl"
BUNDLE = Path("/scratch/10899/kimopro/carbon_synthid_validation_hpc_v4")
SPLIT = BUNDLE / "detection/prompt_split.json"
GENERATIONS = BUNDLE / "generation/draw_00_sequences.jsonl"
BASE_READ_LENGTH = 3456
CONDITION_LENGTHS = (3456, 6912, 13824)
WINDOW_LENGTHS = (384, 768, 1536, 3072)
SAMPLES = 16


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_reads(length: int, samples: int) -> tuple[list[str], str]:
    if length not in CONDITION_LENGTHS or length % BASE_READ_LENGTH:
        raise ValueError("length must be one of the declared conditions")
    split = json.loads(SPLIT.read_text())
    evaluation = sorted(
        case_id for case_id, assignment in split["assignments"].items()
        if assignment == "evaluation"
    )
    prompts = {row["prompt_id"]: row["sequence"] for row in jsonl(COHORT)}
    ordinary = {
        row["case_id"]: row
        for row in jsonl(GENERATIONS)
        if row["scheme"] == "ordinary-categorical-v1"
    }
    chunks = []
    domains = set()
    for case_id in evaluation[:samples * 4]:
        row = ordinary[case_id]
        chunk = prompts[case_id] + row["generated_dna"]
        if len(chunk) != BASE_READ_LENGTH:
            raise ValueError("source read length differs from the frozen design")
        chunks.append(chunk)
        domains.add(row["stream_domain"])
    if len(chunks) != samples * 4 or len(domains) != 1:
        raise ValueError("source data lack the requested read grid or one common domain")
    count = length // BASE_READ_LENGTH
    reads = ["".join(chunks[4 * i:4 * i + count]) for i in range(samples)]
    if any(len(read) != length for read in reads):
        raise ValueError("constructed read length mismatch")
    return reads, domains.pop()


def detect_one(work: tuple[str, str]) -> dict[str, float | int]:
    read, domain = work
    started = time.perf_counter()
    result = detect_synthid_position_independent(
        read,
        key=fixture_key(0),
        domain=domain,
        config=PositionIndependentSynthIDConfig(),
    )
    return {
        "seconds": time.perf_counter() - started,
        "hypotheses": result.hypotheses_searched,
        "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    }


def environment() -> dict[str, Any]:
    try:
        child = subprocess.run(
            [
                sys.executable,
                "-c",
                "import json, torch; print(json.dumps({'version': torch.__version__, "
                "'cuda_build': torch.version.cuda}))",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        torch_build = json.loads(child.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        torch_build = {"version": None, "cuda_build": None}
    return {
        "device_used": "CPU",
        "cpu_model": next(
            (
                line.split(":", 1)[1].strip()
                for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")
            ),
            "unknown",
        ),
        "logical_cpus_visible": len(os.sched_getaffinity(0)),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch": torch_build,
    }


def run_condition(length: int, workers: int, samples: int) -> dict[str, Any]:
    reads, domain = load_reads(length, samples)
    config = PositionIndependentSynthIDConfig()
    if (
        config.window_base_lengths != WINDOW_LENGTHS
        or config.depth != 30
        or config.context_tokens != 4
        or config.context_history_size != 1024
        or config.target_false_positive_rate != 0.01
    ):
        raise ValueError("detector defaults differ from frozen configuration")
    expected = 2 * sum(length - window + 1 for window in WINDOW_LENGTHS)
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        measurements = list(pool.map(detect_one, ((read, domain) for read in reads)))
    wall = time.perf_counter() - started
    if any(row["hypotheses"] != expected for row in measurements):
        raise ValueError("realized window count differs from full-search count")
    seconds = [float(row["seconds"]) for row in measurements]
    rss = [float(row["peak_rss_mib"]) for row in measurements]
    return {
        "schema_version": 1,
        "read_bases": length,
        "workers": workers,
        "sample_reads": samples,
        "read_construction": (
            "For each of 16 sorted evaluation groups, concatenate 1, 2, or 4 distinct "
            "retained prompt-plus-ordinary-continuation reads; 3456 bases per source read; "
            "draw 0. No DNA is written to this artifact."
        ),
        "source_sha256": {
            "cohort": sha256(COHORT),
            "prompt_split": sha256(SPLIT),
            "generation_draw_00": sha256(GENERATIONS),
            "detector_source": sha256(
                ROOT / "src/genomic_watermarks/synthid_position_independent.py"
            ),
            "benchmark_source": sha256(Path(__file__)),
        },
        "configuration": {
            "detector_id": "synthid-position-independent-detector-v1",
            "window_base_lengths": list(WINDOW_LENGTHS),
            "orientations": ["forward", "reverse_complement"],
            "target_fpr": 0.01,
            "depth": 30,
            "context_tokens": 4,
            "context_history_size": 1024,
            "key": "public fixture key index 0; raw bytes omitted",
            "domain": "retained Carbon public generation domain; string omitted",
        },
        "environment": environment(),
        "hypotheses_per_read": expected,
        "wall_seconds_total": wall,
        "wall_seconds_per_read_at_worker_count": wall / samples,
        "detector_seconds_per_read_median": statistics.median(seconds),
        "detector_seconds_per_read_min": min(seconds),
        "detector_seconds_per_read_max": max(seconds),
        "peak_worker_rss_mib": max(rss),
        "sum_worker_peak_rss_mib_upper_bound": sum(sorted(rss, reverse=True)[:workers]),
        "rss_note": (
            "Peak worker RSS comes from getrusage(RUSAGE_SELF); summing worker maxima "
            "is an upper bound, not a synchronized aggregate peak."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lengths", type=int, nargs="+", default=CONDITION_LENGTHS)
    parser.add_argument("--workers", type=int, nargs="+", default=(1, 16))
    parser.add_argument("--samples", type=int, default=SAMPLES)
    parser.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "evidence/derived/detector_search_timing_2026_09_21",
    )
    args = parser.parse_args()
    if args.samples != SAMPLES or any(length not in CONDITION_LENGTHS for length in args.lengths):
        raise ValueError("benchmark design is frozen at 16 reads and the declared lengths")
    if any(workers not in (1, 16) for workers in args.workers):
        raise ValueError("worker count must be 1 or 16")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for length in args.lengths:
        for workers in args.workers:
            path = args.output_dir / f"N{length}_w{workers}.json"
            if path.exists():
                prior = json.loads(path.read_text())
                if prior["read_bases"] != length or prior["workers"] != workers:
                    raise ValueError(f"checkpoint does not match condition: {path}")
                print(f"resume {path.relative_to(ROOT)}")
                continue
            result = run_condition(length, workers, args.samples)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            os.replace(temporary, path)
            print(
                f"{path.relative_to(ROOT)}: {result['hypotheses_per_read']} windows; "
                f"{result['wall_seconds_per_read_at_worker_count']:.3f} wall s/read"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
