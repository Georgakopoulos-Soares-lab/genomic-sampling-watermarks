#!/usr/bin/env python3
"""Compare released mean and weighted-mean SynthID scores on calibration prompts."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import statistics
import sys
from collections import deque
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.dna import tokenize_fixed  # noqa: E402
from genomic_watermarks.large_validation import fixture_key, sha256_file  # noqa: E402
from genomic_watermarks.synthid import (  # noqa: E402
    DEFAULT_CONTEXT_HISTORY_SIZE,
    DEFAULT_CONTEXT_TOKENS,
    DEFAULT_DEPTH,
    SYNTHID_SCHEME,
    KeyedTournament,
    _remember_context,
)
from genomic_watermarks.watermark import ORDINARY_SCHEME  # noqa: E402

PINNED_UPSTREAM_REVISION = "addb4a158143c7c6851a1308f78b89fceed59683"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--draw-index", type=int, action="append")
    parser.add_argument("--token-lengths", type=int, nargs="+", default=(64, 512))
    parser.add_argument("--tournament-depth", type=int, default=DEFAULT_DEPTH)
    parser.add_argument("--context-tokens", type=int, default=DEFAULT_CONTEXT_TOKENS)
    parser.add_argument("--context-history-size", type=int, default=DEFAULT_CONTEXT_HISTORY_SIZE)
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def layer_counts(
    tokens: tuple[str, ...], tournament: KeyedTournament
) -> tuple[tuple[int, ...], int]:
    history: deque[tuple[str, ...]] = deque()
    seen: set[tuple[str, ...]] = set()
    counts = [0] * tournament.depth
    scored = 0
    for index in range(tournament.context_tokens, len(tokens)):
        recent = tokens[index - tournament.context_tokens : index]
        if _remember_context(recent, history, seen, tournament.context_history_size):
            continue
        for layer, value in enumerate(tournament.g_values(recent, tokens[index])):
            counts[layer] += value
        scored += 1
    if scored <= 0:
        raise ValueError("all detector contexts were masked")
    return tuple(counts), scored


def score(counts: tuple[int, ...], scored: int, weights: tuple[float, ...]) -> float:
    return sum(count * weight for count, weight in zip(counts, weights, strict=True)) / (
        len(counts) * scored
    )


def detector_summary(
    watermarked: list[tuple[tuple[int, ...], int]],
    ordinary: list[tuple[tuple[int, ...], int]],
    weights: tuple[float, ...],
) -> dict[str, float]:
    watermarked_scores = [score(counts, scored, weights) for counts, scored in watermarked]
    ordinary_scores = [score(counts, scored, weights) for counts, scored in ordinary]
    ordinary_sd = statistics.stdev(ordinary_scores)
    if ordinary_sd <= 0.0:
        raise ValueError("ordinary detector scores have zero variance")
    watermarked_mean = statistics.fmean(watermarked_scores)
    ordinary_mean = statistics.fmean(ordinary_scores)
    return {
        "watermarked_mean": watermarked_mean,
        "ordinary_mean": ordinary_mean,
        "ordinary_standard_deviation": ordinary_sd,
        "separation_in_ordinary_standard_deviations": (watermarked_mean - ordinary_mean)
        / ordinary_sd,
    }


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"refusing to replace different detector comparison: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    args = parse_args()
    draw_indices = tuple(sorted(set(args.draw_index or (0, 1))))
    token_lengths = tuple(sorted(set(args.token_lengths)))
    if any(draw not in (0, 1) for draw in draw_indices):
        raise ValueError("draw indices must lie in 0..1")
    if any(length <= args.context_tokens for length in token_lengths):
        raise ValueError("token lengths must contain scored contexts")
    split_path = args.output_root / "detection" / "prompt_split.json"
    split_record = json.loads(split_path.read_text(encoding="utf-8"))
    split = {str(case_id): str(value) for case_id, value in split_record["assignments"].items()}
    calibration_ids = {case_id for case_id, value in split.items() if value == "calibration"}
    if len(calibration_ids) != 64:
        raise ValueError("detector comparison requires the frozen 64-prompt calibration split")

    rows: dict[tuple[str, int], list[tuple[tuple[int, ...], int]]] = {}
    input_artifacts: list[dict[str, str]] = [
        {"path": str(split_path), "sha256": sha256_file(str(split_path))}
    ]
    for draw_id in draw_indices:
        sequence_path = args.output_root / "generation" / f"draw_{draw_id:02d}_sequences.jsonl"
        input_artifacts.append(
            {"path": str(sequence_path), "sha256": sha256_file(str(sequence_path))}
        )
        records = [
            row for row in load_jsonl(sequence_path) if str(row["case_id"]) in calibration_ids
        ]
        domains = {str(row["stream_domain"]) for row in records}
        if len(records) != len(calibration_ids) * 2 or len(domains) != 1:
            raise ValueError(f"draw {draw_id} has incomplete calibration records")
        tournament = KeyedTournament(
            key=fixture_key(draw_id),
            domain=domains.pop(),
            depth=args.tournament_depth,
            context_tokens=args.context_tokens,
            context_history_size=args.context_history_size,
        )
        for record in records:
            dna = str(record["generated_dna"])
            for length in token_lengths:
                tokens = tokenize_fixed(dna[: length * 6])
                rows.setdefault((str(record["scheme"]), length), []).append(
                    layer_counts(tokens, tournament)
                )

    raw_weights = (
        (10.0,)
        if args.tournament_depth == 1
        else tuple(
            10.0 - 9.0 * layer / (args.tournament_depth - 1)
            for layer in range(args.tournament_depth)
        )
    )
    scale = args.tournament_depth / sum(raw_weights)
    weighted = tuple(value * scale for value in raw_weights)
    uniform = (1.0,) * args.tournament_depth
    lengths: list[dict[str, Any]] = []
    for length in token_lengths:
        watermarked = rows[(SYNTHID_SCHEME, length)]
        ordinary = rows[(ORDINARY_SCHEME, length)]
        if len(watermarked) != len(ordinary) or len(watermarked) != len(calibration_ids) * len(
            draw_indices
        ):
            raise ValueError(f"length {length} has incomplete detector arms")
        mean = detector_summary(watermarked, ordinary, uniform)
        weighted_mean = detector_summary(watermarked, ordinary, weighted)
        layer_profile = [
            statistics.fmean(counts[layer] / scored for counts, scored in watermarked)
            for layer in range(args.tournament_depth)
        ]
        lengths.append(
            {
                "token_length": length,
                "base_length": length * 6,
                "trials_per_arm": len(watermarked),
                "mean": mean,
                "upstream_default_weighted_mean": weighted_mean,
                "selected_detector": (
                    "mean"
                    if mean["separation_in_ordinary_standard_deviations"]
                    >= weighted_mean["separation_in_ordinary_standard_deviations"]
                    else "upstream_default_weighted_mean"
                ),
                "watermarked_layer_mean_g": {
                    "minimum": min(layer_profile),
                    "maximum": max(layer_profile),
                    "range": max(layer_profile) - min(layer_profile),
                    "values": layer_profile,
                },
            }
        )
    if {entry["selected_detector"] for entry in lengths} != {"mean"}:
        raise ValueError("the calibration-only comparison does not select the mean detector")

    output = args.output or args.output_root / "detection" / "detector_comparison.json"
    summary = {
        "schema_version": 1,
        "classification": "validation_artifact_not_admitted_evidence",
        "complete": True,
        "experiment_id": "carbon_synthid_validation_v1",
        "question": "mean versus released default weighted-mean detector",
        "selection_split": "calibration only",
        "calibration_prompts": len(calibration_ids),
        "draw_indices": list(draw_indices),
        "tournament_depth": args.tournament_depth,
        "upstream_revision": PINNED_UPSTREAM_REVISION,
        "upstream_default_weights": {
            "definition": "linear from 10 to 1, normalized to sum to depth",
            "values": list(weighted),
        },
        "lengths": lengths,
        "selected_detector": "mean",
        "inputs": input_artifacts,
        "command": shlex.join([sys.executable, *sys.argv]),
        "boundary": (
            "Detector selection uses only the frozen calibration prompts. Evaluation prompts are "
            "not scored or summarized, and no signal-matched weights are fitted."
        ),
    }
    atomic_write(output, summary)
    print(json.dumps({"output": str(output), "sha256": sha256_file(str(output))}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
