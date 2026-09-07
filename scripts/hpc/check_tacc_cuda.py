#!/usr/bin/env python3
"""Validate the isolated TACC CUDA environment and optionally record it."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", default="tacc_watermark")
    parser.add_argument("--cuda-module", default="cuda/12.8")
    parser.add_argument("--allow-no-gpu", action="store_true")
    parser.add_argument("--require-slurm", action="store_true")
    parser.add_argument("--minimum-gpus", type=int, default=1)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def git_metadata(root: Path) -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return {
        "commit": commit,
        "dirty_worktree": bool(status),
        "status_sha256": hashlib.sha256(status.encode()).hexdigest(),
    }


def atomic_write(path: Path, payload: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"refusing to replace different environment record: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    args = parse_args()
    if args.minimum_gpus <= 0:
        raise ValueError("minimum-gpus must be positive")
    if os.environ.get("CONDA_DEFAULT_ENV") != args.environment:
        raise RuntimeError(f"activate Conda environment {args.environment!r} first")
    if os.environ.get("PYTHONPATH"):
        raise RuntimeError("PYTHONPATH must be unset to exclude TACC's Python 3.9 MPI packages")
    if args.cuda_module not in os.environ.get("LOADEDMODULES", "").split(":"):
        raise RuntimeError(f"required module is not loaded: {args.cuda_module}")
    if args.require_slurm and not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("this check must run inside a Slurm allocation")

    import numpy
    import scipy
    import torch
    import transformers

    expected_cuda = args.cuda_module.split("/", 1)[1]
    if str(torch.version.cuda) != expected_cuda:
        raise RuntimeError(
            f"PyTorch CUDA {torch.version.cuda!r} does not match module {expected_cuda!r}"
        )
    gpu_count = int(torch.cuda.device_count()) if torch.cuda.is_available() else 0
    if gpu_count < args.minimum_gpus and not args.allow_no_gpu:
        raise RuntimeError(f"found {gpu_count} CUDA devices; need at least {args.minimum_gpus}")

    devices: list[dict[str, Any]] = []
    if gpu_count:
        for index in range(gpu_count):
            properties = torch.cuda.get_device_properties(index)
            devices.append(
                {
                    "index": index,
                    "name": properties.name,
                    "capability": list(torch.cuda.get_device_capability(index)),
                    "total_memory_gib": properties.total_memory / (1024.0**3),
                }
            )
        probe = torch.arange(4096, device="cuda", dtype=torch.float32)
        probe_sum = float((probe * probe).sum().cpu())
        torch.cuda.synchronize()
    else:
        probe_sum = None

    root = Path(__file__).resolve().parents[2]
    slurm_fields = (
        "SLURM_CLUSTER_NAME",
        "SLURM_JOB_ID",
        "SLURM_JOB_NAME",
        "SLURM_JOB_ACCOUNT",
        "SLURM_JOB_PARTITION",
        "SLURM_JOB_NUM_NODES",
        "SLURM_CPUS_PER_TASK",
    )
    record = {
        "schema_version": 1,
        "classification": "runtime_environment_not_admitted_evidence",
        "checked_utc": datetime.now(UTC).isoformat(),
        "environment": {
            "conda_name": os.environ["CONDA_DEFAULT_ENV"],
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python_no_user_site": os.environ.get("PYTHONNOUSERSITE") == "1",
            "pythonpath_unset": not bool(os.environ.get("PYTHONPATH")),
        },
        "dependencies": {
            "torch": torch.__version__,
            "torch_cuda": str(torch.version.cuda),
            "transformers": transformers.__version__,
            "numpy": numpy.__version__,
            "scipy": scipy.__version__,
        },
        "cuda": {
            "module": args.cuda_module,
            "tacc_cuda_dir": os.environ.get("TACC_CUDA_DIR"),
            "available": bool(torch.cuda.is_available()),
            "device_count": gpu_count,
            "devices": devices,
            "tensor_probe_sum": probe_sum,
        },
        "slurm": {
            field.removeprefix("SLURM_").lower(): os.environ[field]
            for field in slurm_fields
            if field in os.environ
        },
        "git": git_metadata(root),
    }
    payload = json.dumps(record, indent=2, sort_keys=True) + "\n"
    if args.output:
        atomic_write(args.output, payload)
    print(payload, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
