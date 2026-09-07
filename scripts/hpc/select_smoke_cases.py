#!/usr/bin/env python3
"""Select four deterministic smoke prompts covering split and negative-control paths."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.large_validation import deterministic_prompt_split  # noqa: E402
from genomic_watermarks.pilot import load_context_cases_jsonl  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort-jsonl", type=Path, required=True)
    parser.add_argument("--calibration-prompts", type=int, default=64)
    args = parser.parse_args()
    cases = load_context_cases_jsonl(args.cohort_jsonl)
    case_ids = tuple(case.case_id for case in cases)
    split = deterministic_prompt_split(case_ids, calibration_prompts=args.calibration_prompts)
    ranked_negative = sorted(
        case_ids,
        key=lambda case_id: hashlib.sha256(
            f"carbon-synthid-validation-v1/distribution-negative-control\x00{case_id}".encode()
        ).digest(),
    )
    chosen = [ranked_negative[0]]
    for needed_split in ("calibration", "evaluation"):
        if not any(split[case_id] == needed_split for case_id in chosen):
            chosen.append(
                next(case_id for case_id in sorted(case_ids) if split[case_id] == needed_split)
            )
    for case_id in sorted(case_ids):
        if case_id not in chosen:
            chosen.append(case_id)
        if len(chosen) == 4:
            break
    if len(chosen) != 4 or {split[case_id] for case_id in chosen} != {"calibration", "evaluation"}:
        raise RuntimeError("could not construct the required smoke subset")
    print("\n".join(chosen))
    return 0


if __name__ == "__main__":
    sys.exit(main())
