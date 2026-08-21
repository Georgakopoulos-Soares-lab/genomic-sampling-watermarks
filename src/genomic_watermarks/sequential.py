"""Reproducible helpers for the sequential E2 capacity pilot."""

from __future__ import annotations

import hashlib
import random
from collections.abc import Mapping, Sequence

from genomic_watermarks.sampling.partition import keyed_balanced_partition

PUBLIC_EVALUATION_SCHEME = "e2-public-partitions-v1"
PATH_SAMPLING_SCHEME = "e2-unwatermarked-path-v1"
_PUBLIC_EVALUATION_MATERIAL = hashlib.sha256(
    b"genomic-sampling-watermarks/e2/public-evaluation-material/v1"
).digest()
_PATH_SEED_LABEL = b"genomic-sampling-watermarks/e2/unwatermarked-path/v1\x00"


def public_evaluation_material() -> bytes:
    """Return fixed public material used only for reproducible capacity measurement."""

    return _PUBLIC_EVALUATION_MATERIAL


def public_evaluation_material_sha256() -> str:
    """Identify the public evaluation material without calling it a secret key."""

    return hashlib.sha256(_PUBLIC_EVALUATION_MATERIAL).hexdigest()


def evaluation_partition_domains(
    cohort_id: str,
    policy_id: str,
    count: int,
) -> tuple[str, ...]:
    """Return paired partition domains reused across prompts and sequential states."""

    if not cohort_id or not policy_id:
        raise ValueError("cohort_id and policy_id must not be empty")
    if count <= 0:
        raise ValueError("partition count must be positive")
    prefix = f"{PUBLIC_EVALUATION_SCHEME}/{cohort_id}/{policy_id}"
    return tuple(f"{prefix}/partition/{index:02d}" for index in range(count))


def build_evaluation_partitions(
    tokens: Sequence[str],
    *,
    cohort_id: str,
    policy_id: str,
    count: int,
) -> tuple[Mapping[str, bool], ...]:
    """Build the fixed public partitions once for all states of one policy run."""

    material = public_evaluation_material()
    return tuple(
        keyed_balanced_partition(tokens, material, domain=domain)
        for domain in evaluation_partition_domains(cohort_id, policy_id, count)
    )


def derive_path_seed(base_seed: int, policy_id: str, case_id: str) -> int:
    """Derive an independent reproducible RNG seed for one prompt and policy."""

    if base_seed < 0:
        raise ValueError("base seed must be non-negative")
    if not policy_id or not case_id:
        raise ValueError("policy_id and case_id must not be empty")
    payload = f"{base_seed}/{policy_id}/{case_id}".encode()
    digest = hashlib.sha256(_PATH_SEED_LABEL + payload).digest()
    return int.from_bytes(digest[:16], "big")


def path_rng(base_seed: int, policy_id: str, case_id: str) -> random.Random:
    """Create the public, non-cryptographic RNG for an unwatermarked continuation path."""

    return random.Random(derive_path_seed(base_seed, policy_id, case_id))
