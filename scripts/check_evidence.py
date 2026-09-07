#!/usr/bin/env python3
"""Dependency-free structural checks for the research evidence ledger."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_FILE = ROOT / "evidence" / "measurements.yaml"
EVIDENCE_MAP = ROOT / "paper" / "context" / "evidence_map.md"
FORBIDDEN_PATTERNS = (
    re.compile(r"(?i)^\s*(secret_key|private_key|hf_token|access_token)\s*:"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
ARTIFACT_DIGEST_FIELDS = (
    ("artifact", "sha256"),
    ("generation_artifact", "generation_sha256"),
    ("detection_artifact", "detection_sha256"),
    ("summary_artifact", "summary_sha256"),
    ("trials_artifact", "trials_sha256"),
)
DOCUMENT_FIELDS = ("protocol", "execution", "amendment")


def _repository_path(value: str) -> Path | None:
    candidate = Path(value)
    if candidate.is_absolute():
        return None
    resolved = (ROOT / candidate).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError:
        return None
    return resolved


def _check_artifact_references(text: str, errors: list[str]) -> int:
    checked = 0
    for path_field, digest_field in ARTIFACT_DIGEST_FIELDS:
        pattern = re.compile(
            rf"^\s+{path_field}:\s+(\S+)\s*$\n"
            rf"^\s+{digest_field}:\s+([0-9a-f]{{64}})\s*$",
            re.MULTILINE,
        )
        for match in pattern.finditer(text):
            relative_path, expected_digest = match.groups()
            artifact = _repository_path(relative_path)
            if artifact is None:
                errors.append(f"non-repository {path_field} path: {relative_path}")
                continue
            if not artifact.is_file():
                errors.append(f"missing evidence artifact: {relative_path}")
                continue
            observed_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            if observed_digest != expected_digest:
                errors.append(
                    f"evidence artifact digest mismatch: {relative_path} "
                    f"(expected {expected_digest}, observed {observed_digest})"
                )
                continue
            checked += 1
    return checked


def _check_document_references(text: str, errors: list[str]) -> int:
    checked_paths: set[str] = set()
    field_names = "|".join(DOCUMENT_FIELDS)
    for match in re.finditer(rf"^\s+(?:{field_names}):\s+(\S+)\s*$", text, re.MULTILINE):
        relative_path = match.group(1)
        if relative_path in checked_paths:
            continue
        checked_paths.add(relative_path)
        document = _repository_path(relative_path)
        if document is None:
            errors.append(f"non-repository evidence document path: {relative_path}")
        elif not document.is_file():
            errors.append(f"missing evidence document: {relative_path}")
    return len(checked_paths)


def _check_manuscript_map(seen_ids: dict[str, Path], errors: list[str]) -> int:
    if not EVIDENCE_MAP.is_file():
        errors.append(f"missing {EVIDENCE_MAP.relative_to(ROOT)}")
        return 0
    map_text = EVIDENCE_MAP.read_text(encoding="utf-8")
    mapped_ids = set(re.findall(r"`(synthid\.[A-Za-z0-9_.-]+)`", map_text))
    missing = sorted(mapped_ids - set(seen_ids))
    for item_id in missing:
        errors.append(f"manuscript evidence map references unknown measurement {item_id}")
    return len(mapped_ids)


def main() -> int:
    errors: list[str] = []
    seen_ids: dict[str, Path] = {}
    checked_artifacts = 0
    checked_documents = 0

    if not EVIDENCE_FILE.is_file():
        errors.append(f"missing {EVIDENCE_FILE.relative_to(ROOT)}")
        text = ""
    else:
        text = EVIDENCE_FILE.read_text(encoding="utf-8")
        if "schema_version:" not in text or "measurements:" not in text:
            errors.append(f"invalid top-level structure in {EVIDENCE_FILE.relative_to(ROOT)}")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                errors.append(f"possible secret material in {EVIDENCE_FILE.relative_to(ROOT)}")
        for match in re.finditer(r"^\s*-\s+id:\s+([A-Za-z0-9_.-]+)\s*$", text, re.MULTILINE):
            item_id = match.group(1)
            if item_id in seen_ids:
                errors.append(f"duplicate measurement id {item_id}")
            seen_ids[item_id] = EVIDENCE_FILE

        statuses = re.findall(r"^\s+status:\s+(\S+)\s*$", text, re.MULTILINE)
        invalid = [value for value in statuses if value not in {"V", "A"}]
        if invalid:
            errors.append(f"invalid evidence statuses: {', '.join(sorted(set(invalid)))}")
        checked_artifacts = _check_artifact_references(text, errors)
        checked_documents = _check_document_references(text, errors)

    mapped_ids = _check_manuscript_map(seen_ids, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(
        "evidence ledger OK "
        f"({len(seen_ids)} measurements, {checked_artifacts} artifact digests, "
        f"{checked_documents} documents, {mapped_ids} manuscript mappings)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
