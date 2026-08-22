#!/usr/bin/env python3
"""Run the E6 crop, strand, and phase pilot under two declared offset searches.

Model-free. Builds one deterministic observed sequence per condition at a fixed
observed length, then repeats each declared search for positives and nulls and
calibrates a threshold per condition and search.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
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
from genomic_watermarks.dna import KMER_SIZE, canonical_kmers, reverse_complement  # noqa: E402
from genomic_watermarks.edits import crop  # noqa: E402
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
POOLED_FAMILIES = ("wrong_key_watermarked", "any_key_ordinary")
FAMILIES = ("positive", *POOLED_FAMILIES)

# (condition id, front crop in bases, reverse complement after cropping)
CONDITIONS: tuple[tuple[str, int, bool], ...] = (
    ("identity", 0, False),
    ("reverse_complement", 0, True),
    ("front_crop_1", 1, False),
    ("front_crop_3", 3, False),
    ("front_crop_6", 6, False),
    ("front_crop_7", 7, False),
    ("front_crop_47", 47, False),
    ("front_crop_48", 48, False),
    ("front_crop_300", 300, False),
    ("front_crop_768", 768, False),
    ("front_crop_3_reverse_complement", 3, True),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequences", type=Path, required=True)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--cohort-manifest", type=Path)
    parser.add_argument("--observed-bases", type=int, default=1536)
    parser.add_argument("--narrow-offsets", type=int, default=8)
    parser.add_argument("--wide-offsets", type=int, default=128)
    parser.add_argument("--null-keys", type=int, default=8)
    parser.add_argument("--target-fpr", type=float, default=0.01)
    parser.add_argument("--bootstrap-replicates", type=int, default=20_000)
    parser.add_argument("--bootstrap-seed", type=int, default=2718)
    parser.add_argument("--experiment-label", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def null_key(index: int) -> bytes:
    return hashlib.sha256(f"{NULL_KEY_LABEL}/{index:04d}".encode()).digest()


def transform(dna: str, *, front_crop: int, complement: bool, observed_bases: int) -> str:
    """Build the observed sequence for one condition, cropping before complementing."""

    fragment = crop(dna, front_crop, observed_bases)
    if len(fragment) != observed_bases:
        raise ValueError("the generated sequence is too short for this condition")
    return reverse_complement(fragment) if complement else fragment


def required_alignment(front_crop: int) -> dict[str, int]:
    """Return the phase and key-stream offset a verifier must reach for this crop."""

    return {
        "required_phase": (-front_crop) % KMER_SIZE,
        "required_stream_offset": math.ceil(front_crop / KMER_SIZE),
    }


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to replace existing output: {args.output}")
    if args.observed_bases <= 0 or args.observed_bases % KMER_SIZE:
        raise ValueError("observed-bases must be a positive multiple of six")
    if args.narrow_offsets <= 0 or args.wide_offsets <= args.narrow_offsets:
        raise ValueError("wide-offsets must exceed narrow-offsets, and both must be positive")
    if args.null_keys <= 0:
        raise ValueError("null-keys must be positive")
    if not 0.0 < args.target_fpr < 1.0:
        raise ValueError("target-fpr must lie in (0, 1)")

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
    known = {case.case_id for case in cases}
    missing = [case_id for case_id in case_ids if case_id not in known]
    if missing:
        raise ValueError(f"sequences reference unknown prompt(s): {', '.join(missing)}")
    generated_bases = min(len(dna) for dna in watermarked.values())
    largest_crop = max(front_crop for _, front_crop, _ in CONDITIONS)
    if largest_crop + args.observed_bases > generated_bases:
        raise ValueError("the corpus is too short for the declared crop grid")

    stream_domain = f"{generation_label}/{cohort_id}/{policy_id}"
    searches = {
        "narrow": DetectorConfig(stream_offsets=tuple(range(args.narrow_offsets))),
        "wide": DetectorConfig(stream_offsets=tuple(range(args.wide_offsets))),
    }
    support = canonical_kmers()
    observed_tokens = args.observed_bases // KMER_SIZE

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

    def score(
        dna: str,
        key: bytes,
        *,
        family: str,
        case_id: str,
        condition_id: str,
        search_id: str,
        key_index: int | None,
    ) -> None:
        stream, cache = keyed(key)
        result = detect(dna, support, stream, searches[search_id], cache=cache)
        trials.append(
            {
                "family": family,
                "case_id": case_id,
                "condition_id": condition_id,
                "search_id": search_id,
                "key_index": key_index,
                "observed_bases": len(dna),
                "statistic": result.statistic,
                "matches": result.matches,
                "total": result.total,
                "orientation": result.hypothesis.orientation,
                "phase": result.hypothesis.phase,
                "stream_offset": result.hypothesis.stream_offset,
                "hypotheses_searched": result.hypotheses_searched,
            }
        )

    for condition_id, front_crop, complement in CONDITIONS:
        for case_id in case_ids:
            positive_dna = transform(
                watermarked[case_id],
                front_crop=front_crop,
                complement=complement,
                observed_bases=args.observed_bases,
            )
            null_dna = transform(
                ordinary[case_id],
                front_crop=front_crop,
                complement=complement,
                observed_bases=args.observed_bases,
            )
            for search_id in searches:
                score(
                    positive_dna,
                    PUBLIC_FIXTURE_KEY,
                    family="positive",
                    case_id=case_id,
                    condition_id=condition_id,
                    search_id=search_id,
                    key_index=None,
                )
                for index in range(args.null_keys):
                    key = null_key(index)
                    score(
                        positive_dna,
                        key,
                        family="wrong_key_watermarked",
                        case_id=case_id,
                        condition_id=condition_id,
                        search_id=search_id,
                        key_index=index,
                    )
                    score(
                        null_dna,
                        key,
                        family="any_key_ordinary",
                        case_id=case_id,
                        condition_id=condition_id,
                        search_id=search_id,
                        key_index=index,
                    )

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {
        (condition_id, search_id, family): []
        for condition_id, _, _ in CONDITIONS
        for search_id in searches
        for family in FAMILIES
    }
    for row in trials:
        grouped[(row["condition_id"], row["search_id"], row["family"])].append(row)

    conditions: list[dict[str, Any]] = []
    for condition_id, front_crop, complement in CONDITIONS:
        alignment = required_alignment(front_crop)
        for search_id, config in searches.items():
            nulls = [
                float(row["statistic"])
                for family in POOLED_FAMILIES
                for row in grouped[(condition_id, search_id, family)]
            ]
            positives_rows = grouped[(condition_id, search_id, "positive")]
            positives = [float(row["statistic"]) for row in positives_rows]
            calibration = calibrate_threshold(nulls, args.target_fpr)
            indicators = {
                str(row["case_id"]): (float(float(row["statistic"]) > calibration.threshold),)
                for row in positives_rows
            }
            cluster = analyze_prompt_clusters(
                indicators,
                bootstrap_replicates=args.bootstrap_replicates,
                bootstrap_seed=args.bootstrap_seed,
            )
            offsets = config.stream_offsets
            conditions.append(
                {
                    "condition_id": condition_id,
                    "front_crop_bases": front_crop,
                    "reverse_complemented": complement,
                    **alignment,
                    "required_offset_inside_search": alignment["required_stream_offset"] in offsets,
                    "search_id": search_id,
                    "searched_offsets": len(offsets),
                    "hypotheses_searched": positives_rows[0]["hypotheses_searched"],
                    "observed_bases": args.observed_bases,
                    "observed_tokens": observed_tokens,
                    "calibration": {
                        "scope": "per condition and search, pooled N1 and N2",
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
                    "positive": {
                        "trials": len(positives),
                        "detection_rate": detection_rate(positives, calibration.threshold),
                        "statistic": numeric_summary(positives),
                        "minimum_empirical_global_p_value": min(
                            empirical_p_value(value, nulls) for value in positives
                        ),
                        "recovered_alignment_counts": {
                            "orientation": sorted(
                                {str(row["orientation"]) for row in positives_rows}
                            ),
                            "phase": sorted({int(row["phase"]) for row in positives_rows}),
                            "stream_offset": sorted(
                                {int(row["stream_offset"]) for row in positives_rows}
                            ),
                        },
                        "detection_rate_prompt_cluster_bootstrap": {
                            "mean": cluster.overall_mean,
                            "lower": cluster.interval_lower,
                            "upper": cluster.interval_upper,
                            "width": cluster.interval_width,
                            "clusters": float(len(indicators)),
                            "confidence_level": 0.95,
                            "replicates": float(args.bootstrap_replicates),
                            "seed": float(args.bootstrap_seed),
                        },
                    },
                    "null_families": {
                        family: {
                            "trials": len(grouped[(condition_id, search_id, family)]),
                            "exceedance_rate_at_threshold": detection_rate(
                                [
                                    float(row["statistic"])
                                    for row in grouped[(condition_id, search_id, family)]
                                ],
                                calibration.threshold,
                            ),
                            "statistic": numeric_summary(
                                float(row["statistic"])
                                for row in grouped[(condition_id, search_id, family)]
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
        "observed_bases": args.observed_bases,
        "observed_tokens": observed_tokens,
        "condition_ids": [condition_id for condition_id, _, _ in CONDITIONS],
        "condition_definitions": [
            {
                "condition_id": condition_id,
                "front_crop_bases": front_crop,
                "reverse_complemented": complement,
                "order_of_operations": "crop first, then reverse complement",
                **required_alignment(front_crop),
            }
            for condition_id, front_crop, complement in CONDITIONS
        ],
        "searches": {
            search_id: {
                "search": config.describe(),
                "searched_offsets": len(config.stream_offsets),
                "hypotheses": 2 * KMER_SIZE * len(config.stream_offsets),
            }
            for search_id, config in searches.items()
        },
        "sliding_observed_window": "not declared; spliced or partial watermarking is out of scope",
        "case_count": len(case_ids),
        "case_ids": list(case_ids),
        "generated_bases_per_case": generated_bases,
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
            "Front crops, full-fragment reverse complementation, and their composition, at one "
            "fixed observed length, under a published fixture key. Thresholds are calibrated per "
            "condition and per search by repeating the identical declared search on nulls that "
            "went through the same transform. No sliding observed window is declared, so spliced "
            "or partial watermarking is not measured. Insertions and deletions are a separate "
            "experiment."
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
                "detection_rate": {
                    f"{entry['condition_id']}/{entry['search_id']}": entry["positive"][
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
