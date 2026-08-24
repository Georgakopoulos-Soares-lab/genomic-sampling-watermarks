#!/usr/bin/env python3
"""Validate an E15 order-sensitive proxy report and bind its provenance for review."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.pilot import cohort_case_digest, load_context_cases_jsonl  # noqa: E402
from genomic_watermarks.structure_report import validate_structure_report  # noqa: E402

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--attack-report", type=Path, help="the E11/E12 run this experiment prices")
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.validate_only and args.output is not None:
        raise ValueError("--output cannot be used with --validate-only")
    if not args.validate_only and args.output is None:
        raise ValueError("--output is required unless --validate-only is set")
    if args.output is not None and args.output.exists():
        raise FileExistsError(f"refusing to replace existing output: {args.output}")

    input_bytes = args.input.read_bytes()
    report = json.loads(input_bytes)
    cases = load_context_cases_jsonl(args.cohort_jsonl)
    validation = validate_structure_report(report, cases)
    if args.validate_only:
        print(json.dumps(validation, indent=2, sort_keys=True))
        return 0

    attack = None
    if args.attack_report is not None:
        raw = args.attack_report.read_bytes()
        loaded = json.loads(raw)
        if loaded["policy_id"] != report["policy_id"]:
            raise ValueError("the attack report is for a different policy")
        if loaded["experiment_label"] != report["experiment_label"]:
            raise ValueError("the attack report is for a different experiment label")
        if sorted(loaded["block_widths"]) != sorted(report["block_widths"]):
            raise ValueError("the attack report used different block widths")
        attack = {
            "path": str(args.attack_report),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "block_widths": loaded["block_widths"],
            "donor_counts": loaded["donor_counts"],
        }

    analysis = {
        "schema_version": 1,
        "classification": "engineering_analysis_pending_evidence_review",
        "input": {"path": str(args.input), "sha256": hashlib.sha256(input_bytes).hexdigest()},
        "provenance": {
            "policy_id": report["policy_id"],
            "experiment_label": report["experiment_label"],
            "attack_report": attack,
            "sequences": report["sequences"],
            "cohort": {
                **report["cohort"],
                "cohort_id": report["cohort_id"],
                "cohort_content_sha256_recomputed": cohort_case_digest(cases),
            },
            "reference_model": report["reference_model"],
            "independence_scope": (
                "The reference model is fitted only on cohort prompts that no detection experiment "
                "uses, checked by id rather than asserted. It is independent of the generator, the "
                "key, and the scored sequence, and it is not an independent biological model."
            ),
            "test_scope": (
                "The result of this experiment is the paired sign-flip p-value, not the relative "
                "shift. Relative shifts here are built from absolute differences and are large "
                "even"
                "where the direction is absent, so the p-value is recomputed from the stored rows "
                "during validation rather than trusted."
            ),
            "interpretation_boundary": report["interpretation_boundary"],
            "edit_scope": report["boundary"],
        },
        "validation": validation,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "input_valid": True,
                "policy_id": validation["policy_id"],
                "conditions_with_directional_orf_effect": validation[
                    "conditions_with_directional_orf_effect"
                ],
                "largest_independent_model_shift": round(
                    validation["largest_independent_model_shift"], 4
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
