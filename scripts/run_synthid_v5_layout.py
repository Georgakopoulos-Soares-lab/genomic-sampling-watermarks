#!/usr/bin/env python3
"""Run the v5 layout study (S1) with the unchanged position-independent SynthID verifier.

Protocol: ``docs/research/synthid_v5_review_studies_protocol_2026_11_12.md``, Section 5.

For every evaluated prompt (the first ``--evaluated-prompts`` held-out prompts in split-rank
order), both draws, both families and each of the 54 layout cells, one read is built by
``genomic_watermarks.review_layouts`` and scored by
``detect_synthid_position_independent`` with its default configuration.  One immutable shard is
written per prompt, so an interrupted run resumes by validating and skipping finished prompts.
The final step writes ``trials.jsonl.gz`` and ``summary.json`` including the two protocol
validity checks.  Keys are public fixtures; only their indices are recorded.
"""

from __future__ import annotations

import argparse
import dataclasses
import gzip
import hashlib
import json
import math
import os
import platform
import shlex
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from run_carbon_synthid_position_independent import exact_interval  # noqa: E402

from genomic_watermarks.dna import normalize_dna, reverse_complement  # noqa: E402
from genomic_watermarks.large_validation import (  # noqa: E402
    CALIBRATION_SPLIT_LABEL,
    deterministic_prompt_split,
    fixture_key,
    sha256_file,
)
from genomic_watermarks.pilot import ContextCase, load_context_cases_jsonl  # noqa: E402
from genomic_watermarks.review_layouts import (  # noqa: E402
    CONTINUATION_BASES,
    PROMPT_BASES,
    REFERENCE_CELL,
    LayoutCell,
    LayoutRead,
    NaturalPool,
    build_read,
    cell_by_name,
    layout_cells,
)
from genomic_watermarks.synthid import SYNTHID_SCHEME  # noqa: E402
from genomic_watermarks.synthid_position_independent import (  # noqa: E402
    POSITION_INDEPENDENT_SYNTHID_DETECTOR,
    PositionIndependentDetection,
    PositionIndependentSynthIDConfig,
    detect_synthid_position_independent,
)
from genomic_watermarks.watermark import ORDINARY_SCHEME  # noqa: E402

PROTOCOL_ID = "synthid_v5_review_studies_protocol_2026_11_12"
DEFAULT_PROTOCOL = ROOT / f"docs/research/{PROTOCOL_ID}.md"
COHORT_ID = "ncbi_refseq_eukaryote_windows_fpr_v2_1608"
DEFAULT_COHORT = ROOT / "data/processed" / COHORT_ID / "prompts.jsonl"
DEFAULT_NATURAL_DIR = ROOT / "data/raw" / COHORT_ID
EXPECTED_COHORT_JSONL_SHA256 = "cb19e90662fcb25f774b0840e2e696132e2dc9c54439d97597bd186d4948f775"
EXPERIMENT_ID = "synthid_v5_s1_layout"
SCHEMA_VERSION = 1
POSITIVE = "watermarked_correct_key"
PRIMARY_NULL = "ordinary_corresponding_key"
FAMILIES = (POSITIVE, PRIMARY_NULL)
FAMILY_SCHEME = {POSITIVE: SYNTHID_SCHEME, PRIMARY_NULL: ORDINARY_SCHEME}
DRAWS = (0, 1)
WINDOW_BASE_LENGTHS = (384, 768, 1536, 3072)
TARGET_FPR = 0.01
CONFIDENCE = 0.95
MODELS = {
    "C_tok": ("HuggingFaceBio/Carbon-500M", "9796b752108258c1d365089f842e62e6c0547704"),
    "G_tok": (
        "GenerTeam/GENERator-v2-eukaryote-1.2b-base",
        "c41b0018da9ee13b9e96ee54647de8da381ccd72",
    ),
}
CODE_FILES = (
    "scripts/run_synthid_v5_layout.py",
    "scripts/run_carbon_synthid_position_independent.py",
    "src/genomic_watermarks/review_layouts.py",
    "src/genomic_watermarks/synthid_position_independent.py",
    "src/genomic_watermarks/synthid_boundary.py",
    "src/genomic_watermarks/synthid.py",
    "src/genomic_watermarks/dna.py",
    "src/genomic_watermarks/large_validation.py",
    "src/genomic_watermarks/pilot.py",
)
LN10 = math.log(10.0)

# Set in each worker process by ``_init_worker`` (spawn-safe: spans are pickled once).
_WORKER_POOL: NaturalPool | None = None


# --------------------------------------------------------------------------- arguments


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--generation-root", type=Path, help="holds generation/draw_XX_sequences.jsonl"
    )
    parser.add_argument(
        "--sequence-file",
        type=Path,
        action="append",
        dest="sequence_files",
        help="generation rows (repeatable); overrides the files under --generation-root",
    )
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument(
        "--expected-cohort-jsonl-sha256",
        default=EXPECTED_COHORT_JSONL_SHA256,
        help="protocol digest of prompts.jsonl; pass an empty string to disable (tests only)",
    )
    parser.add_argument("--natural-dir", type=Path, default=DEFAULT_NATURAL_DIR)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--experiment-label", required=True)
    parser.add_argument("--cohort-id", default=COHORT_ID)
    parser.add_argument("--policy-id", required=True, choices=("C_tok", "G_tok"))
    parser.add_argument("--generation-experiment-id")
    parser.add_argument("--evaluated-prompts", type=int, required=True)
    parser.add_argument("--calibration-prompts", type=int, default=64)
    parser.add_argument("--split-label", default=CALIBRATION_SPLIT_LABEL)
    parser.add_argument("--cells", nargs="+", help="restrict to these cell names (testing only)")
    parser.add_argument(
        "--s0-trials",
        type=Path,
        help="S0 trials.jsonl (or .jsonl.gz) for validity check 1; required unless "
        "--no-s0-check is given",
    )
    parser.add_argument(
        "--no-s0-check",
        action="store_true",
        help="skip validity check 1 (unit tests and smoke runs only; recorded in the summary)",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--finalize-only", action="store_true")
    args = parser.parse_args(argv)
    if args.s0_trials is None and not args.no_s0_check:
        parser.error("--s0-trials is required unless --no-s0-check is given")
    if args.s0_trials is not None and args.no_s0_check:
        parser.error("--s0-trials and --no-s0-check are mutually exclusive")
    return args


def selected_cells(names: Sequence[str] | None) -> tuple[LayoutCell, ...]:
    cells = layout_cells()
    if not names:
        return cells
    wanted = {part for name in names for part in name.split(",") if part}
    unknown = wanted - {cell.cell for cell in cells}
    if unknown:
        raise ValueError(f"unknown cells: {sorted(unknown)}")
    return tuple(cell for cell in cells if cell.cell in wanted)


# --------------------------------------------------------------------------- inputs


def held_out_order(case_ids: Sequence[str], *, calibration_prompts: int, label: str) -> list[str]:
    """Held-out prompts in split-rank order (the rank is sha256(label, case id))."""

    ranked = sorted(
        (str(case_id) for case_id in case_ids),
        key=lambda case_id: (hashlib.sha256(f"{label}\x00{case_id}".encode()).digest(), case_id),
    )
    held_out = ranked[calibration_prompts:]
    assignments = deterministic_prompt_split(
        case_ids, calibration_prompts=calibration_prompts, label=label
    )
    if set(held_out) != {case for case, value in assignments.items() if value == "evaluation"}:
        raise RuntimeError("held-out order disagrees with the frozen prompt split")
    return held_out


def parse_fasta(text: str) -> str:
    return normalize_dna(
        "".join(line.strip() for line in text.splitlines() if line and not line.startswith(">"))
    )


def load_natural_spans(
    natural_dir: Path, cases: Sequence[ContextCase]
) -> tuple[dict[str, str], dict[str, str]]:
    """Read one FASTA per prompt; return spans and per-file sha256 digests."""

    spans: dict[str, str] = {}
    digests: dict[str, str] = {}
    for case in cases:
        path = natural_dir / f"{case.case_id}.fasta"
        if not path.is_file():
            raise FileNotFoundError(f"missing natural span: {path}")
        raw = path.read_bytes()
        span = parse_fasta(raw.decode("ascii"))
        if len(span) != CONTINUATION_BASES:
            raise ValueError(f"{path} has {len(span)} bases, expected 3072")
        if span[:PROMPT_BASES] != case.sequence:
            raise ValueError(f"the first 384 bases of {path} are not the prompt")
        spans[case.case_id] = span
        digests[case.case_id] = hashlib.sha256(raw).hexdigest()
    return spans, digests


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_generation_records(
    paths: Sequence[Path],
    *,
    selected: Sequence[str],
    prompts: Mapping[str, str],
    label: str,
    cohort_id: str,
    policy_id: str,
    generation_experiment_id: str | None,
) -> dict[str, dict[int, dict[str, str]]]:
    """Return ``records[case_id][draw_id] = {watermarked, ordinary, domain}`` and verify them."""

    wanted = set(selected)
    expected_domain = f"{label}/{cohort_id}/{policy_id}"
    found: dict[tuple[str, int, str], dict[str, Any]] = {}
    for path in paths:
        for row in load_jsonl(path):
            if (
                str(row.get("experiment_label")) != label
                or str(row.get("policy_id")) != policy_id
                or str(row.get("cohort_id")) != cohort_id
                or (
                    generation_experiment_id is not None
                    and str(row.get("experiment_id")) != generation_experiment_id
                )
            ):
                raise ValueError(
                    f"generation record in {path} does not belong to the requested run"
                )
            case_id = str(row["case_id"])
            if case_id not in wanted:
                continue
            identity = (case_id, int(row["draw_id"]), str(row["scheme"]))
            if identity in found:
                raise ValueError(f"duplicate generation record {identity}")
            found[identity] = row
    records: dict[str, dict[int, dict[str, str]]] = {}
    for case_id in selected:
        records[case_id] = {}
        for draw_id in DRAWS:
            try:
                marked = found[(case_id, draw_id, SYNTHID_SCHEME)]
                ordinary = found[(case_id, draw_id, ORDINARY_SCHEME)]
            except KeyError as error:
                raise ValueError(f"missing generation record {error} for {case_id}") from error
            domain = str(marked["stream_domain"])
            if domain != str(ordinary["stream_domain"]) or domain != expected_domain:
                raise ValueError(f"stream domain for {case_id} is not {expected_domain}")
            dnas = {}
            for name, row in (("watermarked", marked), ("ordinary", ordinary)):
                dna = normalize_dna(str(row["generated_dna"]))
                if len(dna) != CONTINUATION_BASES:
                    raise ValueError(f"{case_id} draw {draw_id} {name} is not 3,072 bases")
                prompt_sha = row.get("prompt_sequence_sha256")
                if (
                    prompt_sha is not None
                    and prompt_sha != hashlib.sha256(prompts[case_id].encode("ascii")).hexdigest()
                ):
                    raise ValueError(f"{case_id} generation row has a different prompt")
                dnas[name] = dna
            records[case_id][draw_id] = {**dnas, "domain": domain}
    return records


# --------------------------------------------------------------------------- detection


def build_cell_read(
    cell: LayoutCell,
    *,
    prompt: str,
    continuation: str,
    pool: NaturalPool,
    case_id: str,
    draw_id: int,
) -> LayoutRead:
    """Build one read with ``review_layouts.build_read``.

    A reverse-complemented cell is built as the reverse complement of its forward twin.
    ``build_read`` hashes the full cell name into the flank streams, so ``C_*_fw`` and
    ``C_*_rc`` would otherwise receive different flanks and protocol check 2 (a read and its
    reverse complement) could not hold.  The coordinates are the module's own arithmetic.
    """

    arguments = {
        "prompt": prompt,
        "continuation": continuation,
        "pool": pool,
        "case_id": case_id,
        "draw_id": draw_id,
    }
    if not cell.reverse_complemented:
        return build_read(cell, **arguments)
    twin = cell_by_name(cell.cell.removesuffix("_rc") + "_fw")
    if dataclasses.replace(twin, cell=cell.cell, reverse_complemented=True) != cell:
        raise RuntimeError(f"cell {cell.cell} is not the strand twin of {twin.cell}")
    forward = build_read(twin, **arguments)
    return LayoutRead(
        cell.cell,
        reverse_complement(forward.sequence),
        len(forward.sequence) - forward.region_start - forward.region_length,
        forward.region_length,
        False,
    )


def region_overlap(detection: PositionIndependentDetection, read: LayoutRead) -> int:
    best = detection.best_hypothesis
    low = max(best.original_start, read.region_start)
    high = min(best.original_stop, read.region_start + read.region_length)
    return max(0, high - low)


def decision_row(
    *,
    case_id: str,
    draw_id: int,
    family: str,
    cell: LayoutCell,
    read: LayoutRead,
    detection: PositionIndependentDetection,
) -> dict[str, Any]:
    best = detection.best_hypothesis
    return {
        "case_id": case_id,
        "draw_id": draw_id,
        "family": family,
        "cell": cell.cell,
        "series": cell.series,
        "key_index": draw_id,
        "read_bases": len(read.sequence),
        "region_start": read.region_start,
        "region_length": read.region_length,
        "region_on_forward_strand": read.region_on_forward_strand,
        "detected": bool(detection.detected),
        "sequence_p_value": detection.sequence_p_value,
        "sequence_log_p_value": detection.sequence_log_p_value,
        "minimum_local_p_value": detection.minimum_local_p_value,
        "minimum_local_log_p_value": detection.minimum_local_log_p_value,
        "strength": max(0.0, -detection.minimum_local_log_p_value / LN10),
        "hypotheses_searched": detection.hypotheses_searched,
        "best_orientation": best.orientation,
        "best_oriented_start": best.oriented_start,
        "best_original_start": best.original_start,
        "best_original_stop": best.original_stop,
        "best_window_base_length": best.window_base_length,
        "best_g_ones": best.g_ones,
        "best_g_total": best.g_total,
        "region_overlap_bases": region_overlap(detection, read),
        "marked_bases_retained": read.region_length if cell.series == "F" else None,
    }


def evaluate_prompt(work: dict[str, Any], pool: NaturalPool) -> dict[str, Any]:
    started = time.perf_counter()
    case_id = str(work["case_id"])
    config = PositionIndependentSynthIDConfig()
    cells = [cell_by_name(name) for name in work["cells"]]
    rows: list[dict[str, Any]] = []
    cell_seconds: dict[str, float] = {cell.cell: 0.0 for cell in cells}
    for draw_id in DRAWS:
        record = work["records"][draw_id]
        key = fixture_key(draw_id)
        for cell in cells:
            for family in FAMILIES:
                continuation = record["watermarked" if family == POSITIVE else "ordinary"]
                read = build_cell_read(
                    cell,
                    prompt=str(work["prompt"]),
                    continuation=continuation,
                    pool=pool,
                    case_id=case_id,
                    draw_id=draw_id,
                )
                tick = time.perf_counter()
                detection = detect_synthid_position_independent(
                    read.sequence, key=key, domain=record["domain"], config=config
                )
                cell_seconds[cell.cell] += time.perf_counter() - tick
                rows.append(
                    decision_row(
                        case_id=case_id,
                        draw_id=draw_id,
                        family=family,
                        cell=cell,
                        read=read,
                        detection=detection,
                    )
                )
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": str(work["experiment_id"]),
        "run_identity_sha256": str(work["run_identity_sha256"]),
        "case_id": case_id,
        "complete": True,
        "cells": [cell.cell for cell in cells],
        "runtime_seconds": time.perf_counter() - started,
        "cell_seconds": cell_seconds,
        "rows": rows,
    }


def _init_worker(spans: dict[str, str]) -> None:
    global _WORKER_POOL
    _WORKER_POOL = NaturalPool(spans)


def _worker(work: dict[str, Any]) -> dict[str, Any]:
    if _WORKER_POOL is None:
        raise RuntimeError("worker pool was not initialised")
    return evaluate_prompt(work, _WORKER_POOL)


def validate_shard(
    shard: Mapping[str, Any],
    case_id: str,
    *,
    experiment_id: str,
    run_identity_sha256: str,
    cells: Sequence[str],
) -> None:
    if (
        shard.get("schema_version") != SCHEMA_VERSION
        or shard.get("experiment_id") != experiment_id
        or shard.get("run_identity_sha256") != run_identity_sha256
        or shard.get("case_id") != case_id
        or shard.get("complete") is not True
        or list(shard.get("cells", [])) != list(cells)
    ):
        raise ValueError(f"invalid or foreign shard for {case_id}")
    rows = shard.get("rows")
    expected = {(draw, family, cell) for draw in DRAWS for family in FAMILIES for cell in cells}
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError(f"shard {case_id} has the wrong row count")
    observed = {(row.get("draw_id"), row.get("family"), row.get("cell")) for row in rows}
    if observed != expected or any(row.get("case_id") != case_id for row in rows):
        raise ValueError(f"shard {case_id} has an incomplete trial grid")


# --------------------------------------------------------------------------- file helpers


def atomic_write_text(path: Path, payload: str | bytes, *, binary: bool = False) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to replace existing artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    if binary:
        temporary.write_bytes(payload if isinstance(payload, bytes) else payload.encode())
    else:
        temporary.write_text(str(payload), encoding="utf-8")
    os.replace(temporary, path)


def atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_identical_or_new(path: Path, payload: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"refusing to replace different artifact: {path}")
        return
    atomic_write_text(path, payload)


def write_trials(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            if handle.read() != text:
                raise FileExistsError(f"refusing to replace different artifact: {path}")
        return
    atomic_write_text(path, gzip.compress(text.encode(), mtime=0), binary=True)


def load_trials(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL trials file; ``.gz`` files are gunzipped, anything else is plain text."""

    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def cpu_model() -> str:
    try:
        if sys.platform == "darwin":
            return subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return platform.processor() or "unknown"


def file_record(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": sha256_file(str(path))}


# --------------------------------------------------------------------------- statistics


def one_sided_upper_bound(successes: int, trials: int, confidence: float = CONFIDENCE) -> float:
    """Exact (Clopper-Pearson) one-sided upper confidence bound."""

    from scipy.stats import beta

    if not 0 <= successes <= trials or trials <= 0:
        raise ValueError("invalid exact-bound counts")
    if successes == trials:
        return 1.0
    return float(beta.ppf(confidence, successes + 1, trials - successes))


def count_summary(successes: int, trials: int, *, one_sided: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "positives": successes,
        "trials": trials,
        "rate": successes / trials,
        "exact_two_sided_95_interval": exact_interval(successes, trials),
    }
    if one_sided:
        result["exact_one_sided_95_upper_bound"] = one_sided_upper_bound(successes, trials)
    return result


READ_LEVEL_UNIT_NOTE = "reads; two draws per prompt are not independent, interval is descriptive"


def read_level_summary(successes: int, trials: int) -> dict[str, Any]:
    """Read-level count and rate with a descriptive exact interval and no one-sided bound.

    The two draws of a prompt are paired, so reads are not independent trials.  The prompt-level
    blocks (``count_summary`` over prompts) are the inferential statements.
    """

    return {
        "positives": successes,
        "trials": trials,
        "rate": successes / trials,
        "exact_two_sided_95_interval": exact_interval(successes, trials),
        "unit_note": READ_LEVEL_UNIT_NOTE,
    }


def summarize_family(
    rows: Sequence[Mapping[str, Any]], family: str, case_order: Sequence[str]
) -> dict[str, Any]:
    control = family == PRIMARY_NULL
    positives = sum(bool(row["detected"]) for row in rows)
    by_prompt: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        by_prompt[str(row["case_id"])].append(bool(row["detected"]))
    if set(by_prompt) != set(case_order) or any(len(v) != len(DRAWS) for v in by_prompt.values()):
        raise RuntimeError("a cell does not cover every evaluated prompt and draw")
    strengths = [float(row["strength"]) for row in rows]
    overlaps = [int(row["region_overlap_bases"]) for row in rows]
    fractions = [
        int(row["region_overlap_bases"])
        / (int(row["best_original_stop"]) - int(row["best_original_start"]))
        for row in rows
    ]
    lengths = Counter(int(row["best_window_base_length"]) for row in rows)
    summary: dict[str, Any] = {
        "reads": len(rows),
        "sequence_level": read_level_summary(positives, len(rows)),
        "prompt_any_draw": count_summary(
            sum(any(v) for v in by_prompt.values()), len(by_prompt), one_sided=control
        ),
        "prompt_both_draws": count_summary(
            sum(all(v) for v in by_prompt.values()), len(by_prompt), one_sided=control
        ),
        "strength": {
            "median": statistics.median(strengths),
            "minimum": min(strengths),
            "maximum": max(strengths),
        },
        "strongest_window_length_counts": {
            str(length): lengths.get(length, 0) for length in WINDOW_BASE_LENGTHS
        },
        "strongest_window_orientation_counts": dict(
            sorted(Counter(str(row["best_orientation"]) for row in rows).items())
        ),
        "median_region_overlap_bases": statistics.median(overlaps),
        "median_region_overlap_fraction_of_window": statistics.median(fractions),
        "median_hypotheses_searched": statistics.median(
            int(row["hypotheses_searched"]) for row in rows
        ),
    }
    retained = [
        row["marked_bases_retained"] for row in rows if row["marked_bases_retained"] is not None
    ]
    if retained:
        summary["median_region_bases_retained"] = statistics.median(retained)
    if control:
        summary["control_rate_above_target"] = positives / len(rows) > TARGET_FPR
    return summary


def summarize_cells(
    rows: Sequence[Mapping[str, Any]], cells: Sequence[LayoutCell], case_order: Sequence[str]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["cell"]), str(row["family"]))].append(row)
    result: list[dict[str, Any]] = []
    for cell in cells:
        read_bases = sorted({int(row["read_bases"]) for row in grouped[(cell.cell, POSITIVE)]})
        result.append(
            {
                "cell": cell.cell,
                "series": cell.series,
                "region_bases": cell.region_bases,
                "read_bases": read_bases,
                "families": {
                    family: summarize_family(grouped[(cell.cell, family)], family, case_order)
                    for family in FAMILIES
                },
            }
        )
    return result


# --------------------------------------------------------------------------- validity checks


def check_reference_against_s0(
    rows: Sequence[Mapping[str, Any]],
    s0_rows: Iterable[Mapping[str, Any]] | None,
    case_order: Sequence[str],
) -> dict[str, Any]:
    """Check 1: cell A_l3072 reproduces the S0 unedited decisions exactly.

    Per (family, case id, draw) the decision, the number of windows searched and the integer
    counts of the best window must agree.  Floats are not compared for equality; their maximum
    absolute difference is reported.
    """

    reference = [row for row in rows if row["cell"] == REFERENCE_CELL]
    if s0_rows is None or not reference:
        return {
            "status": "not_run",
            "reason": "--no-s0-check given" if s0_rows is None else f"{REFERENCE_CELL} not run",
        }
    s0: dict[tuple[str, int, str], Mapping[str, Any]] = {}
    for row in s0_rows:
        if row.get("condition") != "clean" or row.get("family") not in FAMILIES:
            continue
        identity = (str(row["case_id"]), int(row["draw_id"]), str(row["family"]))
        if identity in s0:
            raise ValueError(f"duplicate S0 row {identity}")
        s0[identity] = row
    mismatch_count = 0
    mismatches: list[dict[str, Any]] = []
    missing = 0
    compared = 0
    max_difference = 0.0
    for row in reference:
        identity = (str(row["case_id"]), int(row["draw_id"]), str(row["family"]))
        other = s0.get(identity)
        if other is None:
            missing += 1
            continue
        compared += 1
        layout_decision = {
            "detected": bool(row["detected"]),
            "hypotheses_searched": int(row["hypotheses_searched"]),
            "g_ones": int(row["best_g_ones"]),
            "g_total": int(row["best_g_total"]),
        }
        s0_best = other.get("best_hypothesis") or {}
        s0_decision = {
            "detected": bool(other["detected"]),
            "hypotheses_searched": int(other["hypotheses_searched"]),
            "g_ones": s0_best.get("g_ones"),
            "g_total": s0_best.get("g_total"),
        }
        difference = abs(
            float(row["minimum_local_log_p_value"]) - float(other["minimum_local_log_p_value"])
        )
        max_difference = max(max_difference, difference)
        if layout_decision != s0_decision:
            mismatch_count += 1
            if len(mismatches) < 20:
                mismatches.append(
                    {
                        "case_id": identity[0],
                        "draw_id": identity[1],
                        "family": identity[2],
                        "layout": layout_decision,
                        "s0": s0_decision,
                    }
                )
    expected = len(case_order) * len(DRAWS) * len(FAMILIES)
    passed = not mismatch_count and not missing and compared == expected
    return {
        "status": "pass" if passed else "fail",
        "compared": compared,
        "expected": expected,
        "missing_in_s0": missing,
        "mismatches": mismatch_count,
        "mismatch_examples": mismatches,
        "max_abs_log_p_difference": max_difference,
        "fields": [
            "detected",
            "hypotheses_searched",
            "best_hypothesis.g_ones",
            "best_hypothesis.g_total",
        ],
        "note": "decisions compare integer window counts; the log P difference is reported, "
        "not compared",
    }


def check_strand_pairs(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Check 2: every series-C forward/reverse-complement pair has identical P and window count."""

    pairs: dict[tuple[str, int, str, str], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in rows:
        if row["series"] != "C":
            continue
        name = str(row["cell"])
        pairs[(str(row["case_id"]), int(row["draw_id"]), str(row["family"]), name[:-3])][
            name[-2:]
        ] = row
    if not pairs:
        return {"status": "not_run", "reason": "no series C cells run"}
    unpaired = 0
    mismatches: list[dict[str, Any]] = []
    for identity, strands in pairs.items():
        if set(strands) != {"fw", "rc"}:
            unpaired += 1
            continue
        forward, reverse = strands["fw"], strands["rc"]
        if (
            forward["minimum_local_log_p_value"] != reverse["minimum_local_log_p_value"]
            or forward["hypotheses_searched"] != reverse["hypotheses_searched"]
        ):
            mismatches.append(
                {
                    "case_id": identity[0],
                    "draw_id": identity[1],
                    "family": identity[2],
                    "pair": identity[3],
                    "forward": [
                        forward["minimum_local_log_p_value"],
                        forward["hypotheses_searched"],
                    ],
                    "reverse_complement": [
                        reverse["minimum_local_log_p_value"],
                        reverse["hypotheses_searched"],
                    ],
                }
            )
    return {
        "status": "pass" if not mismatches and not unpaired else "fail",
        "pairs": len(pairs),
        "unpaired": unpaired,
        "mismatches": len(mismatches),
        "mismatch_examples": mismatches[:20],
        "fields": ["minimum_local_log_p_value", "hypotheses_searched"],
    }


# --------------------------------------------------------------------------- orchestration


def run_identity(
    args: argparse.Namespace,
    *,
    cells: Sequence[LayoutCell],
    case_order: Sequence[str],
    sequence_files: Sequence[Path],
    natural_manifest_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "protocol_id": PROTOCOL_ID,
        "experiment_label": args.experiment_label,
        "cohort_id": args.cohort_id,
        "policy_id": args.policy_id,
        "generation_experiment_id": args.generation_experiment_id,
        "evaluated_case_ids": list(case_order),
        "calibration_prompts": args.calibration_prompts,
        "split_label": args.split_label,
        "cells": [cell.cell for cell in cells],
        "draws": list(DRAWS),
        "families": list(FAMILIES),
        "detector_config": repr(PositionIndependentSynthIDConfig()),
        "no_s0_check": bool(args.no_s0_check),
        "cohort_jsonl_sha256": sha256_file(str(args.cohort_jsonl)),
        "sequence_files_sha256": [sha256_file(str(path)) for path in sequence_files],
        "natural_manifest_sha256": natural_manifest_sha256,
        "code_sha256": {name: sha256_file(str(ROOT / name)) for name in CODE_FILES},
    }


def shard_path(output_dir: Path, case_id: str) -> Path:
    return output_dir / "shards" / f"{case_id}.json"


def write_shard(path: Path, shard: Mapping[str, Any]) -> None:
    atomic_write_text(path, json.dumps(shard, separators=(",", ":"), sort_keys=True) + "\n")


def read_shard(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_prompts(
    args: argparse.Namespace,
    *,
    case_order: Sequence[str],
    prompts: Mapping[str, str],
    records: Mapping[str, Mapping[int, Mapping[str, str]]],
    cells: Sequence[LayoutCell],
    spans: dict[str, str],
    identity_sha256: str,
) -> None:
    cell_names = [cell.cell for cell in cells]
    pending: list[dict[str, Any]] = []
    for case_id in case_order:
        path = shard_path(args.output_dir, case_id)
        if path.exists():
            validate_shard(
                read_shard(path),
                case_id,
                experiment_id=EXPERIMENT_ID,
                run_identity_sha256=identity_sha256,
                cells=cell_names,
            )
            continue
        pending.append(
            {
                "case_id": case_id,
                "prompt": prompts[case_id],
                "records": records[case_id],
                "cells": cell_names,
                "experiment_id": EXPERIMENT_ID,
                "run_identity_sha256": identity_sha256,
            }
        )
    completed = len(case_order) - len(pending)

    def report(case_id: str, shard: dict[str, Any]) -> None:
        nonlocal completed
        write_shard(shard_path(args.output_dir, case_id), shard)
        completed += 1
        print(
            json.dumps({"completed_prompts": completed, "total_prompts": len(case_order)}),
            flush=True,
        )

    if args.workers == 1:
        pool = NaturalPool(spans)
        for work in pending:
            report(work["case_id"], evaluate_prompt(work, pool))
        return
    with ProcessPoolExecutor(
        max_workers=args.workers, initializer=_init_worker, initargs=(spans,)
    ) as executor:
        futures = {executor.submit(_worker, work): work["case_id"] for work in pending}
        for future in as_completed(futures):
            report(str(futures[future]), future.result())


def finalize(
    args: argparse.Namespace,
    *,
    case_order: Sequence[str],
    cells: Sequence[LayoutCell],
    identity_sha256: str,
    sequence_files: Sequence[Path],
    natural_manifest_path: Path,
    natural_spans: int,
    started: float,
    s0_rows: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    summary_path = args.output_dir / "summary.json"
    if summary_path.exists():
        raise FileExistsError("refusing to replace an existing finalized result")
    cell_names = [cell.cell for cell in cells]
    cell_rank = {name: index for index, name in enumerate(cell_names)}
    family_rank = {name: index for index, name in enumerate(FAMILIES)}
    rows: list[dict[str, Any]] = []
    worker_seconds = 0.0
    cell_seconds: dict[str, float] = {name: 0.0 for name in cell_names}
    for case_id in case_order:
        path = shard_path(args.output_dir, case_id)
        if not path.exists():
            raise FileNotFoundError(f"missing prompt shard: {path}")
        shard = read_shard(path)
        validate_shard(
            shard,
            case_id,
            experiment_id=EXPERIMENT_ID,
            run_identity_sha256=identity_sha256,
            cells=cell_names,
        )
        rows.extend(shard["rows"])
        worker_seconds += float(shard["runtime_seconds"])
        for name, seconds in shard["cell_seconds"].items():
            cell_seconds[name] += float(seconds)
    order = {case_id: index for index, case_id in enumerate(case_order)}
    rows.sort(
        key=lambda row: (
            order[row["case_id"]],
            row["draw_id"],
            cell_rank[row["cell"]],
            family_rank[row["family"]],
        )
    )
    expected = len(case_order) * len(DRAWS) * len(FAMILIES) * len(cells)
    if len(rows) != expected:
        raise RuntimeError(f"found {len(rows)} decisions, expected {expected}")
    trials_path = args.output_dir / "trials.jsonl.gz"
    write_trials(trials_path, rows)

    check1 = check_reference_against_s0(rows, s0_rows, case_order)
    check2 = check_strand_pairs(rows)
    reasons = [
        f"check {number} {check['status']}"
        for number, check in ((1, check1), (2, check2))
        if check["status"] != "pass"
    ]
    failed_checks = [check["status"] == "fail" for check in (check1, check2)]
    results_withheld = any(failed_checks)
    model_id, revision = MODELS[args.policy_id]
    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "study": "S1 layout",
        "experiment_id": EXPERIMENT_ID,
        "classification": "layout_result_pending_evidence_admission",
        "valid": not reasons,
        "validity_failures": reasons,
        "results_withheld": results_withheld,
        "s0_check_skipped": bool(args.no_s0_check),
        "validity_checks": {
            "check_1_reference_layout_reproduces_s0_unedited": check1,
            "check_2_series_c_strand_pairs_identical": check2,
        },
        "protocol": {"id": PROTOCOL_ID, **file_record(args.protocol)},
        "watermark_scope": "synthid-tournament-v1 only",
        "detector_id": POSITION_INDEPENDENT_SYNTHID_DETECTOR,
        "detector_config": {
            "window_base_lengths": list(WINDOW_BASE_LENGTHS),
            "orientations": ["forward", "reverse_complement"],
            "target_sequence_false_positive_rate": TARGET_FPR,
            "settings_tuned": False,
        },
        "model": {
            "model_id": model_id,
            "revision": revision,
            "policy_id": args.policy_id,
            "experiment_label": args.experiment_label,
            "cohort_id": args.cohort_id,
            "generation_experiment_id": args.generation_experiment_id,
        },
        "evaluated_prompts": len(case_order),
        "evaluated_case_ids_first_last": [case_order[0], case_order[-1]],
        "draws_per_prompt": len(DRAWS),
        "families": list(FAMILIES),
        "cells_run": cell_names,
        "total_decisions": len(rows),
        "cost": {
            "worker_runtime_seconds_sum": worker_seconds,
            "detector_seconds_by_cell": cell_seconds,
            "detector_seconds_per_read_by_cell": {
                name: seconds / (len(case_order) * len(DRAWS) * len(FAMILIES))
                for name, seconds in cell_seconds.items()
            },
            "finalization_wall_seconds": time.perf_counter() - started,
        },
        "provenance": {
            "command": shlex.join([sys.executable, *sys.argv]),
            "workers": args.workers,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_model": cpu_model(),
            "cpu_count": os.cpu_count(),
            "run_identity_sha256": identity_sha256,
            "cohort": file_record(args.cohort_jsonl),
            "generation_files": [file_record(path) for path in sequence_files],
            "natural_pool": {
                "directory": str(args.natural_dir.resolve()),
                "spans": natural_spans,
                "manifest": file_record(natural_manifest_path),
            },
            "s0_trials": file_record(args.s0_trials) if args.s0_trials else None,
            "code": {name: sha256_file(str(ROOT / name)) for name in CODE_FILES},
        },
        "trials_artifact": file_record(trials_path),
        "flags": [
            "Fixture keys are public reproducibility material, not deployment secrets.",
            "Layouts are chosen by public hash streams, never by a detector, key or score.",
            "The control read has the ordinary continuation of the same prompt and draw with "
            "the same flanks; its region overlap is measured against the same region.",
            "Statistical detection only; no biological function or secret-key claim follows.",
            "Rates above target in a control cell are reported as observed.",
        ],
    }
    if results_withheld:
        # Protocol Section 5.1: a failed validity check "reports nothing".  The failed check
        # details stay in ``validity_checks``; no per-cell result is written.
        summary["flags"].append(
            "A validity check failed: per-cell results are withheld by protocol Section 5.1."
        )
    else:
        cell_summaries = summarize_cells(rows, cells, case_order)
        summary["ordinary_cells_above_target"] = [
            cell["cell"]
            for cell in cell_summaries
            if cell["families"][PRIMARY_NULL]["control_rate_above_target"]
        ]
        summary["cells"] = cell_summaries
        if args.no_s0_check:
            summary["flags"].append(
                "--no-s0-check: validity check 1 was not run; this output is for tests and "
                "smoke runs only and is not a study result."
            )
    atomic_write_json(summary_path, summary)
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.workers <= 0 or args.evaluated_prompts <= 0:
        raise ValueError("workers and evaluated prompts must be positive")
    if not args.protocol.is_file():
        raise FileNotFoundError(args.protocol)
    # Validity check 1 needs the S0 file: confirm it is readable before any scoring starts.
    s0_rows: list[dict[str, Any]] | None = None
    if not args.no_s0_check:
        if args.s0_trials is None or not args.s0_trials.is_file():
            raise FileNotFoundError(f"S0 trials file not found: {args.s0_trials}")
        s0_rows = load_trials(args.s0_trials)
        if not s0_rows:
            raise ValueError(f"S0 trials file is empty: {args.s0_trials}")
    started = time.perf_counter()
    cell_list = selected_cells(args.cells)
    if args.expected_cohort_jsonl_sha256 and (
        sha256_file(str(args.cohort_jsonl)) != args.expected_cohort_jsonl_sha256
    ):
        raise ValueError("prompts.jsonl does not match the protocol digest")
    cases = load_context_cases_jsonl(args.cohort_jsonl)
    if {case.cohort_id for case in cases} != {args.cohort_id}:
        raise ValueError("prompt cohort id disagrees with --cohort-id")
    prompts = {case.case_id: case.sequence for case in cases}
    if any(len(prompt) != PROMPT_BASES for prompt in prompts.values()):
        raise ValueError("every prompt must contain 384 bases")
    held_out = held_out_order(
        list(prompts), calibration_prompts=args.calibration_prompts, label=args.split_label
    )
    if not 0 < args.evaluated_prompts <= len(held_out):
        raise ValueError(f"--evaluated-prompts must lie in [1, {len(held_out)}]")
    case_order = held_out[: args.evaluated_prompts]

    if args.sequence_files:
        sequence_files = list(args.sequence_files)
    elif args.generation_root:
        sequence_files = [
            args.generation_root / f"generation/draw_{draw:02d}_sequences.jsonl" for draw in DRAWS
        ]
    else:
        raise ValueError("give --generation-root or --sequence-file")
    records = load_generation_records(
        sequence_files,
        selected=case_order,
        prompts=prompts,
        label=args.experiment_label,
        cohort_id=args.cohort_id,
        policy_id=args.policy_id,
        generation_experiment_id=args.generation_experiment_id,
    )
    spans, digests = load_natural_spans(args.natural_dir, cases)
    manifest = "".join(f"{case_id}\t{digests[case_id]}\n" for case_id in sorted(digests))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "natural_pool_manifest.tsv"
    write_identical_or_new(manifest_path, manifest)
    identity = run_identity(
        args,
        cells=cell_list,
        case_order=case_order,
        sequence_files=sequence_files,
        natural_manifest_sha256=hashlib.sha256(manifest.encode()).hexdigest(),
    )
    identity_text = json.dumps(identity, indent=2, sort_keys=True) + "\n"
    write_identical_or_new(args.output_dir / "run_identity.json", identity_text)
    identity_sha256 = hashlib.sha256(identity_text.encode()).hexdigest()

    if not args.finalize_only:
        run_prompts(
            args,
            case_order=case_order,
            prompts=prompts,
            records=records,
            cells=cell_list,
            spans=spans,
            identity_sha256=identity_sha256,
        )
    summary = finalize(
        args,
        case_order=case_order,
        cells=cell_list,
        identity_sha256=identity_sha256,
        sequence_files=sequence_files,
        natural_manifest_path=manifest_path,
        natural_spans=len(spans),
        started=started,
        s0_rows=s0_rows,
    )
    print(
        json.dumps(
            {
                "status": "invalid" if summary["results_withheld"] else "complete",
                "valid": summary["valid"],
            }
        ),
        flush=True,
    )
    return 1 if summary["results_withheld"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
