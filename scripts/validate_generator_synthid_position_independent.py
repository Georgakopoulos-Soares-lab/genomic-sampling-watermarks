#!/usr/bin/env python3
"""Strictly validate the GENERATOR position-independent SynthID result bundle."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.large_validation import (  # noqa: E402
    cluster_bootstrap_interval,
    sha256_file,
)
from genomic_watermarks.synthid_position_independent import (  # noqa: E402
    POSITION_INDEPENDENT_SYNTHID_DETECTOR,
    fair_binomial_log_survival_probability,
)
from genomic_watermarks.watermark import public_replay_seed  # noqa: E402

DEFAULT_OUTPUT = ROOT / "outputs/generator_synthid_position_independent_v1"
EXPERIMENT_ID = "generator_synthid_position_independent_v1"
POSITIVE = "watermarked_correct_key"
PRIMARY_NULL = "ordinary_corresponding_key"
WRONG_KEY = "watermarked_wrong_key"
FAMILIES = (POSITIVE, PRIMARY_NULL, WRONG_KEY)
CONDITIONS = ("clean", "substitution_1nt", "insertion_1nt", "deletion_1nt")
WINDOW_BASE_LENGTHS = (384, 768, 1536, 3072)
ORIENTATIONS = ("forward", "reverse_complement")
EXPECTED_PROMPTS = 192
EXPECTED_DRAWS = (0, 1)
TARGET_FPR = 0.01


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def close(left: float, right: float, *, tolerance: float = 1e-11) -> bool:
    return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


def exact_interval(successes: int, trials: int, confidence: float = 0.95) -> tuple[float, float]:
    from scipy.stats import beta

    tail = (1.0 - confidence) / 2.0
    lower = 0.0 if successes == 0 else float(beta.ppf(tail, successes, trials - successes + 1))
    upper = (
        1.0
        if successes == trials
        else float(beta.ppf(1.0 - tail, successes + 1, trials - successes))
    )
    return lower, upper


def expected_read_bases(condition: str) -> int:
    if condition in {"clean", "substitution_1nt"}:
        return 3456
    if condition == "insertion_1nt":
        return 3457
    if condition == "deletion_1nt":
        return 3455
    raise ValueError(f"unsupported condition: {condition}")


def expected_hypotheses(read_bases: int) -> int:
    return len(ORIENTATIONS) * sum(read_bases - length + 1 for length in WINDOW_BASE_LENGTHS)


def expected_key_index(family: str, draw_id: int) -> int:
    if family in {POSITIVE, PRIMARY_NULL}:
        return draw_id
    if family == WRONG_KEY:
        return (draw_id + 1) % 2
    raise ValueError(f"unsupported family: {family}")


def validate_trial(row: dict[str, Any]) -> None:
    forbidden = {
        "dna",
        "sequence",
        "generated_dna",
        "prompt",
        "key",
        "key_bytes",
        "key_hex",
    }
    if forbidden.intersection(row):
        raise ValueError("trial contains forbidden raw sequence or key material")
    case_id = str(row["case_id"])
    draw_id = int(row["draw_id"])
    condition = str(row["condition"])
    family = str(row["family"])
    if not case_id or draw_id not in EXPECTED_DRAWS:
        raise ValueError("trial has an invalid prompt or draw identity")
    if condition not in CONDITIONS or family not in FAMILIES:
        raise ValueError("trial has an invalid condition or family")
    if int(row["key_index"]) != expected_key_index(family, draw_id):
        raise ValueError("trial has an incorrect key mapping")
    if int(row["prompt_bases"]) != 384:
        raise ValueError("trial has an incorrect prompt length")
    read_bases = expected_read_bases(condition)
    if int(row["observed_bases"]) != read_bases:
        raise ValueError("trial has an incorrect observed length")
    if int(row["generated_bases_after_edit"]) != read_bases - 384:
        raise ValueError("trial has an incorrect continuation length")
    position = row["edit_position_in_generation"]
    if condition == "clean":
        if position is not None:
            raise ValueError("clean trial contains an edit position")
    elif not isinstance(position, int) or not 0 <= position < 3072:
        raise ValueError("edited trial has an invalid edit position")

    if row["detector_id"] != POSITION_INDEPENDENT_SYNTHID_DETECTOR:
        raise ValueError("trial uses the wrong detector")
    if tuple(row["orientations_searched"]) != ORIENTATIONS:
        raise ValueError("trial did not search both frozen orientations")
    if tuple(row["window_base_lengths_searched"]) != WINDOW_BASE_LENGTHS:
        raise ValueError("trial did not search every frozen length")
    hypotheses = expected_hypotheses(read_bases)
    if int(row["hypotheses_searched"]) != hypotheses:
        raise ValueError("trial has an incorrect complete-search hypothesis count")
    if not close(float(row["target_false_positive_rate"]), TARGET_FPR):
        raise ValueError("trial uses the wrong false-positive target")

    best = row["best_hypothesis"]
    orientation = str(best["orientation"])
    if orientation not in ORIENTATIONS:
        raise ValueError("winning orientation is invalid")
    window = int(best["window_base_length"])
    if window not in WINDOW_BASE_LENGTHS:
        raise ValueError("winning window length is invalid")
    oriented_start = int(best["oriented_start"])
    original_start = int(best["original_start"])
    original_stop = int(best["original_stop"])
    if not 0 <= oriented_start <= read_bases - window:
        raise ValueError("winning oriented start is invalid")
    if not 0 <= original_start < original_stop <= read_bases:
        raise ValueError("winning original interval is invalid")
    if original_stop - original_start != window:
        raise ValueError("winning original interval has the wrong length")
    expected_interval = (
        (oriented_start, oriented_start + window)
        if orientation == "forward"
        else (read_bases - oriented_start - window, read_bases - oriented_start)
    )
    if (original_start, original_stop) != expected_interval:
        raise ValueError("reverse-complement coordinate mapping is inconsistent")

    g_ones = int(best["g_ones"])
    g_total = int(best["g_total"])
    scored_tokens = int(best["scored_tokens"])
    repeated_contexts = int(best["repeated_contexts"])
    if not 0 <= g_ones <= g_total or g_total <= 0:
        raise ValueError("winning g counts are invalid")
    if g_total != scored_tokens * 30:
        raise ValueError("winning g total disagrees with scored tokens and depth")
    if scored_tokens + repeated_contexts != window // 6 - 4:
        raise ValueError("winning repetition accounting is inconsistent")
    statistic = (2.0 * g_ones - g_total) / math.sqrt(g_total)
    if not close(float(best["statistic"]), statistic):
        raise ValueError("winning statistic disagrees with its g counts")

    local_log_p = fair_binomial_log_survival_probability(g_ones, g_total)
    local_p = math.exp(local_log_p)
    if not close(float(best["local_log_p_value"]), local_log_p):
        raise ValueError("winning log p-value is inconsistent")
    if not close(float(best["local_exact_p_value"]), local_p):
        raise ValueError("winning exact p-value is inconsistent")
    if not close(float(row["minimum_local_log_p_value"]), local_log_p):
        raise ValueError("minimum local log p-value disagrees with the winning region")
    if not close(float(row["minimum_local_p_value"]), local_p):
        raise ValueError("minimum local p-value disagrees with the winning region")
    sequence_log_p = min(0.0, math.log(hypotheses) + local_log_p)
    sequence_p = math.exp(sequence_log_p)
    if not close(float(row["sequence_log_p_value"]), sequence_log_p):
        raise ValueError("global log p-value is inconsistent")
    if not close(float(row["sequence_p_value"]), sequence_p):
        raise ValueError("global p-value is inconsistent")
    detected = sequence_log_p <= math.log(TARGET_FPR)
    if bool(row["detected"]) != detected:
        raise ValueError("detection decision is inconsistent with the frozen threshold")


def validate_rate(
    cell: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    analysis_seed: int,
    bootstrap_replicates: int,
) -> None:
    condition = str(cell["condition"])
    family = str(cell["family"])
    selected = [
        row for row in rows if row["condition"] == condition and row["family"] == family
    ]
    if len(selected) != EXPECTED_PROMPTS * len(EXPECTED_DRAWS):
        raise ValueError("summary cell has the wrong trial count")
    detections = sum(bool(row["detected"]) for row in selected)
    if int(cell["detections"]) != detections or int(cell["trials"]) != len(selected):
        raise ValueError("summary detection count is inconsistent")
    if not close(float(cell["rate"]), detections / len(selected)):
        raise ValueError("summary detection rate is inconsistent")

    by_prompt: dict[str, list[float]] = defaultdict(list)
    for row in selected:
        by_prompt[str(row["case_id"])].append(float(bool(row["detected"])))
    expected_interval = cluster_bootstrap_interval(
        by_prompt,
        replicates=bootstrap_replicates,
        seed=public_replay_seed(
            EXPERIMENT_ID,
            str(analysis_seed),
            condition,
            family,
            "bootstrap",
        ),
    )
    observed_interval = cell["prompt_cluster_bootstrap_95_interval"]
    if not all(
        close(float(got), want)
        for got, want in zip(observed_interval, expected_interval, strict=True)
    ):
        raise ValueError("summary prompt-cluster interval is inconsistent")

    prompt_any = sum(any(values) for values in by_prompt.values())
    prompt_both = sum(all(values) for values in by_prompt.values())
    if int(cell["prompt_any_draw"]["detections"]) != prompt_any:
        raise ValueError("prompt-any count is inconsistent")
    if int(cell["prompt_both_draws"]["detections"]) != prompt_both:
        raise ValueError("prompt-both count is inconsistent")
    if int(cell["prompt_any_draw"]["trials"]) != EXPECTED_PROMPTS:
        raise ValueError("prompt-any denominator is inconsistent")
    if int(cell["prompt_both_draws"]["trials"]) != EXPECTED_PROMPTS:
        raise ValueError("prompt-both denominator is inconsistent")
    for field, successes in (("prompt_any_draw", prompt_any), ("prompt_both_draws", prompt_both)):
        expected_exact = exact_interval(successes, EXPECTED_PROMPTS)
        observed_exact = cell[field]["exact_95_interval"]
        if not all(
            close(float(got), want)
            for got, want in zip(observed_exact, expected_exact, strict=True)
        ):
            raise ValueError(f"{field} exact interval is inconsistent")

    log_ps = [float(row["sequence_log_p_value"]) for row in selected]
    statistics_values = [float(row["best_hypothesis"]["statistic"]) for row in selected]
    expected_summaries = {
        "sequence_log_p_value": (min(log_ps), statistics.median(log_ps), max(log_ps)),
        "best_statistic": (
            min(statistics_values),
            statistics.median(statistics_values),
            max(statistics_values),
        ),
    }
    for field, expected_values in expected_summaries.items():
        observed = cell[field]
        for name, expected in zip(
            ("minimum", "median", "maximum"), expected_values, strict=True
        ):
            if not close(float(observed[name]), expected):
                raise ValueError(f"summary {field} is inconsistent")
    orientations = dict(
        sorted(Counter(row["best_hypothesis"]["orientation"] for row in selected).items())
    )
    if cell["winning_orientation_counts"] != orientations:
        raise ValueError("summary winning orientations are inconsistent")
    lengths = {
        str(key): value
        for key, value in sorted(
            Counter(row["best_hypothesis"]["window_base_length"] for row in selected).items()
        )
    }
    if cell["winning_window_base_length_counts"] != lengths:
        raise ValueError("summary winning lengths are inconsistent")


def main() -> int:
    args = parse_args()
    summary_path = args.output_dir / "summary.json"
    trials_path = args.output_dir / "trials.jsonl"
    report_path = args.output_dir / "report.md"
    summary = json.loads(summary_path.read_text())
    rows = load_jsonl(trials_path)
    if summary.get("schema_version") != 1 or summary.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("result bundle has the wrong identity")
    if summary.get("watermark_scope") != "synthid-tournament-v1 only":
        raise ValueError("result bundle is not SynthID-only")
    if summary.get("detector_id") != POSITION_INDEPENDENT_SYNTHID_DETECTOR:
        raise ValueError("result bundle has the wrong detector")
    if (
        summary.get("generation_rerun") is not False
        or summary.get("calibration_rerun") is not False
    ):
        raise ValueError("result bundle reran generation or calibration")
    if int(summary.get("evaluation_prompts", -1)) != EXPECTED_PROMPTS:
        raise ValueError("result bundle has the wrong prompt count")
    if int(summary.get("draws_per_prompt", -1)) != len(EXPECTED_DRAWS):
        raise ValueError("result bundle has the wrong draw count")
    if tuple(summary.get("families", ())) != FAMILIES:
        raise ValueError("result bundle has the wrong families")
    if tuple(summary.get("conditions", ())) != CONDITIONS:
        raise ValueError("result bundle has the wrong conditions")
    if tuple(summary.get("window_base_lengths", ())) != WINDOW_BASE_LENGTHS:
        raise ValueError("result bundle has the wrong window lengths")
    if tuple(summary.get("orientations", ())) != ORIENTATIONS:
        raise ValueError("result bundle has the wrong orientations")
    if not close(float(summary.get("target_sequence_false_positive_rate", -1)), TARGET_FPR):
        raise ValueError("result bundle has the wrong false-positive target")

    expected_rows = EXPECTED_PROMPTS * len(EXPECTED_DRAWS) * len(CONDITIONS) * len(FAMILIES)
    if len(rows) != expected_rows or int(summary.get("total_decisions", -1)) != expected_rows:
        raise ValueError("result bundle has the wrong number of decisions")
    identities = {
        (row["case_id"], row["draw_id"], row["condition"], row["family"]) for row in rows
    }
    if len(identities) != expected_rows:
        raise ValueError("result bundle contains duplicate decisions")
    prompt_ids = {str(row["case_id"]) for row in rows}
    if len(prompt_ids) != EXPECTED_PROMPTS:
        raise ValueError("result bundle has the wrong number of prompt clusters")
    for case_id in prompt_ids:
        observed = {
            (row["draw_id"], row["condition"], row["family"])
            for row in rows
            if row["case_id"] == case_id
        }
        expected = {
            (draw, condition, family)
            for draw in EXPECTED_DRAWS
            for condition in CONDITIONS
            for family in FAMILIES
        }
        if observed != expected:
            raise ValueError(f"prompt {case_id} has an incomplete decision grid")
    for row in rows:
        validate_trial(row)

    rates = summary.get("rates")
    if not isinstance(rates, list) or len(rates) != len(CONDITIONS) * len(FAMILIES):
        raise ValueError("result bundle has an incomplete rate grid")
    rate_identities = {(cell["condition"], cell["family"]) for cell in rates}
    if rate_identities != {(condition, family) for condition in CONDITIONS for family in FAMILIES}:
        raise ValueError("result bundle has duplicate or missing rate cells")
    analysis_seed = int(summary["provenance"]["analysis_seed"])
    bootstrap_replicates = int(summary["provenance"]["bootstrap_replicates"])
    for cell in rates:
        validate_rate(
            cell,
            rows,
            analysis_seed=analysis_seed,
            bootstrap_replicates=bootstrap_replicates,
        )

    if summary["trials_artifact"]["sha256"] != sha256_file(trials_path):
        raise ValueError("trials artifact checksum mismatch")
    if summary["report_artifact"]["sha256"] != sha256_file(report_path):
        raise ValueError("report artifact checksum mismatch")
    for name in (
        "cohort",
        "prompt_split",
        "protocol",
        "detector",
        "boundary_core",
        "synthid_core",
        "runner",
        "validator",
    ):
        record = summary["provenance"][name]
        path = Path(record["path"])
        if not path.exists() or record["sha256"] != sha256_file(path):
            raise ValueError(f"provenance checksum mismatch: {name}")
    for record in summary["provenance"]["generation"]:
        path = Path(record["path"])
        if not path.exists() or record["sha256"] != sha256_file(path):
            raise ValueError("generation checksum mismatch")

    print(
        json.dumps(
            {
                "status": "ok",
                "experiment_id": EXPERIMENT_ID,
                "prompts": len(prompt_ids),
                "decisions": len(rows),
                "rate_cells": len(rates),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
