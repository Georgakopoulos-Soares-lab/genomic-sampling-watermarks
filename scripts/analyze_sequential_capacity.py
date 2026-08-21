#!/usr/bin/env python3
"""Validate a sequential E2 report and compute prompt-cluster uncertainty."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.cluster_analysis import analyze_prompt_clusters  # noqa: E402
from genomic_watermarks.pilot import (  # noqa: E402
    cohort_case_digest,
    load_context_cases_jsonl,
)
from genomic_watermarks.sequential_report import validate_sequential_report  # noqa: E402

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_v1/prompts.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--cohort-manifest", type=Path)
    parser.add_argument("--expected-states-per-prompt", type=int, default=128)
    parser.add_argument("--expected-partitions-per-state", type=int, default=32)
    parser.add_argument("--allow-prompt-subset", action="store_true")
    parser.add_argument("--bootstrap-replicates", type=int, default=20_000)
    parser.add_argument("--bootstrap-seed", type=int, default=2718)
    parser.add_argument("--interval-width-trigger", type=float, default=0.02)
    parser.add_argument("--leave-one-out-trigger", type=float, default=0.01)
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
    if args.interval_width_trigger <= 0.0 or args.leave_one_out_trigger <= 0.0:
        raise ValueError("expansion triggers must be positive")

    input_bytes = args.input.read_bytes()
    report = json.loads(input_bytes)
    cohort_bytes = args.cohort_jsonl.read_bytes()
    cases = load_context_cases_jsonl(args.cohort_jsonl)
    validation = validate_sequential_report(
        report,
        cases,
        expected_states_per_prompt=args.expected_states_per_prompt,
        expected_partitions_per_state=args.expected_partitions_per_state,
        allow_prompt_subset=args.allow_prompt_subset,
    )
    if args.validate_only:
        print(json.dumps(validation, indent=2, sort_keys=True))
        return 0

    values_by_prompt: dict[str, list[float]] = {case_id: [] for case_id in report["case_ids"]}
    for row in report["states"]:
        values_by_prompt[row["case_id"]].extend(
            float(value) for value in row["information_bits_per_base"]
        )
    cluster = analyze_prompt_clusters(
        values_by_prompt,
        bootstrap_replicates=args.bootstrap_replicates,
        bootstrap_seed=args.bootstrap_seed,
    )
    interval_expands = cluster.interval_width > args.interval_width_trigger
    leave_one_out_expands = cluster.maximum_leave_one_out_change > args.leave_one_out_trigger
    reasons: list[str] = []
    if interval_expands:
        reasons.append("prompt_cluster_interval_width")
    if leave_one_out_expands:
        reasons.append("leave_one_prompt_out_change")

    partition = report["partition_evaluation"]
    provenance = {
        "cohort": {
            "cohort_id": validation["cohort_id"],
            "prompt_count": validation["case_count"],
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
            "states_per_prompt": report["states_per_prompt"],
            "generated_bases_per_prompt": report["generated_bases_per_prompt"],
            "partitions_per_state": partition["partitions_per_state"],
            "partition_scheme": partition["scheme"],
            "partition_public_material_sha256": partition["public_material_sha256"],
            "partitions_paired_and_reused_across_states": partition[
                "paired_and_reused_across_states"
            ],
            "path_sampling_scheme": report["path_sampling"]["scheme"],
            "path_sampling_base_seed": report["path_sampling"]["base_seed"],
            "watermarked": report["path_sampling"]["watermarked"],
        },
        "metric": {
            "name": "maximal_coupling_information_bits_per_base",
            "definition": (
                "I(C; G) = h2(q) - 0.5 h2(|2q - 1|) for a fair latent bit and maximal coupling "
                "on a keyed balanced binary partition of the policy support, divided by six "
                "bases per 6-mer token"
            ),
            "unit": "bit/base",
            "upper_bound_bits_per_base": 1.0 / 6.0,
        },
        "uncertainty_scope": (
            "Prompt-cluster uncertainty over the 24 frozen public prompts, conditional on the "
            "32 fixed public evaluation partitions and the unwatermarked continuation path. "
            "Sequential states and partitions are not independent samples."
        ),
        "comparison_scope": (
            "Each policy uses its own policy-domain-separated partition fixtures, so a "
            "cross-policy difference is not attributable to watermarking alone."
        ),
    }

    analysis = {
        "schema_version": 2,
        "classification": "engineering_analysis_pending_evidence_review",
        "input": {
            "path": str(args.input),
            "sha256": hashlib.sha256(input_bytes).hexdigest(),
        },
        "provenance": provenance,
        "validation": validation,
        "cluster_unit": "prompt",
        "cluster_count": len(values_by_prompt),
        "cluster_means_information_bits_per_base": cluster.cluster_means,
        "overall_mean_information_bits_per_base": cluster.overall_mean,
        "prompt_cluster_bootstrap": {
            "method": "equal-weight prompt-cluster percentile bootstrap",
            "confidence_level": 0.95,
            "replicates": args.bootstrap_replicates,
            "seed": args.bootstrap_seed,
            "lower": cluster.interval_lower,
            "upper": cluster.interval_upper,
            "width": cluster.interval_width,
        },
        "leave_one_prompt_out": [
            {
                "case_id": case_id,
                "mean_information_bits_per_base": mean,
                "absolute_change_from_overall": abs(mean - cluster.overall_mean),
            }
            for case_id, mean in cluster.leave_one_out_means.items()
        ],
        "maximum_leave_one_prompt_out_change": cluster.maximum_leave_one_out_change,
        "expansion_rule": {
            "interval_width_trigger": args.interval_width_trigger,
            "leave_one_out_trigger": args.leave_one_out_trigger,
            "expand_prompt_cohort": bool(reasons),
            "reasons": reasons,
        },
    }
    rendered = json.dumps(analysis, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "input_valid": True,
                "cluster_count": len(values_by_prompt),
                "expand_prompt_cohort": bool(reasons),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
