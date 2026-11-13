#!/usr/bin/env python3
"""Derive the SynthID v5 local review-study evidence artifacts.

Reads the immutable result files under ``outputs/synthid_v5_local`` (never writes there) and

* copies each study ``summary.json`` byte for byte into ``evidence/derived/synthid_v5/`` under a
  clear name (no trials, sequences, shards, or key material), and ``SHA256SUMS`` (compact copies
  plus the derived file);
* writes ``synthid_v5_derived_2026_11_13.json``: every table of the execution record, with each
  number read from those summaries (or, for the S0 median strength, from the S0 trials file);
* checks digests, cross-checks the exact one-sided bounds it computes against the bounds the study
  summaries already store, and fails on any inconsistency.

All outputs are write-once: an existing file with different content is an error.

Usage: PYTHONPATH=src .venv/bin/python scripts/derive_synthid_v5_evidence.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from scipy.stats import beta as beta_dist

ROOT = Path(__file__).resolve().parents[1]
V5 = ROOT / "outputs" / "synthid_v5_local"
DEST = ROOT / "evidence" / "derived" / "synthid_v5"
DERIVED_NAME = "synthid_v5_derived_2026_11_13.json"
PROTOCOL = ROOT / "docs" / "research" / "synthid_v5_review_studies_protocol_2026_11_12.md"
COHORT = ROOT / "data" / "processed" / "ncbi_refseq_eukaryote_windows_fpr_v2_1608" / "prompts.jsonl"
MODELS = ("carbon", "generator")
FAMILIES = ("watermarked_correct_key", "ordinary_corresponding_key", "watermarked_wrong_key")
CONDITIONS = ("clean", "substitution_1nt", "insertion_1nt", "deletion_1nt")
S3_LEVELS = (0.01, 0.05, 0.10, 0.25, 0.50)
DETECTORS = ("aligned_oracle", "phase_only", "verifier", "fine_grid")
EXPECTED_PROTOCOL_SHA = "49509bc664a5dadfcdddce486a45d4be708da6eae1921424482f6b0cd19de317"
EXPECTED_PROMPTS_SHA = "cb19e90662fcb25f774b0840e2e696132e2dc9c54439d97597bd186d4948f775"
EXPECTED_COHORT_CONTENT_SHA = "f6075a85bc056f5159952031618c544fb3a82864ed9029c913e7f5a7d03c5dc5"
N_EVAL = 512


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def one_sided_upper(positives: int, trials: int, confidence: float = 0.95) -> float:
    """Exact (Clopper-Pearson) one-sided upper bound; 1 when every trial is positive."""
    if positives >= trials:
        return 1.0
    return float(beta_dist.ppf(confidence, positives + 1, trials - positives))


def one_sided_lower(positives: int, trials: int, confidence: float = 0.95) -> float:
    if positives <= 0:
        return 0.0
    return float(beta_dist.ppf(1.0 - confidence, positives, trials - positives + 1))


def two_sided(positives: int, trials: int, confidence: float = 0.95) -> list[float]:
    alpha = 1.0 - confidence
    low = (
        0.0
        if positives == 0
        else float(beta_dist.ppf(alpha / 2, positives, trials - positives + 1))
    )
    high = (
        1.0
        if positives == trials
        else float(beta_dist.ppf(1 - alpha / 2, positives + 1, trials - positives))
    )
    return [low, high]


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return math.isclose(a, b, rel_tol=tol, abs_tol=tol)


# ---------------------------------------------------------------------------------------------
# Compact copies
# ---------------------------------------------------------------------------------------------


def compact_sources() -> dict[str, Path]:
    sources: dict[str, Path] = {}
    for model in MODELS:
        base = V5 / model
        sources[f"{model}_s0_position_independent_summary.json"] = (
            base / "merged/position_independent/summary.json"
        )
        sources[f"{model}_generation_summary.json"] = (
            base / "merged/generation/generation_summary.json"
        )
        sources[f"{model}_s1_layout_summary.json"] = base / "studies/s1_layout/summary.json"
        sources[f"{model}_s2_detectors_summary.json"] = base / "studies/s2_detectors/summary.json"
        sources[f"{model}_s2_timing_summary.json"] = base / "studies/s2_timing/summary.json"
        sources[f"{model}_s3_null_ordinary_model_output_summary.json"] = (
            base / "studies/s3_null_ordinary_model_output/summary.json"
        )
        sources[f"{model}_s3_null_marked_independent_key_summary.json"] = (
            base / "studies/s3_null_marked_independent_key/summary.json"
        )
        sources[f"{model}_s4_entropy_summary.json"] = base / "studies/s4_entropy/summary.json"
    sources["shared_s3_null_natural_dna_summary.json"] = (
        V5 / "shared/s3_null_natural_dna/summary.json"
    )
    sources["shared_s4_entropy_analysis_summary.json"] = (
        V5 / "shared/s4_entropy_analysis/summary.json"
    )
    sources["evaluated_case_ids.txt"] = V5 / "evaluated_case_ids.txt"
    return sources


LONG_ACGT = re.compile(r"[ACGTacgt]{60,}")


def write_once(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() != data:
            raise SystemExit(f"refusing to overwrite {rel(path)} with different content")
        return
    path.write_bytes(data)


def copy_compact(sources: dict[str, Path]) -> dict[str, str]:
    DEST.mkdir(parents=True, exist_ok=True)
    digests: dict[str, str] = {}
    for name, source in sources.items():
        data = source.read_bytes()
        if name.endswith(".json"):
            text = data.decode("utf-8")
            if LONG_ACGT.search(text):
                raise SystemExit(f"{name}: contains a long nucleotide run; refusing to copy")
            for forbidden in ('"secret_key"', '"private_key"', '"key_hex"', '"raw_key"'):
                if forbidden in text:
                    raise SystemExit(f"{name}: contains forbidden key field {forbidden}")
        write_once(DEST / name, data)
        digests[name] = hashlib.sha256(data).hexdigest()
        if sha256_file(DEST / name) != sha256_file(source):
            raise SystemExit(f"copy of {name} differs from its source")
    return digests


# ---------------------------------------------------------------------------------------------
# S0
# ---------------------------------------------------------------------------------------------


def s0_strengths(model: str) -> dict[tuple[str, str], dict[str, Any]]:
    """Median/min/max of -log10(smallest window P) per condition and family, from S0 trials."""
    groups: dict[tuple[str, str], list[float]] = {}
    path = V5 / model / "merged/position_independent/trials.jsonl"
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            key = (row["condition"], row["family"])
            groups.setdefault(key, []).append(-row["minimum_local_log_p_value"] / math.log(10.0))
    return {
        key: {
            "reads": len(values),
            "median": statistics.median(values),
            "minimum": min(values),
            "maximum": max(values),
        }
        for key, values in groups.items()
    }


def derive_s0(model: str) -> dict[str, Any]:
    summary = load(V5 / model / "merged/position_independent/summary.json")
    strengths = s0_strengths(model)
    rows = []
    for index, row in enumerate(summary["rates"]):
        any_draw = row["prompt_any_draw"]
        both = row["prompt_both_draws"]
        trials = any_draw["trials"]
        assert trials == N_EVAL == both["trials"] == row["prompt_clusters"]
        entry = {
            "summary_index": index,
            "condition": row["condition"],
            "family": row["family"],
            "reads_detected": row["detections"],
            "reads": row["trials"],
            "read_rate": row["rate"],
            "prompt_any_draw": {
                "positives": any_draw["detections"],
                "trials": trials,
                "rate": any_draw["detections"] / trials,
                "exact_two_sided_95_interval": any_draw["exact_95_interval"],
                "exact_one_sided_95_upper_bound": one_sided_upper(any_draw["detections"], trials),
            },
            "prompt_both_draws": {
                "positives": both["detections"],
                "trials": trials,
                "rate": both["detections"] / trials,
                "exact_two_sided_95_interval": both["exact_95_interval"],
                "exact_one_sided_95_upper_bound": one_sided_upper(both["detections"], trials),
            },
            "median_strength_neg_log10_smallest_window_p": strengths[
                (row["condition"], row["family"])
            ]["median"],
            "strength_read_count": strengths[(row["condition"], row["family"])]["reads"],
            "winning_window_base_length_counts": row["winning_window_base_length_counts"],
            "winning_orientation_counts": row["winning_orientation_counts"],
        }
        if not close(
            entry["prompt_any_draw"]["exact_two_sided_95_interval"][0],
            two_sided(any_draw["detections"], trials)[0],
        ):
            raise SystemExit(f"S0 {model}: stored interval disagrees with recomputation")
        rows.append(entry)
    assert len(rows) == 12
    return {
        "summary": rel(V5 / model / "merged/position_independent/summary.json"),
        "experiment_id": summary["experiment_id"],
        "total_decisions": summary["total_decisions"],
        "expected_hypotheses_by_observed_bases": summary["expected_hypotheses_by_observed_bases"],
        "rows": rows,
    }


# ---------------------------------------------------------------------------------------------
# S1
# ---------------------------------------------------------------------------------------------


def derive_s1(model: str) -> dict[str, Any]:
    summary = load(V5 / model / "studies/s1_layout/summary.json")
    cells: dict[str, Any] = {}
    max_read_rate = (-1.0, [])
    any_draw_above_one_percent = []
    for cell in summary["cells"]:
        marked = cell["families"]["watermarked_correct_key"]
        ordinary = cell["families"]["ordinary_corresponding_key"]
        for family_name, block in (("marked", marked), ("ordinary", ordinary)):
            for level in ("prompt_any_draw", "prompt_both_draws"):
                if family_name == "ordinary":
                    stored = block[level]["exact_one_sided_95_upper_bound"]
                    computed = one_sided_upper(block[level]["positives"], block[level]["trials"])
                    if not close(stored, computed):
                        raise SystemExit(f"S1 {model} {cell['cell']}: one-sided bound mismatch")
        o_reads = ordinary["sequence_level"]
        if o_reads["rate"] > max_read_rate[0] + 1e-15:
            max_read_rate = (o_reads["rate"], [cell["cell"]])
        elif abs(o_reads["rate"] - max_read_rate[0]) <= 1e-15:
            max_read_rate[1].append(cell["cell"])
        if ordinary["prompt_any_draw"]["rate"] > 0.01:
            any_draw_above_one_percent.append(
                {
                    "cell": cell["cell"],
                    "positives": ordinary["prompt_any_draw"]["positives"],
                    "trials": ordinary["prompt_any_draw"]["trials"],
                    "rate": ordinary["prompt_any_draw"]["rate"],
                    "exact_one_sided_95_upper_bound": ordinary["prompt_any_draw"][
                        "exact_one_sided_95_upper_bound"
                    ],
                }
            )
        cells[cell["cell"]] = {
            "series": cell["series"],
            "region_bases": cell["region_bases"],
            "read_bases": cell["read_bases"],
            "marked": {
                "reads_detected": marked["sequence_level"]["positives"],
                "reads": marked["reads"],
                "read_rate": marked["sequence_level"]["rate"],
                "read_exact_two_sided_95_interval": marked["sequence_level"][
                    "exact_two_sided_95_interval"
                ],
                "prompts_both_draws_detected": marked["prompt_both_draws"]["positives"],
                "prompts_any_draw_detected": marked["prompt_any_draw"]["positives"],
                "prompts": marked["prompt_both_draws"]["trials"],
                "prompt_both_draws_exact_two_sided_95_interval": marked["prompt_both_draws"][
                    "exact_two_sided_95_interval"
                ],
                "median_strength": marked["strength"]["median"],
                "minimum_strength": marked["strength"]["minimum"],
                "median_hypotheses_searched": marked["median_hypotheses_searched"],
                "median_region_overlap_bases": marked["median_region_overlap_bases"],
                "median_region_overlap_fraction_of_window": marked[
                    "median_region_overlap_fraction_of_window"
                ],
                "strongest_window_length_counts": marked["strongest_window_length_counts"],
                **(
                    {"median_region_bases_retained": marked["median_region_bases_retained"]}
                    if "median_region_bases_retained" in marked
                    else {}
                ),
            },
            "ordinary": {
                "reads_positive": o_reads["positives"],
                "reads": ordinary["reads"],
                "read_rate": o_reads["rate"],
                "read_exact_two_sided_95_interval": o_reads["exact_two_sided_95_interval"],
                "prompts_any_draw_positive": ordinary["prompt_any_draw"]["positives"],
                "prompts": ordinary["prompt_any_draw"]["trials"],
                "prompt_any_draw_rate": ordinary["prompt_any_draw"]["rate"],
                "prompt_any_draw_exact_one_sided_95_upper_bound": ordinary["prompt_any_draw"][
                    "exact_one_sided_95_upper_bound"
                ],
                "prompts_both_draws_positive": ordinary["prompt_both_draws"]["positives"],
                "median_strength": ordinary["strength"]["median"],
                "control_rate_above_target_per_summary": ordinary["control_rate_above_target"],
            },
        }
    assert len(cells) == 54
    series_counts: dict[str, int] = {}
    for cell in cells.values():
        series_counts[cell["series"]] = series_counts.get(cell["series"], 0) + 1
    marked_missed = {
        name: {
            "reads_missed": cell["marked"]["reads"] - cell["marked"]["reads_detected"],
            "prompts_both_draws_missed": cell["marked"]["prompts"]
            - cell["marked"]["prompts_both_draws_detected"],
        }
        for name, cell in cells.items()
        if cell["marked"]["reads_detected"] != cell["marked"]["reads"]
    }
    checks = summary["validity_checks"]
    return {
        "summary": rel(V5 / model / "studies/s1_layout/summary.json"),
        "valid": summary["valid"],
        "validity_failures": summary["validity_failures"],
        "total_decisions": summary["total_decisions"],
        "check_1": {
            "status": checks["check_1_reference_layout_reproduces_s0_unedited"]["status"],
            "compared": checks["check_1_reference_layout_reproduces_s0_unedited"]["compared"],
            "mismatches": checks["check_1_reference_layout_reproduces_s0_unedited"]["mismatches"],
            "max_abs_log_p_difference": checks["check_1_reference_layout_reproduces_s0_unedited"][
                "max_abs_log_p_difference"
            ],
        },
        "check_2": {
            "status": checks["check_2_series_c_strand_pairs_identical"]["status"],
            "pairs": checks["check_2_series_c_strand_pairs_identical"]["pairs"],
            "mismatches": checks["check_2_series_c_strand_pairs_identical"]["mismatches"],
            "unpaired": checks["check_2_series_c_strand_pairs_identical"]["unpaired"],
        },
        "ordinary_cells_above_target_per_summary": summary["ordinary_cells_above_target"],
        "cells_per_series": series_counts,
        "cells": cells,
        "ordinary_read_level_maximum": {"rate": max_read_rate[0], "cells": max_read_rate[1]},
        "ordinary_any_draw_prompt_rate_above_0_01": any_draw_above_one_percent,
        "ordinary_any_draw_prompt_rate_maximum": max(
            c["ordinary"]["prompt_any_draw_rate"] for c in cells.values()
        ),
        "marked_cells_with_a_missed_read": marked_missed,
        "marked_minimum_read_rate": min(c["marked"]["read_rate"] for c in cells.values()),
        "marked_minimum_prompt_both_draws_rate": min(
            c["marked"]["prompts_both_draws_detected"] / c["marked"]["prompts"]
            for c in cells.values()
        ),
        "detector_seconds_per_read_by_cell_parallel_run": summary["cost"][
            "detector_seconds_per_read_by_cell"
        ],
    }


# ---------------------------------------------------------------------------------------------
# S2
# ---------------------------------------------------------------------------------------------


def s2_table(summary: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    table: dict[str, dict[str, dict[str, Any]]] = {}
    for item in summary["cells_in_summary"]:
        slot = table.setdefault(item["cell"], {}).setdefault(item["detector"], {})
        slot[item["family"]] = item
    return table


def derive_s2(model: str) -> dict[str, Any]:
    detect = load(V5 / model / "studies/s2_detectors/summary.json")
    timing = load(V5 / model / "studies/s2_timing/summary.json")
    assert detect["prompts"] == 256 and timing["prompts"] == 32
    assert timing["runtime"]["workers"] == 1 and timing["runtime"]["timing_only"] is True
    assert timing["runtime"]["seconds_measured_under_parallel_workers"] is False
    table = s2_table(detect)
    timing_table = s2_table(timing)
    out: dict[str, Any] = {}
    for cell in detect["cells"]:
        out[cell] = {}
        for detector in DETECTORS:
            marked = table[cell][detector]["watermarked_correct_key"]
            ordinary = table[cell][detector]["ordinary_corresponding_key"]
            t_marked = timing_table[cell][detector]["watermarked_correct_key"]
            t_ordinary = timing_table[cell][detector]["ordinary_corresponding_key"]
            if ordinary["prompt_level"]["rule"] != "positive if either draw positive":
                raise SystemExit("unexpected S2 ordinary prompt rule")
            computed = one_sided_upper(
                ordinary["prompt_level"]["positives"], ordinary["prompt_level"]["trials"]
            )
            if not close(computed, ordinary["prompt_level"]["exact_one_sided_95_upper_bound"]):
                raise SystemExit(f"S2 {model} {cell} {detector}: one-sided bound mismatch")
            out[cell][detector] = {
                "marked": {
                    "reads_detected": marked["reads"]["positives"],
                    "reads": marked["reads"]["trials"],
                    "read_rate": marked["reads"]["rate"],
                    "read_exact_two_sided_95_interval": marked["reads"][
                        "exact_two_sided_95_interval"
                    ],
                    "prompts_both_draws_detected": marked["prompt_level"]["positives"],
                    "prompts": marked["prompt_level"]["trials"],
                    "prompt_rule": marked["prompt_level"]["rule"],
                    "prompt_exact_two_sided_95_interval": marked["prompt_level"][
                        "exact_two_sided_95_interval"
                    ],
                    "median_corrected_strength": marked["median_corrected_strength"],
                    "windows_searched_min": marked["windows_searched_min"],
                    "windows_searched_max": marked["windows_searched_max"],
                    "median_ms_per_read_parallel_run": marked["median_seconds_per_read"] * 1000.0,
                    "median_ms_per_read_single_process": t_marked["median_seconds_per_read"]
                    * 1000.0,
                    "single_process_reads": t_marked["reads"]["trials"],
                },
                "ordinary": {
                    "reads_positive": ordinary["reads"]["positives"],
                    "reads": ordinary["reads"]["trials"],
                    "read_rate": ordinary["reads"]["rate"],
                    "read_exact_two_sided_95_interval": ordinary["reads"][
                        "exact_two_sided_95_interval"
                    ],
                    "prompts_any_draw_positive": ordinary["prompt_level"]["positives"],
                    "prompts": ordinary["prompt_level"]["trials"],
                    "prompt_any_draw_rate": ordinary["prompt_level"]["rate"],
                    "prompt_exact_two_sided_95_interval": ordinary["prompt_level"][
                        "exact_two_sided_95_interval"
                    ],
                    "prompt_exact_one_sided_95_upper_bound": ordinary["prompt_level"][
                        "exact_one_sided_95_upper_bound"
                    ],
                    "median_corrected_strength": ordinary["median_corrected_strength"],
                    "windows_searched_min": ordinary["windows_searched_min"],
                    "windows_searched_max": ordinary["windows_searched_max"],
                    "median_ms_per_read_single_process": t_ordinary["median_seconds_per_read"]
                    * 1000.0,
                },
            }
    nonoverlap: list[dict[str, Any]] = []
    ordinary_read_above: list[dict[str, Any]] = []
    ordinary_prompt_above: list[dict[str, Any]] = []
    for cell, by_detector in out.items():
        for index, first in enumerate(DETECTORS):
            for second in DETECTORS[index + 1 :]:
                for family, key, interval_key in (
                    ("marked_prompts_both_draws", "marked", "prompt_exact_two_sided_95_interval"),
                    ("ordinary_prompts_any_draw", "ordinary", "prompt_exact_two_sided_95_interval"),
                ):
                    a = by_detector[first][key][interval_key]
                    b = by_detector[second][key][interval_key]
                    if a[1] < b[0] or b[1] < a[0]:
                        nonoverlap.append(
                            {"cell": cell, "family": family, "detectors": [first, second]}
                        )
        for detector, block in by_detector.items():
            ordinary = block["ordinary"]
            if ordinary["read_rate"] > 0.01:
                ordinary_read_above.append(
                    {
                        "cell": cell,
                        "detector": detector,
                        "positives": ordinary["reads_positive"],
                        "reads": ordinary["reads"],
                        "rate": ordinary["read_rate"],
                        "exact_two_sided_95_interval": ordinary["read_exact_two_sided_95_interval"],
                    }
                )
            if ordinary["prompt_any_draw_rate"] > 0.01:
                ordinary_prompt_above.append(
                    {
                        "cell": cell,
                        "detector": detector,
                        "positives": ordinary["prompts_any_draw_positive"],
                        "prompts": ordinary["prompts"],
                        "rate": ordinary["prompt_any_draw_rate"],
                        "exact_one_sided_95_upper_bound": ordinary[
                            "prompt_exact_one_sided_95_upper_bound"
                        ],
                    }
                )
    return {
        "summary": rel(V5 / model / "studies/s2_detectors/summary.json"),
        "timing_summary": rel(V5 / model / "studies/s2_timing/summary.json"),
        "pairs_with_nonoverlapping_prompt_level_intervals": nonoverlap,
        "ordinary_read_rate_above_0_01": ordinary_read_above,
        "ordinary_prompt_any_draw_rate_above_0_01": ordinary_prompt_above,
        "prompts": detect["prompts"],
        "timing_prompts": timing["prompts"],
        "total_decisions": detect["total_decisions"],
        "timing_total_decisions": timing["total_decisions"],
        "cpu_model": timing["runtime"]["cpu_model"],
        "logical_cpus": timing["runtime"]["logical_cpus"],
        "cells": out,
    }


# ---------------------------------------------------------------------------------------------
# S3
# ---------------------------------------------------------------------------------------------


def derive_s3_one(path: Path) -> dict[str, Any]:
    summary = load(path)
    assert summary["partial_run"] is False and summary["keys"] == 64
    assert summary["key_bytes_recorded"] is False
    positives, decisions = summary["positives_at_0_01"], summary["decisions"]
    computed = one_sided_upper(positives, decisions)
    if not close(computed, summary["exact_one_sided_95_upper_bound_at_0_01"]):
        raise SystemExit(f"{path}: pooled upper bound mismatch")
    table = []
    for item in summary["calibration_table"]:
        if not close(
            one_sided_lower(item["count"], item["decisions"]),
            item["exact_one_sided_95_lower_bound"],
        ):
            raise SystemExit(f"{path}: calibration lower-bound mismatch at {item['nominal_level']}")
        table.append(
            {
                "nominal_level": item["nominal_level"],
                "count": item["count"],
                "decisions": item["decisions"],
                "fraction": item["fraction"],
                "exact_two_sided_95_interval": item["exact_two_sided_95_interval"],
                "exact_one_sided_95_lower_bound": item["exact_one_sided_95_lower_bound"],
                "exceeds_nominal": item["exceeds_nominal"],
            }
        )
    assert [t["nominal_level"] for t in table] == list(S3_LEVELS)
    per_key = summary["per_key"]
    assert len(per_key) == 64
    worst = max(per_key, key=lambda item: (item["positives"], -item["key_index"]))
    return {
        "summary": rel(path),
        "family": summary["family"],
        "reads": summary["reads"],
        "keys": summary["keys"],
        "decisions": decisions,
        "positives": positives,
        "rate": summary["rate_at_0_01"],
        "exact_two_sided_95_interval": summary["exact_two_sided_95_interval_at_0_01"],
        "exact_one_sided_95_upper_bound": summary["exact_one_sided_95_upper_bound_at_0_01"],
        "per_key_rate_min": summary["per_key_rate_min"],
        "per_key_rate_median": summary["per_key_rate_median"],
        "per_key_rate_max": summary["per_key_rate_max"],
        "per_key_max_positives": worst["positives"],
        "per_key_max_key_index": worst["key_index"],
        "keys_with_zero_positives": sum(1 for item in per_key if item["positives"] == 0),
        "reads_positive_under_at_least_one_key": summary["reads_positive_under_at_least_one_key"],
        "hypotheses_searched_counts": summary["hypotheses_searched_counts"],
        "calibration": table,
        "any_calibration_level_exceeds_nominal": any(t["exceeds_nominal"] for t in table),
    }


def derive_s3() -> dict[str, Any]:
    out: dict[str, Any] = {
        "natural_dna": derive_s3_one(V5 / "shared/s3_null_natural_dna/summary.json")
    }
    for family in ("ordinary_model_output", "marked_independent_key"):
        out[family] = {
            model: derive_s3_one(V5 / model / f"studies/s3_null_{family}/summary.json")
            for model in MODELS
        }
    return out


# ---------------------------------------------------------------------------------------------
# S4
# ---------------------------------------------------------------------------------------------


def derive_s4() -> dict[str, Any]:
    analysis = load(V5 / "shared/s4_entropy_analysis/summary.json")
    out: dict[str, Any] = {
        "summary": rel(V5 / "shared/s4_entropy_analysis/summary.json"),
        "bootstrap": analysis["bootstrap"],
        "mark_bit_definition": analysis["mark_bit_definition"],
        "strength_definition": analysis["strength_definition"],
        "models": {},
    }
    for model in MODELS:
        block = analysis["models"][model]
        pass_summary = load(V5 / model / "studies/s4_entropy/summary.json")
        out["models"][model] = {
            "entropy_summary": rel(V5 / model / "studies/s4_entropy/summary.json"),
            "sequences": pass_summary["sequences"],
            "positions_per_sequence": pass_summary["positions_per_sequence"],
            "crosscheck_nll": pass_summary["crosscheck_nll"],
            "device": pass_summary["device"],
            "dtype": pass_summary["dtype"],
            "torch_version": pass_summary["session"]["torch_version"],
            "mean_entropy_nats_marked": block["mean_entropy_nats"]["marked"],
            "mean_entropy_nats_ordinary": block["mean_entropy_nats"]["ordinary"],
            "mark_bit_fraction": block["mark_bit_fraction"],
            "s0_strength": block["s0_strength_neg_log10_smallest_window_p"],
            "scored_tokens_per_continuation": block["scored_tokens_per_continuation"],
            "spearman_entropy_vs_s0_strength": block["spearman_entropy_vs_s0_strength"],
            "spearman_entropy_vs_mark_bit_fraction": block["spearman_entropy_vs_mark_bit_fraction"],
            "prior_expectation": block["prior_expectation"],
            "ln_4096_nats": math.log(4096.0),
        }
        for key in ("spearman_entropy_vs_s0_strength", "spearman_entropy_vs_mark_bit_fraction"):
            assert block[key]["prompts"] == N_EVAL and block[key]["bootstrap_replicates"] == 10000
    return out


# ---------------------------------------------------------------------------------------------
# Identity, digests, timeline
# ---------------------------------------------------------------------------------------------


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def derive_identity(compact_digests: dict[str, str]) -> dict[str, Any]:
    protocol_sha = sha256_file(PROTOCOL)
    prompts_sha = sha256_file(COHORT)
    # protocol and cohort digests recorded in every study summary
    recorded: dict[str, set[str]] = {
        "protocol": set(),
        "cohort_jsonl": set(),
        "cohort_content": set(),
    }

    def walk(node: Any, trail: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "protocol" and isinstance(value, dict) and "sha256" in value:
                    recorded["protocol"].add(value["sha256"])
                if key == "protocol_sha256" and isinstance(value, str):
                    recorded["protocol"].add(value)
                if key in ("cohort_jsonl_sha256",) and isinstance(value, str):
                    recorded["cohort_jsonl"].add(value)
                if key == "cohort" and isinstance(value, dict) and "sha256" in value:
                    recorded["cohort_jsonl"].add(value["sha256"])
                if key == "cohort_content_sha256" and isinstance(value, str):
                    recorded["cohort_content"].add(value)
                if key == "inputs" and isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict) and item.get("role") == "cohort_prompts":
                            recorded["cohort_jsonl"].add(item["sha256"])
                walk(value, f"{trail}.{key}")
        elif isinstance(node, list):
            for item in node:
                walk(item, trail)

    for name in compact_digests:
        if name.endswith(".json"):
            walk(load(DEST / name), name)
    # S1 and S2 run identities also record the cohort digest
    for model in MODELS:
        for study in ("s1_layout", "s2_detectors", "s2_timing"):
            walk(load(V5 / model / "studies" / study / "run_identity.json"), study)

    ids_all = (V5 / "evaluated_case_ids.txt").read_text().split()
    for model in MODELS:
        if (V5 / model / "evaluated_case_ids.txt").read_text().split() != ids_all:
            raise SystemExit(f"{model}: evaluated id list differs from the shared list")
    # independent re-derivation of the first N_EVAL held-out prompts in split-rank order
    sys.path.insert(0, str(ROOT / "src"))
    from genomic_watermarks.large_validation import CALIBRATION_SPLIT_LABEL

    cohort_ids = [
        str(json.loads(line)["prompt_id"])
        for line in COHORT.read_text().splitlines()
        if line.strip()
    ]
    ranked = sorted(
        cohort_ids,
        key=lambda c: (hashlib.sha256(f"{CALIBRATION_SPLIT_LABEL}\x00{c}".encode()).digest(), c),
    )
    held_out = ranked[64:]
    rederived = held_out[:N_EVAL]
    split_ok = rederived == ids_all and len(held_out) == 1544 and len(cohort_ids) == 1608

    splits = {}
    for model in MODELS:
        record = load(V5 / model / "merged/detection/prompt_split.json")
        counts: dict[str, int] = {}
        for value in record["assignments"].values():
            counts[value] = counts.get(value, 0) + 1
        evaluation = {c for c, v in record["assignments"].items() if v == "evaluation"}
        splits[model] = {
            "label": record["label"],
            "assignment_counts": counts,
            "evaluation_equals_evaluated_ids": evaluation == set(ids_all),
            "sha256": sha256_file(V5 / model / "merged/detection/prompt_split.json"),
        }

    return {
        "cohort_id": "ncbi_refseq_eukaryote_windows_fpr_v2_1608",
        "cohort_content_sha256_recorded_in_summaries": sorted(recorded["cohort_content"]),
        "cohort_content_sha256_expected_by_protocol": EXPECTED_COHORT_CONTENT_SHA,
        "prompts_jsonl_sha256_current": prompts_sha,
        "prompts_jsonl_sha256_expected_by_protocol": EXPECTED_PROMPTS_SHA,
        "prompts_jsonl_sha256_recorded_in_summaries": sorted(recorded["cohort_jsonl"]),
        "prompts_jsonl_matches": prompts_sha == EXPECTED_PROMPTS_SHA
        and recorded["cohort_jsonl"] == {prompts_sha},
        "protocol_sha256_current": protocol_sha,
        "protocol_sha256_recorded_in_summaries": sorted(recorded["protocol"]),
        "protocol_sha256_matches": recorded["protocol"] == {protocol_sha},
        "evaluated_prompts": N_EVAL,
        "evaluated_case_ids_sha256": sha256_file(V5 / "evaluated_case_ids.txt"),
        "evaluated_ids_equal_rederived_first_512_held_out": split_ok,
        "cohort_prompts": len(cohort_ids),
        "held_out_prompts": len(held_out),
        "split_label": CALIBRATION_SPLIT_LABEL,
        "prompt_split_by_model": splits,
        "prompt_bases": 384,
        "continuation_bases": 3072,
        "draws_per_prompt": 2,
    }


def parse_utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)


def derive_timeline() -> dict[str, Any]:
    out: dict[str, Any] = {"generation": {}, "stages": {}}
    for model in MODELS:
        sessions = []
        for path in sorted((V5 / model / "merged/generation/sessions").glob("*.json")):
            record = load(path)
            recorded = parse_utc(record["started_utc"])
            implied_start = recorded - timedelta(seconds=record["wall_seconds"])
            sessions.append(
                {
                    "file": path.name,
                    "draw": record["draw_id"],
                    "cases": record["case_count"],
                    "started_utc_field": record["started_utc"],
                    "wall_seconds": record["wall_seconds"],
                    "field_minus_wall_seconds_utc": implied_start.isoformat(),
                    "device": record["device"],
                    "dtype": record["dtype"],
                    "python": record["python"],
                    "platform": record["platform"],
                    "process_peak_rss_gib": record["process_peak_rss_gib"],
                    "model_load_seconds": record["model_load_seconds"],
                }
            )
        log_starts = []
        for path in sorted((V5 / model / "logs").glob("p*.log")):
            stamp = path.name.split(".")[1]
            log_starts.append(datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC))
        draw0_ends = [parse_utc(s["started_utc_field"]) for s in sessions if s["draw"] == 0]
        draw1_ends = [parse_utc(s["started_utc_field"]) for s in sessions if s["draw"] == 1]
        # started_utc is read as the session end only if it agrees with the log-name start
        offsets = []
        for log_start, session in zip(
            log_starts, [s for s in sessions if s["draw"] == 0], strict=True
        ):
            end = parse_utc(session["started_utc_field"])
            offsets.append(
                (end - timedelta(seconds=session["wall_seconds"]) - log_start).total_seconds()
            )
        out["generation"][model] = {
            "process_start_utc_from_log_names": [t.isoformat() for t in log_starts],
            "sessions": sessions,
            "last_draw0_session_timestamp": max(draw0_ends).isoformat(),
            "last_draw1_session_timestamp": max(draw1_ends).isoformat(),
            "log_start_vs_timestamp_minus_wall_seconds": offsets,
            "timestamp_field_is_session_end": all(-5.0 <= o <= 5.0 for o in offsets),
            "sessions_wall_seconds_total": sum(s["wall_seconds"] for s in sessions),
            "model_generation_seconds_total": load(
                V5 / model / "merged/generation/generation_summary.json"
            )["model_generation_seconds"],
            "sequences": load(V5 / model / "merged/generation/generation_summary.json")[
                "sequence_count"
            ],
            "ordinary_sequences": load(V5 / model / "merged/generation/generation_summary.json")[
                "ordinary_sequence_count"
            ],
            "watermarked_sequences": load(V5 / model / "merged/generation/generation_summary.json")[
                "watermarked_sequence_count"
            ],
            "total_generated_bases": load(V5 / model / "merged/generation/generation_summary.json")[
                "total_generated_bases"
            ],
        }
    stamp = re.compile(r"^\[(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)\] (.*)$")
    for log in ("detect_generator", "detect_carbon", "final"):
        events = []
        for line in (V5 / "logs" / f"{log}.log").read_text().splitlines():
            match = stamp.match(line)
            if match:
                events.append({"utc": match.group(1), "stage": match.group(2)})
        out["stages"][log] = events
    for log_name in ("detect_generator", "detect_carbon", "final"):
        text = (V5 / "logs" / f"{log_name}.log").read_text()
        out["stages"][f"{log_name}_warning_lines"] = len(
            re.findall(r"WARNING|FAILED|Traceback", text)
        )
        out["stages"][f"{log_name}_validator_ok_lines"] = re.findall(
            r'^\{"decisions": \d+, "experiment_id": "[^"]+", "prompts": \d+, '
            r'"rate_cells": \d+, "status": "ok"\}$',
            text,
            flags=re.M,
        )
        out["stages"][f"{log_name}_s1_complete_lines"] = len(
            re.findall(r'^\{"status": "complete", "valid": true\}$', text, flags=re.M)
        )
    return out


def derive_digests() -> dict[str, Any]:
    entries: dict[str, str] = {}
    for model in MODELS:
        base = V5 / model
        for sub in (
            "merged/generation/draw_00_generation.json",
            "merged/generation/draw_01_generation.json",
            "merged/generation/draw_00_sequences.jsonl",
            "merged/generation/draw_01_sequences.jsonl",
            "merged/generation/generation_summary.json",
            "merged/detection/prompt_split.json",
            "merged/position_independent/summary.json",
            "merged/position_independent/trials.jsonl",
            "merged/position_independent/report.md",
            "studies/s1_layout/summary.json",
            "studies/s1_layout/trials.jsonl.gz",
            "studies/s1_layout/run_identity.json",
            "studies/s1_layout/natural_pool_manifest.tsv",
            "studies/s2_detectors/summary.json",
            "studies/s2_detectors/trials.jsonl.gz",
            "studies/s2_detectors/run_identity.json",
            "studies/s2_timing/summary.json",
            "studies/s2_timing/trials.jsonl.gz",
            "studies/s2_timing/run_identity.json",
            "studies/s3_null_ordinary_model_output/summary.json",
            "studies/s3_null_ordinary_model_output/trials.jsonl.gz",
            "studies/s3_null_marked_independent_key/summary.json",
            "studies/s3_null_marked_independent_key/trials.jsonl.gz",
            "studies/s4_entropy/summary.json",
            "studies/s4_entropy/sequences.jsonl",
        ):
            entries[rel(base / sub)] = sha256_file(base / sub)
    for sub in (
        "shared/s3_null_natural_dna/summary.json",
        "shared/s3_null_natural_dna/trials.jsonl.gz",
        "shared/s4_entropy_analysis/summary.json",
        "shared/s4_entropy_analysis/marked_sequences_joined.jsonl",
        "evaluated_case_ids.txt",
        "logs/detect_generator.log",
        "logs/detect_carbon.log",
        "logs/final.log",
    ):
        entries[rel(V5 / sub)] = sha256_file(V5 / sub)
    # trials artifacts must agree with the digests the summaries store
    stored: dict[str, str] = {}
    for model in MODELS:
        for study in (
            "s1_layout",
            "s2_detectors",
            "s2_timing",
            "s3_null_ordinary_model_output",
            "s3_null_marked_independent_key",
        ):
            summary = load(V5 / model / "studies" / study / "summary.json")
            artifact = summary.get("trials_artifact")
            if artifact:
                stored[rel(Path(artifact["path"]))] = artifact["sha256"]
        stored[rel(V5 / model / "merged/position_independent/trials.jsonl")] = load(
            V5 / model / "merged/position_independent/summary.json"
        )["trials_artifact"]["sha256"]
    stored[rel(V5 / "shared/s3_null_natural_dna/trials.jsonl.gz")] = load(
        V5 / "shared/s3_null_natural_dna/summary.json"
    )["trials_artifact"]["sha256"]
    mismatches = {
        path: (entries[path], digest) for path, digest in stored.items() if entries[path] != digest
    }
    if mismatches:
        raise SystemExit(f"trials digests disagree with summaries: {mismatches}")
    return {
        "files": entries,
        "trials_digests_match_summaries": True,
        "trials_digests_checked": len(stored),
    }


def derive_code() -> dict[str, Any]:
    recorded: dict[str, set[str]] = {}

    def add(path: str, digest: str) -> None:
        recorded.setdefault(path, set()).add(digest)

    def collect(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if (
                    key in ("code_sha256", "code")
                    and isinstance(value, dict)
                    and all(isinstance(v, str) and len(v) == 64 for v in value.values())
                ):
                    for path, digest in value.items():
                        add(path, digest)
                collect(value)
        elif isinstance(node, list):
            for item in node:
                collect(item)

    for path in sorted(DEST.glob("*.json")):
        collect(load(path))
    for model in MODELS:
        for study in ("s1_layout", "s2_detectors", "s2_timing"):
            collect(load(V5 / model / "studies" / study / "run_identity.json"))
    # S0 provenance names its own scripts under explicit keys
    for model in MODELS:
        prov = load(V5 / model / "merged/position_independent/summary.json")["provenance"]
        for key in ("boundary_core", "detector", "runner", "synthid_core", "validator"):
            path = rel(Path(prov[key]["path"]))
            add(path, prov[key]["sha256"])
    extras = [
        "scripts/local/run_synthid_v5_generation.sh",
        "scripts/local/run_synthid_v5_overnight.sh",
        "scripts/local/run_synthid_v5_studies.sh",
        "scripts/run_carbon_large_generation.py",
        "scripts/run_generator_large_generation.py",
        "scripts/summarize_carbon_large_generation.py",
        "scripts/summarize_generator_large_generation.py",
    ]
    files = {}
    for path in sorted(set(recorded) | set(extras)):
        full = ROOT / path
        current = sha256_file(full)
        tracked = (
            subprocess.run(
                ["git", "ls-files", "--error-unmatch", path],
                cwd=ROOT,
                capture_output=True,
                text=True,
            ).returncode
            == 0
        )
        modified = bool(git("status", "--porcelain", "--", path)) if tracked else None
        last_commit = git("log", "-1", "--format=%h %cI", "--", path) if tracked else None
        files[path] = {
            "sha256_current": current,
            "sha256_recorded_in_summaries": sorted(recorded.get(path, [])),
            "current_matches_recorded": (
                None if path not in recorded else recorded[path] == {current}
            ),
            "tracked_in_git": tracked,
            "modified_relative_to_head": modified,
            "last_commit": last_commit,
        }
    return {
        "git_head_now": git("rev-parse", "HEAD"),
        "git_head_now_subject": git("log", "-1", "--format=%s"),
        "git_head_now_commit_time": git("log", "-1", "--format=%cI"),
        "uv_lock_sha256": sha256_file(ROOT / "uv.lock"),
        "files": files,
    }


# ---------------------------------------------------------------------------------------------


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    if not V5.is_dir():
        raise SystemExit(f"missing {rel(V5)}")
    sources = compact_sources()
    compact_digests = copy_compact(sources)
    derived = {
        "schema_version": 1,
        "namespace": "synthid.v5",
        "script": "scripts/derive_synthid_v5_evidence.py",
        "note": (
            "Every number is read from the compact summaries in this directory (digests in "
            "SHA256SUMS) "
            "or, for the S0 median strength, from the S0 trials file. One-sided exact bounds are "
            "recomputed here and cross-checked against the bounds the study summaries store."
        ),
        "compact_digests": compact_digests,
        "identity": derive_identity(compact_digests),
        "timeline": derive_timeline(),
        "digests": derive_digests(),
        "code": derive_code(),
        "s0": {model: derive_s0(model) for model in MODELS},
        "s1": {model: derive_s1(model) for model in MODELS},
        "s2": {model: derive_s2(model) for model in MODELS},
        "s3": derive_s3(),
        "s4": derive_s4(),
    }
    identity = derived["identity"]
    if not (identity["protocol_sha256_matches"] and identity["prompts_jsonl_matches"]):
        print("WARNING: protocol or cohort digest mismatch; see identity block", file=sys.stderr)
    payload = (json.dumps(derived, indent=2, sort_keys=True) + "\n").encode("utf-8")
    write_once(DEST / DERIVED_NAME, payload)
    all_digests = dict(compact_digests)
    all_digests[DERIVED_NAME] = hashlib.sha256(payload).hexdigest()
    lines = "".join(f"{digest}  {name}\n" for name, digest in sorted(all_digests.items()))
    write_once(DEST / "SHA256SUMS", lines.encode("utf-8"))
    print(
        json.dumps(
            {
                "written": rel(DEST / DERIVED_NAME),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "compact_files": len(compact_digests),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
