#!/usr/bin/env python3
"""Recompute every admitted detection-rate interval with the canonical null ordering.

The joint interval resamples the pooled null trials, and it originally indexed that
list in whatever order the caller concatenated the two null families. So the bounds
depended on a pooling order that carries no information, and two honest
recomputations of the same cell could disagree. `joint_detection_rate_interval` now
sorts the nulls, making the result a function of the null multiset.

This walks the existing joint-interval artifacts for their source lists, recomputes
every cell canonically into new versioned artifacts, and patches the ledger. No
experiment is re-run and no point estimate is touched; only interval bounds move,
and only by resampling noise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.detector.search import joint_detection_rate_interval  # noqa: E402

POOLED_FAMILIES = ("wrong_key_watermarked", "any_key_ordinary")
LEDGER = ROOT / "evidence/measurements.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--joint-artifact",
        type=Path,
        nargs="+",
        required=True,
        help="existing joint-interval artifacts, read only for their source lists",
    )
    parser.add_argument("--target-fpr", type=float, default=0.01)
    parser.add_argument("--replicates", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=2718)
    parser.add_argument("--output-suffix", default="canonical_v1")
    parser.add_argument(
        "--patch-ledger",
        action="store_true",
        help="rewrite interval bounds in evidence/measurements.yaml in place",
    )
    return parser.parse_args()


def cell_key(trial: dict[str, Any]) -> tuple[Any, ...]:
    return (
        trial.get("edit_rate"),
        trial.get("token_length"),
        trial.get("condition_id"),
        trial.get("search_id"),
    )


def recompute(source: Path, *, target_fpr: float, replicates: int, seed: int) -> dict[str, Any]:
    """Recompute every cell interval in one completed artifact."""

    payload = source.read_bytes()
    report = json.loads(payload)
    digest = hashlib.sha256(payload).hexdigest()
    policy = report.get("policy_id")
    del payload
    trials = report.get("trials")
    if not trials:
        raise ValueError(f"{source} stores no per-trial rows")
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
            positives[key], nulls[key], target_fpr, replicates=replicates, seed=seed
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
    del report, trials, positives, nulls
    return {
        # Repo-relative, so it matches how the ledger cites artifacts.
        "source_artifact": str(source.resolve().relative_to(ROOT)),
        "source_sha256": digest,
        "policy_id": policy,
        "cells": cells,
    }


def base_length_of(measurement_id: str) -> int | None:
    found = re.search(r"\.b(\d+)\.", measurement_id)
    return int(found.group(1)) if found else None


def lookup(
    cells: list[dict[str, Any]],
    *,
    edit_rate: float | None,
    base_length: int | None,
    condition_id: str | None,
    search_id: str | None,
) -> dict[str, Any] | None:
    """Find the single cell matching a ledger point, or None."""

    matches = [
        cell
        for cell in cells
        if (edit_rate is None or cell["edit_rate"] == edit_rate)
        and (base_length is None or cell["base_length"] == base_length)
        and (condition_id is None or cell["condition_id"] == condition_id)
        and (search_id is None or cell["search_id"] == search_id)
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def patch_ledger(
    cells_by_source: dict[str, list[dict[str, Any]]],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    """Rewrite interval bounds in place, preserving comments and formatting.

    The ledger is edited line by line rather than round-tripped through a YAML
    dumper, because a dump would lose the comments and folded scalars the file
    carries. A float can repeat many times in the file, so a text search for its
    value is ambiguous; instead each interval field's replacements are queued in
    document order and consumed in that order as the lines are walked, and every
    replacement asserts that the value it is about to overwrite is the value the
    parse said was there. The whole patch is re-parsed and re-checked afterwards,
    so a wrong ordering assumption cannot pass silently.
    """

    import yaml

    text = LEDGER.read_text(encoding="utf-8")
    ledger = yaml.safe_load(text)
    unmatched: list[str] = []
    checked = 0
    queued: dict[str, list[tuple[float, float]]] = defaultdict(list)

    def cells_for(measurement: dict[str, Any]) -> list[dict[str, Any]] | None:
        source = measurement.get("source") or {}
        for value in source.values():
            if isinstance(value, str) and value in cells_by_source:
                return cells_by_source[value]
        return None

    def apply(old: float, new: float, context: str) -> None:
        queued[context].append((float(old), float(new)))

    for measurement in ledger["measurements"]:
        cells = cells_for(measurement)
        if cells is None:
            continue
        default_base = base_length_of(measurement["id"])
        for point in (measurement.get("admitted_curve") or {}).get("points", []):
            cell = lookup(
                cells,
                edit_rate=point.get("edit_rate"),
                base_length=point.get("base_length", default_base),
                condition_id=None,
                search_id=None,
            )
            if cell is None:
                unmatched.append(f"{measurement['id']} curve {point.get('edit_rate')}")
                continue
            checked += 1
            apply(point["detection_rate_lower"], cell["lower"], "detection_rate_lower")
            apply(point["detection_rate_upper"], cell["upper"], "detection_rate_upper")
        for point in (measurement.get("admitted_paired_comparison") or {}).get("points", []):
            cell = lookup(
                cells,
                edit_rate=point.get("edit_rate"),
                base_length=default_base,
                condition_id=None,
                search_id="windowed",
            )
            if cell is None:
                unmatched.append(f"{measurement['id']} paired {point.get('edit_rate')}")
                continue
            checked += 1
            apply(
                point["windowed_detection_rate_lower"],
                cell["lower"],
                "windowed_detection_rate_lower",
            )
            apply(
                point["windowed_detection_rate_upper"],
                cell["upper"],
                "windowed_detection_rate_upper",
            )
        conditions = measurement.get("admitted_conditions") or {}
        search_id = conditions.get("search_id") or (
            "narrow"
            if ".narrow." in measurement["id"]
            else "wide"
            if ".wide." in measurement["id"]
            else None
        )
        for point in conditions.get("grid", []):
            cell = lookup(
                cells,
                edit_rate=None,
                base_length=None,
                condition_id=point.get("condition_id"),
                search_id=search_id,
            )
            if cell is None:
                unmatched.append(f"{measurement['id']} grid {point.get('condition_id')}")
                continue
            checked += 1
            apply(point["detection_rate_lower"], cell["lower"], "detection_rate_lower")
            apply(point["detection_rate_upper"], cell["upper"], "detection_rate_upper")

    pending = {field: iter(pairs) for field, pairs in queued.items()}
    fields = tuple(queued)
    pattern = re.compile(r"^(\s*)(" + "|".join(fields) + r"):\s*(\S+)\s*$") if fields else None
    moved: list[dict[str, Any]] = []
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        found = pattern.match(line) if pattern is not None else None
        if found is None:
            continue
        indent, field, raw = found.group(1), found.group(2), found.group(3)
        try:
            old, new = next(pending[field])
        except StopIteration:
            raise ValueError(
                f"{field} appears more often in the file than the parse produced"
            ) from None
        if float(raw) != old:
            raise ValueError(
                f"document order does not match the parse at {field}: file {raw}, parse {old}"
            )
        if new != old:
            lines[index] = f"{indent}{field}: {new!r}\n"
            moved.append({"field": field, "from": old, "to": new})
    for field, remaining in pending.items():
        leftover = list(remaining)
        if leftover:
            raise ValueError(f"{field} had {len(leftover)} queued replacement(s) with no line")

    patched = "".join(lines)
    if not dry_run and moved:
        LEDGER.write_text(patched, encoding="utf-8")
        # Re-parse and confirm every interval field now equals its canonical value,
        # so a wrong ordering assumption cannot survive the run.
        reloaded = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
        residual = 0
        for before, after in zip(ledger["measurements"], reloaded["measurements"], strict=True):
            _require_same_shape(before, after)
        for measurement in reloaded["measurements"]:
            cells = cells_for(measurement)
            if cells is None:
                continue
            default_base = base_length_of(measurement["id"])
            for point in (measurement.get("admitted_curve") or {}).get("points", []):
                cell = lookup(
                    cells,
                    edit_rate=point.get("edit_rate"),
                    base_length=point.get("base_length", default_base),
                    condition_id=None,
                    search_id=None,
                )
                if cell is None:
                    continue
                residual += point["detection_rate_lower"] != cell["lower"]
                residual += point["detection_rate_upper"] != cell["upper"]
        if residual:
            raise ValueError(f"{residual} interval field(s) did not take the canonical value")
    return {
        "points_checked": checked,
        "bounds_moved": len(moved),
        "moved": moved,
        "unmatched": unmatched,
        "largest_shift": max((abs(m["to"] - m["from"]) for m in moved), default=0.0),
        "written": bool(moved) and not dry_run,
    }


def _require_same_shape(before: Any, after: Any) -> None:
    """Fail if the patch changed anything other than a float."""

    if isinstance(before, dict):
        if set(before) != set(after):
            raise ValueError("the patch changed a measurement's keys")
        for key in before:
            _require_same_shape(before[key], after[key])
    elif isinstance(before, list):
        if len(before) != len(after):
            raise ValueError("the patch changed a list length")
        for left, right in zip(before, after, strict=True):
            _require_same_shape(left, right)
    elif not isinstance(before, float) and before != after:
        raise ValueError(f"the patch changed a non-float value: {before!r} -> {after!r}")


def main() -> int:
    args = parse_args()
    sources: list[Path] = []
    for path in args.joint_artifact:
        for report in json.loads(path.read_text(encoding="utf-8"))["reports"]:
            candidate = ROOT / report["source_artifact"]
            if candidate not in sources:
                sources.append(candidate)

    cells_by_source: dict[str, list[dict[str, Any]]] = {}
    recomputed: list[dict[str, Any]] = []
    for source in sources:
        result = recompute(
            source, target_fpr=args.target_fpr, replicates=args.replicates, seed=args.seed
        )
        cells_by_source[result["source_artifact"]] = result["cells"]
        recomputed.append(result)

    output = ROOT / f"outputs/joint_intervals_{args.output_suffix}.json"
    if output.exists():
        raise FileExistsError(f"refusing to replace existing output: {output}")
    analysis = {
        "schema_version": 1,
        "classification": "engineering_analysis_pending_evidence_review",
        "method": (
            "joint resample with a canonical null ordering: the pooled nulls are sorted before "
            "resampling, each replicate recalibrates the threshold from that resample, and the "
            "positive prompt clusters are resampled independently"
        ),
        "why": (
            "the previous interval indexed the pooled null list in the order the caller built it, "
            "so the bounds depended on which null family was concatenated first"
        ),
        "no_experiment_rerun": (
            "every statistic is read from the stored per-trial rows of a completed artifact"
        ),
        "target_false_positive_rate": args.target_fpr,
        "replicates": args.replicates,
        "seed": args.seed,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "reports": recomputed,
    }
    patch = patch_ledger(cells_by_source, dry_run=not args.patch_ledger)
    analysis["ledger_patch"] = patch
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "artifacts": len(recomputed),
                "cells": sum(len(r["cells"]) for r in recomputed),
                "ledger_patch": patch,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
