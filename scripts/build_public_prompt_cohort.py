#!/usr/bin/env python3
"""Build the versioned public NCBI prompt cohort from its tracked manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.pilot import cohort_content_digest  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "data/public_prompt_cohort.yaml")
    parser.add_argument("--raw-root", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--processed-root", type=Path, default=ROOT / "data/processed")
    parser.add_argument("--offline", action="store_true")
    return parser.parse_args()


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as error:
        raise RuntimeError("install the optional 'dev' dependencies first") from error
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict) or loaded.get("schema_version") != 1:
        raise ValueError("unsupported public cohort manifest")
    return loaded


def parse_fasta(text: str) -> tuple[str, str]:
    lines = tuple(line.strip() for line in text.splitlines() if line.strip())
    if len(lines) < 2 or not lines[0].startswith(">"):
        raise ValueError("invalid FASTA response")
    sequence = "".join(lines[1:]).upper()
    if not sequence or any(base not in "ATCG" for base in sequence):
        raise ValueError("FASTA response contains empty or noncanonical DNA")
    return lines[0][1:], sequence


def sequence_sha256(sequence: str) -> str:
    return hashlib.sha256(sequence.encode("ascii")).hexdigest()


def cohort_sha256(prompts: list[dict[str, Any]]) -> str:
    return cohort_content_digest(
        (str(prompt["prompt_id"]), str(prompt["sequence_sha256"])) for prompt in prompts
    )


def fetch_fasta(url: str, *, attempts: int = 3) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "genomic-sampling-watermarks/0.1 public-cohort-builder"},
    )
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8")
        except (OSError, urllib.error.URLError) as error:
            if attempt == attempts:
                raise RuntimeError(
                    f"failed to fetch public FASTA after {attempts} attempts"
                ) from error
            time.sleep(float(attempt))
    raise AssertionError("unreachable")


def main() -> int:
    args = parse_args()
    manifest = load_manifest(args.manifest)
    cohort_id = str(manifest["cohort_id"])
    endpoint = str(manifest["source"]["endpoint"])
    expected_length = int(manifest["selection"]["window_length_bases"])
    raw_dir = args.raw_root / cohort_id
    processed_dir = args.processed_root / cohort_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    prompts: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for record in manifest["records"]:
        accession = str(record["accession"])
        for window in record["windows"]:
            prompt_id = str(window["id"])
            if prompt_id in seen_ids:
                raise ValueError(f"duplicate prompt ID: {prompt_id}")
            seen_ids.add(prompt_id)
            start = int(window["start"])
            stop = int(window["stop"])
            raw_path = raw_dir / f"{prompt_id}.fasta"
            if raw_path.is_file():
                fasta_text = raw_path.read_text(encoding="utf-8")
            elif args.offline:
                raise FileNotFoundError(f"missing cached FASTA: {raw_path}")
            else:
                query = urllib.parse.urlencode(
                    {
                        "db": "nuccore",
                        "id": accession,
                        "seq_start": start,
                        "seq_stop": stop,
                        "strand": 1,
                        "rettype": "fasta",
                        "retmode": "text",
                        "tool": "genomic_sampling_watermarks",
                    }
                )
                fasta_text = fetch_fasta(f"{endpoint}?{query}")
                raw_path.write_text(fasta_text, encoding="utf-8")
                time.sleep(0.4)

            header, sequence = parse_fasta(fasta_text)
            if accession not in header:
                raise ValueError(f"FASTA header for {prompt_id} does not contain {accession}")
            if len(sequence) != expected_length or len(sequence) != stop - start + 1:
                raise ValueError(f"unexpected sequence length for {prompt_id}")
            observed_sha256 = sequence_sha256(sequence)
            if observed_sha256 != str(window["sequence_sha256"]):
                raise ValueError(f"sequence checksum mismatch for {prompt_id}")
            prompts.append(
                {
                    "cohort_id": cohort_id,
                    "prompt_id": prompt_id,
                    "organism": str(record["organism"]),
                    "taxon_id": int(record["taxon_id"]),
                    "accession": accession,
                    "assembly": str(record["assembly"]),
                    "chromosome": str(record["chromosome"]),
                    "position_fraction": float(window["position_fraction"]),
                    "start": start,
                    "stop": stop,
                    "strand": "forward",
                    "sequence_sha256": observed_sha256,
                    "sequence": sequence,
                }
            )

    prompts_path = processed_dir / "prompts.jsonl"
    prompts_path.write_text(
        "".join(json.dumps(prompt, sort_keys=True) + "\n" for prompt in prompts),
        encoding="utf-8",
    )
    summary = {
        "schema_version": 1,
        "cohort_id": cohort_id,
        "prompt_count": len(prompts),
        "window_length_bases": expected_length,
        "cohort_sha256": cohort_sha256(prompts),
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "prompts_path": str(prompts_path.relative_to(ROOT)),
        "offline": args.offline,
    }
    (processed_dir / "provenance.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
