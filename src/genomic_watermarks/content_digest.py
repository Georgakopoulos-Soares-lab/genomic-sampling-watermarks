"""Digests that identify an artifact's scientific content, not its wall clock.

A plain file digest detects tampering but cannot be reproduced by re-running the
command that produced the artifact, because timings and host details differ on
every run. That made "re-run and compare digests" useless as a verification step,
which the 2026-08-23 audit recorded as a defect.

A content digest is taken over the artifact with the volatile fields removed. Two
runs of the same command on the same inputs produce the same content digest, so a
reviewer can reproduce the number rather than trust it. Both digests are worth
recording: the file digest pins the stored bytes, the content digest pins the
science.

The volatile set is deliberately explicit rather than inferred. A field is
volatile only if it records how long something took, how much memory it used, or
which host ran it. Anything that could change a conclusion is never volatile, and
``assert_no_scientific_field_is_volatile`` is the guard that keeps it that way.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

# Timings, memory, and host identity. Every entry either measures the run or names
# the machine; none of them can change a reported result.
VOLATILE_FIELDS: frozenset[str] = frozenset(
    {
        "wall_seconds",
        "model_load_seconds",
        "watermarked_seconds",
        "ordinary_seconds",
        "seconds_by_scheme",
        "process_peak_rss_gib",
        "mps_current_allocated_gib",
        "mps_driver_allocated_gib",
        "platform",
        "python",
    }
)

# Fields that must never be treated as volatile, because dropping any of them
# would let two artifacts with different results share a content digest.
PROTECTED_FIELDS: frozenset[str] = frozenset(
    {
        "achieved_false_positive_rate",
        "agreement_rate",
        "detection_rate",
        "matches",
        "p_value",
        "statistic",
        "threshold",
        "total",
        "total_score",
        "trials",
    }
)

# Where a file happened to live is not part of a result. Every recorded path in
# these artifacts is accompanied by a digest of that file's contents, and the digest
# is the identity: a rerun that reads the same bytes through a relative rather than
# an absolute path is the same run. Excluding the spelling but keeping the digest is
# what makes a content digest reproducible without making it blind to a changed
# input, because a different input still changes the accompanying digest.
PATH_FIELDS: frozenset[str] = frozenset(
    {
        "path",
        "artifact",
        "baseline_path",
        "cohort_jsonl",
        "manifest_path",
        "output",
        "partition_path",
        "prompts_path",
        "sequences_path",
        "source_artifact",
    }
)

_LABEL = b"genomic-sampling-watermarks/content-digest/v2\x00"


EXCLUDED_FIELDS: frozenset[str] = VOLATILE_FIELDS | PATH_FIELDS


def assert_no_scientific_field_is_volatile() -> None:
    """Fail loudly if the excluded set ever grows to cover a result field."""

    overlap = EXCLUDED_FIELDS & PROTECTED_FIELDS
    if overlap:
        raise ValueError(f"excluded set covers result field(s): {', '.join(sorted(overlap))}")


def strip_volatile(value: Any) -> Any:
    """Return the value with every volatile and path field removed, at any depth."""

    if isinstance(value, Mapping):
        return {
            key: strip_volatile(child)
            for key, child in value.items()
            if str(key) not in EXCLUDED_FIELDS
        }
    if isinstance(value, list):
        return [strip_volatile(child) for child in value]
    return value


def content_digest(report: Mapping[str, Any]) -> str:
    """Return the digest of an artifact's reproducible content."""

    assert_no_scientific_field_is_volatile()
    canonical = json.dumps(
        strip_volatile(report), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(_LABEL + canonical.encode("ascii")).hexdigest()


def volatile_fields_present(report: Mapping[str, Any]) -> tuple[str, ...]:
    """Return which volatile fields the artifact actually carries, for the record."""

    found: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if str(key) in VOLATILE_FIELDS:
                    found.add(str(key))
                else:
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(report)
    return tuple(sorted(found))
