#!/usr/bin/env python3
"""Run an edit-robustness pilot with the unchanged declared detector search.

Model-free. Applies one edit channel at a grid of rates to the generated corpus,
repeats the identical search for positives and nulls, and calibrates a threshold
per rate and length. Prefixes are taken from the edited sequence, so every
evaluated length sees the same edit process.
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
    calibrate_threshold,
    detect,
    detection_rate,
    empirical_p_value,
)
from genomic_watermarks.dna import KMER_SIZE, canonical_kmers  # noqa: E402
from genomic_watermarks.edits import delete_bases, insert_bases, substitute_bases  # noqa: E402
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
EDIT_CHANNELS = {
    "substitution": substitute_bases,
    "insertion": insert_bases,
    "deletion": delete_bases,
}
POOLED_FAMILIES = ("wrong_key_watermarked", "any_key_ordinary")
FAMILIES = ("positive", *POOLED_FAMILIES)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequences", type=Path, required=True)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--cohort-manifest", type=Path)
    parser.add_argument("--edit", choices=tuple(EDIT_CHANNELS), required=True)
    parser.add_argument("--rates", type=float, nargs="+", required=True)
    parser.add_argument("--token-lengths", type=int, nargs="+", default=(64, 128, 256, 512))
    parser.add_argument("--stream-offsets", type=int, default=8)
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


def edited(
    dna: str,
    *,
    channel: str,
    rate: float,
    label: str,
    policy_id: str,
    case_id: str,
    arm: str,
    replicate: int,
) -> str:
    """Apply the declared edit channel with a public, reproducible seed."""

    if rate <= 0.0:
        return dna
    seed = public_replay_seed(
        label, policy_id, case_id, arm, channel, f"{rate:.6f}", f"replicate-{replicate}"
    )
    return EDIT_CHANNELS[channel](dna, rate, random.Random(seed))


def cluster_bootstrap(
    values_by_cluster: dict[str, list[float]],
    *,
    replicates: int,
    seed: int,
) -> dict[str, float]:
    analysis = analyze_prompt_clusters(
        {case_id: tuple(values) for case_id, values in values_by_cluster.items()},
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


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to replace existing output: {args.output}")
    if args.stream_offsets <= 0:
        raise ValueError("stream-offsets must be positive")
    if args.null_keys <= 0:
        raise ValueError("null-keys must be positive")
    if args.positive_replicates <= 0:
        raise ValueError("positive-replicates must be positive")
    if not 0.0 < args.target_fpr < 1.0:
        raise ValueError("target-fpr must lie in (0, 1)")
    rates = tuple(sorted(set(round(float(rate), 6) for rate in args.rates)))
    if any(not 0.0 <= rate <= 1.0 for rate in rates):
        raise ValueError("rates must lie in [0, 1]")
    token_lengths = tuple(sorted(set(int(value) for value in args.token_lengths)))
    if any(length <= 0 for length in token_lengths):
        raise ValueError("token lengths must be positive")

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

    cohort_bytes = args.cohort_jsonl.read_bytes()
    cases = load_context_cases_jsonl(args.cohort_jsonl)
    missing = [case_id for case_id in case_ids if case_id not in {c.case_id for c in cases}]
    if missing:
        raise ValueError(f"sequences reference unknown prompt(s): {', '.join(missing)}")
    generated_tokens = min(len(dna) // KMER_SIZE for dna in watermarked.values())
    if max(token_lengths) > generated_tokens:
        raise ValueError("an evaluated length exceeds the generated length")

    stream_domain = f"{generation_label}/{cohort_id}/{policy_id}"
    config = DetectorConfig(stream_offsets=tuple(range(args.stream_offsets)))
    support = canonical_kmers()

    run_started = time.perf_counter()
    trials: list[dict[str, Any]] = []
    # A keyed partition depends on the key, the domain, and the stream position, never on the
    # observed DNA. One cache per key therefore serves every sequence, rate, and length.
    streams: dict[bytes, tuple[KeyedPartitionStream, PartitionCache]] = {}

    def keyed(key: bytes) -> tuple[KeyedPartitionStream, PartitionCache]:
        cached = streams.get(key)
        if cached is None:
            stream = KeyedPartitionStream(key=key, domain=stream_domain)
            cached = (stream, PartitionCache(stream, support))
            streams[key] = cached
        return cached

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
        available = len(dna) // KMER_SIZE
        for length in token_lengths:
            if length > available:
                continue
            result = detect(dna[: length * KMER_SIZE], support, stream, config, cache=cache)
            trials.append(
                {
                    "family": family,
                    "case_id": case_id,
                    "edit_rate": rate,
                    "replicate": replicate,
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

    for rate in rates:
        for case_id in case_ids:
            for replicate in range(args.positive_replicates):
                score(
                    edited(
                        watermarked[case_id],
                        channel=args.edit,
                        rate=rate,
                        label=args.experiment_label,
                        policy_id=policy_id,
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
            null_watermarked = edited(
                watermarked[case_id],
                channel=args.edit,
                rate=rate,
                label=args.experiment_label,
                policy_id=policy_id,
                case_id=case_id,
                arm=PARTITION_MC_SCHEME,
                replicate=0,
            )
            null_ordinary = edited(
                ordinary[case_id],
                channel=args.edit,
                rate=rate,
                label=args.experiment_label,
                policy_id=policy_id,
                case_id=case_id,
                arm=ORDINARY_SCHEME,
                replicate=0,
            )
            for index in range(args.null_keys):
                key = null_key(index)
                score(
                    null_watermarked,
                    key,
                    family="wrong_key_watermarked",
                    case_id=case_id,
                    rate=rate,
                    replicate=0,
                    key_index=index,
                )
                score(
                    null_ordinary,
                    key,
                    family="any_key_ordinary",
                    case_id=case_id,
                    rate=rate,
                    replicate=0,
                    key_index=index,
                )

    grouped: dict[tuple[float, int, str], list[dict[str, Any]]] = {
        (rate, length, family): []
        for rate in rates
        for length in token_lengths
        for family in FAMILIES
    }
    for row in trials:
        grouped[(row["edit_rate"], row["token_length"], row["family"])].append(row)

    pooled_by_length: dict[int, list[float]] = {length: [] for length in token_lengths}
    for (_rate, length, family), rows in grouped.items():
        if family in POOLED_FAMILIES:
            pooled_by_length[length].extend(float(row["statistic"]) for row in rows)

    conditions: list[dict[str, Any]] = []
    for length in token_lengths:
        pooled_all_rates = pooled_by_length[length]
        pooled_calibration = calibrate_threshold(pooled_all_rates, args.target_fpr)
        for rate in rates:
            nulls = [
                float(row["statistic"])
                for family in POOLED_FAMILIES
                for row in grouped[(rate, length, family)]
            ]
            positives_rows = grouped[(rate, length, "positive")]
            if not nulls or not positives_rows:
                continue
            calibration = calibrate_threshold(nulls, args.target_fpr)
            positives = [float(row["statistic"]) for row in positives_rows]
            by_cluster: dict[str, list[float]] = {case_id: [] for case_id in case_ids}
            for row in positives_rows:
                by_cluster[row["case_id"]].append(
                    float(float(row["statistic"]) >= calibration.threshold)
                )
            conditions.append(
                {
                    "edit": args.edit,
                    "edit_rate": rate,
                    "token_length": length,
                    "base_length": length * KMER_SIZE,
                    "hypotheses_searched": positives_rows[0]["hypotheses_searched"],
                    "calibration": {
                        "scope": "per rate and length, pooled N1 and N2",
                        "pooled_null_families": list(POOLED_FAMILIES),
                        "pooled_null_trials": calibration.null_trials,
                        "target_false_positive_rate": calibration.target_false_positive_rate,
                        "achieved_false_positive_rate": (calibration.achieved_false_positive_rate),
                        "attainable_false_positive_rate": (
                            calibration.attainable_false_positive_rate
                        ),
                        "target_is_attainable": calibration.is_attainable,
                        "threshold": calibration.threshold,
                    },
                    "all_rate_pooled_calibration": {
                        "scope": "nulls pooled across every rate at this length; sensitivity check",
                        "pooled_null_trials": pooled_calibration.null_trials,
                        "achieved_false_positive_rate": (
                            pooled_calibration.achieved_false_positive_rate
                        ),
                        "attainable_false_positive_rate": (
                            pooled_calibration.attainable_false_positive_rate
                        ),
                        "threshold": pooled_calibration.threshold,
                        "detection_rate": detection_rate(positives, pooled_calibration.threshold),
                    },
                    "positive": {
                        "trials": len(positives),
                        "replicates_per_prompt": args.positive_replicates,
                        "detection_rate": detection_rate(positives, calibration.threshold),
                        "statistic": numeric_summary(positives),
                        "minimum_empirical_global_p_value": min(
                            empirical_p_value(value, nulls) for value in positives
                        ),
                        "maximum_empirical_global_p_value": max(
                            empirical_p_value(value, nulls) for value in positives
                        ),
                        "detection_rate_prompt_cluster_bootstrap": cluster_bootstrap(
                            by_cluster,
                            replicates=args.bootstrap_replicates,
                            seed=args.bootstrap_seed,
                        ),
                    },
                    "null_families": {
                        family: {
                            "trials": len(grouped[(rate, length, family)]),
                            "exceedance_rate_at_threshold": detection_rate(
                                [
                                    float(row["statistic"])
                                    for row in grouped[(rate, length, family)]
                                ],
                                calibration.threshold,
                            ),
                            "statistic": numeric_summary(
                                float(row["statistic"]) for row in grouped[(rate, length, family)]
                            ),
                        }
                        for family in POOLED_FAMILIES
                    },
                    "separation": {
                        "minimum_positive_statistic": min(positives),
                        "maximum_pooled_null_statistic": max(nulls),
                        "positives_strictly_above_all_pooled_nulls": min(positives) > max(nulls),
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
        "edit_seed_scheme": "public replay seed over label, policy, prompt, arm, rate, replicate",
        "positive_replicates_per_prompt": args.positive_replicates,
        "stream_domain": stream_domain,
        "case_count": len(case_ids),
        "case_ids": list(case_ids),
        "generated_tokens_per_case": generated_tokens,
        "token_lengths": list(token_lengths),
        "detector_search": config.describe(),
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
            "One edit channel only, under a published fixture key, with the detector search "
            "unchanged from the clean pilot. Thresholds are calibrated per rate and length by "
            "repeating the identical search on nulls that went through the same edit process. A "
            "uniform independent per-base channel is a statistical model, not a model of mutation, "
            "sequencing, or synthesis error."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "policy_id": policy_id,
                "edit": args.edit,
                "trial_count": len(trials),
                "wall_seconds": report["wall_seconds"],
                "detection_rate_by_rate_and_length": {
                    f"{entry['base_length']}b/r{entry['edit_rate']}": entry["positive"][
                        "detection_rate"
                    ]
                    for entry in conditions
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
