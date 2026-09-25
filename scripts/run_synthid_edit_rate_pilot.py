#!/usr/bin/env python3
"""Edit-rate breakdown pilot (L1-07 pilot). PILOT ONLY — not admitted evidence.

Governed by docs/research/synthid_v3_edit_rate_pilot_protocol_2026_09_24.md, frozen
before any measurement. Reuses the existing frozen v2 reads; no regeneration, no GPU,
no detector tuning. The declared threat model still covers a single edit per read;
this locates where the single-edit guarantee stops holding.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.large_validation import (  # noqa: E402
    CALIBRATION_SPLIT_LABEL,
    deterministic_prompt_split,
    fixture_key,
)
from genomic_watermarks.pilot import load_context_cases_jsonl  # noqa: E402
from genomic_watermarks.synthid import SYNTHID_SCHEME  # noqa: E402
from genomic_watermarks.synthid_boundary import deterministic_multi_base_edit  # noqa: E402
from genomic_watermarks.synthid_position_independent import (  # noqa: E402
    PositionIndependentSynthIDConfig,
    detect_synthid_position_independent,
)
from genomic_watermarks.watermark import ORDINARY_SCHEME  # noqa: E402

EDIT_LABEL = "synthid-edit-rate-pilot/v1"
RATES = (0.0, 0.0003, 0.001, 0.005, 0.01, 0.02, 0.05, 0.10)
KINDS = ("substitution", "indel", "insertion", "deletion")
DRAWS = (0, 1)
CORRECT, NULL = "watermarked_correct_key", "ordinary_corresponding_key"


def evaluate(work: dict) -> list[dict]:
    label = work["edit_label"]
    config = PositionIndependentSynthIDConfig()
    prompt, case_id, records = work["prompt"], work["case_id"], work["records"]
    rows = []
    for draw_id in DRAWS:
        wm = records[f"{draw_id}:{SYNTHID_SCHEME}"]
        od = records[f"{draw_id}:{ORDINARY_SCHEME}"]
        domain = str(wm["stream_domain"])
        sources = {CORRECT: str(wm["generated_dna"]), NULL: str(od["generated_dna"])}
        for kind in KINDS:
            for rate in RATES:
                if rate == 0.0 and kind != KINDS[0]:
                    continue  # clean is shared; score it once
                for family, source in sources.items():
                    edit = deterministic_multi_base_edit(
                        source,
                        edit_rate=rate,
                        edit_kind=kind,
                        case_id=case_id,
                        draw_id=draw_id,
                        label=label,
                    )
                    result = detect_synthid_position_independent(
                        prompt + edit.sequence,
                        key=fixture_key(draw_id),
                        domain=domain,
                        config=config,
                    )
                    rows.append(
                        {
                            "case_id": case_id,
                            "draw_id": draw_id,
                            "edit_rate": rate,
                            "edit_kind": "clean" if rate == 0.0 else kind,
                            "edit_count": edit.edit_count,
                            "family": family,
                            "detected": bool(result.detected),
                            "sequence_p_value": float(result.sequence_p_value),
                            "sequence_log_p_value": float(result.sequence_log_p_value),
                            "bases_after_edit": len(edit.sequence),
                        }
                    )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-root", type=Path, required=True)
    parser.add_argument("--cohort-jsonl", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompts", type=int, default=96)
    parser.add_argument(
        "--edit-label",
        default=EDIT_LABEL,
        help="public edit-channel label; the full run uses a label distinct from the pilot",
    )
    parser.add_argument(
        "--classification",
        default="pilot_not_admitted_evidence",
        help="recorded in the artifact so a pilot can never be mistaken for admitted evidence",
    )
    parser.add_argument(
        "--protocol",
        default="docs/research/synthid_v3_edit_rate_pilot_protocol_2026_09_24.md",
    )
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    cases = load_context_cases_jsonl(args.cohort_jsonl)
    case_ids = [c.case_id for c in cases]
    split = deterministic_prompt_split(
        case_ids, calibration_prompts=64, label=CALIBRATION_SPLIT_LABEL
    )
    # Fixed digest order only; never a score-dependent choice.
    import hashlib

    evaluation = sorted(
        (c for c in case_ids if split[c] == "evaluation"),
        key=lambda v: hashlib.sha256(f"{CALIBRATION_SPLIT_LABEL}\x00{v}".encode()).digest(),
    )[: args.prompts]
    selected = set(evaluation)
    prompts = {c.case_id: c.sequence for c in cases if c.case_id in selected}

    records: dict[str, dict] = {c: {} for c in selected}
    for draw_id in DRAWS:
        path = args.validation_root / f"generation/draw_{draw_id:02d}_sequences.jsonl"
        for line in path.open(encoding="utf-8"):
            if not line.strip():
                continue
            row = json.loads(line)
            if row["case_id"] in selected:
                records[row["case_id"]][f"{draw_id}:{row['scheme']}"] = row

    work = [
        {"case_id": c, "prompt": prompts[c], "records": records[c],
         "edit_label": args.edit_label}
        for c in sorted(evaluation)
    ]
    started = time.perf_counter()
    rows: list[dict] = []
    if args.workers == 1:
        for item in work:
            rows.extend(evaluate(item))
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for result in pool.map(evaluate, work):
                rows.extend(result)

    cells: dict[tuple, dict] = {}
    for row in rows:
        key = (row["edit_kind"], row["edit_rate"], row["family"])
        cell = cells.setdefault(
            key,
            {
                "edit_kind": row["edit_kind"],
                "edit_rate": row["edit_rate"],
                "family": row["family"],
                "edit_count": row["edit_count"],
                "reads": 0,
                "detected": 0,
                "log_p": [],
            },
        )
        cell["reads"] += 1
        cell["detected"] += int(row["detected"])
        cell["log_p"].append(row["sequence_log_p_value"])
    for cell in cells.values():
        cell["rate"] = cell["detected"] / cell["reads"]
        ordered = sorted(cell.pop("log_p"))
        # Margin matters as much as the pass rate: it shows how much signal is left.
        cell["sequence_log_p_value"] = {
            "min": ordered[0],
            "median": ordered[len(ordered) // 2],
            "max": ordered[-1],
        }

    payload = {
        "schema_version": 1,
        "classification": args.classification,
        "study": "L1-07 pilot: detection power against edit rate",
        "protocol": args.protocol,
        "edit_label": args.edit_label,
        "prompts": len(evaluation),
        "draws": list(DRAWS),
        "rates": list(RATES),
        "kinds": list(KINDS),
        "detector_unchanged": True,
        "runtime_seconds": time.perf_counter() - started,
        "cells": sorted(cells.values(), key=lambda c: (c["family"], c["edit_kind"], c["edit_rate"])),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cells": len(cells), "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
