#!/usr/bin/env python3
"""Held-out, aligned SynthID detection for the GENERATOR validation corpus."""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import resource
import statistics
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.detector.search import (  # noqa: E402
    analytic_normal_threshold,
    binomial_standardized_exceedance_probability,
    calibrate_threshold,
    empirical_p_value,
)
from genomic_watermarks.dna import tokenize_fixed  # noqa: E402
from genomic_watermarks.large_validation import (  # noqa: E402
    CALIBRATION_SPLIT_LABEL,
    benjamini_hochberg,
    cluster_bootstrap_interval,
    cluster_sign_flip_test,
    deterministic_prompt_split,
    exact_mcnemar_p_value,
    fixture_key,
    null_key,
    paired_cluster_summary,
    sequence_identity,
    sha256_file,
)
from genomic_watermarks.pilot import load_context_cases_jsonl, numeric_summary  # noqa: E402
from genomic_watermarks.synthid import (  # noqa: E402
    DEFAULT_CONTEXT_HISTORY_SIZE,
    DEFAULT_CONTEXT_TOKENS,
    DEFAULT_DEPTH,
    SYNTHID_SCHEME,
    KeyedTournament,
    score_synthid_tokens,
)
from genomic_watermarks.watermark import (  # noqa: E402
    ORDINARY_SCHEME,
    public_replay_seed,
)

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_large_v1/prompts.jsonl"
POSITIVE = "watermarked_correct_key"
PRIMARY_NULL = "ordinary_corresponding_key"
WRONG_KEY = "watermarked_wrong_key"
ORDINARY_INDEPENDENT = "ordinary_independent_null_key"
PUBLIC_DNA = "public_refseq_independent_null_key"
EVALUATION_FAMILIES = (POSITIVE, PRIMARY_NULL, WRONG_KEY, ORDINARY_INDEPENDENT, PUBLIC_DNA)
DEFAULT_LABEL = "generator-synthid-validation-v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--draw-index", type=int, action="append")
    parser.add_argument("--token-lengths", type=int, nargs="+", default=(64, 128, 256, 512))
    parser.add_argument("--tournament-depth", type=int, default=DEFAULT_DEPTH)
    parser.add_argument("--context-tokens", type=int, default=DEFAULT_CONTEXT_TOKENS)
    parser.add_argument("--context-history-size", type=int, default=DEFAULT_CONTEXT_HISTORY_SIZE)
    parser.add_argument("--target-fpr", type=float, default=0.01)
    parser.add_argument(
        "--threshold-source",
        choices=("analytic", "empirical"),
        default="analytic",
        help=(
            "analytic: standard-normal quantile of the Binomial mean-g null, with the "
            "calibration trials used as a goodness-of-fit check; empirical: null order statistic"
        ),
    )
    parser.add_argument("--calibration-prompts", type=int, default=64)
    parser.add_argument("--experiment-label", default=DEFAULT_LABEL)
    parser.add_argument("--bootstrap-replicates", type=int, default=20_000)
    parser.add_argument("--permutation-replicates", type=int, default=100_000)
    parser.add_argument("--analysis-seed", type=int, default=2718)
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--expected-pair-count", type=int)
    return parser.parse_args()


def process_peak_rss_gib() -> float:
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    bytes_used = value if sys.platform == "darwin" else value * 1024.0
    return bytes_used / (1024.0**3)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def load_public_nulls(path: Path) -> dict[str, str]:
    rows = load_jsonl(path)
    nulls = {str(row["prompt_id"]): str(row["public_null_dna"]) for row in rows}
    if len(nulls) != len(rows):
        raise ValueError("cohort JSONL contains duplicate prompts")
    if any(len(dna) != 3072 or set(dna) - set("ACGT") for dna in nulls.values()):
        raise ValueError("cohort JSONL does not contain canonical 3,072-base public nulls")
    return nulls


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to replace completed shard: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def shard_name(case_id: str, draw_id: int) -> str:
    return f"{case_id}__draw_{draw_id:02d}.json"


def validate_shard(
    shard: dict[str, Any],
    *,
    case_id: str,
    draw_id: int,
    split: str,
    token_lengths: tuple[int, ...],
) -> None:
    expected = {
        "complete": True,
        "case_id": case_id,
        "draw_id": draw_id,
        "prompt_split": split,
        "token_lengths": list(token_lengths),
    }
    for field, value in expected.items():
        if shard.get(field) != value:
            raise ValueError(f"detection shard has inconsistent {field}")
    trials = shard.get("trials")
    if not isinstance(trials, list):
        raise ValueError("detection shard has no trial rows")
    expected_families = {PRIMARY_NULL} if split == "calibration" else set(EVALUATION_FAMILIES)
    if {str(row["family"]) for row in trials} != expected_families:
        raise ValueError("detection shard has wrong null/positive families")
    for family in expected_families:
        lengths = {int(row["token_length"]) for row in trials if row["family"] == family}
        if lengths != set(token_lengths):
            raise ValueError("detection shard does not score every declared length")


def cluster_rate_interval(
    trials: list[dict[str, Any]],
    threshold: float,
    *,
    replicates: int,
    seed: int,
) -> dict[str, float | int]:
    by_prompt: dict[str, list[float]] = {}
    for row in trials:
        by_prompt.setdefault(str(row["case_id"]), []).append(
            float(float(row["statistic"]) > threshold)
        )
    values = {case_id: tuple(rows) for case_id, rows in by_prompt.items()}
    lower, upper = cluster_bootstrap_interval(values, replicates=replicates, seed=seed)
    mean = statistics.fmean(value for rows in values.values() for value in rows)
    return {
        "rate": mean,
        "lower": lower,
        "upper": upper,
        "confidence_level": 0.95,
        "method": "prompt-cluster percentile bootstrap",
        "replicates": replicates,
        "seed": seed,
        "prompts": len(values),
        "trials": sum(len(rows) for rows in values.values()),
    }


def paired_decisions(
    positives: list[dict[str, Any]],
    ordinary: list[dict[str, Any]],
    threshold: float,
    *,
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    positive_by_id = {
        (str(row["case_id"]), int(row["draw_id"])): float(row["statistic"]) > threshold
        for row in positives
    }
    ordinary_by_id = {
        (str(row["case_id"]), int(row["draw_id"])): float(row["statistic"]) > threshold
        for row in ordinary
    }
    if set(positive_by_id) != set(ordinary_by_id):
        raise ValueError("binary decisions are not matched")
    identities = sorted(positive_by_id)
    cluster_differences: dict[str, list[float]] = {}
    for case_id, draw_id in identities:
        cluster_differences.setdefault(case_id, []).append(
            float(positive_by_id[(case_id, draw_id)]) - float(ordinary_by_id[(case_id, draw_id)])
        )
    return {
        "cluster_sign_flip_p_value": cluster_sign_flip_test(
            cluster_differences,
            replicates=replicates,
            seed=seed,
        ),
        "cluster_unit": "case_id",
        "exact_mcnemar_pair_level_secondary": exact_mcnemar_p_value(
            [positive_by_id[identity] for identity in identities],
            [ordinary_by_id[identity] for identity in identities],
        ),
    }


def finalize(
    *,
    args: argparse.Namespace,
    all_case_ids: tuple[str, ...],
    selected_ids: set[str],
    draw_indices: tuple[int, ...],
    split: dict[str, str],
    shards_dir: Path,
    split_path: Path,
    input_artifacts: list[dict[str, str]],
) -> dict[str, Any]:
    expected_pairs = args.expected_pair_count or len(selected_ids) * len(draw_indices)
    paths = sorted(shards_dir.glob("*.json"))
    if len(paths) != expected_pairs:
        raise ValueError(f"found {len(paths)} detection shards, expected {expected_pairs}")
    shards: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    token_lengths = tuple(sorted(set(args.token_lengths)))
    for path in paths:
        shard = json.loads(path.read_text(encoding="utf-8"))
        identity = (str(shard["case_id"]), int(shard["draw_id"]))
        if identity in seen:
            raise ValueError("duplicate detection shard identity")
        seen.add(identity)
        if identity[0] not in selected_ids or identity[1] not in draw_indices:
            raise ValueError("detection shard lies outside the selected corpus")
        validate_shard(
            shard,
            case_id=identity[0],
            draw_id=identity[1],
            split=split[identity[0]],
            token_lengths=token_lengths,
        )
        shards.append(shard)
    calibration_rows = [
        row for shard in shards if shard["prompt_split"] == "calibration" for row in shard["trials"]
    ]
    evaluation_rows = [
        row for shard in shards if shard["prompt_split"] == "evaluation" for row in shard["trials"]
    ]
    detection_dir = args.output_root / "detection"
    calibration_path = detection_dir / "calibration_trials.parquet"
    evaluation_path = detection_dir / "evaluation_trials.parquet"
    summary_path = detection_dir / "detection_summary.json"
    try:
        import pandas as pd
        from sklearn.metrics import auc, precision_recall_curve, roc_curve
    except ImportError as error:
        raise RuntimeError("install the optional 'analysis' dependencies first") from error
    for path in (calibration_path, evaluation_path):
        if path.exists():
            raise FileExistsError(f"refusing to replace existing output: {path}")
    pd.DataFrame(calibration_rows).sort_values(["token_length", "case_id", "draw_id"]).to_parquet(
        calibration_path, index=False
    )
    pd.DataFrame(evaluation_rows).sort_values(
        ["token_length", "family", "case_id", "draw_id"]
    ).to_parquet(evaluation_path, index=False)
    lengths_summary: list[dict[str, Any]] = []
    score_p_values: dict[str, float] = {}
    for length in token_lengths:
        calibration = [
            row
            for row in calibration_rows
            if int(row["token_length"]) == length and row["family"] == PRIMARY_NULL
        ]
        null_scores = [float(row["statistic"]) for row in calibration]
        if args.threshold_source == "analytic":
            threshold = analytic_normal_threshold(null_scores, args.target_fpr)
        else:
            threshold = calibrate_threshold(null_scores, args.target_fpr)
        grouped = {
            family: [
                row
                for row in evaluation_rows
                if int(row["token_length"]) == length and row["family"] == family
            ]
            for family in EVALUATION_FAMILIES
        }
        positives = grouped[POSITIVE]
        primary = grouped[PRIMARY_NULL]
        if not positives or len(positives) != len(primary):
            raise ValueError("held-out positive and primary-null rows are not matched")
        # The analytic threshold is fixed without looking at any score.  It is
        # therefore legitimate—and substantially more informative—to use the
        # corresponding-key ordinary rows from every prompt as a goodness-of-fit
        # check.  For the optional empirical threshold, retain a genuinely
        # held-out check because its calibration rows selected the threshold.
        fit_check_rows = (
            calibration + primary if threshold.source == "analytic_standard_normal" else primary
        )
        fit_check_scores = [float(row["statistic"]) for row in fit_check_rows]
        exact_fit_probabilities = [
            binomial_standardized_exceedance_probability(int(row["g_total"]), threshold.threshold)
            for row in fit_check_rows
        ]
        exact_fit_rate = statistics.fmean(exact_fit_probabilities)
        fit_check_rate = cluster_rate_interval(
            fit_check_rows,
            threshold.threshold,
            replicates=args.bootstrap_replicates,
            seed=public_replay_seed("detection-null-fit", str(length), str(args.analysis_seed)),
        )
        positive_scores = [float(row["statistic"]) for row in positives]
        primary_scores = [float(row["statistic"]) for row in primary]
        positive_rate = cluster_rate_interval(
            positives,
            threshold.threshold,
            replicates=args.bootstrap_replicates,
            seed=public_replay_seed("detection-tpr", str(length), str(args.analysis_seed)),
        )
        null_rates = {
            family: cluster_rate_interval(
                rows,
                threshold.threshold,
                replicates=args.bootstrap_replicates,
                seed=public_replay_seed(
                    "detection-fpr", family, str(length), str(args.analysis_seed)
                ),
            )
            for family, rows in grouped.items()
            if family != POSITIVE
        }
        primary_by_id = {
            (str(row["case_id"]), int(row["draw_id"])): float(row["statistic"]) for row in primary
        }
        paired_scores: dict[str, list[float]] = {}
        for row in positives:
            identity = (str(row["case_id"]), int(row["draw_id"]))
            paired_scores.setdefault(identity[0], []).append(
                float(row["statistic"]) - primary_by_id[identity]
            )
        score_test = paired_cluster_summary(
            paired_scores,
            bootstrap_replicates=args.bootstrap_replicates,
            permutation_replicates=args.permutation_replicates,
            seed=public_replay_seed("detection-score", str(length), str(args.analysis_seed)),
        )
        score_p_values[str(length)] = score_test.p_value
        labels = [1] * len(positive_scores) + [0] * len(primary_scores)
        scores = positive_scores + primary_scores
        fpr, tpr, roc_thresholds = roc_curve(labels, scores)
        precision, recall, pr_thresholds = precision_recall_curve(labels, scores)
        empirical_reference = (
            fit_check_scores if threshold.source == "analytic_standard_normal" else null_scores
        )
        empirical_values = [
            empirical_p_value(score, empirical_reference) for score in positive_scores
        ]
        lengths_summary.append(
            {
                "token_length": length,
                "base_length": length * 6,
                "calibration": {
                    "family": PRIMARY_NULL,
                    "prompt_count": len({str(row["case_id"]) for row in calibration}),
                    "trials": threshold.null_trials,
                    "target_false_positive_rate": threshold.target_false_positive_rate,
                    "attainable_false_positive_rate": threshold.attainable_false_positive_rate,
                    "target_is_attainable": threshold.is_attainable,
                    "achieved_false_positive_rate": threshold.achieved_false_positive_rate,
                    "threshold": threshold.threshold,
                    "source": threshold.source,
                    "calibration_exceedance_is_fit_check": (
                        threshold.source == "analytic_standard_normal"
                    ),
                },
                "empirical_null_fit_check": {
                    "family": PRIMARY_NULL,
                    "prompt_count": len({str(row["case_id"]) for row in fit_check_rows}),
                    "includes_calibration_and_evaluation_prompts": (
                        threshold.source == "analytic_standard_normal"
                    ),
                    "nominal_target_rate": args.target_fpr,
                    "exact_binomial_expected_rate": exact_fit_rate,
                    "exact_binomial_expected_exceedances": exact_fit_rate * len(fit_check_rows),
                    "exact_binomial_probability_range": {
                        "minimum": min(exact_fit_probabilities),
                        "maximum": max(exact_fit_probabilities),
                    },
                    **fit_check_rate,
                    "statistic": numeric_summary(fit_check_scores),
                },
                "positive": {
                    **positive_rate,
                    "statistic": numeric_summary(positive_scores),
                    "empirical_p_value": {
                        "minimum": min(empirical_values),
                        "median": statistics.median(empirical_values),
                        "maximum": max(empirical_values),
                        "null_reference_trials": len(empirical_reference),
                    },
                },
                "null_families": {
                    family: {
                        **null_rates[family],
                        "statistic": numeric_summary(
                            float(row["statistic"]) for row in grouped[family]
                        ),
                    }
                    for family in null_rates
                },
                "separation": {
                    "roc_auc": float(auc(fpr, tpr)),
                    "roc": {
                        "false_positive_rate": fpr.tolist(),
                        "true_positive_rate": tpr.tolist(),
                        "thresholds": [
                            float(value) if math.isfinite(float(value)) else None
                            for value in roc_thresholds
                        ],
                    },
                    "precision_recall": {
                        "precision": precision.tolist(),
                        "recall": recall.tolist(),
                        "thresholds": pr_thresholds.tolist(),
                    },
                    "paired_score_watermarked_minus_ordinary": asdict(score_test),
                    "paired_binary_decision": paired_decisions(
                        positives,
                        primary,
                        threshold.threshold,
                        replicates=args.permutation_replicates,
                        seed=public_replay_seed(
                            "detection-binary", str(length), str(args.analysis_seed)
                        ),
                    ),
                },
            }
        )
    adjusted = benjamini_hochberg(score_p_values)
    for entry in lengths_summary:
        entry["separation"]["paired_score_watermarked_minus_ordinary"][
            "benjamini_hochberg_p_value_across_lengths"
        ] = adjusted[str(entry["token_length"])]
    summary = {
        "schema_version": 1,
        "classification": "validation_artifact_not_admitted_evidence",
        "complete": True,
        "experiment_id": "generator_synthid_validation_v1",
        "question": "held-out clean watermark detection",
        "policy_id": "G_tok",
        "model_id": "GenerTeam/GENERator-v2-eukaryote-1.2b-base",
        "revision": "c41b0018da9ee13b9e96ee54647de8da381ccd72",
        "prompt_split": {
            "path": str(split_path),
            "sha256": sha256_file(str(split_path)),
            "rule": "SHA-256 rank of frozen split label and case_id",
            "calibration_prompts": sum(value == "calibration" for value in split.values()),
            "evaluation_prompts": sum(value == "evaluation" for value in split.values()),
            "all_draws_stay_with_prompt": True,
        },
        "detector": {
            "score": "standardized mean binary g-value",
            "orientation": "forward",
            "phase": 0,
            "windows": "full evaluated prefix only",
            "offset_search": False,
            "hypotheses_searched": 1,
            "tournament_depth": args.tournament_depth,
            "context_tokens": args.context_tokens,
            "context_history_size": args.context_history_size,
            "repeated_contexts_masked": True,
        },
        "decision_rule": "statistic > frozen threshold",
        "threshold_source": (
            "analytic standard-normal quantile of the Binomial mean-g null"
            if args.threshold_source == "analytic"
            else "calibration ordinary GENERATOR plus corresponding draw key only"
        ),
        "null_families_pooled": False,
        "draw_indices": list(draw_indices),
        "statistical_cluster": "case_id",
        "lengths": lengths_summary,
        "inputs": input_artifacts,
        "artifacts": {
            "calibration_trials": {
                "path": str(calibration_path),
                "sha256": sha256_file(str(calibration_path)),
            },
            "evaluation_trials": {
                "path": str(evaluation_path),
                "sha256": sha256_file(str(evaluation_path)),
            },
        },
        "boundary": (
            "Clean, known-forward, phase-zero detection only. There is no orientation, phase, "
            "window, or key-offset search. Analytic thresholds do not use prompt scores; empirical "
            "fit checks may therefore use ordinary corresponding-key scores from all prompts. "
            "Detection and null-family rates use the disjoint evaluation prompts only."
        ),
    }
    serialized = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if summary_path.exists() and summary_path.read_text(encoding="utf-8") != serialized:
        raise FileExistsError(f"refusing to replace different output: {summary_path}")
    if not summary_path.exists():
        summary_path.write_text(serialized, encoding="utf-8")
    return {
        "summary": str(summary_path),
        "summary_sha256": sha256_file(str(summary_path)),
        "calibration_trials": len(calibration_rows),
        "evaluation_trials": len(evaluation_rows),
    }


def main() -> int:
    args = parse_args()
    token_lengths = tuple(sorted(set(int(value) for value in args.token_lengths)))
    if any(length < 16 for length in token_lengths):
        raise ValueError("token lengths must respect the detector's 16-token minimum")
    if not 0.0 < args.target_fpr < 1.0:
        raise ValueError("target-fpr must lie in (0, 1)")
    draw_indices = tuple(sorted(set(args.draw_index or range(2))))
    if any(draw not in range(2) for draw in draw_indices):
        raise ValueError("draw indices must lie in 0..1")
    cases = load_context_cases_jsonl(args.cohort_jsonl)
    all_case_ids = tuple(case.case_id for case in cases)
    selected_ids = set(args.case_id or all_case_ids)
    if not selected_ids <= set(all_case_ids):
        raise ValueError("an unknown case-id was requested")
    split = deterministic_prompt_split(
        all_case_ids,
        calibration_prompts=args.calibration_prompts,
    )
    selected_splits = {split[case_id] for case_id in selected_ids}
    if args.finalize and selected_splits != {"calibration", "evaluation"}:
        raise ValueError("final detection analysis needs selected prompts in both split partitions")
    public_nulls = load_public_nulls(args.cohort_jsonl)
    records: list[dict[str, Any]] = []
    input_artifacts: list[dict[str, str]] = []
    for draw_id in draw_indices:
        path = args.output_root / "generation" / f"draw_{draw_id:02d}_sequences.jsonl"
        if not path.is_file():
            raise FileNotFoundError(f"missing finalized generation draw: {path}")
        input_artifacts.append({"path": str(path), "sha256": sha256_file(str(path))})
        records.extend(
            record for record in load_jsonl(path) if str(record["case_id"]) in selected_ids
        )
    expected_records = len(selected_ids) * len(draw_indices) * 2
    if len(records) != expected_records or len({sequence_identity(row) for row in records}) != len(
        records
    ):
        raise ValueError("selected generation corpus is incomplete or duplicated")
    by_identity = {
        (str(row["case_id"]), int(row["draw_id"]), str(row["scheme"])): row for row in records
    }
    detection_dir = args.output_root / "detection"
    shards_dir = detection_dir / "score_shards"
    sessions_dir = detection_dir / "sessions"
    split_path = detection_dir / "prompt_split.json"
    detection_dir.mkdir(parents=True, exist_ok=True)
    selected_split_record = {
        "schema_version": 1,
        "label": CALIBRATION_SPLIT_LABEL,
        "assignment_rule": (
            "rank sha256(label, case_id); first "
            f"{args.calibration_prompts} calibration, rest evaluation"
        ),
        "calibration_prompts": args.calibration_prompts,
        "assignments": split,
    }
    split_text = json.dumps(selected_split_record, indent=2, sort_keys=True) + "\n"
    if split_path.exists() and split_path.read_text(encoding="utf-8") != split_text:
        raise FileExistsError(f"refusing to replace different split: {split_path}")
    if not split_path.exists():
        split_path.write_text(split_text, encoding="utf-8")
    shards_dir.mkdir(parents=True, exist_ok=True)
    pending: list[tuple[str, int]] = []
    for case_id in sorted(selected_ids):
        for draw_id in draw_indices:
            path = shards_dir / shard_name(case_id, draw_id)
            if path.exists():
                validate_shard(
                    json.loads(path.read_text(encoding="utf-8")),
                    case_id=case_id,
                    draw_id=draw_id,
                    split=split[case_id],
                    token_lengths=token_lengths,
                )
            else:
                pending.append((case_id, draw_id))
    if pending:
        run_started = time.perf_counter()
        stream_domain = f"{args.experiment_label}/{cases[0].cohort_id}/G_tok"
        keyed_tournaments: dict[tuple[str, int], KeyedTournament] = {}

        def keyed(kind: str, index: int) -> KeyedTournament:
            identity = (kind, index)
            cached = keyed_tournaments.get(identity)
            if cached is None:
                key = fixture_key(index) if kind == "fixture" else null_key(index)
                cached = KeyedTournament(
                    key=key,
                    domain=stream_domain,
                    depth=args.tournament_depth,
                    context_tokens=args.context_tokens,
                    context_history_size=args.context_history_size,
                )
                keyed_tournaments[identity] = cached
            return cached

        def score_family(
            dna: str,
            *,
            family: str,
            case_id: str,
            draw_id: int,
            key_kind: str,
            key_index: int,
        ) -> list[dict[str, Any]]:
            tournament = keyed(key_kind, key_index)
            rows: list[dict[str, Any]] = []
            for length in token_lengths:
                tokens = tokenize_fixed(dna[: length * 6], phase=0)
                result = score_synthid_tokens(tokens, tournament)
                rows.append(
                    {
                        "family": family,
                        "case_id": case_id,
                        "draw_id": draw_id,
                        "key_kind": key_kind,
                        "key_index": key_index,
                        "token_length": length,
                        "base_length": length * 6,
                        "statistic": result.statistic,
                        "mean_g_value": result.mean_g_value,
                        "g_ones": result.g_ones,
                        "g_total": result.g_total,
                        "scored_tokens": result.scored_tokens,
                        "repeated_contexts": result.repeated_contexts,
                        "orientation": "forward",
                        "phase": 0,
                        "hypotheses_searched": 1,
                    }
                )
            return rows

        for completed, (case_id, draw_id) in enumerate(pending, start=1):
            watermarked = str(by_identity[(case_id, draw_id, SYNTHID_SCHEME)]["generated_dna"])
            ordinary = str(by_identity[(case_id, draw_id, ORDINARY_SCHEME)]["generated_dna"])
            rows = score_family(
                ordinary,
                family=PRIMARY_NULL,
                case_id=case_id,
                draw_id=draw_id,
                key_kind="fixture",
                key_index=draw_id,
            )
            if split[case_id] == "evaluation":
                rows.extend(
                    score_family(
                        watermarked,
                        family=POSITIVE,
                        case_id=case_id,
                        draw_id=draw_id,
                        key_kind="fixture",
                        key_index=draw_id,
                    )
                )
                rows.extend(
                    score_family(
                        watermarked,
                        family=WRONG_KEY,
                        case_id=case_id,
                        draw_id=draw_id,
                        key_kind="fixture",
                        key_index=(draw_id + 1) % 2,
                    )
                )
                rows.extend(
                    score_family(
                        ordinary,
                        family=ORDINARY_INDEPENDENT,
                        case_id=case_id,
                        draw_id=draw_id,
                        key_kind="null",
                        key_index=draw_id,
                    )
                )
                rows.extend(
                    score_family(
                        public_nulls[case_id],
                        family=PUBLIC_DNA,
                        case_id=case_id,
                        draw_id=draw_id,
                        key_kind="null",
                        key_index=4 + draw_id,
                    )
                )
            shard = {
                "schema_version": 1,
                "classification": "validation_artifact_not_admitted_evidence",
                "complete": True,
                "policy_id": "G_tok",
                "case_id": case_id,
                "draw_id": draw_id,
                "prompt_split": split[case_id],
                "token_lengths": list(token_lengths),
                "trials": rows,
            }
            atomic_write_json(shards_dir / shard_name(case_id, draw_id), shard)
            print(
                json.dumps(
                    {
                        "case_id": case_id,
                        "draw_id": draw_id,
                        "split": split[case_id],
                        "completed_in_session": completed,
                        "pending_in_session": len(pending) - completed,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        session = {
            "schema_version": 1,
            "pair_count": len(pending),
            "wall_seconds": time.perf_counter() - run_started,
            "process_peak_rss_gib": process_peak_rss_gib(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cached_key_streams": len(keyed_tournaments),
            "model_forward_calls": 0,
        }
        sessions_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(
            sessions_dir / f"session_{len(tuple(sessions_dir.glob('*.json'))):03d}.json",
            session,
        )
    result: dict[str, Any] = {
        "selected_pairs": len(selected_ids) * len(draw_indices),
        "scored_now": len(pending),
        "resumed_pairs": len(selected_ids) * len(draw_indices) - len(pending),
        "score_shards": str(shards_dir),
    }
    if args.finalize:
        result["finalized"] = finalize(
            args=args,
            all_case_ids=all_case_ids,
            selected_ids=selected_ids,
            draw_indices=draw_indices,
            split=split,
            shards_dir=shards_dir,
            split_path=split_path,
            input_artifacts=input_artifacts,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
