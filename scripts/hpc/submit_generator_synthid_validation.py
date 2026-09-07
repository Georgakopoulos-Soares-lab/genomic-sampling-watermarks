#!/usr/bin/env python3
"""Submit the optional TACC CUDA validation as dependent GPU and CPU jobs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_large_v1/prompts.jsonl"
HPC_CONFIG = ROOT / "configs/generator_synthid_validation_hpc_v1.toml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("smoke", "full"), default="full")
    parser.add_argument("--account", default=os.environ.get("SLURM_TACC_ACCOUNT"))
    parser.add_argument("--gpu-partition")
    parser.add_argument("--post-partition")
    parser.add_argument("--gpu-time")
    parser.add_argument("--post-time")
    parser.add_argument("--conda-environment", default="tacc_watermark")
    parser.add_argument("--cuda-module", default="cuda/12.8")
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / ".cache/huggingface")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def checked_identifier(value: str, label: str, *, extra: str = "") -> str:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.:" + extra)
    if not value or set(value) - allowed:
        raise ValueError(f"{label} contains unsupported characters")
    return value


def command_output(command: list[str]) -> str:
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode:
        diagnostic = (
            completed.stderr.strip() or completed.stdout.strip() or "no output was returned"
        )
        raise RuntimeError(f"command failed ({shlex.join(command)}): {diagnostic}")
    return completed.stdout.strip()


def sbatch_job_id(output: str) -> str:
    """Extract a job ID despite TACC's validation banner on stdout."""

    for line in reversed(output.splitlines()):
        candidate = line.strip().split(";", 1)[0]
        if re.fullmatch(r"[0-9]+", candidate):
            return candidate
    raise RuntimeError("sbatch output did not contain a numeric job ID")


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"refusing to replace different submission record: {path}")
        return
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    args = parse_args()
    if os.environ.get("SLURM_JOB_ID") and not args.dry_run:
        raise RuntimeError(
            "TACC accepts sbatch only from a login node; leave the current compute allocation "
            "and rerun this submitter on login*.ls6.tacc.utexas.edu"
        )
    if not args.account:
        raise ValueError("--account is required outside an existing TACC Slurm allocation")
    account = checked_identifier(args.account, "account")
    gpu_partition = checked_identifier(
        args.gpu_partition or ("gpu-a100-dev" if args.profile == "smoke" else "gpu-a100"),
        "gpu partition",
    )
    post_partition = checked_identifier(
        args.post_partition or ("development" if args.profile == "smoke" else "normal"),
        "post partition",
    )
    gpu_time = args.gpu_time or ("02:00:00" if args.profile == "smoke" else "24:00:00")
    post_time = args.post_time or ("00:30:00" if args.profile == "smoke" else "12:00:00")
    conda_environment = checked_identifier(args.conda_environment, "Conda environment")
    cuda_module = checked_identifier(args.cuda_module, "CUDA module", extra="/")
    scratch = os.environ.get("SCRATCH")
    if args.output_root is None:
        if not scratch:
            raise ValueError("--output-root is required when SCRATCH is unset")
        suffix = "smoke_v1" if args.profile == "smoke" else "v1"
        args.output_root = Path(scratch) / f"generator_synthid_validation_hpc_{suffix}"
    output_root = args.output_root.resolve()
    cohort = args.cohort_jsonl.resolve()
    cache_dir = args.cache_dir.resolve()
    for required in (cohort, HPC_CONFIG, cache_dir):
        if not required.exists():
            raise FileNotFoundError(required)
    for value in (ROOT, output_root, cohort, cache_dir):
        if "," in str(value):
            raise ValueError("Slurm export paths may not contain commas")

    prepare = [
        sys.executable,
        str(ROOT / "scripts/prepare_generator_large_validation.py"),
        "--output-root",
        str(output_root),
        "--cohort-jsonl",
        str(cohort),
        "--cohort-manifest",
        str(ROOT / "data/public_prompt_cohort_large_v1.yaml"),
        "--config",
        str(HPC_CONFIG),
    ]
    log_dir = output_root / "orchestration/logs"
    source_manifest = output_root / "orchestration/source_manifest.json"
    exports = {
        "GSW_REPO_ROOT": str(ROOT),
        "GSW_OUTPUT_ROOT": str(output_root),
        "GSW_HF_CACHE": str(cache_dir),
        "GSW_COHORT": str(cohort),
        "GSW_PROFILE": args.profile,
        "GSW_CONDA_ENV": conda_environment,
        "GSW_CUDA_MODULE": cuda_module,
    }
    export_argument = "ALL," + ",".join(f"{key}={value}" for key, value in exports.items())
    gpu_command = [
        "sbatch",
        "--parsable",
        "--account",
        account,
        "--partition",
        gpu_partition,
        "--time",
        gpu_time,
        "--export",
        export_argument,
        "--output",
        str(log_dir / "%x-%j.out"),
        str(ROOT / "scripts/hpc/generator_synthid_gpu.sbatch"),
    ]
    if args.dry_run:
        commands = {"prepare": shlex.join(prepare), "gpu": shlex.join(gpu_command)}
        print(json.dumps(commands, indent=2))
        return 0

    subprocess.run(prepare, cwd=ROOT, check=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/hpc/freeze_source_manifest.py"),
            "--output",
            str(source_manifest),
        ],
        cwd=ROOT,
        check=True,
    )
    gpu_job_id = sbatch_job_id(command_output(gpu_command))
    post_command = [
        "sbatch",
        "--parsable",
        "--account",
        account,
        "--partition",
        post_partition,
        "--time",
        post_time,
        "--dependency",
        f"afterok:{gpu_job_id}",
        "--export",
        export_argument,
        "--output",
        str(log_dir / "%x-%j.out"),
        str(ROOT / "scripts/hpc/generator_synthid_post.sbatch"),
    ]
    try:
        post_job_id = sbatch_job_id(command_output(post_command))
    except Exception as error:
        raise RuntimeError(f"GPU job {gpu_job_id} was submitted but post job failed") from error

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout
    record = {
        "schema_version": 1,
        "classification": "slurm_submission_not_admitted_evidence",
        "submitted_utc": datetime.now(UTC).isoformat(),
        "profile": args.profile,
        "output_root": str(output_root),
        "account": account,
        "gpu_partition": gpu_partition,
        "post_partition": post_partition,
        "gpu_job_id": gpu_job_id,
        "post_job_id": post_job_id,
        "dependency": f"afterok:{gpu_job_id}",
        "conda_environment": conda_environment,
        "cuda_module": cuda_module,
        "cohort_jsonl": str(cohort),
        "cache_dir": str(cache_dir),
        "config_sha256": hashlib.sha256(HPC_CONFIG.read_bytes()).hexdigest(),
        "source_manifest": str(source_manifest),
        "source_manifest_sha256": hashlib.sha256(source_manifest.read_bytes()).hexdigest(),
        "git_commit": command_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"]),
        "dirty_worktree": bool(status),
        "dirty_status_sha256": hashlib.sha256(status.encode()).hexdigest(),
        "command": shlex.join([sys.executable, *sys.argv]),
    }
    record_path = output_root / "orchestration" / f"submission_{gpu_job_id}.json"
    atomic_write(record_path, record)
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
