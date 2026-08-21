#!/usr/bin/env python3
"""E3 stage 2: compare matched watermarked and ordinary arms on sequence proxies.

Model-free. Reads a generated sequences file and reports, per proxy metric, the
paired per-prompt difference with an exact sign-flip permutation p-value, plus the
k-mer divergence between the two arms and between each arm and its prompt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.gof import summarize_p_values  # noqa: E402
from genomic_watermarks.pilot import (  # noqa: E402
    cohort_case_digest,
    load_context_cases_jsonl,
    numeric_summary,
)
from genomic_watermarks.sequence_proxies import (  # noqa: E402
    PROXY_METRICS,
    kmer_divergence_bits,
    paired_proxy_comparison,
    proxy_metrics,
)
from genomic_watermarks.watermark import ORDINARY_SCHEME, PARTITION_MC_SCHEME  # noqa: E402

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl"
DIVERGENCE_K = (1, 2, 3)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequences", type=Path, required=True)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--cohort-manifest", type=Path)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to replace existing output: {args.output}")
    if not 0.0 < args.alpha < 1.0:
        raise ValueError("alpha must lie in (0, 1)")

    sequence_bytes = args.sequences.read_bytes()
    records = [
        json.loads(line) for line in sequence_bytes.decode("utf-8").splitlines() if line.strip()
    ]
    if not records:
        raise ValueError("sequences file is empty")
    policies = {record["policy_id"] for record in records}
    labels = {record["experiment_label"] for record in records}
    cohorts = {record["cohort_id"] for record in records}
    if len(policies) != 1 or len(labels) != 1 or len(cohorts) != 1:
        raise ValueError("sequences file must hold one policy, label, and cohort")
    policy_id = records[0]["policy_id"]
    experiment_label = records[0]["experiment_label"]
    cohort_id = records[0]["cohort_id"]

    watermarked = {
        record["case_id"]: record["generated_dna"]
        for record in records
        if record["scheme"] == PARTITION_MC_SCHEME
    }
    ordinary = {
        record["case_id"]: record["generated_dna"]
        for record in records
        if record["scheme"] == ORDINARY_SCHEME
    }
    cohort_bytes = args.cohort_jsonl.read_bytes()
    cases = load_context_cases_jsonl(args.cohort_jsonl)
    cases_by_id = {case.case_id: case for case in cases}
    case_ids = tuple(sorted(watermarked))
    missing = [case_id for case_id in case_ids if case_id not in cases_by_id]
    if missing:
        raise ValueError(f"sequences reference unknown prompt(s): {', '.join(missing)}")

    run_started = time.perf_counter()
    comparison = paired_proxy_comparison(watermarked, ordinary)
    per_prompt: list[dict[str, Any]] = []
    for case_id in case_ids:
        prompt = cases_by_id[case_id].sequence
        per_prompt.append(
            {
                "case_id": case_id,
                "organism": cases_by_id[case_id].organism,
                "prompt_sequence_sha256": cases_by_id[case_id].sequence_sha256,
                "generated_bases": len(watermarked[case_id]),
                "watermarked": proxy_metrics(watermarked[case_id]),
                "ordinary": proxy_metrics(ordinary[case_id]),
                "arm_divergence_bits": {
                    f"k{k}": kmer_divergence_bits(watermarked[case_id], ordinary[case_id], k)
                    for k in DIVERGENCE_K
                },
                "watermarked_prompt_divergence_bits": {
                    f"k{k}": kmer_divergence_bits(watermarked[case_id], prompt, k)
                    for k in DIVERGENCE_K
                },
                "ordinary_prompt_divergence_bits": {
                    f"k{k}": kmer_divergence_bits(ordinary[case_id], prompt, k)
                    for k in DIVERGENCE_K
                },
            }
        )

    divergence_summary = {
        f"k{k}": {
            "arms": numeric_summary(row["arm_divergence_bits"][f"k{k}"] for row in per_prompt),
            "watermarked_versus_prompt": numeric_summary(
                row["watermarked_prompt_divergence_bits"][f"k{k}"] for row in per_prompt
            ),
            "ordinary_versus_prompt": numeric_summary(
                row["ordinary_prompt_divergence_bits"][f"k{k}"] for row in per_prompt
            ),
        }
        for k in DIVERGENCE_K
    }
    p_values = {metric: comparison[metric]["p_value"] for metric in PROXY_METRICS}
    family = summarize_p_values(p_values, args.alpha)

    report: dict[str, Any] = {
        "schema_version": 1,
        "classification": "engineering_pilot_not_paper_evidence",
        "complete": True,
        "policy_id": policy_id,
        "cohort_id": cohort_id,
        "experiment_label": experiment_label,
        "watermark_method": PARTITION_MC_SCHEME,
        "control_method": ORDINARY_SCHEME,
        "case_count": len(case_ids),
        "case_ids": list(case_ids),
        "generated_bases_per_case": len(watermarked[case_ids[0]]),
        "metrics": list(PROXY_METRICS),
        "divergence_k": list(DIVERGENCE_K),
        "test": {
            "name": "exact two-sided sign-flip permutation test on paired per-prompt differences",
            "pairs": len(case_ids),
            "permutations": 2 ** len(case_ids),
            "statistic": "absolute mean paired difference",
            "alpha": args.alpha,
        },
        "sequences": {
            "path": str(args.sequences),
            "sha256": hashlib.sha256(sequence_bytes).hexdigest(),
        },
        "cohort": {
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
        "python": platform.python_version(),
        "platform": platform.platform(),
        "wall_seconds": time.perf_counter() - run_started,
        "paired_comparison": comparison,
        "p_value_family": family,
        "arm_divergence_summary": divergence_summary,
        "per_prompt": per_prompt,
        "boundary": (
            "Sequence composition and complexity proxies only. Closeness is not biological "
            "equivalence and supports no functional, viability, or safety inference. The paired "
            "test detects a systematic shift between arms; it does not certify that no difference "
            "exists, and its power at this number of prompts is limited."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "policy_id": policy_id,
                "prompts": len(case_ids),
                "metrics_tested": len(PROXY_METRICS),
                "rejections_at_alpha": family["rejections_at_alpha"],
                "rejections_at_bonferroni": family["rejections_at_bonferroni"],
                "minimum_p_value": family["minimum_p_value"],
                "median_arm_divergence_bits_k3": statistics.median(
                    row["arm_divergence_bits"]["k3"] for row in per_prompt
                ),
                "wall_seconds": report["wall_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
