#!/usr/bin/env python3
"""Assemble the runtime envelope from completed, already-cited experiment artifacts.

No new measurement is taken. Each source artifact's digest is verified against the
value the evidence ledger already cites, so a runtime claim cannot drift away from
the experiment that produced it. Memory fields are deliberately not summarized;
see the protocol document for why.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "evidence" / "measurements.yaml"
POLICIES = (("C_tok", "carbon_c_tok"), ("G_tok", "generator_g_tok"), ("G_bp", "generator_g_bp"))
MEMORY_FIELDS = (
    "process_peak_rss_gib",
    "mps_current_allocated_gib",
    "mps_driver_allocated_gib",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cited_digests() -> dict[str, str]:
    """Return every artifact digest the ledger already cites, keyed by path."""

    import yaml

    ledger = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
    found: dict[str, str] = {}
    for measurement in ledger["measurements"]:
        source = measurement.get("source", {})
        for key, value in source.items():
            if not key.endswith("_artifact"):
                continue
            digest_key = f"{key[: -len('artifact')]}sha256"
            if digest_key in source:
                found[str(value)] = str(source[digest_key])
    return found


def load_cited(path: Path, cited: dict[str, str]) -> dict[str, Any]:
    key = str(path.relative_to(ROOT)) if path.is_absolute() else str(path)
    expected = cited.get(key)
    if expected is None:
        raise ValueError(f"{key} is not cited by any admitted measurement")
    observed = digest(path)
    if observed != expected:
        raise ValueError(f"{key} digest {observed} does not match the cited {expected}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to replace existing output: {args.output}")
    cited = cited_digests()

    stages: list[dict[str, Any]] = []
    for policy, name in POLICIES:
        capacity = load_cited(ROOT / f"outputs/{name}_e2_sequential_v2.json", cited)
        generation = load_cited(ROOT / f"outputs/{name}_e4_generation_v1.json", cited)
        detection = load_cited(ROOT / f"outputs/{name}_e4_detection_v4.json", cited)
        generated_bases = int(generation["case_count"]) * int(
            generation["generated_bases_per_case"]
        )
        stages.append(
            {
                "policy_id": policy,
                "device": capacity["device"],
                "dtype": capacity["dtype"],
                "sequential_capacity": {
                    "artifact": f"outputs/{name}_e2_sequential_v2.json",
                    "sha256": digest(ROOT / f"outputs/{name}_e2_sequential_v2.json"),
                    "states": int(capacity["state_count"]),
                    "wall_seconds": float(capacity["wall_seconds"]),
                    "model_load_seconds": float(capacity["model_load_seconds"]),
                    "states_per_second": float(capacity["states_per_second"]),
                },
                "matched_generation": {
                    "artifact": f"outputs/{name}_e4_generation_v1.json",
                    "sha256": digest(ROOT / f"outputs/{name}_e4_generation_v1.json"),
                    "generated_bases_per_arm": generated_bases,
                    "wall_seconds": float(generation["wall_seconds"]),
                    "watermarked_seconds": float(generation["watermarked_seconds"]),
                    "ordinary_seconds": float(generation["ordinary_seconds"]),
                    "watermarked_bases_per_second": generated_bases
                    / float(generation["watermarked_seconds"]),
                },
                "clean_detection": {
                    "artifact": f"outputs/{name}_e4_detection_v4.json",
                    "sha256": digest(ROOT / f"outputs/{name}_e4_detection_v4.json"),
                    "trials": int(detection["trial_count"]),
                    "wall_seconds": float(detection["wall_seconds"]),
                    "trials_per_second": int(detection["trial_count"])
                    / float(detection["wall_seconds"]),
                    "uses_model": False,
                    "uses_gpu": False,
                },
            }
        )

    report = {
        "schema_version": 1,
        "classification": "engineering_summary_pending_evidence_review",
        "complete": True,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "measurement_note": (
            "Every runtime below was recorded by the experiment that produced it. This summary "
            "takes no new measurement and verifies each source digest against the value the "
            "evidence ledger already cites."
        ),
        "feasibility_not_benchmark": (
            "Single observations on one machine under uncontrolled desktop load. A feasibility "
            "envelope, not a benchmark, and no claim about other hardware."
        ),
        "memory_not_summarized": {
            "reason": (
                "None of the recorded memory fields supports a residency claim. Process peak RSS "
                "misses Metal-side allocations on unified memory; the current-allocated field is a "
                "point sample after the loop, not a peak; and the driver counter reports 52.31 GiB "
                "in the C_tok generation run on a 48 GiB machine, so it cannot be resident use."
            ),
            "fields_excluded": list(MEMORY_FIELDS),
            "open_item": (
                "Record a sampled high-water allocation during the loop alongside resident set "
                "size before admitting any memory figure."
            ),
        },
        "stages": stages,
        "totals": {
            "sequential_capacity_wall_seconds": sum(
                stage["sequential_capacity"]["wall_seconds"] for stage in stages
            ),
            "matched_generation_wall_seconds": sum(
                stage["matched_generation"]["wall_seconds"] for stage in stages
            ),
            "clean_detection_wall_seconds": sum(
                stage["clean_detection"]["wall_seconds"] for stage in stages
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"output": str(args.output), "stages": len(stages), **report["totals"]},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
