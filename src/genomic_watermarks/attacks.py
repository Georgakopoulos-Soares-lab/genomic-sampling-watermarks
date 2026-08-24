"""Key-reuse attacks on a position-indexed sampling watermark.

Every attack here is model-free and key-free. The attacker sees generated DNA and
knows the public configuration; it never queries the model, never sees a
probability, and never sees the key.

The attacks exist because of one structural property of the construction: the
detector's decision at read position ``i`` depends only on which half of the keyed
partition at stream index ``i`` the observed token falls into, and that partition
is a function of the key, the domain, and ``i`` alone. The statistic is therefore a
sum of per-position, content-blind indicators, and nothing binds the token at one
position to the token at any other.

``positional_splice`` exploits that directly: a token observed at position ``i``
already carries the group membership position ``i`` requires, so it satisfies the
detector when placed at position ``i`` of a sequence the generator never produced.
``positional_shuffle`` and ``block_shuffle`` exploit the converse, that a token
moved to a different position carries no information about the group there.
"""

from __future__ import annotations

import random
from collections.abc import Sequence

from genomic_watermarks.dna import KMER_SIZE

SPLICE_ATTACK = "positional_splice"
SHUFFLE_ATTACK = "positional_shuffle"
BLOCK_SHUFFLE_ATTACK = "block_shuffle"
ATTACKS = (SPLICE_ATTACK, SHUFFLE_ATTACK, BLOCK_SHUFFLE_ATTACK)


def tokenize(sequence: str) -> tuple[str, ...]:
    """Split a sequence into whole 6-mers from position zero, dropping any remainder."""

    if len(sequence) < KMER_SIZE:
        raise ValueError("sequence is shorter than one k-mer")
    count = len(sequence) // KMER_SIZE
    return tuple(sequence[index * KMER_SIZE : (index + 1) * KMER_SIZE] for index in range(count))


def positional_splice(
    donors: Sequence[str],
    rng: random.Random,
    *,
    forbid_single_donor: bool = True,
) -> tuple[str, tuple[int, ...]]:
    """Forge a novel sequence by copying each token position from some donor.

    Returns the forged DNA and, for the record, which donor supplied each position.
    A draw that happens to take every position from one donor is a verbatim copy
    rather than a forgery, so it is rejected and redrawn: a reported spoofing
    success must never be a copy of an observed output.
    """

    if len(donors) < 2:
        raise ValueError("splicing needs at least two donor sequences")
    tokenized = [tokenize(donor) for donor in donors]
    length = min(len(tokens) for tokens in tokenized)
    if length < 1:
        raise ValueError("donors must hold at least one token")
    for _attempt in range(64):
        choice = tuple(rng.randrange(len(tokenized)) for _ in range(length))
        if not forbid_single_donor or len(set(choice)) > 1:
            return "".join(tokenized[choice[i]][i] for i in range(length)), choice
    raise RuntimeError("could not draw a splice that uses more than one donor")


def positional_shuffle(sequence: str, rng: random.Random) -> tuple[str, float]:
    """Remove the mark by permuting token positions.

    Returns the attacked DNA and the fraction of positions whose token moved, which
    is the quantity the signal loss should track.
    """

    tokens = list(tokenize(sequence))
    order = list(range(len(tokens)))
    rng.shuffle(order)
    displaced = sum(1 for index, source in enumerate(order) if index != source)
    return "".join(tokens[source] for source in order), displaced / len(tokens)


def block_shuffle(sequence: str, width: int, rng: random.Random) -> tuple[str, float]:
    """Remove the mark by shuffling token positions only inside blocks of ``width``.

    A bounded rearrangement, so the attacker keeps local sequence structure that a
    full permutation destroys. The final partial block is shuffled within itself.
    """

    if width < 2:
        raise ValueError("block width must be at least two tokens")
    tokens = list(tokenize(sequence))
    result: list[str] = []
    displaced = 0
    for start in range(0, len(tokens), width):
        block = tokens[start : start + width]
        order = list(range(len(block)))
        rng.shuffle(order)
        displaced += sum(1 for index, source in enumerate(order) if index != source)
        result.extend(block[source] for source in order)
    return "".join(result), displaced / len(tokens)
