#!/usr/bin/env python3
"""Validate an E8/E9 matched baseline comparison and bind its provenance for review."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.baseline_comparison_report import (  # noqa: E402
    NULL_FAMILIES,
    POOLED_FAMILIES,
    validate_baseline_comparison_report,
)
from genomic_watermarks.pilot import cohort_case_digest, load_context_cases_jsonl  # noqa: E402

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--partition-generation-report",
        type=Path,
        help="the E4 generation report that produced the partition_mc arm and the control",
    )
    parser.add_argument(
        "--baseline-generation-report",
        type=Path,
        help="the E8/E9 generation report that produced the its and exp arms",
    )
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--cohort-manifest", type=Path)
    parser.add_argument("--expected-offsets", type=int, default=8)
    parser.add_argument("--expected-null-keys", type=int, default=20)
    parser.add_argument("--expected-target-fpr", type=float, default=0.01)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def bind_generation(
    path: Path, report: dict[str, object], *, expected_label: str
) -> dict[str, object]:
    """Check a generation report against the comparison and return its bound provenance."""

    raw = path.read_bytes()
    loaded = json.loads(raw)
    if loaded["policy_id"] != report["policy_id"]:
        raise ValueError(f"{path} is for a different policy")
    if loaded["cohort_id"] != report["cohort_id"]:
        raise ValueError(f"{path} is for a different cohort")
    if loaded["experiment_label"] != expected_label:
        raise ValueError(f"{path} does not carry the experiment label the comparison scored")
    if not loaded["keyed_recomputation_matches_generation"]:
        raise ValueError(f"{path} did not verify keyed recomputation")
    return {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "experiment_label": loaded["experiment_label"],
        "model_id": loaded["model_id"],
        "revision": loaded["revision"],
        "device": loaded["device"],
        "dtype": loaded["dtype"],
        "temperature": loaded["temperature"],
        "truncation": loaded["truncation"],
        "generated_tokens_per_case": loaded["generated_tokens_per_case"],
        "generated_bases_per_case": loaded["generated_bases_per_case"],
        "key_source": loaded["key_source"],
        "keyed_recomputation_matches_generation": True,
    }


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
    validation = validate_baseline_comparison_report(
        report,
        cases,
        expected_offsets=args.expected_offsets,
        expected_null_keys=args.expected_null_keys,
        expected_target_fpr=args.expected_target_fpr,
    )
    if args.validate_only:
        print(json.dumps(validation, indent=2, sort_keys=True))
        return 0

    generation: dict[str, object] = {}
    if args.partition_generation_report is not None:
        generation["partition"] = bind_generation(
            args.partition_generation_report,
            report,
            expected_label=report["sequences"]["partition_experiment_label"],
        )
    if args.baseline_generation_report is not None:
        generation["baseline"] = bind_generation(
            args.baseline_generation_report,
            report,
            expected_label=report["sequences"]["baseline_experiment_label"],
        )

    analysis = {
        "schema_version": 1,
        "classification": "engineering_analysis_pending_evidence_review",
        "input": {
            "path": str(args.input),
            "sha256": hashlib.sha256(input_bytes).hexdigest(),
        },
        "provenance": {
            "policy_id": report["policy_id"],
            "methods": report["methods"],
            "generation": generation,
            "sequences": report["sequences"],
            "cohort": {
                **report["cohort"],
                "cohort_id": report["cohort_id"],
                "cohort_content_sha256_recomputed": cohort_case_digest(cases),
                "prompts_file_sha256_recomputed": hashlib.sha256(cohort_bytes).hexdigest(),
            },
            "detector": {
                "search": report["detector_search"],
                "hypotheses_searched": validation["hypotheses_searched"],
                "identical_search_across_methods": validation["identical_search_across_methods"],
                "support_size": report["support_size"],
                "key_source": report["key_source"],
                "null_key_source": report["null_key_source"],
                "null_keys": report["null_keys"],
                "decision_rule": report["decision_rule"],
            },
            "fairness_scope": (
                "All three methods score the identical declared search, so no method gains a "
                "cheaper threshold from a smaller multiplicity. Each is calibrated separately on "
                "its own nulls at the same target rate, because the three statistics are on "
                "different scales. Prompts, evaluated lengths, model policy, and the ordinary "
                "control are shared; only the sampler differs."
            ),
            "calibration_scope": (
                "Every threshold, false-positive rate, and p-value comes from null trials that "
                "repeat the identical declared search. No nominal per-hypothesis normal tail is "
                "used anywhere."
            ),
            "null_scope": (
                "Pooled null families are "
                + ", ".join(POOLED_FAMILIES)
                + ". The public-DNA family is reported separately and is not pooled into any "
                "threshold."
            ),
            "uncertainty_scope": (
                "Detection-rate intervals are joint: each replicate resamples the pooled nulls, "
                "recalibrates the threshold from that resample, and independently resamples the "
                "prompt clusters. Resampling only the clusters would treat an estimated threshold "
                "as known."
            ),
            "comparison_scope": (
                "Raw statistics must never be compared across methods. The per-token signal is "
                "derived and is expressed in units of each method's own null standard deviation, "
                "which is the only sense in which the three are on a common footing."
            ),
            "security_scope": (
                "Measured under a published non-secret fixture key. This is a power measurement, "
                "not a security claim: it says nothing about key reuse, many-output attacks, or "
                "adaptive removal, for any of the three methods."
            ),
            "edit_scope": (
                "Clean generated sequences only. Edit robustness for the two baselines is a "
                "separate experiment and nothing about it may be inferred from this comparison."
            ),
        },
        "validation": validation,
        "null_families": list(NULL_FAMILIES),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "input_valid": True,
                "policy_id": validation["policy_id"],
                "trial_count": validation["trial_count"],
                "identical_search_across_methods": validation["identical_search_across_methods"],
                "methods": [
                    {
                        "method": entry["method"],
                        "shortest_fully_detected_base_length": entry[
                            "shortest_fully_detected_base_length"
                        ],
                        "signal_per_token": [
                            round(row["signal_per_token"], 4) for row in entry["lengths"]
                        ],
                        "detection_rate": [row["detection_rate"] for row in entry["lengths"]],
                    }
                    for entry in validation["methods"]
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
