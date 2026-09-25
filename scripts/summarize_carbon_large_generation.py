#!/usr/bin/env python3
"""Validate and summarize completed Carbon large-validation draw artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.large_validation import sequence_identity, sha256_file  # noqa: E402
from genomic_watermarks.pilot import cohort_case_digest, load_context_cases_jsonl  # noqa: E402
from genomic_watermarks.synthid import SYNTHID_SCHEME  # noqa: E402
from genomic_watermarks.watermark import ORDINARY_SCHEME  # noqa: E402

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_large_v1/prompts.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--draw-index", type=int, action="append", default=[])
    parser.add_argument("--expected-case-count", type=int, required=True)
    parser.add_argument("--experiment-id", default="carbon_synthid_validation_v1")
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def main() -> int:
    args = parse_args()
    draw_indices = tuple(args.draw_index or range(2))
    if len(set(draw_indices)) != len(draw_indices) or any(
        index not in range(2) for index in draw_indices
    ):
        raise ValueError("draw indices must be unique values in 0..1")
    if args.expected_case_count <= 0:
        raise ValueError("expected-case-count must be positive")
    cases = load_context_cases_jsonl(args.cohort_jsonl)
    known_ids = {case.case_id for case in cases}
    identities: set[tuple[str, int, str]] = set()
    artifacts: list[dict[str, Any]] = []
    total_records = 0
    total_wall_seconds = 0.0
    total_model_generation_seconds = 0.0
    generated_tokens: set[int] = set()
    experiment_labels: set[str] = set()
    for draw_index in draw_indices:
        sequences_path = args.output_root / "generation" / f"draw_{draw_index:02d}_sequences.jsonl"
        report_path = args.output_root / "generation" / f"draw_{draw_index:02d}_generation.json"
        if not sequences_path.is_file() or not report_path.is_file():
            raise FileNotFoundError(f"missing finalized generation artifacts for draw {draw_index}")
        records = load_jsonl(sequences_path)
        if len(records) != args.expected_case_count * 2:
            raise ValueError(f"draw {draw_index} has the wrong sequence count")
        draw_case_ids = {str(record["case_id"]) for record in records}
        if len(draw_case_ids) != args.expected_case_count or not draw_case_ids <= known_ids:
            raise ValueError(f"draw {draw_index} has an invalid prompt set")
        for record in records:
            identity = sequence_identity(record)
            if identity in identities:
                raise ValueError(f"duplicate sequence identity: {identity}")
            identities.add(identity)
            if int(record["draw_id"]) != draw_index:
                raise ValueError("a sequence is stored under the wrong draw file")
            if (
                str(record.get("experiment_id", "carbon_synthid_validation_v1"))
                != args.experiment_id
            ):
                raise ValueError("a sequence has the wrong experiment ID")
            if str(record["policy_id"]) != "C_tok":
                raise ValueError("large validation accepts C_tok only")
            dna = str(record["generated_dna"])
            if set(dna) - set("ACGT") or len(dna) != int(record["generated_bases"]):
                raise ValueError("a generated sequence is noncanonical or has the wrong length")
            if hashlib.sha256(dna.encode("ascii")).hexdigest() != str(record["sequence_sha256"]):
                raise ValueError("a generated sequence checksum does not match")
            generated_tokens.add(int(record["generated_tokens"]))
            experiment_labels.add(str(record["experiment_label"]))
        counts = {
            scheme: sum(str(record["scheme"]) == scheme for record in records)
            for scheme in (SYNTHID_SCHEME, ORDINARY_SCHEME)
        }
        if set(counts.values()) != {args.expected_case_count}:
            raise ValueError(f"draw {draw_index} does not have matched arms")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if str(report["experiment_id"]) != args.experiment_id:
            raise ValueError("a draw report has the wrong experiment ID")
        if not bool(report.get("all_keyed_recomputations_match")):
            raise ValueError(f"draw {draw_index} failed keyed recomputation")
        artifacts.append(
            {
                "draw_id": draw_index,
                "fixture_key_index": draw_index,
                "sequences_path": str(sequences_path),
                "sequences_sha256": sha256_file(str(sequences_path)),
                "report_path": str(report_path),
                "report_sha256": sha256_file(str(report_path)),
                "sequence_count": len(records),
                "case_count": len(draw_case_ids),
                "wall_seconds": report["known_successful_session_wall_seconds"],
                "model_load_seconds": report["known_model_load_seconds"],
                "model_generation_seconds": report["model_generation_seconds"],
                "sequences_per_second": report["sequences_per_second"],
                "generated_bp_per_second": report["generated_bp_per_second"],
                "job_wall_sequences_per_second": report["job_wall_sequences_per_second"],
                "job_wall_generated_bp_per_second": report["job_wall_generated_bp_per_second"],
                "process_peak_rss_gib": report["peak_rss_gib"],
                "mps_driver_allocated_gib": report["peak_mps_driver_allocated_gib"],
                "cuda_peak_allocated_gib": report.get("peak_cuda_allocated_gib", 0.0),
                "cuda_peak_reserved_gib": report.get("peak_cuda_reserved_gib", 0.0),
            }
        )
        total_records += len(records)
        total_wall_seconds += float(report["known_successful_session_wall_seconds"])
        total_model_generation_seconds += float(report["model_generation_seconds"])
    if len(generated_tokens) != 1 or len(experiment_labels) != 1:
        raise ValueError("draws disagree on generation length or experiment label")
    steps = next(iter(generated_tokens))
    summary = {
        "schema_version": 1,
        "classification": "validation_artifact_not_admitted_evidence",
        "complete": True,
        "experiment_id": args.experiment_id,
        "experiment_label": next(iter(experiment_labels)),
        "policy_id": "C_tok",
        "model_id": "HuggingFaceBio/Carbon-500M",
        "revision": "9796b752108258c1d365089f842e62e6c0547704",
        "cohort_id": cases[0].cohort_id,
        "cohort_content_sha256": cohort_case_digest(cases),
        "draw_indices": list(draw_indices),
        "fixture_key_mapping": {str(index): index for index in draw_indices},
        "case_count": args.expected_case_count,
        "draws_per_case": len(draw_indices),
        "sequence_count": total_records,
        "watermarked_sequence_count": total_records // 2,
        "ordinary_sequence_count": total_records // 2,
        "generated_tokens_per_sequence": steps,
        "generated_bases_per_sequence": steps * 6,
        "total_generated_tokens": total_records * steps,
        "total_generated_bases": total_records * steps * 6,
        "autoregressive_model_forward_calls": total_records * steps,
        "known_successful_session_wall_seconds": total_wall_seconds,
        "model_generation_seconds": total_model_generation_seconds,
        "sequences_per_second": total_records / total_model_generation_seconds,
        "generated_bp_per_second": total_records * steps * 6 / total_model_generation_seconds,
        "job_wall_sequences_per_second": total_records / total_wall_seconds,
        "job_wall_generated_bp_per_second": total_records * steps * 6 / total_wall_seconds,
        "unique_sequence_identities": len(identities),
        "artifacts": artifacts,
        "artifact_sha256": {
            str(row["sequences_path"]): row["sequences_sha256"] for row in artifacts
        }
        | {str(row["report_path"]): row["report_sha256"] for row in artifacts},
        "boundary": (
            "Fixture keys are public reproducibility material. This summary validates generated "
            "artifacts but does not admit them to the evidence ledger."
        ),
    }
    output = args.output_root / "generation" / "generation_summary.json"
    serialized = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if output.exists() and output.read_text(encoding="utf-8") != serialized:
        raise FileExistsError(f"refusing to replace different output: {output}")
    if not output.exists():
        output.write_text(serialized, encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "sha256": sha256_file(str(output)),
                "case_count": args.expected_case_count,
                "sequence_count": total_records,
                "generated_bases": summary["total_generated_bases"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
