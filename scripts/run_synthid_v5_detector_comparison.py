#!/usr/bin/env python3
"""S2 detector comparison of the v5 review protocol (Section 6).

Protocol: ``docs/research/synthid_v5_review_studies_protocol_2026_11_12.md``.

Reads are the first ``--prompts`` evaluated prompts in split-rank order, both draws, both
families (``watermarked_correct_key`` and ``ordinary_corresponding_key``), in five cells:
``reference`` (layout cell ``A_l3072``), ``reference_insertion`` (the reference read after
the existing deterministic single insertion), and layout cells ``B_l0768``, ``B_l1152`` and
``B_l3072`` built by ``review_layouts.build_read`` (byte-identical to the S1 reads).  Four
detectors score every read: the aligned oracle, phase-only, the unchanged verifier, and the
fine-grid search.  The three baselines are analysis baselines only
(``genomic_watermarks.detector_baselines``); they do not modify the verifier.

Runtime.  Every decision records the wall seconds of its single detection call
(``time.perf_counter`` around the call, one thread per call).  With ``--workers > 1`` those
seconds are measured while other workers compete for cores, memory bandwidth, and thermal
headroom, so they are an upper bound.  For the paper's runtime medians, rerun on a quiet
machine with ``--timing-only --prompts 32 --output-dir <new dir>``: one process, no
competing workers, same code and reads, and the summary says so.  Report those medians with
the CPU model recorded in the summary.  Detection results and timings come from the same
code path, so the two runs agree on every decision.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

for _name in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ.setdefault(_name, "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from run_carbon_synthid_position_independent import exact_interval  # noqa: E402

from genomic_watermarks.detector_baselines import (  # noqa: E402
    BaselineDetection,
    detect_aligned_oracle,
    detect_fine_grid,
    detect_phase_only,
)
from genomic_watermarks.dna import normalize_dna  # noqa: E402
from genomic_watermarks.large_validation import (  # noqa: E402
    CALIBRATION_SPLIT_LABEL,
    fixture_key,
    sha256_file,
)
from genomic_watermarks.review_layouts import (  # noqa: E402
    CONTINUATION_BASES,
    PROMPT_BASES,
    REFERENCE_CELL,
    LayoutRead,
    NaturalPool,
    build_read,
    cell_by_name,
)
from genomic_watermarks.synthid import SYNTHID_SCHEME  # noqa: E402
from genomic_watermarks.synthid_boundary import deterministic_single_base_edit  # noqa: E402
from genomic_watermarks.synthid_position_independent import (  # noqa: E402
    POSITION_INDEPENDENT_SYNTHID_DETECTOR,
    PositionIndependentSynthIDConfig,
    detect_synthid_position_independent,
)
from genomic_watermarks.watermark import ORDINARY_SCHEME  # noqa: E402

PROTOCOL_ID = "synthid.v5.review-studies"
STUDY = "S2"
DEFAULT_PROTOCOL = ROOT / "docs/research/synthid_v5_review_studies_protocol_2026_11_12.md"
DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_fpr_v2_1608/prompts.jsonl"
DEFAULT_NATURAL_DIR = ROOT / "data/raw/ncbi_refseq_eukaryote_windows_fpr_v2_1608"
EXPERIMENT_ID = "synthid_v5_s2_detector_comparison"
POSITIVE = "watermarked_correct_key"
CONTROL = "ordinary_corresponding_key"
FAMILIES = (POSITIVE, CONTROL)
DRAWS = (0, 1)
DETECTORS = ("aligned_oracle", "phase_only", "verifier", "fine_grid")
REFERENCE = "reference"
INSERTION = "reference_insertion"
EMBEDDED_CELLS = ("B_l0768", "B_l1152", "B_l3072")
CELLS = (REFERENCE, INSERTION, *EMBEDDED_CELLS)
TARGET_FPR = 0.01
INSERTION_CONDITION = "insertion_1nt"
ROWS_PER_PROMPT = len(DRAWS) * len(FAMILIES) * len(CELLS) * len(DETECTORS)
CODE_FILES = (
    Path(__file__).resolve(),
    ROOT / "src/genomic_watermarks/detector_baselines.py",
    ROOT / "src/genomic_watermarks/review_layouts.py",
    ROOT / "src/genomic_watermarks/synthid_position_independent.py",
    ROOT / "src/genomic_watermarks/synthid_boundary.py",
    ROOT / "src/genomic_watermarks/synthid.py",
    ROOT / "src/genomic_watermarks/dna.py",
    ROOT / "src/genomic_watermarks/large_validation.py",
)

_POOL: NaturalPool | None = None
_WARMED = False


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--generation-root", type=Path, help="holds generation/draw_NN_sequences.jsonl"
    )
    parser.add_argument(
        "--sequence-file",
        type=Path,
        action="append",
        dest="sequence_files",
        help="generation rows (one file per draw); overrides --generation-root",
    )
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--natural-dir", type=Path, default=DEFAULT_NATURAL_DIR)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--experiment-label", required=True, help="e.g. carbon-synthid-local-v5")
    parser.add_argument("--policy-id", required=True, choices=("C_tok", "G_tok"))
    parser.add_argument("--cohort-id", help="defaults to the cohort id in --cohort-jsonl")
    parser.add_argument("--generation-experiment-id", help="checked against rows when given")
    parser.add_argument("--experiment-id", default=EXPERIMENT_ID)
    parser.add_argument(
        "--evaluated-prompts", type=int, required=True, help="N_eval of the generated cohort"
    )
    parser.add_argument("--prompts", type=int, default=256, help="first N evaluated prompts used")
    parser.add_argument("--calibration-prompts", type=int, default=64)
    parser.add_argument("--split-label", default=CALIBRATION_SPLIT_LABEL)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--timing-only",
        action="store_true",
        help="single process (workers forced to 1) for clean runtime medians; use a new "
        "--output-dir and a small --prompts",
    )
    parser.add_argument("--finalize-only", action="store_true")
    return parser.parse_args(argv)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def atomic_write_text(path: Path, payload: str) -> None:
    """Write once; an existing file must already hold the same content."""

    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"refusing to replace different artifact: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    """Write a new shard or summary; never replace an existing file."""

    if path.exists():
        raise FileExistsError(f"refusing to replace existing artifact: {path}")
    atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def cpu_model() -> str:
    try:
        if sys.platform == "darwin":
            out = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            if out:
                return out
        elif Path("/proc/cpuinfo").is_file():
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return platform.processor() or platform.machine()


def evaluation_order(case_ids: Sequence[str], *, label: str, calibration_prompts: int) -> list[str]:
    """Held-out prompts in split-rank order: the hash ranking after the reserved prompts.

    The ranking is the one inside ``deterministic_prompt_split``; the first
    ``calibration_prompts`` ranks are the reserved prompts.
    """

    resolved = [str(case_id) for case_id in case_ids]
    if len(set(resolved)) != len(resolved) or not 0 < calibration_prompts < len(resolved):
        raise ValueError("case ids must be unique and the reserved count inside the cohort")
    ranked = sorted(
        resolved,
        key=lambda case_id: (hashlib.sha256(f"{label}\x00{case_id}".encode()).digest(), case_id),
    )
    return ranked[calibration_prompts:]


def read_fasta(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith(">"):
        raise ValueError(f"not a FASTA file: {path}")
    return normalize_dna("".join(line.strip() for line in lines[1:]))


def load_natural_spans(
    natural_dir: Path, prompts: Mapping[str, str]
) -> tuple[dict[str, str], dict[str, str]]:
    """One span per cohort prompt; check its length and that it begins with the prompt."""

    spans: dict[str, str] = {}
    digests: dict[str, str] = {}
    for case_id in sorted(prompts):
        path = natural_dir / f"{case_id}.fasta"
        if not path.is_file():
            raise FileNotFoundError(f"missing natural source span: {path}")
        span = read_fasta(path)
        if len(span) != CONTINUATION_BASES:
            raise ValueError(f"span {case_id} has {len(span)} bases, expected {CONTINUATION_BASES}")
        if span[:PROMPT_BASES] != normalize_dna(prompts[case_id]):
            raise ValueError(f"span {case_id} does not begin with its prompt")
        spans[case_id] = span
        digests[case_id] = sha256_file(str(path))
    return spans, digests


def load_generation_records(
    paths: Sequence[Path],
    *,
    selected: set[str],
    experiment_label: str,
    policy_id: str,
    cohort_id: str,
    generation_experiment_id: str | None,
) -> dict[tuple[str, int, str], dict[str, Any]]:
    records: dict[tuple[str, int, str], dict[str, Any]] = {}
    for path in paths:
        for row in load_jsonl(path):
            if (
                str(row.get("experiment_label")) != experiment_label
                or str(row.get("policy_id")) != policy_id
                or str(row.get("cohort_id")) != cohort_id
                or (
                    generation_experiment_id is not None
                    and str(row.get("experiment_id")) != generation_experiment_id
                )
            ):
                raise ValueError(f"generation record in {path} does not belong to this run")
            case_id = str(row["case_id"])
            if case_id not in selected:
                continue
            identity = (case_id, int(row["draw_id"]), str(row["scheme"]))
            if identity in records:
                raise ValueError(f"duplicate generation record {identity}")
            records[identity] = row
    return records


def make_reads(
    *,
    prompt: str,
    continuation: str,
    pool: NaturalPool,
    case_id: str,
    draw_id: int,
) -> tuple[dict[str, LayoutRead], int]:
    """The five S2 reads of one continuation and the insertion's position."""

    prompt_dna = normalize_dna(prompt)
    reads: dict[str, LayoutRead] = {}
    reads[REFERENCE] = build_read(
        cell_by_name(REFERENCE_CELL),
        prompt=prompt_dna,
        continuation=continuation,
        pool=pool,
        case_id=case_id,
        draw_id=draw_id,
    )
    edit = deterministic_single_base_edit(
        normalize_dna(continuation),
        condition=INSERTION_CONDITION,
        case_id=case_id,
        draw_id=draw_id,
    )
    reads[INSERTION] = LayoutRead(
        INSERTION,
        prompt_dna + edit.sequence,
        PROMPT_BASES,
        CONTINUATION_BASES,
        True,
    )
    for name in EMBEDDED_CELLS:
        reads[name] = build_read(
            cell_by_name(name),
            prompt=prompt_dna,
            continuation=continuation,
            pool=pool,
            case_id=case_id,
            draw_id=draw_id,
        )
    return reads, edit.position


def _flatten(
    *,
    detected: bool,
    uncapped: float,
    capped: float,
    local: float,
    windows: int,
    orientation: str,
    oriented_start: int,
    original_start: int,
    original_stop: int,
    length: int,
    g_ones: int,
    g_total: int,
    scored: int,
    repeated: int,
) -> dict[str, Any]:
    return {
        "detected": detected,
        "corrected_log_p_uncapped": uncapped,
        "corrected_log_p": capped,
        "smallest_window_log_p": local,
        "windows_searched": windows,
        "best_orientation": orientation,
        "best_oriented_start": oriented_start,
        "best_original_start": original_start,
        "best_original_stop": original_stop,
        "best_window_bases": length,
        "best_g_ones": g_ones,
        "best_g_total": g_total,
        "best_scored_tokens": scored,
        "best_repeated_contexts": repeated,
    }


def _from_baseline(result: BaselineDetection) -> dict[str, Any]:
    window = result.best_window
    return _flatten(
        detected=result.detected,
        uncapped=result.uncapped_sequence_log_p_value,
        capped=result.sequence_log_p_value,
        local=result.minimum_local_log_p_value,
        windows=result.hypotheses_searched,
        orientation=window.orientation,
        oriented_start=window.oriented_start,
        original_start=window.original_start,
        original_stop=window.original_stop,
        length=window.window_base_length,
        g_ones=window.g_ones,
        g_total=window.g_total,
        scored=window.scored_tokens,
        repeated=window.repeated_contexts,
    )


def run_detector(
    name: str,
    read: LayoutRead,
    *,
    key: bytes,
    domain: str,
    region_start: int,
    region_length: int,
    config: PositionIndependentSynthIDConfig,
) -> dict[str, Any]:
    """Run one detector on one read.  The oracle is told the region, not any edit."""

    if name == "aligned_oracle":
        return _from_baseline(
            detect_aligned_oracle(
                read.sequence,
                key=key,
                domain=domain,
                region_start=region_start,
                region_length=region_length,
                region_on_forward_strand=read.region_on_forward_strand,
                config=config,
            )
        )
    if name == "phase_only":
        return _from_baseline(
            detect_phase_only(read.sequence, key=key, domain=domain, config=config)
        )
    if name == "fine_grid":
        return _from_baseline(
            detect_fine_grid(read.sequence, key=key, domain=domain, config=config)
        )
    if name == "verifier":
        result = detect_synthid_position_independent(
            read.sequence, key=key, domain=domain, config=config
        )
        best = result.best_hypothesis
        return _flatten(
            detected=result.detected,
            uncapped=math.log(result.hypotheses_searched) + result.minimum_local_log_p_value,
            capped=result.sequence_log_p_value,
            local=result.minimum_local_log_p_value,
            windows=result.hypotheses_searched,
            orientation=best.orientation,
            oriented_start=best.oriented_start,
            original_start=best.original_start,
            original_stop=best.original_stop,
            length=best.window_base_length,
            g_ones=best.g_ones,
            g_total=best.g_total,
            scored=best.scored_tokens,
            repeated=best.repeated_contexts,
        )
    raise ValueError(f"unknown detector {name}")


def init_worker(spans: Mapping[str, str]) -> None:
    global _POOL, _WARMED
    _POOL = NaturalPool(spans)
    _WARMED = False


def evaluate_prompt(work: Mapping[str, Any]) -> dict[str, Any]:
    """All 80 decisions of one prompt: 2 draws x 2 families x 5 cells x 4 detectors."""

    global _WARMED
    if _POOL is None:
        raise RuntimeError("the natural pool is not initialised in this process")
    started = time.perf_counter()
    case_id = str(work["case_id"])
    prompt = str(work["prompt"])
    records = work["records"]
    config = PositionIndependentSynthIDConfig()
    rows: list[dict[str, Any]] = []
    for draw_id in DRAWS:
        marked = records[f"{draw_id}:{SYNTHID_SCHEME}"]
        ordinary = records[f"{draw_id}:{ORDINARY_SCHEME}"]
        domain = str(marked["stream_domain"])
        if str(ordinary["stream_domain"]) != domain:
            raise ValueError("matched generation arms disagree on the SynthID domain")
        key = fixture_key(draw_id)
        built: dict[str, tuple[dict[str, LayoutRead], int]] = {}
        for family, record in ((POSITIVE, marked), (CONTROL, ordinary)):
            built[family] = make_reads(
                prompt=prompt,
                continuation=str(record["generated_dna"]),
                pool=_POOL,
                case_id=case_id,
                draw_id=draw_id,
            )
        if built[POSITIVE][1] != built[CONTROL][1]:
            raise RuntimeError("matched arms received different insertion positions")
        for family in FAMILIES:
            reads, edit_position = built[family]
            for cell in CELLS:
                read = reads[cell]
                # The oracle is told the original region, never the insertion.
                region_start, region_length = PROMPT_BASES, CONTINUATION_BASES
                if cell in EMBEDDED_CELLS:
                    region_start, region_length = read.region_start, read.region_length
                for detector in DETECTORS:
                    if not _WARMED:
                        run_detector(
                            detector,
                            read,
                            key=key,
                            domain=domain,
                            region_start=region_start,
                            region_length=region_length,
                            config=config,
                        )
                    tick = time.perf_counter()
                    outcome = run_detector(
                        detector,
                        read,
                        key=key,
                        domain=domain,
                        region_start=region_start,
                        region_length=region_length,
                        config=config,
                    )
                    seconds = time.perf_counter() - tick
                    rows.append(
                        {
                            "detector": detector,
                            "cell": cell,
                            "family": family,
                            "case_id": case_id,
                            "draw_id": draw_id,
                            "read_bases": len(read.sequence),
                            "told_region_start": region_start
                            if detector == "aligned_oracle"
                            else None,
                            "told_region_length": region_length
                            if detector == "aligned_oracle"
                            else None,
                            "insertion_position_in_continuation": (
                                edit_position if cell == INSERTION else None
                            ),
                            **outcome,
                            "seconds": seconds,
                        }
                    )
            if not _WARMED:
                _WARMED = True
    return {
        "schema_version": 1,
        "experiment_id": str(work["experiment_id"]),
        "case_id": case_id,
        "complete": True,
        "runtime_seconds": time.perf_counter() - started,
        "rows": rows,
    }


def validate_shard(shard: Mapping[str, Any], case_id: str, experiment_id: str) -> None:
    if shard.get("schema_version") != 1 or shard.get("experiment_id") != experiment_id:
        raise ValueError(f"invalid shard identity for {case_id}")
    if shard.get("case_id") != case_id or shard.get("complete") is not True:
        raise ValueError(f"incomplete shard for {case_id}")
    rows = shard.get("rows")
    if not isinstance(rows, list) or len(rows) != ROWS_PER_PROMPT:
        raise ValueError(f"shard {case_id} has the wrong row count")
    identities = {(r["draw_id"], r["family"], r["cell"], r["detector"]) for r in rows}
    expected = {
        (draw, family, cell, detector)
        for draw in DRAWS
        for family in FAMILIES
        for cell in CELLS
        for detector in DETECTORS
    }
    if identities != expected or any(r["case_id"] != case_id for r in rows):
        raise ValueError(f"shard {case_id} has an incomplete or foreign trial grid")


def strength(row: Mapping[str, Any]) -> float:
    """``-log10`` of the corrected P-value before capping at 1."""

    return -float(row["corrected_log_p_uncapped"]) / math.log(10.0)


READ_LEVEL_UNIT_NOTE = "reads; two draws per prompt are not independent, interval is descriptive"


def _count_block(
    successes: int, trials: int, *, control: bool, prompt_level: bool = True
) -> dict[str, Any]:
    """Counts with an exact interval.

    Only prompt-level blocks (prompts as independent trials) carry the exact one-sided 95% upper
    bound.  Read-level blocks pool both draws of a prompt, which are paired, so they keep the
    count, rate and a descriptive interval and say so in ``unit_note``.
    """

    block: dict[str, Any] = {
        "positives": successes,
        "trials": trials,
        "rate": successes / trials,
        "exact_two_sided_95_interval": exact_interval(successes, trials),
    }
    if not prompt_level:
        block["unit_note"] = READ_LEVEL_UNIT_NOTE
    if control:
        if prompt_level:
            block["exact_one_sided_95_upper_bound"] = exact_interval(successes, trials, 0.90)[1]
        block["exceeds_target"] = successes / trials > TARGET_FPR
    return block


def summarize_cell(rows: Sequence[Mapping[str, Any]], *, family: str) -> dict[str, Any]:
    control = family == CONTROL
    by_prompt: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        by_prompt[str(row["case_id"])].append(bool(row["detected"]))
    positives = sum(bool(row["detected"]) for row in rows)
    prompt_positive = sum(any(flags) if control else all(flags) for flags in by_prompt.values())
    windows = sorted({int(row["windows_searched"]) for row in rows})
    return {
        "reads": _count_block(positives, len(rows), control=control, prompt_level=False),
        "prompt_level": {
            "rule": "positive if either draw positive"
            if control
            else "positive if both draws detected",
            **_count_block(prompt_positive, len(by_prompt), control=control),
        },
        "median_corrected_strength": statistics.median(strength(row) for row in rows),
        "median_seconds_per_read": statistics.median(float(row["seconds"]) for row in rows),
        "mean_seconds_per_read": statistics.fmean(float(row["seconds"]) for row in rows),
        "windows_searched_min": windows[0],
        "windows_searched_max": windows[-1],
    }


def summarize(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for cell in CELLS:
        for detector in DETECTORS:
            for family in FAMILIES:
                selected = [
                    row
                    for row in rows
                    if row["cell"] == cell
                    and row["detector"] == detector
                    and row["family"] == family
                ]
                if selected:
                    cells.append(
                        {
                            "cell": cell,
                            "detector": detector,
                            "family": family,
                            **summarize_cell(selected, family=family),
                        }
                    )
    return cells


def gzip_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to replace existing artifact: {path}")
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as stream:
        stream.write(text.encode("utf-8"))
    os.replace(temporary, path)


def run_identity(args: argparse.Namespace, selected: Sequence[str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "study": STUDY,
        "experiment_id": args.experiment_id,
        "experiment_label": args.experiment_label,
        "policy_id": args.policy_id,
        "cohort_id": args.cohort_id,
        "split_label": args.split_label,
        "calibration_prompts": args.calibration_prompts,
        "prompts": len(selected),
        "selected_prompts_sha256": hashlib.sha256("\n".join(selected).encode()).hexdigest(),
        "cells": list(CELLS),
        "detectors": list(DETECTORS),
        "families": list(FAMILIES),
        "code_sha256": {str(p.relative_to(ROOT)): sha256_file(str(p)) for p in CODE_FILES},
    }


def finalize(
    args: argparse.Namespace,
    *,
    selected: Sequence[str],
    inputs: Mapping[str, Any],
    started: float,
) -> dict[str, Any]:
    summary_path = args.output_dir / "summary.json"
    if summary_path.exists():
        raise FileExistsError("refusing to replace an existing finalized result")
    rows: list[dict[str, Any]] = []
    worker_seconds = 0.0
    for case_id in selected:
        shard_path = args.output_dir / "shards" / f"{case_id}.json"
        if not shard_path.is_file():
            raise FileNotFoundError(f"missing prompt shard: {shard_path}")
        shard = json.loads(shard_path.read_text(encoding="utf-8"))
        validate_shard(shard, case_id, args.experiment_id)
        rows.extend(shard["rows"])
        worker_seconds += float(shard["runtime_seconds"])
    if len(rows) != len(selected) * ROWS_PER_PROMPT:
        raise RuntimeError("decision count does not match the declared grid")
    rows.sort(
        key=lambda r: (
            r["case_id"],
            r["draw_id"],
            CELLS.index(r["cell"]),
            DETECTORS.index(r["detector"]),
            FAMILIES.index(r["family"]),
        )
    )
    trials_path = args.output_dir / "trials.jsonl.gz"
    gzip_jsonl(trials_path, rows)
    workers = 1 if args.timing_only else args.workers
    summary: dict[str, Any] = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": sha256_file(str(args.protocol)),
        "study": STUDY,
        "classification": "pending_evidence_admission",
        "experiment_id": args.experiment_id,
        "experiment_label": args.experiment_label,
        "policy_id": args.policy_id,
        "cohort_id": args.cohort_id,
        "evaluated_prompts_in_cohort": args.evaluated_prompts,
        "prompts": len(selected),
        "draws_per_prompt": len(DRAWS),
        "total_decisions": len(rows),
        "cells": list(CELLS),
        "detectors": list(DETECTORS),
        "families": list(FAMILIES),
        "target_sequence_false_positive_rate": TARGET_FPR,
        "verifier": POSITION_INDEPENDENT_SYNTHID_DETECTOR,
        "baseline_note": (
            "Aligned oracle, phase-only and fine-grid are S2 analysis baselines; none replaces "
            "or modifies the verifier."
        ),
        "insertion_rule": (
            f"deterministic_single_base_edit(continuation, condition={INSERTION_CONDITION!r}) "
            "as in the position-independent runners; the oracle is told the original region "
            "(start 384, length 3072)"
        ),
        "cells_in_summary": summarize(rows),
        "runtime": {
            "timing_only": bool(args.timing_only),
            "workers": workers,
            "seconds_measured_under_parallel_workers": workers > 1,
            "unit": "wall seconds of one single-threaded detection call (perf_counter)",
            "worker_seconds_sum": worker_seconds,
            "cpu_model": cpu_model(),
            "logical_cpus": os.cpu_count(),
            "paper_guidance": (
                "Report runtime medians from a --timing-only run on an otherwise idle machine; "
                "medians from a parallel run are an upper bound."
            ),
        },
        "provenance": {
            "command": [sys.executable, *sys.argv],
            "python": platform.python_version(),
            "platform": platform.platform(),
            "inputs": inputs,
            "code_sha256": run_identity(args, selected)["code_sha256"],
            "trials_artifact": {
                "path": str(trials_path.resolve()),
                "sha256": sha256_file(str(trials_path)),
            },
            "finalization_seconds": time.perf_counter() - started,
        },
        "flags": [
            "Fixture keys are public reproducibility material, not deployment secrets.",
            "The fine-grid search stands in for a search over all contiguous spans; it is not one.",
            "Prompts are the independent unit; the two draws of a prompt are correlated.",
        ],
    }
    atomic_write_json(summary_path, summary)
    return summary


def run_shards(
    args: argparse.Namespace,
    *,
    selected: Sequence[str],
    prompts: Mapping[str, str],
    records: Mapping[tuple[str, int, str], dict[str, Any]],
    spans: Mapping[str, str],
) -> None:
    pending: list[dict[str, Any]] = []
    done = 0
    for case_id in selected:
        shard_path = args.output_dir / "shards" / f"{case_id}.json"
        if shard_path.exists():
            validate_shard(
                json.loads(shard_path.read_text(encoding="utf-8")), case_id, args.experiment_id
            )
            done += 1
            continue
        pending.append(
            {
                "case_id": case_id,
                "prompt": prompts[case_id],
                "experiment_id": args.experiment_id,
                "records": {
                    f"{draw}:{scheme}": records[(case_id, draw, scheme)]
                    for draw in DRAWS
                    for scheme in (SYNTHID_SCHEME, ORDINARY_SCHEME)
                },
            }
        )
    workers = 1 if args.timing_only else args.workers

    def store(shard: Mapping[str, Any]) -> None:
        nonlocal done
        atomic_write_json(args.output_dir / "shards" / f"{shard['case_id']}.json", shard)
        done += 1
        print(json.dumps({"completed_prompts": done, "total_prompts": len(selected)}), flush=True)

    if workers == 1:
        init_worker(spans)
        for work in pending:
            store(evaluate_prompt(work))
        return
    with ProcessPoolExecutor(
        max_workers=workers, initializer=init_worker, initargs=(dict(spans),)
    ) as executor:
        futures = [executor.submit(evaluate_prompt, work) for work in pending]
        for future in as_completed(futures):
            store(future.result())


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.workers <= 0 or args.prompts <= 0:
        raise ValueError("workers and prompts must be positive")
    if args.prompts > args.evaluated_prompts:
        raise ValueError("--prompts cannot exceed --evaluated-prompts")
    started = time.perf_counter()
    cohort_rows = load_jsonl(args.cohort_jsonl)
    prompts = {str(row["prompt_id"]): str(row["sequence"]) for row in cohort_rows}
    cohort_ids = {str(row["cohort_id"]) for row in cohort_rows}
    if len(cohort_ids) != 1 or len(prompts) != len(cohort_rows):
        raise ValueError("the prompt file must hold unique prompts of one cohort")
    args.cohort_id = args.cohort_id or next(iter(cohort_ids))
    if args.cohort_id not in cohort_ids:
        raise ValueError("--cohort-id disagrees with the prompt file")
    if any(len(normalize_dna(seq)) != PROMPT_BASES for seq in prompts.values()):
        raise ValueError("every prompt must hold 384 bases")
    order = evaluation_order(
        list(prompts), label=args.split_label, calibration_prompts=args.calibration_prompts
    )
    if args.evaluated_prompts > len(order):
        raise ValueError("--evaluated-prompts exceeds the held-out prompts")
    selected = order[: args.prompts]

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
        selected=set(selected),
        experiment_label=args.experiment_label,
        policy_id=args.policy_id,
        cohort_id=args.cohort_id,
        generation_experiment_id=args.generation_experiment_id,
    )
    expected_records = len(selected) * len(DRAWS) * 2
    if len(records) != expected_records:
        raise ValueError(f"found {len(records)} generation records, expected {expected_records}")

    spans, span_digests = load_natural_spans(args.natural_dir, prompts)
    inputs = {
        "cohort_jsonl": {
            "path": str(args.cohort_jsonl.resolve()),
            "sha256": sha256_file(str(args.cohort_jsonl)),
        },
        "protocol": {
            "path": str(args.protocol.resolve()),
            "sha256": sha256_file(str(args.protocol)),
        },
        "generation": [
            {"path": str(path.resolve()), "sha256": sha256_file(str(path))}
            for path in sequence_files
        ],
        "natural_spans": {
            "directory": str(args.natural_dir.resolve()),
            "count": len(span_digests),
            "sha256_by_prompt_id": span_digests,
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        args.output_dir / "run_identity.json",
        json.dumps(run_identity(args, selected), indent=2, sort_keys=True) + "\n",
    )
    if not args.finalize_only:
        run_shards(args, selected=selected, prompts=prompts, records=records, spans=spans)
    finalize(args, selected=selected, inputs=inputs, started=started)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
