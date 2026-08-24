#!/usr/bin/env python3
"""Run the E8/E9 matched baseline comparison. Model-free: it loads no weights.

Scores the partition-coupling arm and the inverse-transform and exponential arms
with the *identical* declared search, calibrates a threshold separately for each
method on that method's own nulls, and reports detection rate against length. The
three statistics are on different scales, so only the calibrated detection rates
are comparable; raw statistics are recorded per trial but must never be compared
across methods.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.baselines import (  # noqa: E402
    EXP_SCHEME,
    ITS_SCHEME,
    KeyedBaselineStream,
)
from genomic_watermarks.detector.baseline_search import (  # noqa: E402
    baseline_cache,
    detect_baseline,
)
from genomic_watermarks.detector.search import (  # noqa: E402
    DECISION_RULE,
    DetectorConfig,
    PartitionCache,
    calibrate_threshold,
    detect,
    detection_rate,
    empirical_p_value,
    joint_detection_rate_interval,
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
METHODS = (PARTITION_MC_SCHEME, ITS_SCHEME, EXP_SCHEME)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--partition-sequences",
        type=Path,
        required=True,
        help="E4 sequences file holding the partition_mc arm and the shared ordinary control",
    )
    parser.add_argument(
        "--baseline-sequences",
        type=Path,
        required=True,
        help="E8/E9 sequences file holding the its and exp arms",
    )
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


def load_sequences(path: Path) -> tuple[dict[str, Any], ...]:
    records = tuple(
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    )
    if not records:
        raise ValueError(f"sequences file is empty: {path}")
    for field in ("policy_id", "experiment_label", "cohort_id"):
        if len({record[field] for record in records}) != 1:
            raise ValueError(f"{path} must hold exactly one {field}")
    return records


def arm(records: tuple[dict[str, Any], ...], scheme: str) -> dict[str, str]:
    return {
        record["case_id"]: record["generated_dna"]
        for record in records
        if record["scheme"] == scheme
    }


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
    if args.bootstrap_replicates <= 0:
        raise ValueError("bootstrap-replicates must be positive")
    token_lengths = tuple(sorted({int(value) for value in args.token_lengths}))
    if any(length <= 0 for length in token_lengths):
        raise ValueError("token lengths must be positive")

    partition_records = load_sequences(args.partition_sequences)
    baseline_records = load_sequences(args.baseline_sequences)
    policy_id = partition_records[0]["policy_id"]
    cohort_id = partition_records[0]["cohort_id"]
    if baseline_records[0]["policy_id"] != policy_id:
        raise ValueError("the two sequence files describe different policies")
    if baseline_records[0]["cohort_id"] != cohort_id:
        raise ValueError("the two sequence files describe different cohorts")

    arms = {
        PARTITION_MC_SCHEME: arm(partition_records, PARTITION_MC_SCHEME),
        ITS_SCHEME: arm(baseline_records, ITS_SCHEME),
        EXP_SCHEME: arm(baseline_records, EXP_SCHEME),
    }
    ordinary = arm(partition_records, ORDINARY_SCHEME)
    if not ordinary:
        raise ValueError("the partition sequences file must hold the shared ordinary control")
    case_ids = tuple(sorted(arms[PARTITION_MC_SCHEME]))
    for scheme, sequences in arms.items():
        if tuple(sorted(sequences)) != case_ids:
            raise ValueError(f"the {scheme} arm does not cover the same prompts")
    if tuple(sorted(ordinary)) != case_ids:
        raise ValueError("the ordinary control does not cover the same prompts")

    cases = load_context_cases_jsonl(args.cohort_jsonl)
    cases_by_id = {case.case_id: case for case in cases}
    missing = [case_id for case_id in case_ids if case_id not in cases_by_id]
    if missing:
        raise ValueError(f"sequences reference unknown prompt(s): {', '.join(missing)}")

    generated_tokens = min(
        len(dna) // KMER_SIZE for sequences in arms.values() for dna in sequences.values()
    )
    if max(token_lengths) > generated_tokens:
        raise ValueError("an evaluated length exceeds the generated length")

    # Each method's key stream lives in the domain of the run that generated its arm,
    # which is why the partition arm can be reused from E4 unchanged.
    domains = {
        PARTITION_MC_SCHEME: (
            f"{partition_records[0]['experiment_label']}/{cohort_id}/{policy_id}"
        ),
        ITS_SCHEME: f"{baseline_records[0]['experiment_label']}/{cohort_id}/{policy_id}",
        EXP_SCHEME: f"{baseline_records[0]['experiment_label']}/{cohort_id}/{policy_id}",
    }
    config = DetectorConfig(stream_offsets=tuple(range(args.stream_offsets)))
    support = canonical_kmers()

    run_started = time.perf_counter()
    trials: list[dict[str, Any]] = []

    def score_sequence(
        scheme: str,
        dna: str,
        stream: Any,
        cache: Any,
        *,
        family: str,
        case_id: str,
        key_index: int | None,
    ) -> None:
        """Score one sequence at every evaluated prefix length."""

        available = len(dna) // KMER_SIZE
        for length in token_lengths:
            if length > available:
                continue
            prefix = dna[: length * KMER_SIZE]
            if scheme == PARTITION_MC_SCHEME:
                result = detect(prefix, support, stream, config, cache=cache)
            else:
                result = detect_baseline(prefix, config, cache, scheme=scheme)
            row = {
                "method": scheme,
                "family": family,
                "case_id": case_id,
                "key_index": key_index,
                "token_length": length,
                "base_length": length * KMER_SIZE,
                "statistic": result.statistic,
                "total": result.total,
                "orientation": result.hypothesis.orientation,
                "phase": result.hypothesis.phase,
                "stream_offset": result.hypothesis.stream_offset,
                "hypotheses_searched": result.hypotheses_searched,
            }
            # Store the primitive each statistic is computed from, so a validator can
            # re-derive the statistic instead of trusting it.
            if scheme == PARTITION_MC_SCHEME:
                row["matches"] = result.matches
            else:
                row["total_score"] = result.total_score
            trials.append(row)

    keys: list[tuple[int | None, bytes]] = [(None, PUBLIC_FIXTURE_KEY)]
    keys.extend((index, null_key(index)) for index in range(args.null_keys))

    for scheme in METHODS:
        for key_index, key in keys:
            # A keyed partition and a keyed permutation are both DNA-independent, so
            # one cache per key serves every sequence and every length. The
            # exponential baseline instead keys its cache on the observed token, so
            # it gets a fresh cache per sequence to keep memory bounded; nothing is
            # recomputed twice within a sequence.
            if scheme == PARTITION_MC_SCHEME:
                stream: Any = KeyedPartitionStream(key=key, domain=domains[scheme])
                shared: Any = PartitionCache(stream, support)
            else:
                stream = KeyedBaselineStream(key=key, domain=domains[scheme])
                shared = baseline_cache(scheme, stream, support) if scheme == ITS_SCHEME else None

            def cache_for(
                _stream: Any = stream, _shared: Any = shared, _scheme: str = scheme
            ) -> Any:
                if _shared is not None:
                    return _shared
                return baseline_cache(_scheme, _stream, support)

            if key_index is None:
                targets = [("positive", arms[scheme])]
            else:
                targets = [
                    ("wrong_key_watermarked", arms[scheme]),
                    ("any_key_ordinary", ordinary),
                    (
                        "any_key_public_dna",
                        {case_id: cases_by_id[case_id].sequence for case_id in case_ids},
                    ),
                ]
            for family, sequences in targets:
                for case_id in case_ids:
                    score_sequence(
                        scheme,
                        sequences[case_id],
                        stream,
                        cache_for(),
                        family=family,
                        case_id=case_id,
                        key_index=key_index,
                    )
            del stream, shared

    grouped: dict[tuple[str, int, str], list[dict[str, Any]]] = defaultdict(list)
    for trial in trials:
        grouped[(trial["method"], trial["token_length"], trial["family"])].append(trial)

    methods_report: list[dict[str, Any]] = []
    for scheme in METHODS:
        lengths_report: list[dict[str, Any]] = []
        for length in token_lengths:
            positives_rows = grouped[(scheme, length, "positive")]
            pooled = [
                trial["statistic"]
                for family in POOLED_FAMILIES
                for trial in grouped[(scheme, length, family)]
            ]
            if not positives_rows or not pooled:
                continue
            calibration = calibrate_threshold(pooled, args.target_fpr)
            positives = [trial["statistic"] for trial in positives_rows]
            by_cluster: dict[str, list[float]] = defaultdict(list)
            for trial in positives_rows:
                by_cluster[trial["case_id"]].append(trial["statistic"])
            interval = joint_detection_rate_interval(
                by_cluster,
                pooled,
                args.target_fpr,
                replicates=args.bootstrap_replicates,
                seed=args.bootstrap_seed,
            )
            lengths_report.append(
                {
                    "token_length": length,
                    "base_length": length * KMER_SIZE,
                    "hypotheses_searched": positives_rows[0]["hypotheses_searched"],
                    "calibration": {
                        "pooled_null_families": list(POOLED_FAMILIES),
                        "pooled_null_trials": calibration.null_trials,
                        "target_false_positive_rate": calibration.target_false_positive_rate,
                        "achieved_false_positive_rate": calibration.achieved_false_positive_rate,
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
                            empirical_p_value(value, pooled) for value in positives
                        ),
                        "maximum_empirical_global_p_value": max(
                            empirical_p_value(value, pooled) for value in positives
                        ),
                        "detection_rate_joint_interval": interval,
                    },
                    "null_families": {
                        family: {
                            "trials": len(grouped[(scheme, length, family)]),
                            "exceedance_rate_at_threshold": detection_rate(
                                [trial["statistic"] for trial in grouped[(scheme, length, family)]],
                                calibration.threshold,
                            )
                            if grouped[(scheme, length, family)]
                            else None,
                            "statistic": numeric_summary(
                                trial["statistic"] for trial in grouped[(scheme, length, family)]
                            )
                            if grouped[(scheme, length, family)]
                            else None,
                        }
                        for family in NULL_FAMILIES
                    },
                    "separation": {
                        "minimum_positive_statistic": min(positives),
                        "maximum_pooled_null_statistic": max(pooled),
                        "positives_strictly_above_all_pooled_nulls": min(positives) > max(pooled),
                    },
                    "derived_signal_per_token": {
                        "value": numeric_summary(
                            trial["statistic"] / math.sqrt(trial["total"])
                            for trial in positives_rows
                        ),
                        "unit": "standard deviations of this method's own null, per 6-mer token",
                        "boundary": (
                            "Derived, not a detection rate. It expresses each method's signal in "
                            "units of that method's own null, which is why it may be compared "
                            "across methods; the raw statistics may not be, and the calibrated "
                            "thresholds differ slightly because each null maximum differs."
                        ),
                    },
                }
            )
        fully = [
            entry["base_length"]
            for entry in lengths_report
            if entry["positive"]["detection_rate"] >= 1.0
        ]
        methods_report.append(
            {
                "method": scheme,
                "stream_domain": domains[scheme],
                "shortest_fully_detected_base_length": min(fully) if fully else None,
                "lengths": lengths_report,
            }
        )

    searched = {
        (entry["method"], length["base_length"]): length["hypotheses_searched"]
        for entry in methods_report
        for length in entry["lengths"]
    }
    by_length_counts: dict[int, set[int]] = defaultdict(set)
    for (_method, base_length), count in searched.items():
        by_length_counts[base_length].add(count)
    identical_search = all(len(counts) == 1 for counts in by_length_counts.values())

    report: dict[str, Any] = {
        "schema_version": 1,
        "classification": "engineering_pilot_not_paper_evidence",
        "complete": True,
        "policy_id": policy_id,
        "cohort_id": cohort_id,
        "methods": list(METHODS),
        "control_method": ORDINARY_SCHEME,
        "decision_rule": DECISION_RULE,
        "key_source": "public_fixture",
        "null_key_source": "public_fixture_labels",
        "null_keys": args.null_keys,
        "case_count": len(case_ids),
        "case_ids": list(case_ids),
        "generated_tokens_per_case": generated_tokens,
        "token_lengths": list(token_lengths),
        "detector_search": config.describe(),
        "identical_search_across_methods": identical_search,
        "hypotheses_searched_by_base_length": {
            str(base_length): sorted(counts) for base_length, counts in by_length_counts.items()
        },
        "support_size": len(support),
        "sequences": {
            "partition_path": str(args.partition_sequences),
            "partition_sha256": hashlib.sha256(args.partition_sequences.read_bytes()).hexdigest(),
            "partition_experiment_label": partition_records[0]["experiment_label"],
            "baseline_path": str(args.baseline_sequences),
            "baseline_sha256": hashlib.sha256(args.baseline_sequences.read_bytes()).hexdigest(),
            "baseline_experiment_label": baseline_records[0]["experiment_label"],
        },
        "cohort": {
            "prompts_path": str(args.cohort_jsonl),
            "prompts_file_sha256": hashlib.sha256(args.cohort_jsonl.read_bytes()).hexdigest(),
            "cohort_content_sha256": cohort_case_digest(cases),
            "manifest_path": str(args.cohort_manifest) if args.cohort_manifest else None,
            "manifest_sha256": (
                hashlib.sha256(args.cohort_manifest.read_bytes()).hexdigest()
                if args.cohort_manifest
                else None
            ),
        },
        "interval_method": (
            "joint resample: every replicate resamples the pooled nulls, recalibrates the "
            "threshold from that resample, and independently resamples the prompt clusters"
        ),
        "bootstrap_replicates": args.bootstrap_replicates,
        "bootstrap_seed": args.bootstrap_seed,
        "trial_count": len(trials),
        "trials": trials,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "wall_seconds": time.perf_counter() - run_started,
        "method_results": methods_report,
        "boundary": (
            "Clean sequences only, under a published fixture key. Each method is calibrated on "
            "its own nulls because the three statistics are on different scales; only the "
            "calibrated detection rates are comparable, never the raw statistics. Edit "
            "robustness for the two baselines is a separate experiment and nothing about it may "
            "be inferred from this clean comparison."
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
                "identical_search_across_methods": identical_search,
                "wall_seconds": report["wall_seconds"],
                "methods": [
                    {
                        "method": entry["method"],
                        "shortest_fully_detected_base_length": entry[
                            "shortest_fully_detected_base_length"
                        ],
                        "lengths": [
                            {
                                "base_length": length["base_length"],
                                "threshold": length["calibration"]["threshold"],
                                "achieved_fpr": length["calibration"][
                                    "achieved_false_positive_rate"
                                ],
                                "detection_rate": length["positive"]["detection_rate"],
                                "interval": [
                                    length["positive"]["detection_rate_joint_interval"]["lower"],
                                    length["positive"]["detection_rate_joint_interval"]["upper"],
                                ],
                                "separated": length["separation"][
                                    "positives_strictly_above_all_pooled_nulls"
                                ],
                            }
                            for length in entry["lengths"]
                        ],
                    }
                    for entry in methods_report
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
