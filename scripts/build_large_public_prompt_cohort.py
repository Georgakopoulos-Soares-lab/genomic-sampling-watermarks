#!/usr/bin/env python3
"""Freeze, build, or verify the 256-window public RefSeq large cohort.

The initial ``--freeze-manifest`` mode applies the tracked output-blind source
and coordinate rule, fetches only small public RefSeq spans, and writes a
checksum-complete candidate manifest.  Normal and ``--offline`` modes rebuild
the ignored prompt JSONL from that frozen manifest without changing selection.
"""

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

DEFAULT_SOURCE_SPEC = ROOT / "data/public_prompt_cohort_large_v1_sources.yaml"
DEFAULT_MANIFEST = ROOT / "data/public_prompt_cohort_large_v1.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-spec", type=Path, default=DEFAULT_SOURCE_SPEC)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--freeze-manifest",
        type=Path,
        help="initial-fetch mode: write a new checksum-complete manifest and stop",
    )
    parser.add_argument("--raw-root", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--processed-root", type=Path, default=ROOT / "data/processed")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--request-interval-seconds", type=float, default=0.36)
    return parser.parse_args()


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as error:
        raise RuntimeError("install the optional 'dev' dependencies first") from error
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict) or int(loaded.get("schema_version", -1)) != 1:
        raise ValueError(f"unsupported cohort YAML: {path}")
    return loaded


def write_yaml(path: Path, value: dict[str, Any]) -> None:
    try:
        import yaml
    except ImportError as error:
        raise RuntimeError("install the optional 'dev' dependencies first") from error
    if path.exists():
        raise FileExistsError(f"refusing to replace existing manifest: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False, width=100), encoding="utf-8")


def parse_fasta(text: str) -> tuple[str, str]:
    lines = tuple(line.strip() for line in text.splitlines() if line.strip())
    if len(lines) < 2 or not lines[0].startswith(">"):
        raise ValueError("invalid FASTA response")
    return lines[0][1:], "".join(lines[1:]).upper()


def sequence_sha256(sequence: str) -> str:
    return hashlib.sha256(sequence.encode("ascii")).hexdigest()


def fetch_text(url: str, *, attempts: int = 4) -> str:
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
                raise RuntimeError(f"failed to fetch public NCBI data: {url}") from error
            time.sleep(float(attempt))
    raise AssertionError("unreachable")


def efetch_url(endpoint: str, accession: str, start: int, stop: int) -> str:
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
    return f"{endpoint}?{query}"


def candidate_coordinates(
    *,
    record_length: int,
    span_length: int,
    segment_index: int,
    segments: int,
    selection_label: str,
    accession: str,
    attempt: int,
) -> tuple[int, int, int, int]:
    """Map a public digest into starts whose complete span fits one segment."""

    if not 0 <= segment_index < segments:
        raise ValueError("segment index is outside the declared segment count")
    segment_start = (segment_index * record_length) // segments + 1
    segment_stop = ((segment_index + 1) * record_length) // segments
    latest_start = segment_stop - span_length + 1
    if latest_start < segment_start:
        raise ValueError("a declared segment is shorter than the source span")
    digest = hashlib.sha256(
        f"{selection_label}\x00{accession}\x00{segment_index:02d}\x00{attempt:02d}".encode()
    ).digest()
    choices = latest_start - segment_start + 1
    start = segment_start + int.from_bytes(digest[:8], "big") % choices
    return start, start + span_length - 1, segment_start, segment_stop


def validate_source_spec(spec: dict[str, Any]) -> None:
    selection = spec["selection"]
    records = spec["records"]
    if int(selection["record_count"]) != len(records):
        raise ValueError("record count does not match the source list")
    expected = int(selection["record_count"]) * int(selection["windows_per_record"])
    if int(selection["prompt_count"]) != expected:
        raise ValueError("prompt count does not match records times windows")
    accessions = [str(record["accession"]) for record in records]
    prefixes = [str(record["id_prefix"]) for record in records]
    if len(set(accessions)) != len(accessions) or len(set(prefixes)) != len(prefixes):
        raise ValueError("record accessions and ID prefixes must be unique")
    if any("." not in accession for accession in accessions):
        raise ValueError("every accession must include a frozen version")
    if int(selection["prompt_length_bases"]) != 384:
        raise ValueError("the frozen large cohort requires 384-base prompts")
    if int(selection["source_span_length_bases"]) < int(selection["prompt_length_bases"]):
        raise ValueError("the source span must contain the complete prompt")
    if bool(selection["selection_used_model_output"]):
        raise ValueError("cohort selection must not use model output")


def freeze_manifest(args: argparse.Namespace) -> dict[str, Any]:
    if args.offline:
        raise ValueError("--offline cannot be combined with initial manifest freezing")
    spec = load_yaml(args.source_spec)
    validate_source_spec(spec)
    selection = spec["selection"]
    endpoint = str(spec["source"]["endpoint"])
    cohort_id = str(spec["cohort_id"])
    raw_dir = args.raw_root / cohort_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    segments = int(selection["windows_per_record"])
    span_length = int(selection["source_span_length_bases"])
    prompt_length = int(selection["prompt_length_bases"])
    retries = int(selection["maximum_canonical_retries"])
    label = str(selection["selection_label"])
    frozen_records: list[dict[str, Any]] = []

    for record in spec["records"]:
        accession = str(record["accession"])
        frozen_record = {key: value for key, value in record.items() if key != "id_prefix"}
        windows: list[dict[str, Any]] = []
        for segment_index in range(segments):
            prompt_id = f"{record['id_prefix']}_s{segment_index:02d}"
            accepted: tuple[int, int, int, int, int, str, str] | None = None
            for attempt in range(retries):
                start, stop, segment_start, segment_stop = candidate_coordinates(
                    record_length=int(record["record_length"]),
                    span_length=span_length,
                    segment_index=segment_index,
                    segments=segments,
                    selection_label=label,
                    accession=accession,
                    attempt=attempt,
                )
                fasta_text = fetch_text(efetch_url(endpoint, accession, start, stop))
                header, span = parse_fasta(fasta_text)
                if accession not in header:
                    raise ValueError(f"FASTA header for {prompt_id} does not contain {accession}")
                if len(span) != span_length:
                    raise ValueError(f"unexpected source-span length for {prompt_id}")
                if set(span) <= set("ACGT"):
                    accepted = (
                        attempt,
                        start,
                        stop,
                        segment_start,
                        segment_stop,
                        fasta_text,
                        span,
                    )
                    break
                time.sleep(args.request_interval_seconds)
            if accepted is None:
                raise RuntimeError(f"no canonical candidate found for {prompt_id}")
            attempt, start, stop, segment_start, segment_stop, fasta_text, span = accepted
            raw_path = raw_dir / f"{prompt_id}.fasta"
            if raw_path.exists() and raw_path.read_text(encoding="utf-8") != fasta_text:
                raise RuntimeError(f"cached FASTA disagrees for {prompt_id}")
            raw_path.write_text(fasta_text, encoding="utf-8")
            prompt = span[:prompt_length]
            windows.append(
                {
                    "id": prompt_id,
                    "segment_index": segment_index,
                    "selection_attempt": attempt,
                    "segment_start": segment_start,
                    "segment_stop": segment_stop,
                    "source_span_start": start,
                    "source_span_stop": stop,
                    "source_span_sha256": sequence_sha256(span),
                    "prompt_start": start,
                    "prompt_stop": start + prompt_length - 1,
                    "sequence_sha256": sequence_sha256(prompt),
                    "public_null_start": start,
                    "public_null_stop": stop,
                    "public_null_sha256": sequence_sha256(span),
                    "strand": "forward",
                }
            )
            print(
                json.dumps(
                    {
                        "frozen": prompt_id,
                        "record": accession,
                        "segment": segment_index,
                        "attempt": attempt,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            time.sleep(args.request_interval_seconds)
        frozen_record["windows"] = windows
        frozen_records.append(frozen_record)

    manifest = {
        "schema_version": 1,
        "cohort_id": cohort_id,
        "purpose": spec["purpose"],
        "created": spec["created"],
        "frozen_after_public_fetch": "2026-08-27",
        "source": spec["source"],
        "selection": selection,
        "source_spec_sha256": hashlib.sha256(args.source_spec.read_bytes()).hexdigest(),
        "records": frozen_records,
    }
    validate_frozen_manifest(manifest)
    assert args.freeze_manifest is not None
    write_yaml(args.freeze_manifest, manifest)
    return {
        "mode": "freeze_manifest",
        "manifest": str(args.freeze_manifest),
        "prompt_count": sum(len(record["windows"]) for record in frozen_records),
        "manifest_sha256": hashlib.sha256(args.freeze_manifest.read_bytes()).hexdigest(),
    }


def validate_frozen_manifest(manifest: dict[str, Any]) -> None:
    selection = manifest["selection"]
    records = manifest["records"]
    expected_records = int(selection["record_count"])
    expected_windows = int(selection["prompt_count"])
    if len(records) != expected_records:
        raise ValueError("frozen manifest record count is incorrect")
    windows = [(record, window) for record in records for window in record["windows"]]
    if len(windows) != expected_windows:
        raise ValueError("frozen manifest prompt count is incorrect")
    ids = [str(window["id"]) for _record, window in windows]
    if len(set(ids)) != len(ids):
        raise ValueError("frozen manifest contains duplicate prompt IDs")
    prompt_length = int(selection["prompt_length_bases"])
    span_length = int(selection["source_span_length_bases"])
    for record, window in windows:
        if int(window["prompt_stop"]) - int(window["prompt_start"]) + 1 != prompt_length:
            raise ValueError("a frozen prompt has the wrong coordinate length")
        if int(window["source_span_stop"]) - int(window["source_span_start"]) + 1 != span_length:
            raise ValueError("a frozen source span has the wrong coordinate length")
        if str(window["strand"]) != "forward":
            raise ValueError("the frozen selection declares forward strand only")
        if not (
            int(window["segment_start"])
            <= int(window["source_span_start"])
            <= int(window["source_span_stop"])
            <= int(window["segment_stop"])
        ):
            raise ValueError("a source span escapes its preregistered segment")
        if int(window["source_span_stop"]) > int(record["record_length"]):
            raise ValueError("a source span escapes its accession")
        for field in ("sequence_sha256", "source_span_sha256", "public_null_sha256"):
            if len(str(window[field])) != 64:
                raise ValueError(f"invalid {field} in frozen manifest")
    by_accession: dict[str, list[tuple[int, int]]] = {}
    for record, window in windows:
        by_accession.setdefault(str(record["accession"]), []).append(
            (int(window["source_span_start"]), int(window["source_span_stop"]))
        )
    for spans in by_accession.values():
        ordered = sorted(spans)
        if any(left[1] >= right[0] for left, right in zip(ordered, ordered[1:], strict=False)):
            raise ValueError("frozen source spans overlap within an accession")


def build_from_manifest(args: argparse.Namespace) -> dict[str, Any]:
    manifest = load_yaml(args.manifest)
    validate_frozen_manifest(manifest)
    cohort_id = str(manifest["cohort_id"])
    endpoint = str(manifest["source"]["endpoint"])
    prompt_length = int(manifest["selection"]["prompt_length_bases"])
    span_length = int(manifest["selection"]["source_span_length_bases"])
    raw_dir = args.raw_root / cohort_id
    processed_dir = args.processed_root / cohort_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    prompts: list[dict[str, Any]] = []
    prompt_sequences: set[str] = set()
    public_null_sequences: set[str] = set()
    for record in manifest["records"]:
        accession = str(record["accession"])
        for window in record["windows"]:
            prompt_id = str(window["id"])
            raw_path = raw_dir / f"{prompt_id}.fasta"
            if raw_path.is_file():
                fasta_text = raw_path.read_text(encoding="utf-8")
            elif args.offline:
                raise FileNotFoundError(f"missing cached FASTA: {raw_path}")
            else:
                fasta_text = fetch_text(
                    efetch_url(
                        endpoint,
                        accession,
                        int(window["source_span_start"]),
                        int(window["source_span_stop"]),
                    )
                )
                raw_path.write_text(fasta_text, encoding="utf-8")
                time.sleep(args.request_interval_seconds)
            header, span = parse_fasta(fasta_text)
            if accession not in header:
                raise ValueError(f"FASTA header for {prompt_id} does not contain {accession}")
            if len(span) != span_length or set(span) - set("ACGT"):
                raise ValueError(
                    f"source span for {prompt_id} is not canonical length {span_length}"
                )
            prompt = span[:prompt_length]
            if sequence_sha256(span) != str(window["source_span_sha256"]):
                raise ValueError(f"source-span checksum mismatch for {prompt_id}")
            if sequence_sha256(prompt) != str(window["sequence_sha256"]):
                raise ValueError(f"prompt checksum mismatch for {prompt_id}")
            if sequence_sha256(span) != str(window["public_null_sha256"]):
                raise ValueError(f"public-null checksum mismatch for {prompt_id}")
            if prompt in prompt_sequences or span in public_null_sequences:
                raise ValueError("cohort contains a duplicate sequence")
            prompt_sequences.add(prompt)
            public_null_sequences.add(span)
            prompts.append(
                {
                    "cohort_id": cohort_id,
                    "prompt_id": prompt_id,
                    "organism": str(record["organism"]),
                    "taxon_id": int(record["taxon_id"]),
                    "accession": accession,
                    "assembly": str(record["assembly"]),
                    "chromosome": str(record["chromosome"]),
                    "start": int(window["prompt_start"]),
                    "stop": int(window["prompt_stop"]),
                    "strand": str(window["strand"]),
                    "sequence_sha256": str(window["sequence_sha256"]),
                    "sequence": prompt,
                    "public_null_start": int(window["public_null_start"]),
                    "public_null_stop": int(window["public_null_stop"]),
                    "public_null_sha256": str(window["public_null_sha256"]),
                    "public_null_dna": span,
                }
            )

    prompts_path = processed_dir / "prompts.jsonl"
    prompts_path.write_text(
        "".join(json.dumps(prompt, sort_keys=True) + "\n" for prompt in prompts),
        encoding="utf-8",
    )
    cohort_sha256 = cohort_content_digest(
        (str(prompt["prompt_id"]), str(prompt["sequence_sha256"])) for prompt in prompts
    )
    public_null_sha256 = cohort_content_digest(
        (str(prompt["prompt_id"]), str(prompt["public_null_sha256"])) for prompt in prompts
    )
    summary = {
        "schema_version": 1,
        "cohort_id": cohort_id,
        "prompt_count": len(prompts),
        "unique_accessions": len({prompt["accession"] for prompt in prompts}),
        "unique_organisms": len({prompt["taxon_id"] for prompt in prompts}),
        "window_length_bases": prompt_length,
        "public_null_length_bases": span_length,
        "cohort_sha256": cohort_sha256,
        "public_null_cohort_sha256": public_null_sha256,
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "prompts_file_sha256": hashlib.sha256(prompts_path.read_bytes()).hexdigest(),
        "prompts_path": str(prompts_path.relative_to(ROOT)),
        "offline": args.offline,
        "validation": {
            "unique_case_ids": True,
            "canonical_prompts": True,
            "unique_prompt_sequences": True,
            "unique_public_null_sequences": True,
            "hashes_verified": True,
            "non_overlapping_source_spans": True,
            "selection_used_model_output": False,
        },
    }
    (processed_dir / "provenance.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    args = parse_args()
    if args.request_interval_seconds < 0.0:
        raise ValueError("request interval must be non-negative")
    if args.freeze_manifest is not None:
        summary = freeze_manifest(args)
    else:
        summary = build_from_manifest(args)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
