"""Canonical 6-mer vocabulary extraction from audited model tokenizers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from genomic_watermarks.dna import KMER_SIZE, canonical_kmers


@dataclass(frozen=True, slots=True)
class CanonicalVocabulary:
    """Ordered canonical DNA tokens and their model vocabulary IDs."""

    tokens: tuple[str, ...]
    ids: tuple[int, ...]
    mapping_source: str

    @property
    def is_contiguous(self) -> bool:
        return self.ids == tuple(range(self.ids[0], self.ids[0] + len(self.ids)))

    @property
    def first_id(self) -> int:
        return self.ids[0]

    @property
    def last_id(self) -> int:
        return self.ids[-1]


def _mapping_from_tokenizer(tokenizer: Any) -> tuple[Mapping[str, int], str]:
    # Carbon deliberately assigns DNA-specific IDs even when a 6-mer string is
    # also present in the BPE vocabulary. Its public get_vocab() deduplicates
    # those strings, so the dedicated mapping is the only correct source.
    dna_mapping = getattr(tokenizer, "dna_token_to_id", None)
    if isinstance(dna_mapping, Mapping):
        return dna_mapping, "dna_token_to_id"

    vocab = getattr(tokenizer, "vocab", None)
    if isinstance(vocab, Mapping):
        return vocab, "vocab"

    get_vocab = getattr(tokenizer, "get_vocab", None)
    if callable(get_vocab):
        resolved = get_vocab()
        if isinstance(resolved, Mapping):
            return resolved, "get_vocab"
    raise TypeError("tokenizer exposes no supported token-to-id mapping")


def extract_canonical_vocabulary(
    tokenizer: Any,
    *,
    k: int = KMER_SIZE,
    require_contiguous: bool = True,
) -> CanonicalVocabulary:
    """Extract and verify all canonical k-mer IDs in A/T/C/G product order."""

    tokenizer_k = getattr(tokenizer, "k", k)
    if tokenizer_k != k:
        raise ValueError(f"expected tokenizer k={k}, found k={tokenizer_k}")

    expected = canonical_kmers(k)
    declared = getattr(tokenizer, "kmers", None)
    if declared is not None and tuple(declared) != expected:
        raise ValueError("tokenizer k-mer order differs from canonical A/T/C/G product order")

    mapping, source = _mapping_from_tokenizer(tokenizer)
    missing = [token for token in expected if token not in mapping]
    if missing:
        raise ValueError(f"tokenizer is missing {len(missing)} canonical k-mer(s)")

    ids = tuple(int(mapping[token]) for token in expected)
    if len(set(ids)) != len(ids):
        raise ValueError("canonical k-mers do not have unique token IDs")

    vocabulary = CanonicalVocabulary(tokens=expected, ids=ids, mapping_source=source)
    if require_contiguous and not vocabulary.is_contiguous:
        raise ValueError("canonical k-mer IDs are not contiguous in canonical order")

    convert = getattr(tokenizer, "convert_ids_to_tokens", None)
    if callable(convert):
        observed = tuple(str(convert(token_id)) for token_id in ids)
        if observed != expected:
            mismatches = sum(left != right for left, right in zip(observed, expected, strict=True))
            raise ValueError(f"tokenizer ID round trip failed for {mismatches} canonical k-mer(s)")

    return vocabulary
