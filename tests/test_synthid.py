from __future__ import annotations

import hashlib
import hmac
import itertools
import random
import unittest

from genomic_watermarks import synthid
from genomic_watermarks.synthid import (
    KeyedTournament,
    _length_prefixed,
    generate_synthid,
    score_synthid_tokens,
    tournament_distribution,
    update_tournament_probabilities,
)

PUBLIC_KEY = b"public-synthid-unit-test-key"

# The accelerated path exists only when NumPy is installed. A dev-only install from the
# frozen lock is a legitimate configuration, so tests that require the accelerated path
# skip rather than fail there; the tests that compare it against the pure-Python
# reference remove NumPy deliberately and run in either configuration.
NUMPY_AVAILABLE = synthid._numpy() is not None
requires_numpy = unittest.skipUnless(
    NUMPY_AVAILABLE, "NumPy is not installed, so there is no accelerated path to compare"
)


def brute_force_tournament(
    probabilities: tuple[float, ...],
    g_values: tuple[tuple[int, ...], ...],
) -> tuple[float, ...]:
    """Enumerate candidates and tie coins for a small conceptual bracket."""

    depth = len(g_values[0])
    leaves = 1 << depth
    result = [0.0] * len(probabilities)
    for candidates in itertools.product(range(len(probabilities)), repeat=leaves):
        candidate_probability = 1.0
        for candidate in candidates:
            candidate_probability *= probabilities[candidate]
        outcomes: dict[tuple[int, ...], float] = {candidates: 1.0}
        for layer in range(depth):
            next_outcomes: dict[tuple[int, ...], float] = {}
            for competitors, branch_probability in outcomes.items():
                pairs = tuple(zip(competitors[::2], competitors[1::2], strict=True))
                choices: list[tuple[tuple[int, float], ...]] = []
                for left, right in pairs:
                    left_g = g_values[left][layer]
                    right_g = g_values[right][layer]
                    if left_g > right_g:
                        choices.append(((left, 1.0),))
                    elif right_g > left_g:
                        choices.append(((right, 1.0),))
                    else:
                        choices.append(((left, 0.5), (right, 0.5)))
                for winners in itertools.product(*choices):
                    tokens = tuple(winner for winner, _ in winners)
                    probability = branch_probability
                    for _, tie_probability in winners:
                        probability *= tie_probability
                    next_outcomes[tokens] = next_outcomes.get(tokens, 0.0) + probability
            outcomes = next_outcomes
        for (winner,), tournament_probability in outcomes.items():
            result[winner] += candidate_probability * tournament_probability
    return tuple(result)


class SynthIDTournamentTest(unittest.TestCase):
    def test_probability_update_matches_reference_formula(self) -> None:
        result = update_tournament_probabilities(
            (0.1, 0.2, 0.7),
            ((1,), (0,), (1,)),
        )
        self.assertAlmostEqual(result.g_masses[0], 0.8)
        for actual, expected in zip(result.probabilities, (0.12, 0.04, 0.84), strict=True):
            self.assertAlmostEqual(actual, expected)
        self.assertAlmostEqual(sum(result.probabilities), 1.0)

    def test_probability_update_is_exact_tournament_distribution(self) -> None:
        probabilities = (0.2, 0.3, 0.5)
        g_values = ((0, 1), (1, 1), (1, 0))
        updated = update_tournament_probabilities(probabilities, g_values).probabilities
        enumerated = brute_force_tournament(probabilities, g_values)
        for actual, expected in zip(updated, enumerated, strict=True):
            self.assertAlmostEqual(actual, expected, places=12)

    def test_prf_is_deterministic_domain_separated_and_secret_in_repr(self) -> None:
        context = ("AAAAAA", "AAAAAT", "AAAAAC", "AAAAAG")
        first = KeyedTournament(key=PUBLIC_KEY, domain="first", depth=30)
        replay = KeyedTournament(key=PUBLIC_KEY, domain="first", depth=30)
        other_domain = KeyedTournament(key=PUBLIC_KEY, domain="second", depth=30)
        other_key = KeyedTournament(key=b"other-public-key", domain="first", depth=30)
        self.assertEqual(
            first.g_values(context, "AAAATA"),
            replay.g_values(context, "AAAATA"),
        )
        self.assertNotEqual(
            first.g_values(context, "AAAATA"),
            other_domain.g_values(context, "AAAATA"),
        )
        self.assertNotEqual(
            first.g_values(context, "AAAATA"),
            other_key.g_values(context, "AAAATA"),
        )
        self.assertNotIn(PUBLIC_KEY.decode(), repr(first))

    def test_key_averaged_law_recovers_the_input_distribution(self) -> None:
        items = ("AAAAAA", "AAAAAT", "AAAAAC", "AAAAAG")
        probabilities = (0.1, 0.2, 0.3, 0.4)
        context = items
        averaged = [0.0] * len(items)
        key_count = 4_000
        for index in range(key_count):
            stream = KeyedTournament(
                key=f"public-key-{index}".encode(),
                domain="key-average",
                depth=3,
            )
            updated = tournament_distribution(items, probabilities, context, stream)
            for token_index, probability in enumerate(updated.probabilities):
                averaged[token_index] += probability / key_count
        for actual, expected in zip(averaged, probabilities, strict=True):
            self.assertAlmostEqual(actual, expected, delta=0.01)

    def test_generation_and_detector_recompute_the_same_trace(self) -> None:
        items = tuple("".join(chars) for chars in itertools.product("ATCG", repeat=3))

        def draw(_context: str) -> tuple[tuple[str, ...], tuple[float, ...]]:
            return items, tuple(1.0 for _ in items)

        tournament = KeyedTournament(
            key=PUBLIC_KEY,
            domain="generation-recompute",
            depth=3,
            context_tokens=4,
        )
        result = generate_synthid(
            draw,
            "AAAAAA",
            steps=128,
            tournament=tournament,
            rng=random.Random(7),
        )
        score = score_synthid_tokens(result.tokens, tournament)
        self.assertEqual(score.g_ones, result.g_ones)
        self.assertEqual(score.g_total, result.g_total)
        self.assertEqual(score.scored_tokens, result.scored_tokens)
        self.assertEqual(score.repeated_contexts, result.repeated_contexts)
        self.assertGreater(score.mean_g_value, 0.5)
        self.assertGreater(score.statistic, 3.0)

    def test_repeated_context_is_sampled_ordinarily_and_masked(self) -> None:
        items = ("AAAAAA",)

        def draw(_context: str) -> tuple[tuple[str, ...], tuple[float, ...]]:
            return items, (1.0,)

        tournament = KeyedTournament(
            key=PUBLIC_KEY,
            domain="repeat-mask",
            depth=3,
            context_tokens=4,
        )
        result = generate_synthid(
            draw,
            "AAAAAA",
            steps=8,
            tournament=tournament,
            rng=random.Random(1),
        )
        self.assertEqual(result.scored_tokens, 1)
        self.assertEqual(result.repeated_contexts, 3)
        score = score_synthid_tokens(result.tokens, tournament)
        self.assertEqual(score.scored_tokens, 1)
        self.assertEqual(score.repeated_contexts, 3)
        self.assertEqual(score.g_ones, result.g_ones)

    def test_invalid_configuration_and_values_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "depth"):
            KeyedTournament(key=PUBLIC_KEY, domain="invalid", depth=0)
        with self.assertRaisesRegex(ValueError, "binary"):
            update_tournament_probabilities((0.5, 0.5), ((0, 2), (1, 0)))
        tournament = KeyedTournament(key=PUBLIC_KEY, domain="invalid")
        with self.assertRaisesRegex(ValueError, "exactly"):
            tournament.g_values(("AAAAAA",), "AAAAAT")


if __name__ == "__main__":
    unittest.main()


class SynthIDAcceleratedPathTest(unittest.TestCase):
    """The vectorised path must be an accelerator, never a second construction.

    Every assertion here compares it against the pure Python reference or
    against the standard library, so a NumPy regression cannot silently change
    the watermark.
    """

    def setUp(self) -> None:
        self.items = tuple(f"{a}{b}{c}" for a in "ACGT" for b in "ACGT" for c in "ACGT")
        self.context = self.items[:4]

    @staticmethod
    def _without_numpy():
        """Context-manager-free helper returning the saved NumPy module."""

        saved = synthid._numpy_module
        synthid._numpy_module = None
        return saved

    def test_batch_digests_are_bit_identical_to_hmac(self) -> None:
        for key_length in (1, 32, 64, 65, 200):
            key = bytes((index * 7 + key_length) % 251 for index in range(key_length))
            tournament = KeyedTournament(key=key, domain="batch/digest")
            digests = tournament.candidate_digests(self.context, self.items)
            self.assertEqual(len(digests), 32 * len(self.items))
            for index, candidate in enumerate(self.items):
                message = tournament._context_prefix(self.context) + _length_prefixed(
                    candidate.encode("ascii")
                )
                self.assertEqual(
                    digests[index * 32 : (index + 1) * 32],
                    hmac.new(key, message, hashlib.sha256).digest(),
                    f"key_length={key_length} candidate={candidate}",
                )

    @requires_numpy
    def test_g_bit_matrix_matches_scalar_g_values(self) -> None:
        tournament = KeyedTournament(key=PUBLIC_KEY, domain="bits/matrix", depth=30)
        bits = tournament.candidate_g_bits(self.context, self.items)
        self.assertIsNotNone(bits, "the accelerated path must return a bit matrix")
        self.assertEqual(bits.shape, (len(self.items), 30))
        for index, candidate in enumerate(self.items):
            self.assertEqual(
                tuple(int(value) for value in bits[index]),
                tournament.g_values(self.context, candidate),
            )

    @requires_numpy
    def test_vectorised_law_agrees_with_pure_python_reference(self) -> None:
        rng = random.Random(4242)
        for depth in (1, 7, 30):
            tournament = KeyedTournament(key=PUBLIC_KEY, domain="law/agree", depth=depth)
            weights = [rng.expovariate(1.0) for _ in self.items]
            total = sum(weights)
            probabilities = tuple(weight / total for weight in weights)
            fast = tournament_distribution(self.items, probabilities, self.context, tournament)
            saved = self._without_numpy()
            try:
                reference = tournament_distribution(
                    self.items, probabilities, self.context, tournament
                )
            finally:
                synthid._numpy_module = saved
            for got, want in zip(fast.probabilities, reference.probabilities, strict=True):
                self.assertAlmostEqual(got, want, delta=1e-12)
            for got, want in zip(fast.g_masses, reference.g_masses, strict=True):
                self.assertAlmostEqual(got, want, delta=1e-12)

    def test_generation_is_identical_with_and_without_numpy(self) -> None:
        items = self.items

        def next_distribution(context: str) -> tuple[tuple[str, ...], tuple[float, ...]]:
            local = random.Random(hash(context[-16:]) & 0xFFFFFFFF)
            weights = [local.expovariate(1.0) for _ in items]
            total = sum(weights)
            return items, tuple(weight / total for weight in weights)

        for depth, context_tokens in ((30, 4), (16, 2), (1, 4)):
            tournament = KeyedTournament(
                key=PUBLIC_KEY,
                domain="generate/parity",
                depth=depth,
                context_tokens=context_tokens,
            )
            fast = generate_synthid(
                next_distribution,
                "ACAC",
                steps=40,
                tournament=tournament,
                rng=random.Random(19),
            )
            saved = self._without_numpy()
            try:
                reference = generate_synthid(
                    next_distribution,
                    "ACAC",
                    steps=40,
                    tournament=tournament,
                    rng=random.Random(19),
                )
            finally:
                synthid._numpy_module = saved
            self.assertEqual(fast.tokens, reference.tokens)
            self.assertEqual(
                [(step.applied, step.repeated_context, step.g_values) for step in fast.steps],
                [(step.applied, step.repeated_context, step.g_values) for step in reference.steps],
            )

    def test_suffix_cache_does_not_leak_between_vocabularies(self) -> None:
        tournament = KeyedTournament(key=PUBLIC_KEY, domain="cache/isolation")
        other = tuple(token.lower() for token in self.items)
        first = tournament.candidate_digests(self.context, self.items)
        second = tournament.candidate_digests(self.context, other)
        self.assertNotEqual(first, second)
        self.assertEqual(first, tournament.candidate_digests(self.context, self.items))

    def test_reference_path_is_used_when_numpy_is_absent(self) -> None:
        tournament = KeyedTournament(key=PUBLIC_KEY, domain="fallback/path")
        probabilities = tuple(1.0 / len(self.items) for _ in self.items)
        saved = self._without_numpy()
        try:
            self.assertIsNone(tournament.candidate_g_bits(self.context, self.items))
            law = tournament_distribution(self.items, probabilities, self.context, tournament)
        finally:
            synthid._numpy_module = saved
        self.assertAlmostEqual(sum(law.probabilities), 1.0, places=12)
