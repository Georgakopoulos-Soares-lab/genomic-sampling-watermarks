#!/usr/bin/env python3
"""Run E7 stage 2: the windowed detector against an indel channel.

Model-free. For every trial it scores two declared searches on the *same* edited
sequence — the windowed search and the unwindowed comparator from stage 1 — so the
comparison is paired rather than across experiments. Each search is calibrated
separately, on nulls that went through the same edit process.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
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
    WindowedSearchConfig,
    calibrate_threshold,
    detect,
    detect_windowed,
    detection_rate,
    empirical_p_value,
)
from genomic_watermarks.dna import KMER_SIZE, canonical_kmers  # noqa: E402
from genomic_watermarks.edits import delete_bases, insert_bases  # noqa: E402
from genomic_watermarks.pilot import (  # noqa: E402
    cohort_case_digest,
    load_context_cases_jsonl,
    numeric_summary,
)
from genomic_watermarks.watermark import (  # noqa: E402
    ORDINARY_SCHEME,
    PARTITION_MC_SCHEME,
    KeyedPartitionStream,
    public_replay_seed,
)

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl"
PUBLIC_FIXTURE_KEY = b"genomic-sampling-watermarks/public-generation-fixture/v1"
NULL_KEY_LABEL = "genomic-sampling-watermarks/public-null-key/v1"
EDIT_CHANNELS = {"insertion": insert_bases, "deletion": delete_bases}
POOLED_FAMILIES = ("wrong_key_watermarked", "any_key_ordinary")
FAMILIES = ("positive", *POOLED_FAMILIES)
SEARCH_IDS = ("windowed", "unwindowed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequences", type=Path, required=True)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--cohort-manifest", type=Path)
    parser.add_argument("--edit", choices=tuple(EDIT_CHANNELS), required=True)
    parser.add_argument("--rates", type=float, nargs="+", required=True)
    parser.add_argument("--observed-bases", type=int, default=1536)
    parser.add_argument("--window-tokens", type=int, nargs="+", default=(32, 64, 128, 256))
    parser.add_argument(
        "--drift-radius",
        type=int,
        default=15,
        help="signed drift range searched, from -radius to +radius; insertions need negative drift",
    )
    parser.add_argument("--unwindowed-offsets", type=int, default=8)
    parser.add_argument("--null-keys", type=int, default=8)
    parser.add_argument("--positive-replicates", type=int, default=5)
    parser.add_argument("--target-fpr", type=float, default=0.01)
    parser.add_argument("--bootstrap-replicates", type=int, default=20_000)
    parser.add_argument("--bootstrap-seed", type=int, default=2718)
    parser.add_argument("--experiment-label", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def null_key(index: int) -> bytes:
    return hashlib.sha256(f"{NULL_KEY_LABEL}/{index:04d}".encode()).digest()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to replace existing output: {args.output}")
    if args.observed_bases <= 0 or args.observed_bases % KMER_SIZE:
        raise ValueError("observed-bases must be a positive multiple of six")
    if args.drift_radius < 0 or args.unwindowed_offsets <= 0:
        raise ValueError("drift radius must be non-negative and offset counts positive")
    if args.null_keys <= 0 or args.positive_replicates <= 0:
        raise ValueError("null-keys and positive-replicates must be positive")
    if not 0.0 < args.target_fpr < 1.0:
        raise ValueError("target-fpr must lie in (0, 1)")
    rates = tuple(sorted(set(round(float(rate), 6) for rate in args.rates)))
    if any(not 0.0 <= rate <= 1.0 for rate in rates):
        raise ValueError("rates must lie in [0, 1]")

    sequence_bytes = args.sequences.read_bytes()
    records = [
        json.loads(line) for line in sequence_bytes.decode("utf-8").splitlines() if line.strip()
    ]
    if not records:
        raise ValueError("sequences file is empty")
    if len({record["policy_id"] for record in records}) != 1:
        raise ValueError("sequences file must hold one policy")
    policy_id = records[0]["policy_id"]
    generation_label = records[0]["experiment_label"]
    cohort_id = records[0]["cohort_id"]
    watermarked = {
        r["case_id"]: r["generated_dna"] for r in records if r["scheme"] == PARTITION_MC_SCHEME
    }
    ordinary = {r["case_id"]: r["generated_dna"] for r in records if r["scheme"] == ORDINARY_SCHEME}
    if not watermarked or set(watermarked) != set(ordinary):
        raise ValueError("both arms must cover the same prompts")
    case_ids = tuple(watermarked)

    cohort_bytes = args.cohort_jsonl.read_bytes()
    cases = load_context_cases_jsonl(args.cohort_jsonl)
    known = {case.case_id for case in cases}
    missing = [case_id for case_id in case_ids if case_id not in known]
    if missing:
        raise ValueError(f"sequences reference unknown prompt(s): {', '.join(missing)}")

    stream_domain = f"{generation_label}/{cohort_id}/{policy_id}"
    windowed = WindowedSearchConfig(
        window_tokens=tuple(sorted(set(int(w) for w in args.window_tokens))),
        drift_offsets=tuple(range(-args.drift_radius, args.drift_radius + 1)),
    )
    unwindowed = DetectorConfig(stream_offsets=tuple(range(args.unwindowed_offsets)))
    support = canonical_kmers()

    run_started = time.perf_counter()
    trials: list[dict[str, Any]] = []
    streams: dict[bytes, tuple[KeyedPartitionStream, PartitionCache]] = {}

    def keyed(key: bytes) -> tuple[KeyedPartitionStream, PartitionCache]:
        cached = streams.get(key)
        if cached is None:
            stream = KeyedPartitionStream(key=key, domain=stream_domain)
            cached = (stream, PartitionCache(stream, support))
            streams[key] = cached
        return cached

    def edited(dna: str, *, rate: float, case_id: str, arm: str, replicate: int) -> str:
        if rate > 0.0:
            seed = public_replay_seed(
                args.experiment_label,
                policy_id,
                case_id,
                arm,
                args.edit,
                f"{rate:.6f}",
                f"replicate-{replicate}",
            )
            dna = EDIT_CHANNELS[args.edit](dna, rate, random.Random(seed))
        if len(dna) < args.observed_bases:
            raise ValueError("an edited sequence is shorter than the observed length")
        return dna[: args.observed_bases]

    def score(
        dna: str,
        key: bytes,
        *,
        family: str,
        case_id: str,
        rate: float,
        replicate: int,
        key_index: int | None,
    ) -> None:
        stream, cache = keyed(key)
        win = detect_windowed(dna, support, stream, windowed, cache=cache)
        flat = detect(dna, support, stream, unwindowed, cache=cache)
        for search_id, result, extra in (
            (
                "windowed",
                win,
                {
                    "window_tokens": win.hypothesis.window_tokens,
                    "window_start": win.hypothesis.window_start,
                    "drift": win.hypothesis.drift,
                },
            ),
            (
                "unwindowed",
                flat,
                {
                    "window_tokens": flat.hypothesis.window_tokens,
                    "window_start": flat.hypothesis.window_start,
                    "drift": flat.hypothesis.stream_offset,
                },
            ),
        ):
            trials.append(
                {
                    "family": family,
                    "case_id": case_id,
                    "edit_rate": rate,
                    "replicate": replicate,
                    "key_index": key_index,
                    "search_id": search_id,
                    "statistic": result.statistic,
                    "matches": result.matches,
                    "total": result.total,
                    "orientation": result.hypothesis.orientation,
                    "phase": result.hypothesis.phase,
                    "hypotheses_searched": result.hypotheses_searched,
                    **extra,
                }
            )

    for rate in rates:
        for case_id in case_ids:
            for replicate in range(args.positive_replicates):
                score(
                    edited(
                        watermarked[case_id],
                        rate=rate,
                        case_id=case_id,
                        arm=PARTITION_MC_SCHEME,
                        replicate=replicate,
                    ),
                    PUBLIC_FIXTURE_KEY,
                    family="positive",
                    case_id=case_id,
                    rate=rate,
                    replicate=replicate,
                    key_index=None,
                )
            null_wm = edited(
                watermarked[case_id],
                rate=rate,
                case_id=case_id,
                arm=PARTITION_MC_SCHEME,
                replicate=0,
            )
            null_or = edited(
                ordinary[case_id], rate=rate, case_id=case_id, arm=ORDINARY_SCHEME, replicate=0
            )
            for index in range(args.null_keys):
                key = null_key(index)
                score(
                    null_wm,
                    key,
                    family="wrong_key_watermarked",
                    case_id=case_id,
                    rate=rate,
                    replicate=0,
                    key_index=index,
                )
                score(
                    null_or,
                    key,
                    family="any_key_ordinary",
                    case_id=case_id,
                    rate=rate,
                    replicate=0,
                    key_index=index,
                )

    grouped: dict[tuple[float, str, str], list[dict[str, Any]]] = {
        (rate, search_id, family): []
        for rate in rates
        for search_id in SEARCH_IDS
        for family in FAMILIES
    }
    for row in trials:
        grouped[(row["edit_rate"], row["search_id"], row["family"])].append(row)

    conditions: list[dict[str, Any]] = []
    for rate in rates:
        for search_id in SEARCH_IDS:
            nulls = [
                float(row["statistic"])
                for family in POOLED_FAMILIES
                for row in grouped[(rate, search_id, family)]
            ]
            positive_rows = grouped[(rate, search_id, "positive")]
            positives = [float(row["statistic"]) for row in positive_rows]
            calibration = calibrate_threshold(nulls, args.target_fpr)
            by_cluster: dict[str, list[float]] = {case_id: [] for case_id in case_ids}
            for row in positive_rows:
                by_cluster[row["case_id"]].append(
                    float(float(row["statistic"]) > calibration.threshold)
                )
            cluster = analyze_prompt_clusters(
                {k: tuple(v) for k, v in by_cluster.items()},
                bootstrap_replicates=args.bootstrap_replicates,
                bootstrap_seed=args.bootstrap_seed,
            )
            detected = [
                row for row in positive_rows if float(row["statistic"]) > calibration.threshold
            ]
            conditions.append(
                {
                    "edit": args.edit,
                    "edit_rate": rate,
                    "search_id": search_id,
                    "observed_bases": args.observed_bases,
                    "hypotheses_searched": positive_rows[0]["hypotheses_searched"],
                    "calibration": {
                        "scope": "per rate and search, pooled N1 and N2",
                        "pooled_null_families": list(POOLED_FAMILIES),
                        "pooled_null_trials": calibration.null_trials,
                        "target_false_positive_rate": calibration.target_false_positive_rate,
                        "achieved_false_positive_rate": (calibration.achieved_false_positive_rate),
                        "attainable_false_positive_rate": (
                            calibration.attainable_false_positive_rate
                        ),
                        "threshold": calibration.threshold,
                    },
                    "positive": {
                        "trials": len(positives),
                        "detection_rate": detection_rate(positives, calibration.threshold),
                        "statistic": numeric_summary(positives),
                        "minimum_empirical_global_p_value": min(
                            empirical_p_value(value, nulls) for value in positives
                        ),
                        "detection_rate_prompt_cluster_bootstrap": {
                            "mean": cluster.overall_mean,
                            "lower": cluster.interval_lower,
                            "upper": cluster.interval_upper,
                            "clusters": float(len(by_cluster)),
                            "confidence_level": 0.95,
                            "replicates": float(args.bootstrap_replicates),
                            "seed": float(args.bootstrap_seed),
                        },
                        "recovered_window_tokens": sorted(
                            {int(row["window_tokens"]) for row in detected}
                        ),
                        "recovered_drift": sorted({int(row["drift"]) for row in detected}),
                        "detected_trials": len(detected),
                    },
                    "null_families": {
                        family: {
                            "trials": len(grouped[(rate, search_id, family)]),
                            "exceedance_rate_at_threshold": detection_rate(
                                [
                                    float(row["statistic"])
                                    for row in grouped[(rate, search_id, family)]
                                ],
                                calibration.threshold,
                            ),
                            "statistic": numeric_summary(
                                float(row["statistic"])
                                for row in grouped[(rate, search_id, family)]
                            ),
                        }
                        for family in POOLED_FAMILIES
                    },
                    "separation": {
                        "minimum_positive_statistic": min(positives),
                        "maximum_pooled_null_statistic": max(nulls),
                    },
                }
            )

    report: dict[str, Any] = {
        "schema_version": 1,
        "classification": "engineering_pilot_not_paper_evidence",
        "complete": True,
        "policy_id": policy_id,
        "cohort_id": cohort_id,
        "experiment_label": args.experiment_label,
        "generation_experiment_label": generation_label,
        "watermark_method": PARTITION_MC_SCHEME,
        "control_method": ORDINARY_SCHEME,
        "key_source": "public_fixture",
        "null_key_source": "public_fixture_labels",
        "null_keys": args.null_keys,
        "edit": args.edit,
        "edit_rates": list(rates),
        "positive_replicates_per_prompt": args.positive_replicates,
        "observed_bases": args.observed_bases,
        "paired_comparison": (
            "both searches score the identical edited sequence in the same process, so the "
            "comparison is paired; the windowed search includes the full-read window, so it "
            "contains the unwindowed search as a special case"
        ),
        "searches": {
            "windowed": {
                "search": windowed.describe(),
                "hypotheses": windowed.hypothesis_count(args.observed_bases),
            },
            "unwindowed": {
                "search": unwindowed.describe(),
                "hypotheses": 2 * KMER_SIZE * len(unwindowed.stream_offsets),
            },
        },
        "case_count": len(case_ids),
        "case_ids": list(case_ids),
        "support_size": len(support),
        "sequences": {
            "path": str(args.sequences),
            "sha256": hashlib.sha256(sequence_bytes).hexdigest(),
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
        "python": platform.python_version(),
        "platform": platform.platform(),
        "wall_seconds": time.perf_counter() - run_started,
        "conditions": conditions,
        "trials": trials,
        "boundary": (
            "One indel channel, one observed length, under a published fixture key. Thresholds "
            "are calibrated per rate and per search by repeating the identical declared search on "
            "nulls that went through the same edit process. The windowed search declares no "
            "absolute "
            "key-position sweep, so a watermarked fragment spliced at an unknown position inside a "
            "longer sequence is out of scope. No error-correcting or synchronization code is used."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {}
    for entry in conditions:
        summary.setdefault(f"r{entry['edit_rate']}", {})[entry["search_id"]] = entry["positive"][
            "detection_rate"
        ]
    print(
        json.dumps(
            {
                "output": str(args.output),
                "policy_id": policy_id,
                "edit": args.edit,
                "trial_count": len(trials),
                "wall_seconds": report["wall_seconds"],
                "detection_rate": summary,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
