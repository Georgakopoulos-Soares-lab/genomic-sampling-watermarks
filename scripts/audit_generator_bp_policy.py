#!/usr/bin/env python3
"""Compare local G_bp math with the pinned GENERator base-marginal helper."""

from __future__ import annotations

import argparse
import json
import platform
import resource
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.metrics import total_variation_distance  # noqa: E402
from genomic_watermarks.models.huggingface import generator_prompt, load_adapter  # noqa: E402
from genomic_watermarks.models.policy_math import (  # noqa: E402
    base_marginals,
    canonical_softmax,
    product_distribution_from_base_marginals,
)
from genomic_watermarks.pilot import load_context_cases_jsonl, numeric_summary  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cohort-jsonl",
        type=Path,
        default=ROOT / "data/processed/ncbi_refseq_eukaryote_windows_v1/prompts.jsonl",
    )
    parser.add_argument("--cache-dir", default=".cache/huggingface")
    parser.add_argument("--device", choices=("mps", "cpu"), default="mps")
    parser.add_argument("--dtype", choices=("float32",), default="float32")
    parser.add_argument("--base-atol", type=float, default=1e-6)
    parser.add_argument("--token-atol", type=float, default=1e-7)
    parser.add_argument("--tv-atol", type=float, default=1e-5)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--local-files-only", action="store_true")
    return parser.parse_args()


def process_peak_rss_gib() -> float:
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    bytes_used = value if sys.platform == "darwin" else value * 1024.0
    return bytes_used / (1024.0**3)


def aggregate(rows: list[dict[str, Any]], name: str) -> dict[str, float]:
    return numeric_summary(float(row[name]) for row in rows)


def main() -> int:
    args = parse_args()
    if min(args.base_atol, args.token_atol, args.tv_atol) <= 0.0:
        raise ValueError("audit tolerances must be positive")

    try:
        import torch
    except ImportError as error:
        raise RuntimeError("install the optional 'models' dependencies first") from error

    cases = load_context_cases_jsonl(args.cohort_jsonl)
    load_started = time.perf_counter()
    adapter = load_adapter(
        "G_tok",
        device=args.device,
        dtype=args.dtype,
        allow_cpu_fallback=False,
        cache_dir=args.cache_dir,
        local_files_only=args.local_files_only,
    )
    load_seconds = time.perf_counter() - load_started
    model = adapter._model
    tokenizer = adapter._tokenizer
    vocabulary = adapter.canonical_vocabulary
    compute_bp_probs = getattr(model, "compute_bp_probs", None)
    if not callable(compute_bp_probs):
        raise RuntimeError("pinned GENERator model exposes no compute_bp_probs helper")

    upstream_kmer_ids = tuple(int(value) for value in model._kmer_ids.detach().cpu().tolist())
    if upstream_kmer_ids != vocabulary.ids:
        raise RuntimeError("upstream and local canonical k-mer ID orders differ")

    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    for case in cases:
        prompt = generator_prompt(case.sequence)
        inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False)
        inputs = {name: value.to(args.device) for name, value in inputs.items()}
        with torch.inference_mode():
            logits = model(**inputs, return_dict=True).logits[:, -1, :]

        direct = canonical_softmax(logits[0].detach().float().cpu().tolist(), vocabulary.ids)
        local_marginals = base_marginals(vocabulary.tokens, direct)
        upstream_tensor = compute_bp_probs(logits)[0].detach().float().cpu()
        upstream_marginals = tuple(
            tuple(float(value) for value in row) for row in upstream_tensor.tolist()
        )
        local_product = product_distribution_from_base_marginals(vocabulary.tokens, local_marginals)
        upstream_product = product_distribution_from_base_marginals(
            vocabulary.tokens, upstream_marginals
        )
        base_delta = max(
            abs(left - right)
            for local_row, upstream_row in zip(local_marginals, upstream_marginals, strict=True)
            for left, right in zip(local_row, upstream_row, strict=True)
        )
        token_delta = max(
            abs(left - right) for left, right in zip(local_product, upstream_product, strict=True)
        )
        tv_distance = total_variation_distance(local_product, upstream_product)
        rows.append(
            {
                "case_id": case.case_id,
                "source": {
                    "cohort_id": case.cohort_id,
                    "organism": case.organism,
                    "accession": case.accession,
                    "start": case.start,
                    "stop": case.stop,
                    "sequence_sha256": case.sequence_sha256,
                },
                "maximum_base_marginal_delta": base_delta,
                "maximum_token_probability_delta": token_delta,
                "total_variation_distance": tv_distance,
                "passed": (
                    base_delta <= args.base_atol
                    and token_delta <= args.token_atol
                    and tv_distance <= args.tv_atol
                ),
            }
        )
    audit_seconds = time.perf_counter() - started

    passed = all(bool(row["passed"]) for row in rows)
    report = {
        "schema_version": 1,
        "classification": "engineering_policy_equivalence_audit_not_paper_evidence",
        "comparison": "local_G_bp_vs_upstream_compute_bp_probs",
        "policy_id": "G_bp",
        "model_id": adapter.policy.model_id,
        "revision": adapter.policy.revision,
        "cohort_id": cases[0].cohort_id,
        "context_count": len(cases),
        "device": args.device,
        "dtype": args.dtype,
        "canonical_count": len(vocabulary.tokens),
        "canonical_ids_match": True,
        "tolerances": {
            "maximum_base_marginal_delta": args.base_atol,
            "maximum_token_probability_delta": args.token_atol,
            "total_variation_distance": args.tv_atol,
        },
        "passed": passed,
        "model_load_seconds": load_seconds,
        "audit_seconds": audit_seconds,
        "states_per_second": len(rows) / audit_seconds,
        "process_peak_rss_gib": process_peak_rss_gib(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "summary": {
            "maximum_base_marginal_delta": aggregate(rows, "maximum_base_marginal_delta"),
            "maximum_token_probability_delta": aggregate(rows, "maximum_token_probability_delta"),
            "total_variation_distance": aggregate(rows, "total_variation_distance"),
        },
        "contexts": rows,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
