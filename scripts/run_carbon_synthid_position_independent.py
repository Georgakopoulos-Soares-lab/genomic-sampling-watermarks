#!/usr/bin/env python3
"""Run the frozen Carbon position-independent SynthID detector validation."""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.large_validation import (  # noqa: E402
    cluster_bootstrap_interval,
    fixture_key,
    sha256_file,
)
from genomic_watermarks.synthid import SYNTHID_SCHEME  # noqa: E402
from genomic_watermarks.synthid_boundary import (  # noqa: E402
    deterministic_single_base_edit,
)
from genomic_watermarks.synthid_position_independent import (  # noqa: E402
    POSITION_INDEPENDENT_SYNTHID_DETECTOR,
    PositionIndependentSynthIDConfig,
    detect_synthid_position_independent,
)
from genomic_watermarks.watermark import ORDINARY_SCHEME, public_replay_seed  # noqa: E402

DEFAULT_VALIDATION_ROOT = Path("/scratch/10899/kimopro/carbon_synthid_validation_hpc_v4")
DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_large_v1/prompts.jsonl"
DEFAULT_OUTPUT = ROOT / "outputs/carbon_synthid_position_independent_v1"
DEFAULT_PROTOCOL = ROOT / "docs/research/carbon_synthid_position_independent_validation_protocol.md"
EXPERIMENT_ID = "carbon_synthid_position_independent_v1"
POSITIVE = "watermarked_correct_key"
PRIMARY_NULL = "ordinary_corresponding_key"
WRONG_KEY = "watermarked_wrong_key"
FAMILIES = (POSITIVE, PRIMARY_NULL, WRONG_KEY)
CONDITIONS = ("clean", "substitution_1nt", "insertion_1nt", "deletion_1nt")
WINDOW_BASE_LENGTHS = (384, 768, 1536, 3072)
TARGET_FPR = 0.01
EXPECTED_PROMPTS = 192
DRAWS = (0, 1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-root", type=Path, default=DEFAULT_VALIDATION_ROOT)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--bootstrap-replicates", type=int, default=20_000)
    parser.add_argument("--analysis-seed", type=int, default=2718)
    parser.add_argument("--finalize-only", action="store_true")
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to replace existing artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    if temporary.exists():
        raise FileExistsError(f"temporary output already exists: {temporary}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def exact_interval(successes: int, trials: int, confidence: float = 0.95) -> list[float]:
    from scipy.stats import beta

    if not 0 <= successes <= trials or trials <= 0:
        raise ValueError("invalid exact-interval counts")
    tail = (1.0 - confidence) / 2.0
    lower = 0.0 if successes == 0 else float(beta.ppf(tail, successes, trials - successes + 1))
    upper = (
        1.0
        if successes == trials
        else float(beta.ppf(1.0 - tail, successes + 1, trials - successes))
    )
    return [lower, upper]


def expected_hypotheses(read_bases: int) -> int:
    return 2 * sum(read_bases - length + 1 for length in WINDOW_BASE_LENGTHS)


def _edited(sequence: str, *, condition: str, case_id: str, draw_id: int) -> tuple[str, int | None]:
    if condition == "clean":
        return sequence, None
    edit = deterministic_single_base_edit(
        sequence,
        condition=condition,
        case_id=case_id,
        draw_id=draw_id,
    )
    return edit.sequence, edit.position


def evaluate_prompt(work: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    case_id = str(work["case_id"])
    prompt = str(work["prompt"])
    records = work["records"]
    rows: list[dict[str, Any]] = []
    config = PositionIndependentSynthIDConfig()
    for draw_id in DRAWS:
        watermarked_record = records[f"{draw_id}:{SYNTHID_SCHEME}"]
        ordinary_record = records[f"{draw_id}:{ORDINARY_SCHEME}"]
        domain = str(watermarked_record["stream_domain"])
        if str(ordinary_record["stream_domain"]) != domain:
            raise ValueError("matched generation arms disagree on the SynthID domain")
        source_sequences = {
            POSITIVE: str(watermarked_record["generated_dna"]),
            PRIMARY_NULL: str(ordinary_record["generated_dna"]),
            WRONG_KEY: str(watermarked_record["generated_dna"]),
        }
        key_indices = {
            POSITIVE: draw_id,
            PRIMARY_NULL: draw_id,
            WRONG_KEY: (draw_id + 1) % 2,
        }
        for condition in CONDITIONS:
            edited: dict[str, str] = {}
            positions: dict[str, int | None] = {}
            for family in FAMILIES:
                edited[family], positions[family] = _edited(
                    source_sequences[family],
                    condition=condition,
                    case_id=case_id,
                    draw_id=draw_id,
                )
            if positions[POSITIVE] != positions[PRIMARY_NULL]:
                raise RuntimeError("matched arms received different edit positions")
            for family in FAMILIES:
                observed = prompt + edited[family]
                result = detect_synthid_position_independent(
                    observed,
                    key=fixture_key(key_indices[family]),
                    domain=domain,
                    config=config,
                )
                rows.append(
                    {
                        "case_id": case_id,
                        "draw_id": draw_id,
                        "condition": condition,
                        "family": family,
                        "key_index": key_indices[family],
                        "prompt_bases": len(prompt),
                        "generated_bases_after_edit": len(edited[family]),
                        "observed_bases": len(observed),
                        "edit_position_in_generation": positions[family],
                        **asdict(result),
                    }
                )
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "case_id": case_id,
        "complete": True,
        "runtime_seconds": time.perf_counter() - started,
        "rows": rows,
    }


def validate_prompt_shard(shard: dict[str, Any], case_id: str) -> None:
    if shard.get("schema_version") != 1 or shard.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError(f"invalid shard identity for {case_id}")
    if shard.get("case_id") != case_id or shard.get("complete") is not True:
        raise ValueError(f"incomplete shard for {case_id}")
    rows = shard.get("rows")
    expected = len(DRAWS) * len(CONDITIONS) * len(FAMILIES)
    if not isinstance(rows, list) or len(rows) != expected:
        raise ValueError(f"shard {case_id} has the wrong row count")
    identities = {(row.get("draw_id"), row.get("condition"), row.get("family")) for row in rows}
    expected_identities = {
        (draw, condition, family)
        for draw in DRAWS
        for condition in CONDITIONS
        for family in FAMILIES
    }
    if identities != expected_identities:
        raise ValueError(f"shard {case_id} has an incomplete trial grid")


def summarize_rate(
    rows: list[dict[str, Any]],
    *,
    bootstrap_replicates: int,
    seed: int,
) -> dict[str, Any]:
    by_prompt: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_prompt[str(row["case_id"])].append(float(bool(row["detected"])))
    values = [value for prompt_values in by_prompt.values() for value in prompt_values]
    cluster_interval = cluster_bootstrap_interval(
        by_prompt,
        replicates=bootstrap_replicates,
        seed=seed,
    )
    prompt_any = sum(any(prompt_values) for prompt_values in by_prompt.values())
    prompt_all = sum(all(prompt_values) for prompt_values in by_prompt.values())
    log_ps = [float(row["sequence_log_p_value"]) for row in rows]
    statistics_values = [float(row["best_hypothesis"]["statistic"]) for row in rows]
    return {
        "detections": int(sum(values)),
        "trials": len(values),
        "rate": statistics.fmean(values),
        "prompt_cluster_bootstrap_95_interval": list(cluster_interval),
        "prompt_clusters": len(by_prompt),
        "prompt_any_draw": {
            "detections": prompt_any,
            "trials": len(by_prompt),
            "exact_95_interval": exact_interval(prompt_any, len(by_prompt)),
        },
        "prompt_both_draws": {
            "detections": prompt_all,
            "trials": len(by_prompt),
            "exact_95_interval": exact_interval(prompt_all, len(by_prompt)),
        },
        "sequence_log_p_value": {
            "minimum": min(log_ps),
            "median": statistics.median(log_ps),
            "maximum": max(log_ps),
        },
        "best_statistic": {
            "minimum": min(statistics_values),
            "median": statistics.median(statistics_values),
            "maximum": max(statistics_values),
        },
        "winning_orientation_counts": dict(
            sorted(Counter(row["best_hypothesis"]["orientation"] for row in rows).items())
        ),
        "winning_window_base_length_counts": {
            str(key): value
            for key, value in sorted(
                Counter(row["best_hypothesis"]["window_base_length"] for row in rows).items()
            )
        },
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Carbon SynthID position-independent detector validation",
        "",
        "The detector received no prompt boundary, phase, strand, or offset. It searched both",
        "orientations, every nucleotide start, and all four declared lengths in one globally",
        "corrected decision. Generation and calibration were not rerun.",
        "",
        "## Sequence-level detection",
        "",
        "| Condition | Family | Detections | Rate | Prompt-cluster 95% interval |",
        "|---|---|---:|---:|---:|",
    ]
    for cell in summary["rates"]:
        interval = cell["prompt_cluster_bootstrap_95_interval"]
        lines.append(
            f"| {cell['condition']} | {cell['family']} | "
            f"{cell['detections']}/{cell['trials']} | {cell['rate']:.4%} | "
            f"{interval[0]:.4%}–{interval[1]:.4%} |"
        )
    lines.extend(
        [
            "",
            "## Protocol facts",
            "",
            f"- Evaluation prompts: {summary['evaluation_prompts']}",
            f"- Draws per prompt: {summary['draws_per_prompt']}",
            f"- Total decisions: {summary['total_decisions']}",
            "- Search: both orientations × every nucleotide start × 384/768/1,536/3,072 bases",
            "- Decision: exact local fair-binomial tail with one global Bonferroni correction",
            "- Calibration rerun: no",
            "- Generation rerun: no",
            "",
            "This is a detector validation only. It does not establish biological function,",
            "viability, adversarial authenticity, or secret-key security from many observations.",
            "",
        ]
    )
    return "\n".join(lines)


def finalize(
    *,
    args: argparse.Namespace,
    evaluation_ids: list[str],
    generation_paths: list[Path],
    started: float,
) -> None:
    final_paths = (
        args.output_dir / "trials.jsonl",
        args.output_dir / "summary.json",
        args.output_dir / "report.md",
    )
    if any(path.exists() for path in final_paths):
        raise FileExistsError("refusing to replace an existing finalized result")
    rows: list[dict[str, Any]] = []
    runtime_seconds = 0.0
    for case_id in evaluation_ids:
        shard_path = args.output_dir / "shards" / f"{case_id}.json"
        if not shard_path.exists():
            raise FileNotFoundError(f"missing prompt shard: {shard_path}")
        shard = json.loads(shard_path.read_text())
        validate_prompt_shard(shard, case_id)
        rows.extend(shard["rows"])
        runtime_seconds += float(shard["runtime_seconds"])
    expected_rows = EXPECTED_PROMPTS * len(DRAWS) * len(CONDITIONS) * len(FAMILIES)
    if len(rows) != expected_rows:
        raise RuntimeError(f"found {len(rows)} decisions, expected {expected_rows}")
    rows.sort(key=lambda row: (row["case_id"], row["draw_id"], row["condition"], row["family"]))
    trials_path = args.output_dir / "trials.jsonl"
    trials_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    trials_path.write_text(trials_text)

    rates: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        for family in FAMILIES:
            selected = [
                row for row in rows if row["condition"] == condition and row["family"] == family
            ]
            rates.append(
                {
                    "condition": condition,
                    "family": family,
                    **summarize_rate(
                        selected,
                        bootstrap_replicates=args.bootstrap_replicates,
                        seed=public_replay_seed(
                            EXPERIMENT_ID,
                            str(args.analysis_seed),
                            condition,
                            family,
                            "bootstrap",
                        ),
                    ),
                }
            )
    summary: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "classification": "validation_result_pending_evidence_admission",
        "watermark_scope": "synthid-tournament-v1 only",
        "detector_id": POSITION_INDEPENDENT_SYNTHID_DETECTOR,
        "model_id": "HuggingFaceBio/Carbon-500M",
        "revision": "9796b752108258c1d365089f842e62e6c0547704",
        "policy_id": "C_tok",
        "evaluation_prompts": EXPECTED_PROMPTS,
        "draws_per_prompt": len(DRAWS),
        "families": list(FAMILIES),
        "conditions": list(CONDITIONS),
        "window_base_lengths": list(WINDOW_BASE_LENGTHS),
        "orientations": ["forward", "reverse_complement"],
        "target_sequence_false_positive_rate": TARGET_FPR,
        "calibration": (
            "none; analytic exact-binomial local tests plus one global Bonferroni correction"
        ),
        "generation_rerun": False,
        "calibration_rerun": False,
        "total_decisions": len(rows),
        "expected_hypotheses_by_observed_bases": {
            str(length): expected_hypotheses(length) for length in (3455, 3456, 3457)
        },
        "rates": rates,
        "worker_runtime_seconds_sum": runtime_seconds,
        "finalization_runtime_seconds": time.perf_counter() - started,
        "provenance": {
            "command": "scripts/run_carbon_synthid_position_independent.py",
            "workers": args.workers,
            "bootstrap_replicates": args.bootstrap_replicates,
            "analysis_seed": args.analysis_seed,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cohort": {
                "path": str(args.cohort_jsonl.resolve()),
                "sha256": sha256_file(args.cohort_jsonl),
            },
            "prompt_split": {
                "path": str((args.validation_root / "detection/prompt_split.json").resolve()),
                "sha256": sha256_file(args.validation_root / "detection/prompt_split.json"),
            },
            "generation": [
                {"path": str(path.resolve()), "sha256": sha256_file(path)}
                for path in generation_paths
            ],
            "protocol": {
                "path": str(args.protocol.resolve()),
                "sha256": sha256_file(args.protocol),
            },
            "detector": {
                "path": str(
                    (ROOT / "src/genomic_watermarks/synthid_position_independent.py").resolve()
                ),
                "sha256": sha256_file(
                    ROOT / "src/genomic_watermarks/synthid_position_independent.py"
                ),
            },
            "boundary_core": {
                "path": str((ROOT / "src/genomic_watermarks/synthid_boundary.py").resolve()),
                "sha256": sha256_file(ROOT / "src/genomic_watermarks/synthid_boundary.py"),
            },
            "synthid_core": {
                "path": str((ROOT / "src/genomic_watermarks/synthid.py").resolve()),
                "sha256": sha256_file(ROOT / "src/genomic_watermarks/synthid.py"),
            },
            "runner": {
                "path": str(Path(__file__).resolve()),
                "sha256": sha256_file(Path(__file__).resolve()),
            },
            "validator": {
                "path": str(
                    (ROOT / "scripts/validate_carbon_synthid_position_independent.py").resolve()
                ),
                "sha256": sha256_file(
                    ROOT / "scripts/validate_carbon_synthid_position_independent.py"
                ),
            },
        },
        "trials_artifact": {"path": str(trials_path.resolve()), "sha256": sha256_file(trials_path)},
        "flags": [
            "Fixture keys are public reproducibility material, not deployment secrets.",
            "Single edits are one nucleotide event, not a one-percent edit rate.",
            "This detector-only run does not re-evaluate model quality or biological function.",
            "Prompt-correlated draws do not provide 384 independent prompt clusters.",
        ],
    }
    report_path = args.output_dir / "report.md"
    report_path.write_text(render_report(summary))
    summary["report_artifact"] = {
        "path": str(report_path.resolve()),
        "sha256": sha256_file(report_path),
    }
    atomic_write_json(args.output_dir / "summary.json", summary)


def main() -> int:
    args = parse_args()
    if args.workers <= 0 or args.bootstrap_replicates <= 0:
        raise ValueError("workers and bootstrap replicates must be positive")
    if not args.protocol.exists():
        raise FileNotFoundError(args.protocol)
    started = time.perf_counter()
    cohort_rows = load_jsonl(args.cohort_jsonl)
    prompts = {str(row["prompt_id"]): str(row["sequence"]) for row in cohort_rows}
    split_path = args.validation_root / "detection/prompt_split.json"
    split = json.loads(split_path.read_text())
    evaluation_ids = sorted(
        case_id
        for case_id, assignment in split["assignments"].items()
        if assignment == "evaluation"
    )
    if len(evaluation_ids) != EXPECTED_PROMPTS:
        raise ValueError(
            f"expected {EXPECTED_PROMPTS} evaluation prompts, found {len(evaluation_ids)}"
        )
    if any(len(prompts[case_id]) != 384 for case_id in evaluation_ids):
        raise ValueError("every selected prompt must contain 384 bases")

    records: dict[tuple[str, int, str], dict[str, Any]] = {}
    generation_paths: list[Path] = []
    for draw_id in DRAWS:
        path = args.validation_root / f"generation/draw_{draw_id:02d}_sequences.jsonl"
        generation_paths.append(path)
        for row in load_jsonl(path):
            case_id = str(row["case_id"])
            if case_id in evaluation_ids:
                records[(case_id, draw_id, str(row["scheme"]))] = row
    expected_records = EXPECTED_PROMPTS * len(DRAWS) * 2
    if len(records) != expected_records:
        raise ValueError(f"found {len(records)} generation records, expected {expected_records}")

    if not args.finalize_only:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        pending: list[dict[str, Any]] = []
        for case_id in evaluation_ids:
            shard_path = args.output_dir / "shards" / f"{case_id}.json"
            if shard_path.exists():
                validate_prompt_shard(json.loads(shard_path.read_text()), case_id)
                continue
            selected_records = {
                f"{draw}:{scheme}": records[(case_id, draw, scheme)]
                for draw in DRAWS
                for scheme in (SYNTHID_SCHEME, ORDINARY_SCHEME)
            }
            pending.append(
                {"case_id": case_id, "prompt": prompts[case_id], "records": selected_records}
            )
        completed = EXPECTED_PROMPTS - len(pending)
        if args.workers == 1:
            results = ((work["case_id"], evaluate_prompt(work)) for work in pending)
            for case_id, shard in results:
                atomic_write_json(args.output_dir / "shards" / f"{case_id}.json", shard)
                completed += 1
                print(
                    json.dumps({"completed_prompts": completed, "total_prompts": EXPECTED_PROMPTS}),
                    flush=True,
                )
        else:
            with ProcessPoolExecutor(max_workers=args.workers) as executor:
                futures = {
                    executor.submit(evaluate_prompt, work): work["case_id"] for work in pending
                }
                for future in as_completed(futures):
                    case_id = str(futures[future])
                    shard = future.result()
                    atomic_write_json(args.output_dir / "shards" / f"{case_id}.json", shard)
                    completed += 1
                    print(
                        json.dumps(
                            {"completed_prompts": completed, "total_prompts": EXPECTED_PROMPTS}
                        ),
                        flush=True,
                    )
    finalize(
        args=args,
        evaluation_ids=evaluation_ids,
        generation_paths=generation_paths,
        started=started,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
