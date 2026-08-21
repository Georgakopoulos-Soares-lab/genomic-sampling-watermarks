#!/usr/bin/env python3
"""Audit a pinned model tokenizer without downloading model weights."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.models.huggingface import POLICIES, load_tokenizer  # noqa: E402
from genomic_watermarks.models.vocabulary import extract_canonical_vocabulary  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=sorted(POLICIES), required=True)
    parser.add_argument("--cache-dir")
    parser.add_argument("--local-files-only", action="store_true")
    return parser.parse_args()


def dependency_revision(tokenizer: Any) -> str | None:
    base = getattr(tokenizer, "_base_tokenizer", None)
    init_kwargs = getattr(base, "init_kwargs", {}) if base is not None else {}
    value = getattr(base, "_commit_hash", None)
    if not value and isinstance(init_kwargs, dict):
        value = init_kwargs.get("_commit_hash")
    return str(value) if value else None


def dependency_model_id(tokenizer: Any) -> str | None:
    base = getattr(tokenizer, "_base_tokenizer", None)
    value = getattr(base, "name_or_path", None) if base is not None else None
    return str(value) if value else None


def main() -> int:
    args = parse_args()
    spec = POLICIES[args.policy]
    try:
        tokenizer = load_tokenizer(
            args.policy,
            cache_dir=args.cache_dir,
            local_files_only=args.local_files_only,
        )
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 2
    vocabulary = extract_canonical_vocabulary(tokenizer)
    dependency = spec.transitive_tokenizer_pin
    report = {
        "policy_id": args.policy,
        "model_id": spec.policy.model_id,
        "revision": spec.policy.tokenizer_revision,
        "tokenizer_class": type(tokenizer).__name__,
        "k": int(getattr(tokenizer, "k", 0)),
        "canonical_count": len(vocabulary.tokens),
        "canonical_first_id": vocabulary.first_id,
        "canonical_last_id": vocabulary.last_id,
        "canonical_ids_contiguous": vocabulary.is_contiguous,
        "mapping_source": vocabulary.mapping_source,
        "base_dependency_model_id": dependency_model_id(tokenizer) or "none",
        "base_dependency_observed_revision": dependency_revision(tokenizer) or "unreported",
        "base_dependency_required_revision": dependency.revision if dependency else "none",
        "base_dependency_pin_enforced": dependency is not None,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
