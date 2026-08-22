#!/usr/bin/env python3
"""Run the E4 clean-detection pilot. Model-free: it loads no weights at all.

Reads a generated sequences file, repeats the identical declared search for every
positive and null trial, calibrates a threshold from pooled nulls, and reports
detection rate per evaluated length with a prompt-cluster bootstrap.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.cluster_analysis import analyze_prompt_clusters  # noqa: E402
from genomic_watermarks.detector.search import (  # noqa: E402
    DetectorConfig,
    PartitionCache,
    calibrate_threshold,
    detect,
    detection_rate,
    empirical_p_value,
)
from genomic_watermarks.dna import KMER_SIZE, canonical_kmers  # noqa: E402
from genomic_watermarks.pilot import (  # noqa: E402
    cohort_case_digest,
    load_context_cases_jsonl,
    numeric_summary,
)
from genomic_watermarks.watermark import (  # noqa: E402
    ORDINARY_SCHEME,
    PARTITION_MC_SCHEME,
    KeyedPartitionStream,
)

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl"
PUBLIC_FIXTURE_KEY = b"genomic-sampling-watermarks/public-generation-fixture/v1"
NULL_KEY_LABEL = "genomic-sampling-watermarks/public-null-key/v1"
NULL_FAMILIES = ("wrong_key_watermarked", "any_key_ordinary", "any_key_public_dna")
POOLED_FAMILIES = ("wrong_key_watermarked", "any_key_ordinary")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequences", type=Path, required=True)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--cohort-manifest", type=Path)
    parser.add_argument("--token-lengths", type=int, nargs="+", default=(64, 128, 256, 512))
    parser.add_argument("--stream-offsets", type=int, default=8, help="offsets 0..n-1 are searched")
    parser.add_argument("--null-keys", type=int, default=20)
    parser.add_argument("--target-fpr", type=float, default=0.01)
    parser.add_argument("--bootstrap-replicates", type=int, default=20_000)
    parser.add_argument("--bootstrap-seed", type=int, default=2718)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def null_key(index: int) -> bytes:
    """Return a published non-secret null key derived from a public label."""

    return hashlib.sha256(f"{NULL_KEY_LABEL}/{index:04d}".encode()).digest()


def cluster_bootstrap(
    values_by_cluster: dict[str, float],
    *,
    replicates: int,
    seed: int,
) -> dict[str, float]:
    """Equal-weight prompt-cluster percentile bootstrap of a per-prompt indicator."""

    analysis = analyze_prompt_clusters(
        {case_id: (value,) for case_id, value in values_by_cluster.items()},
        bootstrap_replicates=replicates,
        bootstrap_seed=seed,
    )
    return {
        "mean": analysis.overall_mean,
        "lower": analysis.interval_lower,
        "upper": analysis.interval_upper,
        "width": analysis.interval_width,
        "clusters": float(len(values_by_cluster)),
        "confidence_level": 0.95,
        "replicates": float(replicates),
        "seed": float(seed),
    }


def load_sequences(path: Path) -> tuple[dict[str, Any], ...]:
    records = tuple(
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    )
    if not records:
        raise ValueError("sequences file is empty")
    policies = {record["policy_id"] for record in records}
    labels = {record["experiment_label"] for record in records}
    cohorts = {record["cohort_id"] for record in records}
    if len(policies) != 1 or len(labels) != 1 or len(cohorts) != 1:
        raise ValueError("sequences file must hold one policy, label, and cohort")
    return records


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to replace existing output: {args.output}")
    if args.stream_offsets <= 0:
        raise ValueError("stream-offsets must be positive")
    if args.null_keys <= 0:
        raise ValueError("null-keys must be positive")
    if not 0.0 < args.target_fpr < 1.0:
        raise ValueError("target-fpr must lie in (0, 1)")
    token_lengths = tuple(sorted(set(int(value) for value in args.token_lengths)))
    if any(length <= 0 for length in token_lengths):
        raise ValueError("token lengths must be positive")

    records = load_sequences(args.sequences)
    policy_id = records[0]["policy_id"]
    experiment_label = records[0]["experiment_label"]
    cohort_id = records[0]["cohort_id"]
    cohort_bytes = args.cohort_jsonl.read_bytes()
    cases = load_context_cases_jsonl(args.cohort_jsonl)
    cases_by_id = {case.case_id: case for case in cases}

    watermarked = {
        record["case_id"]: record["generated_dna"]
        for record in records
        if record["scheme"] == PARTITION_MC_SCHEME
    }
    ordinary = {
        record["case_id"]: record["generated_dna"]
        for record in records
        if record["scheme"] == ORDINARY_SCHEME
    }
    if not watermarked or set(watermarked) != set(ordinary):
        raise ValueError("both arms must cover the same prompts")
    case_ids = tuple(watermarked)
    missing = [case_id for case_id in case_ids if case_id not in cases_by_id]
    if missing:
        raise ValueError(f"sequences reference unknown prompt(s): {', '.join(missing)}")
    offsets = tuple(range(args.stream_offsets))
    generated_tokens = min(len(dna) // KMER_SIZE for dna in watermarked.values())
    if max(token_lengths) > generated_tokens:
        raise ValueError("an evaluated length exceeds the generated length")

    stream_domain = f"{experiment_label}/{cohort_id}/{policy_id}"
    config = DetectorConfig(stream_offsets=offsets)
    support = canonical_kmers()

    run_started = time.perf_counter()
    trials: list[dict[str, Any]] = []
    # A keyed partition depends on the key, the domain, and the stream position, never on the
    # observed DNA. One cache per key therefore serves every sequence and length.
    streams: dict[bytes, tuple[KeyedPartitionStream, PartitionCache]] = {}

    def keyed(key: bytes) -> tuple[KeyedPartitionStream, PartitionCache]:
        cached = streams.get(key)
        if cached is None:
            stream = KeyedPartitionStream(key=key, domain=stream_domain)
            cached = (stream, PartitionCache(stream, support))
            streams[key] = cached
        return cached

    def score_all_lengths(
        dna: str,
        key: bytes,
        *,
        family: str,
        case_id: str,
        key_index: int | None,
    ) -> None:
        stream, cache = keyed(key)
        available = len(dna) // KMER_SIZE
        for length in token_lengths:
            if length > available:
                continue
            prefix = dna[: length * KMER_SIZE]
            result = detect(prefix, support, stream, config, cache=cache)
            trials.append(
                {
                    "family": family,
                    "case_id": case_id,
                    "key_index": key_index,
                    "token_length": length,
                    "base_length": length * KMER_SIZE,
                    "statistic": result.statistic,
                    "matches": result.matches,
                    "total": result.total,
                    "orientation": result.hypothesis.orientation,
                    "phase": result.hypothesis.phase,
                    "stream_offset": result.hypothesis.stream_offset,
                    "hypotheses_searched": result.hypotheses_searched,
                }
            )

    for case_id in case_ids:
        score_all_lengths(
            watermarked[case_id],
            PUBLIC_FIXTURE_KEY,
            family="positive",
            case_id=case_id,
            key_index=None,
        )
    for index in range(args.null_keys):
        key = null_key(index)
        for case_id in case_ids:
            score_all_lengths(
                watermarked[case_id],
                key,
                family="wrong_key_watermarked",
                case_id=case_id,
                key_index=index,
            )
            score_all_lengths(
                ordinary[case_id],
                key,
                family="any_key_ordinary",
                case_id=case_id,
                key_index=index,
            )
            score_all_lengths(
                cases_by_id[case_id].sequence,
                key,
                family="any_key_public_dna",
                case_id=case_id,
                key_index=index,
            )

    by_length: dict[int, dict[str, list[dict[str, Any]]]] = {
        length: {family: [] for family in ("positive", *NULL_FAMILIES)} for length in token_lengths
    }
    for trial in trials:
        by_length[trial["token_length"]][trial["family"]].append(trial)

    lengths_report: list[dict[str, Any]] = []
    for length in token_lengths:
        groups = by_length[length]
        pooled = [trial["statistic"] for family in POOLED_FAMILIES for trial in groups[family]]
        if not pooled:
            continue
        calibration = calibrate_threshold(pooled, args.target_fpr)
        positives = [trial["statistic"] for trial in groups["positive"]]
        detected_by_case = {
            trial["case_id"]: float(trial["statistic"] > calibration.threshold)
            for trial in groups["positive"]
        }
        family_rates = {
            family: (
                detection_rate(
                    [trial["statistic"] for trial in groups[family]], calibration.threshold
                )
                if groups[family]
                else None
            )
            for family in NULL_FAMILIES
        }
        lengths_report.append(
            {
                "token_length": length,
                "base_length": length * KMER_SIZE,
                "hypotheses_searched": groups["positive"][0]["hypotheses_searched"],
                "calibration": {
                    "pooled_null_families": list(POOLED_FAMILIES),
                    "pooled_null_trials": calibration.null_trials,
                    "target_false_positive_rate": calibration.target_false_positive_rate,
                    "achieved_false_positive_rate": calibration.achieved_false_positive_rate,
                    "attainable_false_positive_rate": calibration.attainable_false_positive_rate,
                    "target_is_attainable": calibration.is_attainable,
                    "threshold": calibration.threshold,
                },
                "positive": {
                    "trials": len(positives),
                    "detection_rate": detection_rate(positives, calibration.threshold),
                    "statistic": numeric_summary(positives),
                    "minimum_empirical_global_p_value": min(
                        empirical_p_value(value, pooled) for value in positives
                    ),
                    "maximum_empirical_global_p_value": max(
                        empirical_p_value(value, pooled) for value in positives
                    ),
                    "detection_rate_prompt_cluster_bootstrap": cluster_bootstrap(
                        detected_by_case,
                        replicates=args.bootstrap_replicates,
                        seed=args.bootstrap_seed,
                    ),
                },
                "null_families": {
                    family: {
                        "trials": len(groups[family]),
                        "exceedance_rate_at_threshold": family_rates[family],
                        "statistic": numeric_summary(trial["statistic"] for trial in groups[family])
                        if groups[family]
                        else None,
                    }
                    for family in NULL_FAMILIES
                },
                "separation": {
                    "minimum_positive_statistic": min(positives),
                    "maximum_pooled_null_statistic": max(pooled),
                    "positives_strictly_above_all_pooled_nulls": min(positives) > max(pooled),
                },
            }
        )

    report: dict[str, Any] = {
        "schema_version": 1,
        "classification": "engineering_pilot_not_paper_evidence",
        "complete": True,
        "policy_id": policy_id,
        "cohort_id": cohort_id,
        "experiment_label": experiment_label,
        "watermark_method": PARTITION_MC_SCHEME,
        "control_method": ORDINARY_SCHEME,
        "key_source": "public_fixture",
        "null_key_source": "public_fixture_labels",
        "null_keys": args.null_keys,
        "stream_domain": stream_domain,
        "case_count": len(case_ids),
        "case_ids": list(case_ids),
        "generated_tokens_per_case": generated_tokens,
        "token_lengths": list(token_lengths),
        "detector_search": config.describe(),
        "support_size": len(support),
        "sequences": {
            "path": str(args.sequences),
            "sha256": hashlib.sha256(args.sequences.read_bytes()).hexdigest(),
        },
        "cohort": {
            "prompts_path": str(args.cohort_jsonl),
            "prompts_file_sha256": hashlib.sha256(cohort_bytes).hexdigest(),
            "cohort_content_sha256": cohort_case_digest(cases),
            "manifest_path": str(args.cohort_manifest) if args.cohort_manifest else None,
            "manifest_sha256": (
                hashlib.sha256(args.cohort_manifest.read_bytes()).hexdigest()
                if args.cohort_manifest
                else None
            ),
        },
        "trial_count": len(trials),
        "cached_key_streams": len(streams),
        "trials": trials,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "wall_seconds": time.perf_counter() - run_started,
        "lengths": lengths_report,
        "boundary": (
            "Clean detection only, under a published fixture key. The threshold is calibrated "
            "by repeating the identical declared search on null trials; no nominal "
            "per-hypothesis tail is used. Edits, crops, reverse complementation, adaptive "
            "removal, and key reuse are separate experiments."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "policy_id": policy_id,
                "trial_count": len(trials),
                "wall_seconds": report["wall_seconds"],
                "lengths": [
                    {
                        "base_length": entry["base_length"],
                        "threshold": entry["calibration"]["threshold"],
                        "achieved_fpr": entry["calibration"]["achieved_false_positive_rate"],
                        "detection_rate": entry["positive"]["detection_rate"],
                        "separated": entry["separation"][
                            "positives_strictly_above_all_pooled_nulls"
                        ],
                    }
                    for entry in lengths_report
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
