#!/usr/bin/env python3
"""E10: can an observer without the key tell watermarked output from ordinary output?

Model-free. Runs a paired two-alternative forced choice with leave-one-prompt-out
fitting, so no distinguisher is scored on a prompt it was fit to. Chance is exactly
one half because the two alternatives come from the same prompt.
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
from genomic_watermarks.distinguishers import (  # noqa: E402
    DISTINGUISHERS,
    exact_cluster_sign_flip_p_value,
    leave_one_prompt_out_forced_choice,
    matched_draw_forced_choice,
)
from genomic_watermarks.pilot import (  # noqa: E402
    cohort_case_digest,
    load_context_cases_jsonl,
)
from genomic_watermarks.watermark import ORDINARY_SCHEME, PARTITION_MC_SCHEME  # noqa: E402

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-sequences", type=Path, required=True)
    parser.add_argument("--additional-sequences", type=Path, nargs="*", default=())
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--cohort-manifest", type=Path)
    parser.add_argument(
        "--matched-draws",
        action="store_true",
        help=(
            "pair each watermarked sequence with the ordinary sequence from its own generation "
            "draw; every sequences file must carry both arms. Required by the amended protocol, "
            "because a shared control lets a distinguisher learn that control's realization"
        ),
    )
    parser.add_argument("--bootstrap-replicates", type=int, default=20_000)
    parser.add_argument("--bootstrap-seed", type=int, default=2718)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def read_records(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def arm(records: list[dict[str, Any]], scheme: str) -> dict[str, str]:
    return {r["case_id"]: r["generated_dna"] for r in records if r["scheme"] == scheme}


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to replace existing output: {args.output}")

    base_bytes = args.base_sequences.read_bytes()
    base = read_records(args.base_sequences)
    if not base:
        raise ValueError("the base sequences file is empty")
    policy_id = base[0]["policy_id"]
    cohort_id = base[0]["cohort_id"]
    ordinary = arm(base, ORDINARY_SCHEME)
    if not ordinary:
        raise ValueError("the base sequences file must contain the ordinary control arm")

    watermarked_by_key = {"key_00": arm(base, PARTITION_MC_SCHEME)}
    ordinary_by_key = {"key_00": ordinary}
    key_sources = [
        {
            "key_label": "key_00",
            "path": str(args.base_sequences),
            "sha256": hashlib.sha256(base_bytes).hexdigest(),
        }
    ]
    for index, path in enumerate(sorted(args.additional_sequences), start=1):
        payload = path.read_bytes()
        records = read_records(path)
        if {r["policy_id"] for r in records} != {policy_id}:
            raise ValueError(f"{path} is for a different policy")
        label = f"key_{index:02d}"
        watermarked_by_key[label] = arm(records, PARTITION_MC_SCHEME)
        if args.matched_draws:
            control = arm(records, ORDINARY_SCHEME)
            if not control:
                raise ValueError(f"{path} holds no ordinary arm, which --matched-draws requires")
            ordinary_by_key[label] = control
        key_sources.append(
            {
                "key_label": label,
                "path": str(path),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )

    cohort_bytes = args.cohort_jsonl.read_bytes()
    cases = load_context_cases_jsonl(args.cohort_jsonl)
    known = {case.case_id for case in cases}
    missing = [case_id for case_id in ordinary if case_id not in known]
    if missing:
        raise ValueError(f"sequences reference unknown prompt(s): {', '.join(missing)}")

    started = time.perf_counter()
    pairs_by_draw = (
        {
            label: {
                case_id: (watermarked_by_key[label][case_id], ordinary_by_key[label][case_id])
                for case_id in ordinary_by_key[label]
            }
            for label in watermarked_by_key
        }
        if args.matched_draws
        else {}
    )

    results = []
    for name in sorted(DISTINGUISHERS):
        outcome = (
            matched_draw_forced_choice(pairs_by_draw, name)
            if args.matched_draws
            else leave_one_prompt_out_forced_choice(watermarked_by_key, ordinary, name)
        )
        draws_per_prompt = outcome.decisions // len(outcome.accuracy_by_prompt)
        exact = exact_cluster_sign_flip_p_value(
            {
                case_id: round(value * draws_per_prompt)
                for case_id, value in outcome.accuracy_by_prompt.items()
            },
            draws_per_prompt,
        )
        cluster = analyze_prompt_clusters(
            {case_id: (value,) for case_id, value in outcome.accuracy_by_prompt.items()},
            bootstrap_replicates=args.bootstrap_replicates,
            bootstrap_seed=args.bootstrap_seed,
        )
        results.append(
            {
                "distinguisher": name,
                "decisions": outcome.decisions,
                "correct": outcome.correct,
                "accuracy": outcome.accuracy,
                "accuracy_by_prompt": dict(outcome.accuracy_by_prompt),
                "exact_cluster_test": exact,
                "descriptive_prompt_cluster_bootstrap": {
                    "caveat": (
                        "descriptive only, and not a test: it resamples per-prompt accuracies as "
                        "if they were known, so it ignores within-prompt noise and can exclude "
                        "chance when the pooled count is unremarkable. Read exact_cluster_test."
                    ),
                    "mean": cluster.overall_mean,
                    "lower": cluster.interval_lower,
                    "upper": cluster.interval_upper,
                    "clusters": float(len(outcome.accuracy_by_prompt)),
                    "confidence_level": 0.95,
                    "replicates": float(args.bootstrap_replicates),
                    "seed": float(args.bootstrap_seed),
                },
            }
        )

    report: dict[str, Any] = {
        "schema_version": 1,
        "classification": "engineering_pilot_not_paper_evidence",
        "complete": True,
        "policy_id": policy_id,
        "cohort_id": cohort_id,
        "watermark_method": PARTITION_MC_SCHEME,
        "control_method": ORDINARY_SCHEME,
        "keys": len(watermarked_by_key),
        "key_sources": key_sources,
        "key_material": "published non-secret fixture keys with distinct indices",
        "observer_has_key": False,
        "pairing": (
            "each watermarked sequence is paired with the ordinary sequence from its own draw"
            if args.matched_draws
            else "every watermarked sequence shares one control, which the amendment rejects"
        ),
        "matched_draws": bool(args.matched_draws),
        "case_count": len(ordinary),
        "case_ids": sorted(ordinary),
        "generated_bases_per_case": len(next(iter(ordinary.values()))),
        "task": {
            "name": "paired two-alternative forced choice with leave-one-prompt-out fitting",
            "test": (
                "exact two-sided sign-flip over prompt clusters; a bootstrap over per-prompt "
                "accuracies is reported descriptively only and is not a valid test here"
            ),
            "chance_accuracy": 0.5,
            "tie_rule": "a tie counts as a miss, never as a coin flip",
            "decisions": len(ordinary) * len(watermarked_by_key),
        },
        "distinguishers": sorted(DISTINGUISHERS),
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
        "python": platform.python_version(),
        "platform": platform.platform(),
        "wall_seconds": time.perf_counter() - started,
        "results": results,
        "boundary": (
            "Three cheap unkeyed distinguishers on a small paired corpus. Failing to distinguish "
            "rules out these crude attacks and does not establish undetectability: a stronger "
            "classifier, more outputs per key, or an adaptive observer are all out of scope."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "policy_id": policy_id,
                "keys": len(watermarked_by_key),
                "accuracy": {r["distinguisher"]: r["accuracy"] for r in results},
                "exact_p_value": {
                    r["distinguisher"]: r["exact_cluster_test"]["p_value"] for r in results
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
