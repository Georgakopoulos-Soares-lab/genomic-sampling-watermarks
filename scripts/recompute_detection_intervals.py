#!/usr/bin/env python3
"""Recompute every detection-rate interval so it carries the threshold's uncertainty.

A detection rate is measured against a threshold estimated from null trials. The
intervals originally reported resampled only the positive prompt clusters, which
treats that threshold as known. This walks the stored per-trial rows of each
detection artifact and recomputes each cell's interval with a joint resample of
the nulls and the clusters. No experiment is re-run; the trials are read from the
completed artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.detector.search import joint_detection_rate_interval  # noqa: E402

POOLED_FAMILIES = ("wrong_key_watermarked", "any_key_ordinary")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, nargs="+", required=True)
    parser.add_argument("--target-fpr", type=float, default=0.01)
    parser.add_argument("--replicates", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=2718)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def cell_key(trial: dict[str, Any]) -> tuple[Any, ...]:
    """Group trials into the cell whose threshold they share."""

    return (
        trial.get("edit_rate"),
        trial.get("token_length"),
        trial.get("condition_id"),
        trial.get("search_id"),
    )


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to replace existing output: {args.output}")

    reports: list[dict[str, Any]] = []
    for path in args.input:
        payload = path.read_bytes()
        report = json.loads(payload)
        digest = hashlib.sha256(payload).hexdigest()
        policy = report.get("policy_id")
        del payload
        trials = report.get("trials")
        if not trials:
            raise ValueError(f"{path} stores no per-trial rows, so intervals cannot be recomputed")
        positives: dict[tuple[Any, ...], dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        nulls: dict[tuple[Any, ...], list[float]] = defaultdict(list)
        for trial in trials:
            key = cell_key(trial)
            if trial["family"] == "positive":
                positives[key][str(trial["case_id"])].append(float(trial["statistic"]))
            elif trial["family"] in POOLED_FAMILIES:
                nulls[key].append(float(trial["statistic"]))

        cells: list[dict[str, Any]] = []
        for key in sorted(positives, key=lambda k: tuple(str(part) for part in k)):
            if not nulls.get(key):
                continue
            joint = joint_detection_rate_interval(
                positives[key],
                nulls[key],
                args.target_fpr,
                replicates=args.replicates,
                seed=args.seed,
            )
            cells.append(
                {
                    "edit_rate": key[0],
                    "token_length": key[1],
                    "condition_id": key[2],
                    "search_id": key[3],
                    "base_length": key[1] * 6 if isinstance(key[1], int) else None,
                    **joint,
                }
            )
        reports.append(
            {
                "source_artifact": str(path),
                "source_sha256": digest,
                "policy_id": policy,
                "cells": cells,
            }
        )
        # Release the artifact before opening the next one; several store thousands of trials.
        del report, trials, positives, nulls

    thin = [
        {
            "source_artifact": r["source_artifact"],
            **{k: c[k] for k in ("edit_rate", "token_length", "condition_id", "search_id")},
            "detection_rate": c["detection_rate"],
            "lower": c["lower"],
            "upper": c["upper"],
        }
        for r in reports
        for c in r["cells"]
        if c["lower"] < 1.0 and c["detection_rate"] >= 1.0
    ]

    analysis = {
        "schema_version": 1,
        "classification": "engineering_analysis_pending_evidence_review",
        "method": (
            "joint resample: each replicate resamples the null trials, recalibrates the threshold "
            "from that resample, and independently resamples the positive prompt clusters"
        ),
        "why": (
            "resampling only the positive clusters treats an estimated threshold as known, which "
            "understates uncertainty when the positive and null distributions are close"
        ),
        "no_experiment_rerun": (
            "every statistic is read from the stored per-trial rows of a completed artifact"
        ),
        "target_false_positive_rate": args.target_fpr,
        "replicates": args.replicates,
        "seed": args.seed,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "reports": reports,
        "cells_where_a_unanimous_rate_is_not_reliably_unanimous": thin,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "artifacts": len(reports),
                "cells": sum(len(r["cells"]) for r in reports),
                "unanimous_but_uncertain_cells": len(thin),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
