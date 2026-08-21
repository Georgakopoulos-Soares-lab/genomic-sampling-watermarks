#!/usr/bin/env python3
"""Validate an edit-robustness report and bind its provenance for review."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.edit_report import (  # noqa: E402
    POOLED_FAMILIES,
    validate_edit_report,
)
from genomic_watermarks.pilot import (  # noqa: E402
    cohort_case_digest,
    load_context_cases_jsonl,
)

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--generation-report", type=Path)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--cohort-manifest", type=Path)
    parser.add_argument("--expected-offsets", type=int, default=8)
    parser.add_argument("--expected-null-keys", type=int, default=8)
    parser.add_argument("--expected-replicates", type=int, default=5)
    parser.add_argument("--expected-target-fpr", type=float, default=0.01)
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
    validation = validate_edit_report(
        report,
        cases,
        expected_offsets=args.expected_offsets,
        expected_null_keys=args.expected_null_keys,
        expected_replicates=args.expected_replicates,
        expected_target_fpr=args.expected_target_fpr,
    )
    if args.validate_only:
        print(json.dumps(validation, indent=2, sort_keys=True))
        return 0

    generation: dict[str, object] | None = None
    if args.generation_report is not None:
        generation_bytes = args.generation_report.read_bytes()
        loaded = json.loads(generation_bytes)
        if loaded["policy_id"] != report["policy_id"]:
            raise ValueError("the generation report is for a different policy")
        if loaded["experiment_label"] != report["generation_experiment_label"]:
            raise ValueError("the generation report is for a different generation label")
        if loaded["cohort_id"] != report["cohort_id"]:
            raise ValueError("the generation report is for a different cohort")
        if loaded["sequences_path"] != report["sequences"]["path"]:
            raise ValueError("the generation report wrote a different sequences file")
        if not loaded["keyed_recomputation_matches_generation"]:
            raise ValueError("the generation report did not verify keyed recomputation")
        generation = {
            "path": str(args.generation_report),
            "sha256": hashlib.sha256(generation_bytes).hexdigest(),
            "model_id": loaded["model_id"],
            "revision": loaded["revision"],
            "device": loaded["device"],
            "dtype": loaded["dtype"],
            "temperature": loaded["temperature"],
            "truncation": loaded["truncation"],
            "generated_bases_per_case": loaded["generated_bases_per_case"],
            "key_source": loaded["key_source"],
            "keyed_recomputation_matches_generation": True,
        }

    analysis = {
        "schema_version": 1,
        "classification": "engineering_analysis_pending_evidence_review",
        "input": {
            "path": str(args.input),
            "sha256": hashlib.sha256(input_bytes).hexdigest(),
        },
        "provenance": {
            "policy_id": report["policy_id"],
            "experiment_label": report["experiment_label"],
            "generation": generation,
            "sequences": report["sequences"],
            "cohort": {
                **report["cohort"],
                "cohort_id": report["cohort_id"],
                "cohort_content_sha256_recomputed": cohort_case_digest(cases),
                "prompts_file_sha256_recomputed": hashlib.sha256(cohort_bytes).hexdigest(),
            },
            "edit": {
                "channel": report["edit"],
                "rates": report["edit_rates"],
                "seed_scheme": report["edit_seed_scheme"],
                "positive_replicates_per_prompt": report["positive_replicates_per_prompt"],
                "model": (
                    "Independent per-base substitution to a different base. A statistical channel, "
                    "not a model of mutation, sequencing error, or synthesis error, and no "
                    "biological inference may be drawn from it."
                )
                if report["edit"] == "substitution"
                else "See the protocol document for this channel's declared model.",
            },
            "detector": {
                "search": report["detector_search"],
                "hypotheses_searched": validation["hypotheses_searched"],
                "support_size": report["support_size"],
                "unchanged_from_clean_pilot": True,
                "key_source": report["key_source"],
                "null_key_source": report["null_key_source"],
                "null_keys": report["null_keys"],
            },
            "calibration_scope": (
                "Thresholds are calibrated per edit rate and per length, from nulls that went "
                "through the same edit process, by repeating the identical declared search. "
                "Pooled families are " + ", ".join(POOLED_FAMILIES) + "."
            ),
            "null_invariance_scope": (
                "Under a wrong key each observed token's group is a fair coin whether or not its "
                "bases were edited, so the null distribution should not depend on the rate. The "
                "per-rate null summaries are reported so this can be checked rather than assumed."
            ),
            "uncertainty_scope": (
                "Detection-rate intervals resample the prompt clusters and average edit replicates "
                "within a prompt. Replicates and null keys are not independent clusters."
            ),
            "security_scope": (
                "Measured under a published non-secret fixture key. A power measurement under a "
                "random edit channel, not resistance to an adversary who chooses where to edit."
            ),
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
                "edit": validation["edit"],
                "trial_count": validation["trial_count"],
                "maximum_fully_detected_rate_by_length": validation[
                    "maximum_fully_detected_rate_by_length"
                ],
                "null_mean_spread_by_length": {
                    length: value["null_mean_spread"]
                    for length, value in validation["null_invariance_by_length"].items()
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
