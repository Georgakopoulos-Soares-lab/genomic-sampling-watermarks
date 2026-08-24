#!/usr/bin/env python3
"""E11/E12: what key reuse buys an attacker who never sees the key.

Model-free. Reads a generated sequences file, builds spoofing and removal attacks
from the watermarked outputs alone, and scores every attacked sequence with the
same detector, the same declared search, and the same thresholds as the genuine
E4 sequences.

A high detection rate on the spoofing attack is a vulnerability, not a success.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.attacks import (  # noqa: E402
    BLOCK_SHUFFLE_ATTACK,
    SHUFFLE_ATTACK,
    SPLICE_ATTACK,
    block_shuffle,
    positional_shuffle,
    positional_splice,
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
from genomic_watermarks.sequence_proxies import PROXY_METRICS, proxy_metrics  # noqa: E402
from genomic_watermarks.watermark import (  # noqa: E402
    ORDINARY_SCHEME,
    PARTITION_MC_SCHEME,
    KeyedPartitionStream,
    public_replay_seed,
)

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl"
PUBLIC_FIXTURE_KEY = b"genomic-sampling-watermarks/public-generation-fixture/v1"
NULL_KEY_LABEL = "genomic-sampling-watermarks/public-null-key/v1"
POOLED_FAMILIES = ("wrong_key_watermarked", "any_key_ordinary")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequences", type=Path, required=True)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--cohort-manifest", type=Path)
    parser.add_argument("--token-lengths", type=int, nargs="+", default=(64, 128, 256, 512))
    parser.add_argument("--donor-counts", type=int, nargs="+", default=(2, 4, 8))
    parser.add_argument("--block-widths", type=int, nargs="+", default=(2, 3, 4, 6, 8, 16, 32))
    parser.add_argument("--splice-draws", type=int, default=8, help="forgeries per donor count")
    parser.add_argument("--stream-offsets", type=int, default=8)
    parser.add_argument("--null-keys", type=int, default=20)
    parser.add_argument("--target-fpr", type=float, default=0.01)
    parser.add_argument("--bootstrap-replicates", type=int, default=20_000)
    parser.add_argument("--bootstrap-seed", type=int, default=2718)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def null_key(index: int) -> bytes:
    return hashlib.sha256(f"{NULL_KEY_LABEL}/{index:04d}".encode()).digest()


def load_sequences(path: Path) -> tuple[dict[str, Any], ...]:
    records = tuple(
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    )
    if not records:
        raise ValueError("sequences file is empty")
    for field in ("policy_id", "experiment_label", "cohort_id"):
        if len({record[field] for record in records}) != 1:
            raise ValueError(f"sequences file must hold exactly one {field}")
    return records


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to replace existing output: {args.output}")
    token_lengths = tuple(sorted({int(v) for v in args.token_lengths}))
    donor_counts = tuple(sorted({int(v) for v in args.donor_counts}))
    block_widths = tuple(sorted({int(v) for v in args.block_widths}))
    if any(v <= 0 for v in token_lengths):
        raise ValueError("token lengths must be positive")
    if any(v < 2 for v in donor_counts):
        raise ValueError("splicing needs at least two donors")
    if any(v < 2 for v in block_widths):
        raise ValueError("block widths must be at least two tokens")
    if args.splice_draws <= 0:
        raise ValueError("splice-draws must be positive")

    records = load_sequences(args.sequences)
    policy_id = records[0]["policy_id"]
    experiment_label = records[0]["experiment_label"]
    cohort_id = records[0]["cohort_id"]
    watermarked = {
        r["case_id"]: r["generated_dna"] for r in records if r["scheme"] == PARTITION_MC_SCHEME
    }
    ordinary = {r["case_id"]: r["generated_dna"] for r in records if r["scheme"] == ORDINARY_SCHEME}
    if not watermarked or set(watermarked) != set(ordinary):
        raise ValueError("both arms must cover the same prompts")
    case_ids = tuple(sorted(watermarked))
    if max(donor_counts) > len(case_ids):
        raise ValueError("a donor count exceeds the number of available outputs")

    cases = load_context_cases_jsonl(args.cohort_jsonl)
    cases_by_id = {c.case_id: c for c in cases}
    missing = [c for c in case_ids if c not in cases_by_id]
    if missing:
        raise ValueError(f"sequences reference unknown prompt(s): {', '.join(missing)}")

    stream_domain = f"{experiment_label}/{cohort_id}/{policy_id}"
    config = DetectorConfig(stream_offsets=tuple(range(args.stream_offsets)))
    support = canonical_kmers()
    run_started = time.perf_counter()

    trials: list[dict[str, Any]] = []

    def score(
        dna: str,
        stream: KeyedPartitionStream,
        cache: PartitionCache,
        *,
        family: str,
        cluster: str,
        key_index: int | None,
        attack: str | None,
        parameter: Any,
        displaced: float | None,
        replicate: int | None,
    ) -> None:
        available = len(dna) // KMER_SIZE
        for length in token_lengths:
            if length > available:
                continue
            result = detect(dna[: length * KMER_SIZE], support, stream, config, cache=cache)
            trials.append(
                {
                    "family": family,
                    "attack": attack,
                    "parameter": parameter,
                    "cluster": cluster,
                    "key_index": key_index,
                    "replicate": replicate,
                    "token_length": length,
                    "base_length": length * KMER_SIZE,
                    "statistic": result.statistic,
                    "matches": result.matches,
                    "total": result.total,
                    "displaced_fraction": displaced,
                    "orientation": result.hypothesis.orientation,
                    "phase": result.hypothesis.phase,
                    "stream_offset": result.hypothesis.stream_offset,
                    "hypotheses_searched": result.hypotheses_searched,
                }
            )

    real_stream = KeyedPartitionStream(key=PUBLIC_FIXTURE_KEY, domain=stream_domain)
    real_cache = PartitionCache(real_stream, support)

    # Genuine outputs, so every attack is read against the rate it is trying to reach.
    for case_id in case_ids:
        score(
            watermarked[case_id],
            real_stream,
            real_cache,
            family="genuine",
            cluster=case_id,
            key_index=None,
            attack=None,
            parameter=None,
            displaced=None,
            replicate=None,
        )

    # Attack A: positional splice forgery. Every forgery is novel by construction.
    proxy_rows: list[dict[str, Any]] = []
    for donors in donor_counts:
        for replicate in range(args.splice_draws):
            seed = public_replay_seed("e11-splice", policy_id, str(donors), str(replicate))
            rng = random.Random(seed)
            chosen = rng.sample(case_ids, donors)
            forged, choice = positional_splice([watermarked[c] for c in chosen], rng)
            if forged in set(watermarked.values()):
                raise RuntimeError("a forgery matched a donor verbatim")
            score(
                forged,
                real_stream,
                real_cache,
                family="spoof",
                cluster=chosen[0],
                key_index=None,
                attack=SPLICE_ATTACK,
                parameter=donors,
                displaced=None,
                replicate=replicate,
            )
            proxy_rows.append(
                {
                    "attack": SPLICE_ATTACK,
                    "parameter": donors,
                    "replicate": replicate,
                    "distinct_donors_used": len(set(choice)),
                    "proxies": proxy_metrics(forged),
                    "reference_proxies": proxy_metrics(watermarked[chosen[0]]),
                }
            )

    # Attacks B and C: removal by rearrangement, with the utility cost recorded.
    for case_id in case_ids:
        source = watermarked[case_id]
        source_proxies = proxy_metrics(source)
        rng = random.Random(public_replay_seed("e11-shuffle", policy_id, case_id))
        attacked, displaced = positional_shuffle(source, rng)
        score(
            attacked,
            real_stream,
            real_cache,
            family="removal",
            cluster=case_id,
            key_index=None,
            attack=SHUFFLE_ATTACK,
            parameter=None,
            displaced=displaced,
            replicate=None,
        )
        proxy_rows.append(
            {
                "attack": SHUFFLE_ATTACK,
                "parameter": None,
                "case_id": case_id,
                "displaced_fraction": displaced,
                "proxies": proxy_metrics(attacked),
                "reference_proxies": source_proxies,
            }
        )
        for width in block_widths:
            rng = random.Random(public_replay_seed("e11-block", policy_id, case_id, str(width)))
            attacked, displaced = block_shuffle(source, width, rng)
            score(
                attacked,
                real_stream,
                real_cache,
                family="removal",
                cluster=case_id,
                key_index=None,
                attack=BLOCK_SHUFFLE_ATTACK,
                parameter=width,
                displaced=displaced,
                replicate=None,
            )
            proxy_rows.append(
                {
                    "attack": BLOCK_SHUFFLE_ATTACK,
                    "parameter": width,
                    "case_id": case_id,
                    "displaced_fraction": displaced,
                    "proxies": proxy_metrics(attacked),
                    "reference_proxies": source_proxies,
                }
            )

    # Nulls, pooled exactly as E4 pools them, plus attack D: one fixed key against
    # many sequences it did not generate.
    for index in range(args.null_keys):
        stream = KeyedPartitionStream(key=null_key(index), domain=stream_domain)
        cache = PartitionCache(stream, support)
        for case_id in case_ids:
            score(
                watermarked[case_id],
                stream,
                cache,
                family="wrong_key_watermarked",
                cluster=case_id,
                key_index=index,
                attack=None,
                parameter=None,
                displaced=None,
                replicate=None,
            )
            score(
                ordinary[case_id],
                stream,
                cache,
                family="any_key_ordinary",
                cluster=case_id,
                key_index=index,
                attack=None,
                parameter=None,
                displaced=None,
                replicate=None,
            )
        del stream, cache

    # Attack D uses the real key against sequences it did not generate: the ordinary
    # arm and the public prompts. This is the many-query question key reuse raises.
    for case_id in case_ids:
        score(
            ordinary[case_id],
            real_stream,
            real_cache,
            family="fixed_key_many_query_ordinary",
            cluster=case_id,
            key_index=None,
            attack=None,
            parameter=None,
            displaced=None,
            replicate=None,
        )
        score(
            cases_by_id[case_id].sequence,
            real_stream,
            real_cache,
            family="fixed_key_many_query_public_dna",
            cluster=case_id,
            key_index=None,
            attack=None,
            parameter=None,
            displaced=None,
            replicate=None,
        )

    grouped: dict[tuple[int, str, str | None, Any], list[dict[str, Any]]] = defaultdict(list)
    for row in trials:
        grouped[(row["token_length"], row["family"], row["attack"], row["parameter"])].append(row)

    lengths_report: list[dict[str, Any]] = []
    for length in token_lengths:
        pooled = [
            row["statistic"]
            for family in POOLED_FAMILIES
            for row in grouped[(length, family, None, None)]
        ]
        if not pooled:
            continue
        calibration = calibrate_threshold(pooled, args.target_fpr)

        def cell(
            family: str,
            attack: str | None,
            parameter: Any,
            _length: int = length,
            _calibration: Any = calibration,
            _pooled: list[float] = pooled,
        ) -> dict[str, Any] | None:
            rows = grouped[(_length, family, attack, parameter)]
            if not rows:
                return None
            values = [row["statistic"] for row in rows]
            by_cluster: dict[str, list[float]] = defaultdict(list)
            for row in rows:
                by_cluster[row["cluster"]].append(row["statistic"])
            entry: dict[str, Any] = {
                "family": family,
                "attack": attack,
                "parameter": parameter,
                "trials": len(values),
                "detection_rate": detection_rate(values, _calibration.threshold),
                "statistic": numeric_summary(values),
                "maximum_empirical_global_p_value": max(
                    empirical_p_value(value, _pooled) for value in values
                ),
            }
            displaced = [
                row["displaced_fraction"] for row in rows if row["displaced_fraction"] is not None
            ]
            if displaced:
                entry["displaced_fraction"] = numeric_summary(displaced)
            if len(by_cluster) >= 2:
                entry["detection_rate_joint_interval"] = joint_detection_rate_interval(
                    by_cluster,
                    _pooled,
                    args.target_fpr,
                    replicates=args.bootstrap_replicates,
                    seed=args.bootstrap_seed,
                )
            return entry

        cells = [cell("genuine", None, None)]
        cells.extend(cell("spoof", SPLICE_ATTACK, donors) for donors in donor_counts)
        cells.append(cell("removal", SHUFFLE_ATTACK, None))
        cells.extend(cell("removal", BLOCK_SHUFFLE_ATTACK, width) for width in block_widths)
        for family in (
            "fixed_key_many_query_ordinary",
            "fixed_key_many_query_public_dna",
            "wrong_key_watermarked",
            "any_key_ordinary",
        ):
            cells.append(cell(family, None, None))
        lengths_report.append(
            {
                "token_length": length,
                "base_length": length * KMER_SIZE,
                "hypotheses_searched": grouped[(length, "genuine", None, None)][0][
                    "hypotheses_searched"
                ],
                "calibration": {
                    "pooled_null_families": list(POOLED_FAMILIES),
                    "pooled_null_trials": calibration.null_trials,
                    "target_false_positive_rate": calibration.target_false_positive_rate,
                    "achieved_false_positive_rate": calibration.achieved_false_positive_rate,
                    "attainable_false_positive_rate": calibration.attainable_false_positive_rate,
                    "target_is_attainable": calibration.is_attainable,
                    "threshold": calibration.threshold,
                },
                "cells": [entry for entry in cells if entry is not None],
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
        "decision_rule": DECISION_RULE,
        "attacks": [SPLICE_ATTACK, SHUFFLE_ATTACK, BLOCK_SHUFFLE_ATTACK],
        "attacker_knowledge": (
            "generated DNA and the public configuration only. The attacker never queries the "
            "model, never observes a probability, and never observes the key."
        ),
        "key_source": "public_fixture",
        "null_key_source": "public_fixture_labels",
        "null_keys": args.null_keys,
        "stream_domain": stream_domain,
        "case_count": len(case_ids),
        "case_ids": list(case_ids),
        "outputs_available_to_attacker": len(case_ids),
        "donor_counts": list(donor_counts),
        "block_widths": list(block_widths),
        "splice_draws_per_donor_count": args.splice_draws,
        "token_lengths": list(token_lengths),
        "detector_search": config.describe(),
        "support_size": len(support),
        "sequences": {
            "path": str(args.sequences),
            "sha256": hashlib.sha256(args.sequences.read_bytes()).hexdigest(),
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
        "proxy_metrics": list(PROXY_METRICS),
        "utility_rows": proxy_rows,
        "trial_count": len(trials),
        "trials": trials,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "wall_seconds": time.perf_counter() - run_started,
        "lengths": lengths_report,
        "sign_of_the_result": (
            "For the spoofing attack a HIGH detection rate is a vulnerability, not a success: it "
            "means a sequence the generator never produced is accepted as provenance. For the "
            "removal attacks a LOW detection rate is a successful attack, and it must be read "
            "beside the proxy cost, because a rearrangement that destroys the sequence is not a "
            "useful attack."
        ),
        "boundary": (
            "Clean sequences only; no attack is composed with substitutions or indels. Measured "
            "under a published fixture key against one specified construction and one specified "
            "attacker. These are measurements, not a security reduction, and nothing here says "
            "whether a content-binding construction or a per-sequence nonce would close the gap."
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
                "summary": [
                    {
                        "base_length": entry["base_length"],
                        "threshold": entry["calibration"]["threshold"],
                        "cells": [
                            {
                                "family": c["family"],
                                "attack": c["attack"],
                                "parameter": c["parameter"],
                                "detection_rate": c["detection_rate"],
                                "mean_statistic": c["statistic"]["mean"],
                            }
                            for c in entry["cells"]
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
