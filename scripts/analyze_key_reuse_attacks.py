#!/usr/bin/env python3
"""Validate an E11/E12 key-reuse attack report and bind its provenance for review."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.attack_report import (  # noqa: E402
    POOLED_FAMILIES,
    validate_attack_report,
)
from genomic_watermarks.pilot import cohort_case_digest, load_context_cases_jsonl  # noqa: E402

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--generation-report", type=Path)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--expected-offsets", type=int, default=8)
    parser.add_argument("--expected-null-keys", type=int, default=20)
    parser.add_argument("--expected-target-fpr", type=float, default=0.01)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def utility_summary(report: dict) -> list[dict]:
    """Largest relative proxy shift per attack, so removal is never priced at zero."""

    proxies = list(report["proxy_metrics"])
    groups: dict[tuple, list[dict]] = {}
    for row in report["utility_rows"]:
        groups.setdefault((row["attack"], row["parameter"]), []).append(row)
    out = []
    for key in sorted(groups, key=lambda k: (str(k[0]), -1 if k[1] is None else k[1])):
        rows = groups[key]
        relative = {}
        for metric in proxies:
            shift = statistics.fmean(
                abs(r["proxies"][metric] - r["reference_proxies"][metric]) for r in rows
            )
            base = statistics.fmean(abs(r["reference_proxies"][metric]) for r in rows) or 1.0
            relative[metric] = shift / base
        worst = max(relative, key=lambda m: relative[m])
        out.append(
            {
                "attack": key[0],
                "parameter": key[1],
                "rows": len(rows),
                "largest_relative_proxy_shift": relative[worst],
                "largest_shift_metric": worst,
                "relative_proxy_shift": relative,
            }
        )
    return out


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
    validation = validate_attack_report(
        report,
        cases,
        expected_offsets=args.expected_offsets,
        expected_null_keys=args.expected_null_keys,
        expected_target_fpr=args.expected_target_fpr,
    )
    utility = utility_summary(report)
    if args.validate_only:
        print(json.dumps({**validation, "utility": utility}, indent=2, sort_keys=True))
        return 0

    generation = None
    if args.generation_report is not None:
        raw = args.generation_report.read_bytes()
        loaded = json.loads(raw)
        if loaded["policy_id"] != report["policy_id"]:
            raise ValueError("the generation report is for a different policy")
        if loaded["experiment_label"] != report["experiment_label"]:
            raise ValueError("the generation report is for a different experiment label")
        if not loaded["keyed_recomputation_matches_generation"]:
            raise ValueError("the generation report did not verify keyed recomputation")
        generation = {
            "path": str(args.generation_report),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "model_id": loaded["model_id"],
            "revision": loaded["revision"],
            "device": loaded["device"],
            "dtype": loaded["dtype"],
            "generated_bases_per_case": loaded["generated_bases_per_case"],
            "key_source": loaded["key_source"],
        }

    analysis = {
        "schema_version": 1,
        "classification": "engineering_analysis_pending_evidence_review",
        "input": {"path": str(args.input), "sha256": hashlib.sha256(input_bytes).hexdigest()},
        "provenance": {
            "policy_id": report["policy_id"],
            "experiment_label": report["experiment_label"],
            "generation": generation,
            "sequences": report["sequences"],
            "cohort": {
                **report["cohort"],
                "cohort_id": report["cohort_id"],
                "cohort_content_sha256_recomputed": cohort_case_digest(cases),
            },
            "detector": {
                "search": report["detector_search"],
                "decision_rule": report["decision_rule"],
                "null_keys": report["null_keys"],
            },
            "attacker_model": report["attacker_knowledge"],
            "calibration_scope": (
                "Attacked sequences are scored against a threshold calibrated on the "
                + " and ".join(POOLED_FAMILIES)
                + " families of unattacked sequences. Calibrating on attacked material would "
                "measure a different question."
            ),
            "sign_scope": report["sign_of_the_result"],
            "utility_scope": (
                "The nine admitted proxies are composition and complexity statistics. The removal "
                "attacks permute whole 6-mers, so they preserve the 6-mer multiset exactly and "
                "these proxies are nearly blind to them by construction. A small proxy shift is "
                "therefore evidence about the proxies, not proof that the attack is free: the "
                "declared but unimplemented ORF and independent-model-likelihood proxies are what "
                "would price the long-range structure a rearrangement destroys."
            ),
            "security_scope": (
                "Measured under a published non-secret fixture key against one construction and "
                "one attacker. These are measurements, not a security reduction."
            ),
            "edit_scope": (
                "Clean sequences only; no attack is composed with substitutions or indels."
            ),
        },
        "validation": validation,
        "utility": utility,
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
                "lengths": [
                    {
                        "base_length": e["base_length"],
                        "genuine": e["genuine_detection_rate"],
                        "spoof_minimum": e["spoof_detection_rate_minimum"],
                        "spoof_matches_genuine": e["spoof_matches_genuine"],
                    }
                    for e in validation["lengths"]
                ],
                "largest_relative_proxy_shift": max(
                    row["largest_relative_proxy_shift"] for row in utility
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
