#!/usr/bin/env python3
"""Validate an E3 stage-1 preservation report and bind its provenance for review."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.pilot import (  # noqa: E402
    cohort_case_digest,
    load_context_cases_jsonl,
)
from genomic_watermarks.preservation_report import (  # noqa: E402
    ARMS,
    validate_preservation_report,
)

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--cohort-manifest", type=Path)
    parser.add_argument("--expected-draws", type=int, default=8_000)
    parser.add_argument("--expected-replicates", type=int, default=999)
    parser.add_argument("--expected-seed", type=int, default=2718)
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
    cohort_bytes = args.cohort_jsonl.read_bytes()
    cases = load_context_cases_jsonl(args.cohort_jsonl)
    validation = validate_preservation_report(
        report,
        cases,
        expected_draws=args.expected_draws,
        expected_replicates=args.expected_replicates,
        expected_seed=args.expected_seed,
    )
    if args.validate_only:
        print(json.dumps(validation, indent=2, sort_keys=True))
        return 0

    analysis = {
        "schema_version": 1,
        "classification": "engineering_analysis_pending_evidence_review",
        "input": {
            "path": str(args.input),
            "sha256": hashlib.sha256(input_bytes).hexdigest(),
        },
        "provenance": {
            "cohort": {
                "cohort_id": validation["cohort_id"],
                "state_count": validation["state_count"],
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
            "model": {
                "policy_id": report["policy_id"],
                "model_id": report["model_id"],
                "revision": report["revision"],
                "device": report["device"],
                "dtype": report["dtype"],
                "temperature": report["temperature"],
                "truncation": report["truncation"],
            },
            "protocol": {
                "watermark_method": report["watermark_method"],
                "control_method": report["control_method"],
                "key_source": report["key_source"],
                "stream_domain": report["stream_domain"],
                **{f"test_{name}": value for name, value in report["test"].items()},
            },
            "test_scope": (
                "Fixed-state one-step marginal test. Draws within a state are independent given "
                "that state; states are not independent genomic observations. A pass supports "
                "one-step marginal preservation at the tested states and is not evidence of "
                "sequence-level indistinguishability."
            ),
            "control_scope": (
                "The ordinary arm is a size control: ordinary sampling is the declared law, so a "
                "rejection there indicates a defect in the test or the declared-law extraction, "
                "not in the watermark."
            ),
            "multiplicity_scope": (
                "The family summary reports rejections at the nominal and Bonferroni levels for "
                "the declared number of states. It is not a single global test."
            ),
        },
        "validation": validation,
        "states": [
            {
                "case_id": row["case_id"],
                "entropy_bits": row["entropy_bits"],
                "effective_support": row["effective_support"],
                "top1_mass": row["top1_mass"],
                "watermarked_agreement_rate": row["watermarked_agreement_rate"],
                **{f"{arm}_p_value": row[arm]["p_value"] for arm in ARMS},
                **{f"{arm}_statistic": row[arm]["statistic"] for arm in ARMS},
            }
            for row in report["states"]
        ],
        "watermarked_p_value_family": report["watermarked_p_value_family"],
        "ordinary_p_value_family": report["ordinary_p_value_family"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "input_valid": True,
                "policy_id": validation["policy_id"],
                "state_count": validation["state_count"],
                "watermarked_rejections_at_bonferroni": validation[
                    "watermarked_rejections_at_bonferroni"
                ],
                "ordinary_rejections_at_bonferroni": validation[
                    "ordinary_rejections_at_bonferroni"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
