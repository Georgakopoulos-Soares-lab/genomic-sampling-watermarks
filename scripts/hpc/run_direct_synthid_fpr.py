#!/usr/bin/env python3
"""Run and resume the v2 FPR generation and detector directly on an A100 node.

Use separate output roots for smoke and full profiles. Generation writes one
validated, immutable shard per prompt and draw; detection writes one per
evaluation prompt. Repeating the same command validates and skips those shards.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shlex
import subprocess
import sys
import time
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.large_validation import (  # noqa: E402
    CALIBRATION_SPLIT_LABEL,
    deterministic_prompt_split,
)
from genomic_watermarks.pilot import cohort_case_digest, load_context_cases_jsonl  # noqa: E402

LABELS = {"carbon": "carbon-synthid-fpr-v2", "generator": "generator-synthid-fpr-v2"}
GENERATION_IDS = {
    "carbon": "carbon_synthid_v2_fpr_generation",
    "generator": "generator_synthid_v2_fpr_generation",
}
DETECTOR_IDS = {
    "carbon": "carbon_synthid_v2_fpr_position_independent",
    "generator": "generator_synthid_v2_fpr_position_independent",
}
MODEL_IDS = {
    "carbon": ("HuggingFaceBio/Carbon-500M", "C_tok", "9796b752108258c1d365089f842e62e6c0547704"),
    "generator": (
        "GenerTeam/GENERator-v2-eukaryote-1.2b-base",
        "G_tok",
        "c41b0018da9ee13b9e96ee54647de8da381ccd72",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=tuple(LABELS), required=True)
    parser.add_argument("--profile", choices=("smoke", "full"), required=True)
    parser.add_argument("--cohort-jsonl", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / ".cache/huggingface")
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--experiment-label")
    parser.add_argument("--experiment-id")
    parser.add_argument("--detector-experiment-id")
    parser.add_argument("--calibration-prompts", type=int, default=64)
    parser.add_argument("--expected-full-prompts", type=int, default=1608)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument(
        "--draw",
        type=int,
        action="append",
        choices=(0, 1),
        dest="draws",
        help="draw index to generate; repeatable. Default both. Use one draw per job on a "
        "single-GPU partition; the summary is written once both draws are finalized.",
    )
    parser.add_argument("--stage", choices=("all", "generation", "detection"), default="all")
    parser.add_argument("--status", action="store_true", help="report shard counts without running")
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, value: dict[str, Any], *, immutable: bool = False) -> None:
    payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if path.exists() and immutable:
        if path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"refusing to change run identity: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def copy_immutable(source: Path, destination: Path) -> None:
    payload = source.read_bytes()
    if destination.exists():
        if destination.read_bytes() != payload:
            raise FileExistsError(f"refusing to change frozen input: {destination}")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)


def checked_config(
    args: argparse.Namespace,
    *,
    cohort_id: str,
    cohort_digest: str,
    cohort_count: int,
    generation_id: str,
    label: str,
) -> None:
    if not args.config:
        return
    config = tomllib.loads(args.config.read_text(encoding="utf-8"))
    model_id, policy_id, revision = MODEL_IDS[args.model]
    expected = {
        "experiment_id": generation_id,
        "model_id": model_id,
        "model_revision": revision,
        "policy_id": policy_id,
        "cohort_id": cohort_id,
        "cohort_sha256": cohort_digest,
        "prompt_count": cohort_count,
        "generated_tokens": 512,
        "device": "cuda",
        "dtype": "bfloat16",
    }
    for field, value in expected.items():
        if config.get(field) != value:
            raise ValueError(f"config {field} disagrees with the direct v2 run")
    generation = config.get("generation", {})
    if generation.get("experiment_label") != label:
        raise ValueError("config generation.experiment_label disagrees with the direct v2 run")
    tournament = config.get("tournament", {})
    for field, value in (("depth", 30), ("context_tokens", 4), ("context_history_size", 1024)):
        if tournament.get(field) != value:
            raise ValueError(f"config tournament.{field} disagrees with the direct v2 run")
    detection = config.get("detection", {})
    for field, value in (
        ("calibration_prompts", args.calibration_prompts),
        ("evaluation_prompts", cohort_count - args.calibration_prompts),
        ("target_fpr", 0.01),
    ):
        if detection.get(field) != value:
            raise ValueError(f"config detection.{field} disagrees with the direct v2 run")
    if "protocol_sha256" in config:
        if not args.protocol or config["protocol_sha256"] != sha256(args.protocol):
            raise ValueError("config protocol_sha256 disagrees with the supplied protocol")


def environment_record(required_gpus: int = 2) -> tuple[dict[str, Any], tuple[str, ...]]:
    import torch

    if not torch.cuda.is_available() or torch.cuda.device_count() < required_gpus:
        raise RuntimeError(
            f"{required_gpus} visible CUDA GPU(s) are required to generate "
            f"{required_gpus} draw(s) concurrently"
        )
    visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    device_ids = (
        tuple(visible.split(",")[:required_gpus])
        if visible
        else tuple(str(index) for index in range(required_gpus))
    )
    if len(device_ids) != required_gpus or any(not item for item in device_ids):
        raise RuntimeError("CUDA_VISIBLE_DEVICES does not expose enough valid device IDs")
    probe = torch.arange(1024, device="cuda", dtype=torch.float32)
    probe_sum = float(probe.sum().cpu())
    torch.cuda.synchronize()
    git_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    return (
        {
            "checked_utc": datetime.now(UTC).isoformat(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "torch": torch.__version__,
            "torch_cuda": torch.version.cuda,
            "numpy": importlib.metadata.version("numpy"),
            "scipy": importlib.metadata.version("scipy"),
            "transformers": importlib.metadata.version("transformers"),
            "git_commit": git_commit,
            "cuda_visible_devices": visible or None,
            "device_count": torch.cuda.device_count(),
            "devices": [
                torch.cuda.get_device_name(index) for index in range(torch.cuda.device_count())
            ],
            "probe_sum": probe_sum,
            "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        },
        tuple(str(item) for item in device_ids),
    )


def run_logged(command: list[str], log: Path, *, env: dict[str, str] | None = None) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    print(shlex.join(command), flush=True)
    with log.open("w", encoding="utf-8") as stream:
        stream.write("command: " + shlex.join(command) + "\n")
        stream.flush()
        completed = subprocess.run(
            command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT
        )
    if completed.returncode:
        raise RuntimeError(f"command failed with code {completed.returncode}; see {log}")


def generation_commands(
    args: argparse.Namespace, *, selected_ids: list[str], generation_id: str, label: str
) -> list[list[str]]:
    steps = 64 if args.profile == "smoke" else 512
    script = ROOT / f"scripts/run_{args.model}_large_generation.py"
    commands = []
    for draw in args.draws:
        command = [
            sys.executable,
            str(script),
            "--output-root",
            str(args.output_root),
            "--cohort-jsonl",
            str(args.cohort_jsonl),
            "--draw-index",
            str(draw),
            "--steps",
            str(steps),
            "--experiment-id",
            generation_id,
            "--experiment-label",
            label,
            "--tournament-depth",
            "30",
            "--context-tokens",
            "4",
            "--context-history-size",
            "1024",
            "--device",
            "cuda",
            "--dtype",
            "bfloat16",
            "--cache-dir",
            str(args.cache_dir),
            "--local-files-only",
            "--finalize",
            "--expected-case-count",
            str(len(selected_ids)),
        ]
        if args.profile == "smoke":
            for case_id in selected_ids:
                command.extend(("--case-id", case_id))
        commands.append(command)
    return commands


def run_generation(
    args: argparse.Namespace,
    *,
    selected_ids: list[str],
    generation_id: str,
    label: str,
    attempt_dir: Path,
) -> None:
    record, gpu_ids = environment_record(len(args.draws))
    record["draws"] = list(args.draws)
    atomic_json(attempt_dir / "environment.json", record)
    commands = generation_commands(
        args, selected_ids=selected_ids, generation_id=generation_id, label=label
    )
    processes: list[subprocess.Popen[str]] = []
    streams = []
    try:
        for draw, (command, gpu_id) in zip(args.draws, zip(commands, gpu_ids, strict=True)):
            log = attempt_dir / f"generation_draw_{draw:02d}.log"
            stream = log.open("w", encoding="utf-8")
            streams.append(stream)
            stream.write("command: " + shlex.join(command) + "\n")
            stream.flush()
            env = os.environ.copy()
            env["CUDA_VISIBLE_DEVICES"] = gpu_id
            env["PYTHONNOUSERSITE"] = "1"
            env["TOKENIZERS_PARALLELISM"] = "false"
            processes.append(
                subprocess.Popen(
                    command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT, text=True
                )
            )
            print(f"draw {draw} pid={processes[-1].pid} gpu={gpu_id} log={log}", flush=True)
        statuses = [process.wait() for process in processes]
        if any(status != 0 for status in statuses):
            raise RuntimeError(f"generation failed: draw exit codes {statuses}")
    except BaseException:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            process.wait()
        raise
    finally:
        for stream in streams:
            stream.close()

    generation_dir = args.output_root / "generation"
    missing = [
        draw
        for draw in (0, 1)
        if not (generation_dir / f"draw_{draw:02d}_sequences.jsonl").is_file()
        or not (generation_dir / f"draw_{draw:02d}_generation.json").is_file()
    ]
    if missing:
        # One draw per job on a single-GPU partition: the cross-draw summary, and therefore
        # detection, waits for the job holding the other draw. This is not a failure.
        print(
            json.dumps(
                {
                    "status": "draws_incomplete",
                    "finalized_draws": [draw for draw in (0, 1) if draw not in missing],
                    "missing_draws": missing,
                    "note": "rerun with --stage detection once every draw is finalized",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return
    command = [
        sys.executable,
        str(ROOT / f"scripts/summarize_{args.model}_large_generation.py"),
        "--output-root",
        str(args.output_root),
        "--cohort-jsonl",
        str(args.cohort_jsonl),
        "--draw-index",
        "0",
        "--draw-index",
        "1",
        "--expected-case-count",
        str(len(selected_ids)),
        "--experiment-id",
        generation_id,
    ]
    run_logged(command, attempt_dir / "generation_summary.log")


def ensure_split(args: argparse.Namespace, case_ids: list[str]) -> int:
    assignments = deterministic_prompt_split(
        case_ids, calibration_prompts=args.calibration_prompts, label=CALIBRATION_SPLIT_LABEL
    )
    record = {
        "schema_version": 1,
        "label": CALIBRATION_SPLIT_LABEL,
        "assignment_rule": (
            "rank sha256(label, case_id); first "
            f"{args.calibration_prompts} calibration, rest evaluation"
        ),
        "calibration_prompts": args.calibration_prompts,
        "assignments": assignments,
    }
    atomic_json(args.output_root / "detection/prompt_split.json", record, immutable=True)
    return sum(value == "evaluation" for value in assignments.values())


def run_detection(
    args: argparse.Namespace,
    *,
    case_ids: list[str],
    label: str,
    generation_id: str,
    detector_id: str,
    cohort_id: str,
    cohort_digest: str,
    attempt_dir: Path,
) -> None:
    if args.profile != "full":
        raise ValueError("position-independent detector needs the full 512-token profile")
    if not args.protocol or not args.protocol.is_file():
        raise FileNotFoundError("--protocol is required for full detection")
    generation_summary = args.output_root / "generation/generation_summary.json"
    if not generation_summary.is_file():
        raise FileNotFoundError("both generation draws must be finalized before detection")
    summary = json.loads(generation_summary.read_text(encoding="utf-8"))
    if (
        summary.get("case_count") != len(case_ids)
        or summary.get("generated_tokens_per_sequence") != 512
        or summary.get("sequence_count") != len(case_ids) * 4
        or summary.get("experiment_id") != generation_id
        or summary.get("experiment_label") != label
        or summary.get("cohort_id") != cohort_id
        or summary.get("cohort_content_sha256") != cohort_digest
        or summary.get("complete") is not True
    ):
        raise ValueError("generation summary is incomplete or has the wrong cohort")
    evaluation_count = ensure_split(args, case_ids)
    if evaluation_count < 1536:
        raise ValueError("v2 FPR evaluation requires at least 1,536 independent prompts")
    output_dir = args.output_root / "position_independent"
    validator = [
        sys.executable,
        str(ROOT / f"scripts/validate_{args.model}_synthid_position_independent.py"),
        "--output-dir",
        str(output_dir),
        "--experiment-id",
        detector_id,
        "--expected-evaluation-prompts",
        str(evaluation_count),
    ]
    if (output_dir / "summary.json").is_file():
        run_logged(validator, attempt_dir / "detector_validator.log")
        return
    command = [
        sys.executable,
        str(ROOT / f"scripts/run_{args.model}_synthid_position_independent.py"),
        "--validation-root",
        str(args.output_root),
        "--cohort-jsonl",
        str(args.cohort_jsonl),
        "--protocol",
        str(args.protocol),
        "--output-dir",
        str(output_dir),
        "--workers",
        str(args.workers),
        "--experiment-id",
        detector_id,
        "--generation-experiment-id",
        generation_id,
        "--experiment-label",
        label,
        "--expected-evaluation-prompts",
        str(evaluation_count),
    ]
    run_logged(command, attempt_dir / "position_independent.log")
    run_logged(validator, attempt_dir / "detector_validator.log")


def main() -> int:
    args = parse_args()
    args.cohort_jsonl = args.cohort_jsonl.resolve()
    args.output_root = args.output_root.resolve()
    args.cache_dir = args.cache_dir.resolve()
    args.protocol = args.protocol.resolve() if args.protocol else None
    args.config = args.config.resolve() if args.config else None
    for path in (args.cohort_jsonl, args.cache_dir):
        if not path.exists():
            raise FileNotFoundError(path)
    if args.workers <= 0 or args.calibration_prompts <= 0:
        raise ValueError("workers and calibration prompts must be positive")
    args.draws = tuple(sorted(set(args.draws))) if args.draws else (0, 1)
    cases = load_context_cases_jsonl(args.cohort_jsonl)
    case_ids = [case.case_id for case in cases]
    if args.profile == "full" and len(cases) != args.expected_full_prompts:
        raise ValueError(
            f"full cohort contains {len(cases)} prompts; expected {args.expected_full_prompts}"
        )
    selected_ids = (
        sorted(
            case_ids,
            key=lambda value: hashlib.sha256(f"{cases[0].cohort_id}\x00{value}".encode()).digest(),
        )[:4]
        if args.profile == "smoke"
        else case_ids
    )
    config = tomllib.loads(args.config.read_text(encoding="utf-8")) if args.config else {}
    label = (
        args.experiment_label
        or config.get("generation", {}).get("experiment_label")
        or LABELS[args.model]
    )
    generation_id = args.experiment_id or config.get("experiment_id") or GENERATION_IDS[args.model]
    detector_id = args.detector_experiment_id or DETECTOR_IDS[args.model]
    if args.status:
        result = {
            "model": args.model,
            "profile": args.profile,
            "selected_prompts": len(selected_ids),
        }
        for draw in (0, 1):
            shard_dir = args.output_root / f"generation/shards/draw_{draw:02d}"
            result[f"draw_{draw:02d}_shards"] = len(tuple(shard_dir.glob("*.json")))
        result["detector_shards"] = len(
            tuple((args.output_root / "position_independent/shards").glob("*.json"))
        )
        result["generation_finalized"] = (
            args.output_root / "generation/generation_summary.json"
        ).is_file()
        result["detector_finalized"] = (
            args.output_root / "position_independent/summary.json"
        ).is_file()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.profile == "full" and args.stage in ("all", "detection") and not args.protocol:
        raise ValueError("--protocol is required for full detection")
    cohort_digest = cohort_case_digest(cases)
    checked_config(
        args,
        cohort_id=cases[0].cohort_id,
        cohort_digest=cohort_digest,
        cohort_count=len(cases),
        generation_id=generation_id,
        label=label,
    )
    sources = [
        Path(__file__),
        ROOT / f"scripts/run_{args.model}_large_generation.py",
        ROOT / f"scripts/summarize_{args.model}_large_generation.py",
        ROOT / f"scripts/run_{args.model}_synthid_position_independent.py",
        ROOT / f"scripts/validate_{args.model}_synthid_position_independent.py",
        ROOT / "src/genomic_watermarks/synthid.py",
        ROOT / "src/genomic_watermarks/synthid_position_independent.py",
    ]
    identity = {
        "schema_version": 1,
        "model": args.model,
        "profile": args.profile,
        "cohort_id": cases[0].cohort_id,
        "cohort_content_sha256": cohort_digest,
        "cohort_jsonl_sha256": sha256(args.cohort_jsonl),
        "selected_case_ids": selected_ids if args.profile == "smoke" else None,
        "selected_count": len(selected_ids),
        "steps": 64 if args.profile == "smoke" else 512,
        "generation_experiment_id": generation_id,
        "detector_experiment_id": detector_id,
        "experiment_label": label,
        "calibration_prompts": args.calibration_prompts,
        "cache_dir": str(args.cache_dir),
        "config_sha256": sha256(args.config) if args.config else None,
        "protocol_sha256": sha256(args.protocol) if args.protocol else None,
        "source_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in sources},
    }
    # Detection can legitimately run under a later code revision than generation, so it
    # records its own immutable identity instead of overwriting the generation one. The
    # two files together state exactly which sources produced which stage.
    identity_name = (
        "run_identity_detection.json" if args.stage == "detection" else "run_identity.json"
    )
    atomic_json(args.output_root / "orchestration" / identity_name, identity, immutable=True)
    copy_immutable(args.cohort_jsonl, args.output_root / "prompts.jsonl")
    if args.config:
        copy_immutable(args.config, args.output_root / "resolved_config.toml")
    attempt_dir = (
        args.output_root
        / "orchestration/attempts"
        / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}_{os.getpid()}"
    )
    attempt_dir.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    atomic_json(
        attempt_dir / "status.json",
        {
            "status": "running",
            "started_utc": datetime.now(UTC).isoformat(),
            "draws": list(args.draws),
            "command": shlex.join([sys.executable, *sys.argv]),
        },
    )
    try:
        if args.stage in ("all", "generation"):
            run_generation(
                args,
                selected_ids=selected_ids,
                generation_id=generation_id,
                label=label,
                attempt_dir=attempt_dir,
            )
        if args.stage in ("all", "detection") and args.profile == "full":
            run_detection(
                args,
                case_ids=case_ids,
                label=label,
                generation_id=generation_id,
                detector_id=detector_id,
                cohort_id=cases[0].cohort_id,
                cohort_digest=cohort_digest,
                attempt_dir=attempt_dir,
            )
    except BaseException as error:
        atomic_json(
            attempt_dir / "status.json",
            {
                "status": "failed",
                "error": repr(error),
                "elapsed_seconds": time.monotonic() - started,
            },
        )
        raise
    atomic_json(
        attempt_dir / "status.json",
        {
            "status": "complete",
            "elapsed_seconds": time.monotonic() - started,
        },
    )
    print(json.dumps({"status": "complete", "attempt_dir": str(attempt_dir)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
