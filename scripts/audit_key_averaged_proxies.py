#!/usr/bin/env python3
"""E3 stage 2, key-averaged: compare arms after averaging proxies over independent keys.

Model-free. The fixed-key stage-2 run left an unresolved directional pattern,
because the construction is exact only in expectation over keys and one key is one
realization. This run averages each prompt's proxy over several independent
published keys and reports the spread across keys, which says how large the
fixed-key drift was.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
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
)
from genomic_watermarks.sequence_proxies import (  # noqa: E402
    PROXY_METRICS,
    key_averaged_proxy_comparison,
    symmetric_averaged_proxy_comparison,
)
from genomic_watermarks.watermark import ORDINARY_SCHEME, PARTITION_MC_SCHEME  # noqa: E402

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-sequences",
        type=Path,
        required=True,
        help="sequences file holding both arms; its watermarked arm is the first key",
    )
    parser.add_argument(
        "--additional-sequences",
        type=Path,
        nargs="+",
        required=True,
        help="watermarked-only sequences files, one per additional independent key",
    )
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--cohort-manifest", type=Path)
    parser.add_argument(
        "--symmetric",
        action="store_true",
        help=(
            "average both arms over independent draws; every sequences file must carry both arms "
            "and each draw must share neither its key nor its replay seed with another"
        ),
    )
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def read_records(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def arm(records: list[dict[str, Any]], scheme: str) -> dict[str, str]:
    return {r["case_id"]: r["generated_dna"] for r in records if r["scheme"] == scheme}


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to replace existing output: {args.output}")
    if not 0.0 < args.alpha < 1.0:
        raise ValueError("alpha must lie in (0, 1)")

    base_bytes = args.base_sequences.read_bytes()
    base = read_records(args.base_sequences)
    if not base:
        raise ValueError("the base sequences file is empty")
    policy_id = base[0]["policy_id"]
    cohort_id = base[0]["cohort_id"]
    ordinary = arm(base, ORDINARY_SCHEME)
    if not ordinary:
        raise ValueError("the base sequences file must contain the ordinary control arm")

    watermarked_by_key: dict[str, dict[str, str]] = {"key_00": arm(base, PARTITION_MC_SCHEME)}
    ordinary_by_key: dict[str, dict[str, str]] = {"key_00": ordinary}
    key_sources = [
        {
            "key_label": "key_00",
            "path": str(args.base_sequences),
            "sha256": hashlib.sha256(base_bytes).hexdigest(),
        }
    ]
    for index, path in enumerate(sorted(args.additional_sequences), start=1):
        payload = path.read_bytes()
        records = read_records(path)
        if not records:
            raise ValueError(f"{path} is empty")
        if {r["policy_id"] for r in records} != {policy_id}:
            raise ValueError(f"{path} is for a different policy")
        if {r["cohort_id"] for r in records} != {cohort_id}:
            raise ValueError(f"{path} is for a different cohort")
        label = f"key_{index:02d}"
        watermarked_by_key[label] = arm(records, PARTITION_MC_SCHEME)
        if not watermarked_by_key[label]:
            raise ValueError(f"{path} holds no watermarked arm")
        if args.symmetric:
            control = arm(records, ORDINARY_SCHEME)
            if not control:
                raise ValueError(f"{path} holds no ordinary arm, which --symmetric requires")
            ordinary_by_key[label] = control
        key_sources.append(
            {
                "key_label": label,
                "path": str(path),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )

    cohort_bytes = args.cohort_jsonl.read_bytes()
    cases = load_context_cases_jsonl(args.cohort_jsonl)
    known = {case.case_id for case in cases}
    missing = [case_id for case_id in ordinary if case_id not in known]
    if missing:
        raise ValueError(f"sequences reference unknown prompt(s): {', '.join(missing)}")

    started = time.perf_counter()
    if args.symmetric:
        comparison = symmetric_averaged_proxy_comparison(watermarked_by_key, ordinary_by_key)
    else:
        comparison = key_averaged_proxy_comparison(watermarked_by_key, ordinary)
    p_values = {metric: comparison[metric]["p_value"] for metric in PROXY_METRICS}
    family = summarize_p_values(p_values, args.alpha)

    report: dict[str, Any] = {
        "schema_version": 1,
        "classification": "engineering_pilot_not_paper_evidence",
        "complete": True,
        "policy_id": policy_id,
        "cohort_id": cohort_id,
        "watermark_method": PARTITION_MC_SCHEME,
        "control_method": ORDINARY_SCHEME,
        "keys": len(watermarked_by_key),
        "averaging": "symmetric, both arms" if args.symmetric else "watermarked arm only",
        "independence": (
            "each draw uses a distinct experiment label, so it shares neither its stream domain "
            "nor its residual-randomness seed with another draw"
            if args.symmetric
            else "keys differ but the residual-randomness seed may be shared; see the protocol"
        ),
        "key_sources": key_sources,
        "key_material": "published non-secret fixture keys with distinct indices",
        "case_count": len(ordinary),
        "case_ids": sorted(ordinary),
        "generated_bases_per_case": len(next(iter(ordinary.values()))),
        "metrics": list(PROXY_METRICS),
        "test": {
            "name": "exact two-sided sign-flip permutation test on averaged paired differences",
            "pairs": len(ordinary),
            "permutations": 2 ** len(ordinary),
            "statistic": "absolute mean paired difference of the key-averaged proxy",
            "alpha": args.alpha,
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
        "wall_seconds": time.perf_counter() - started,
        "averaged_comparison": comparison,
        "p_value_family": family,
        "boundary": (
            "Sequence composition and complexity proxies only, averaged over a small number of "
            "published keys. Closeness is not biological equivalence and supports no functional, "
            "viability, or safety inference. Averaging over keys removes fixed-key realization "
            "drift; it does not turn a proxy comparison into a test of sequence-level "
            "indistinguishability."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "policy_id": policy_id,
                "keys": len(watermarked_by_key),
                "prompts": len(ordinary),
                "rejections_at_alpha": family["rejections_at_alpha"],
                "rejections_at_bonferroni": family["rejections_at_bonferroni"],
                "minimum_p_value": family["minimum_p_value"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
