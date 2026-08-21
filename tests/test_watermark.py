from __future__ import annotations

import random
import statistics
import unittest
from collections import Counter

from genomic_watermarks.dna import canonical_kmers, tokenize_fixed
from genomic_watermarks.watermark import (
    ORDINARY_SCHEME,
    PARTITION_MC_SCHEME,
    GenerationResult,
    KeyedPartitionStream,
    generate_ordinary,
    generate_partition_mc,
    public_replay_seed,
    stream_agreements,
)

PUBLIC_TEST_KEY = b"public-fixture-key-not-a-secret-v1"
OTHER_PUBLIC_TEST_KEY = b"public-fixture-key-not-a-secret-v2"


def fixed_distribution(items, probabilities):
    """Return a context-independent next-distribution callable."""

    def draw(_context: str) -> tuple[tuple[str, ...], tuple[float, ...]]:
        return tuple(items), tuple(probabilities)

    return draw


def context_dependent_distribution(items):
    """Return a callable whose law depends on the last emitted token."""

    def draw(context: str) -> tuple[tuple[str, ...], tuple[float, ...]]:
        offset = (len(context) // len(items[0])) % len(items)
        weights = [1.0] * len(items)
        weights[offset] = 4.0
        return tuple(items), tuple(weights)

    return draw


class KeyedPartitionStreamTest(unittest.TestCase):
    def test_stream_rejects_missing_key_or_domain(self) -> None:
        with self.assertRaisesRegex(ValueError, "key must not be empty"):
            KeyedPartitionStream(key=b"", domain="run")
        with self.assertRaisesRegex(ValueError, "domain must not be empty"):
            KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="")

    def test_stream_repr_hides_key_material(self) -> None:
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="run")
        rendered = repr(stream)
        self.assertIn("run", rendered)
        self.assertNotIn("public-fixture-key", rendered)

    def test_partition_is_balanced_and_position_dependent(self) -> None:
        items = tuple(f"t{index}" for index in range(16))
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="run")
        first = stream.partition(items, 0)
        second = stream.partition(items, 1)
        self.assertEqual(sum(first.values()), len(items) // 2)
        self.assertEqual(sum(second.values()), len(items) // 2)
        self.assertNotEqual(first, second)
        self.assertEqual(first, stream.partition(items, 0))

    def test_partition_and_bits_are_key_and_domain_separated(self) -> None:
        items = tuple(f"t{index}" for index in range(16))
        base = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="run-a")
        other_domain = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="run-b")
        other_key = KeyedPartitionStream(key=OTHER_PUBLIC_TEST_KEY, domain="run-a")
        self.assertNotEqual(base.partition(items, 0), other_domain.partition(items, 0))
        self.assertNotEqual(base.partition(items, 0), other_key.partition(items, 0))
        base_bits = [base.latent_bit(index) for index in range(64)]
        self.assertNotEqual(base_bits, [other_domain.latent_bit(index) for index in range(64)])
        self.assertNotEqual(base_bits, [other_key.latent_bit(index) for index in range(64)])

    def test_latent_bit_stream_is_close_to_fair(self) -> None:
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="fairness")
        ones = sum(stream.latent_bit(index) for index in range(4096))
        self.assertTrue(1900 <= ones <= 2196, ones)

    def test_stream_index_bounds_are_enforced(self) -> None:
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="run")
        with self.assertRaisesRegex(ValueError, "non-negative"):
            stream.latent_bit(-1)
        with self.assertRaisesRegex(ValueError, "64 bits"):
            stream.latent_bit(1 << 64)


class PartitionMcGenerationTest(unittest.TestCase):
    def test_generation_produces_dna_and_a_complete_step_record(self) -> None:
        items = canonical_kmers()[:8]
        draw = fixed_distribution(items, [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="generate")
        result = generate_partition_mc(
            draw,
            "ATCGGC",
            steps=12,
            stream=stream,
            rng=random.Random(7),
        )
        self.assertEqual(result.scheme, PARTITION_MC_SCHEME)
        self.assertEqual(len(result.tokens), 12)
        self.assertEqual(result.bases, 72)
        self.assertEqual(len(result.dna), 72)
        self.assertEqual([step.index for step in result.steps], list(range(12)))
        self.assertEqual([step.stream_index for step in result.steps], list(range(12)))
        self.assertTrue(all(token in items for token in result.tokens))
        self.assertTrue(all(0.0 <= step.group_one_mass <= 1.0 for step in result.steps))

    def test_generation_replays_deterministically(self) -> None:
        items = canonical_kmers()[:8]
        draw = context_dependent_distribution(items)
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="replay")
        first = generate_partition_mc(
            draw, "ATCGGC", steps=20, stream=stream, rng=random.Random(11)
        )
        second = generate_partition_mc(
            draw, "ATCGGC", steps=20, stream=stream, rng=random.Random(11)
        )
        self.assertEqual(first.tokens, second.tokens)
        self.assertEqual(
            [step.latent_bit for step in first.steps],
            [step.latent_bit for step in second.steps],
        )
        self.assertEqual(first.agreement_count, second.agreement_count)

    def test_generation_uses_the_context_it_has_already_emitted(self) -> None:
        items = canonical_kmers()[:8]
        seen: list[str] = []

        def draw(context: str) -> tuple[tuple[str, ...], tuple[float, ...]]:
            seen.append(context)
            return tuple(items), tuple([1.0] * len(items))

        result = generate_partition_mc(
            draw,
            "ATCGGC",
            steps=5,
            stream=KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="context"),
            rng=random.Random(3),
        )
        self.assertEqual(seen[0], "ATCGGC")
        for index in range(1, 5):
            self.assertEqual(seen[index], "ATCGGC" + "".join(result.tokens[:index]))

    def test_stream_offset_shifts_the_keyed_stream(self) -> None:
        items = canonical_kmers()[:8]
        draw = fixed_distribution(items, [1.0] * 8)
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="offset")
        shifted = generate_partition_mc(
            draw, "ATCGGC", steps=6, stream=stream, rng=random.Random(5), stream_offset=100
        )
        self.assertEqual([step.stream_index for step in shifted.steps], list(range(100, 106)))
        self.assertEqual(
            [step.latent_bit for step in shifted.steps],
            [stream.latent_bit(index) for index in range(100, 106)],
        )

    def test_marginal_is_preserved_on_a_fixed_distribution(self) -> None:
        items = canonical_kmers()[:8]
        weights = (0.30, 0.22, 0.18, 0.12, 0.08, 0.05, 0.03, 0.02)
        draw = fixed_distribution(items, weights)
        rng = random.Random(20260821)
        counts: Counter[str] = Counter()
        trials = 200
        steps = 100
        for trial in range(trials):
            stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain=f"marginal/{trial}")
            result = generate_partition_mc(draw, "ATCGGC", steps=steps, stream=stream, rng=rng)
            counts.update(result.tokens)
        total = trials * steps
        for item, weight in zip(items, weights, strict=True):
            observed = counts[item] / total
            self.assertAlmostEqual(observed, weight, delta=0.012, msg=item)

    def test_agreement_rate_matches_the_realized_mass_prediction(self) -> None:
        items = canonical_kmers()[:8]
        draw = fixed_distribution(items, [1.0] * 8)
        rng = random.Random(4242)
        rates: list[float] = []
        predicted: list[float] = []
        for trial in range(40):
            stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain=f"agree/{trial}")
            result = generate_partition_mc(draw, "ATCGGC", steps=64, stream=stream, rng=rng)
            rates.append(result.agreement_rate)
            predicted.append(result.expected_agreement_rate)
        self.assertAlmostEqual(statistics.fmean(rates), statistics.fmean(predicted), delta=0.03)

    def test_balanced_partition_mass_gives_perfect_agreement(self) -> None:
        items = canonical_kmers()[:8]
        draw = fixed_distribution(items, [1.0] * 8)
        result = generate_partition_mc(
            draw,
            "ATCGGC",
            steps=32,
            stream=KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="balanced"),
            rng=random.Random(19),
        )
        for step in result.steps:
            self.assertAlmostEqual(step.group_one_mass, 0.5)
        self.assertEqual(result.agreement_count, 32)
        self.assertAlmostEqual(result.agreement_rate, 1.0)
        self.assertAlmostEqual(result.expected_agreement_rate, 1.0)

    def test_degenerate_support_still_generates_and_carries_no_signal(self) -> None:
        items = canonical_kmers()[:8]
        weights = [0.0] * 8
        weights[3] = 1.0
        draw = fixed_distribution(items, weights)
        result = generate_partition_mc(
            draw,
            "ATCGGC",
            steps=16,
            stream=KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="degenerate"),
            rng=random.Random(23),
        )
        self.assertEqual(set(result.tokens), {items[3]})
        self.assertTrue(all(step.group_one_mass in {0.0, 1.0} for step in result.steps))
        self.assertAlmostEqual(result.expected_agreement_rate, 0.5)

    def test_imbalanced_mass_reduces_but_keeps_agreement_above_chance(self) -> None:
        items = canonical_kmers()[:8]
        weights = [0.86] + [0.02] * 7
        draw = fixed_distribution(items, weights)
        rng = random.Random(77)
        agreements = 0
        total = 0
        for trial in range(60):
            stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain=f"skew/{trial}")
            result = generate_partition_mc(draw, "ATCGGC", steps=32, stream=stream, rng=rng)
            agreements += result.agreement_count
            total += len(result.steps)
        rate = agreements / total
        self.assertGreater(rate, 0.5)
        self.assertLess(rate, 1.0)

    def test_generation_rejects_invalid_arguments(self) -> None:
        items = canonical_kmers()[:8]
        draw = fixed_distribution(items, [1.0] * 8)
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="invalid")
        with self.assertRaisesRegex(ValueError, "steps must be positive"):
            generate_partition_mc(draw, "ATCGGC", steps=0, stream=stream, rng=random.Random(1))
        with self.assertRaisesRegex(ValueError, "stream_offset must be non-negative"):
            generate_partition_mc(
                draw, "ATCGGC", steps=2, stream=stream, rng=random.Random(1), stream_offset=-1
            )
        with self.assertRaisesRegex(TypeError, "must be callable"):
            generate_partition_mc(
                "not-callable", "ATCGGC", steps=2, stream=stream, rng=random.Random(1)
            )
        with self.assertRaisesRegex(ValueError, "same length"):
            generate_partition_mc(
                fixed_distribution(items, [1.0] * 7),
                "ATCGGC",
                steps=2,
                stream=stream,
                rng=random.Random(1),
            )
        with self.assertRaisesRegex(ValueError, "even number"):
            generate_partition_mc(
                fixed_distribution(items[:7], [1.0] * 7),
                "ATCGGC",
                steps=2,
                stream=stream,
                rng=random.Random(1),
            )


class OrdinaryControlTest(unittest.TestCase):
    def test_ordinary_control_matches_the_declared_marginal(self) -> None:
        items = canonical_kmers()[:8]
        weights = (0.30, 0.22, 0.18, 0.12, 0.08, 0.05, 0.03, 0.02)
        draw = fixed_distribution(items, weights)
        result = generate_ordinary(draw, "ATCGGC", steps=20000, rng=random.Random(31337))
        self.assertEqual(result.scheme, ORDINARY_SCHEME)
        self.assertEqual(result.steps, ())
        self.assertEqual(result.agreement_count, 0)
        self.assertEqual(result.agreement_rate, 0.0)
        counts = Counter(result.tokens)
        for item, weight in zip(items, weights, strict=True):
            self.assertAlmostEqual(counts[item] / 20000, weight, delta=0.012, msg=item)

    def test_ordinary_control_replays_and_validates(self) -> None:
        items = canonical_kmers()[:8]
        draw = context_dependent_distribution(items)
        first = generate_ordinary(draw, "ATCGGC", steps=25, rng=random.Random(9))
        second = generate_ordinary(draw, "ATCGGC", steps=25, rng=random.Random(9))
        self.assertEqual(first.tokens, second.tokens)
        with self.assertRaisesRegex(ValueError, "steps must be positive"):
            generate_ordinary(draw, "ATCGGC", steps=-1, rng=random.Random(9))
        with self.assertRaisesRegex(TypeError, "must be callable"):
            generate_ordinary(None, "ATCGGC", steps=2, rng=random.Random(9))


class StreamAgreementTest(unittest.TestCase):
    def test_keyed_recomputation_reproduces_generation_agreement(self) -> None:
        items = canonical_kmers()[:64]
        draw = context_dependent_distribution(items)
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="round-trip")
        result = generate_partition_mc(
            draw, "ATCGGC", steps=40, stream=stream, rng=random.Random(13), stream_offset=9
        )
        recovered = stream_agreements(
            tokenize_fixed(result.dna),
            items,
            stream,
            stream_offset=9,
        )
        self.assertEqual(recovered, tuple(step.agrees for step in result.steps))

    def test_wrong_key_and_wrong_offset_lose_the_signal(self) -> None:
        items = canonical_kmers()[:64]
        draw = fixed_distribution(items, [1.0] * 64)
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="null")
        result = generate_partition_mc(
            draw, "ATCGGC", steps=256, stream=stream, rng=random.Random(17)
        )
        tokens = tokenize_fixed(result.dna)
        correct = stream_agreements(tokens, items, stream)
        self.assertEqual(sum(correct), len(tokens))
        wrong_key = KeyedPartitionStream(key=OTHER_PUBLIC_TEST_KEY, domain="null")
        wrong_rate = sum(stream_agreements(tokens, items, wrong_key)) / len(tokens)
        offset_rate = sum(stream_agreements(tokens, items, stream, stream_offset=1)) / len(tokens)
        self.assertLess(wrong_rate, 0.65)
        self.assertLess(offset_rate, 0.65)

    def test_stream_agreements_validates_its_inputs(self) -> None:
        items = canonical_kmers()[:8]
        stream = KeyedPartitionStream(key=PUBLIC_TEST_KEY, domain="validate")
        with self.assertRaisesRegex(ValueError, "tokens must not be empty"):
            stream_agreements((), items, stream)
        with self.assertRaisesRegex(ValueError, "non-negative"):
            stream_agreements((items[0],), items, stream, stream_offset=-1)
        with self.assertRaisesRegex(ValueError, "support is missing"):
            stream_agreements(("TTTTTT",), items, stream)


class PublicReplaySeedTest(unittest.TestCase):
    def test_seed_is_deterministic_label_separated_and_bounded(self) -> None:
        first = public_replay_seed("run", "C_tok", "yeast_q20", "watermarked")
        self.assertEqual(first, public_replay_seed("run", "C_tok", "yeast_q20", "watermarked"))
        self.assertNotEqual(first, public_replay_seed("run", "C_tok", "yeast_q20", "ordinary"))
        self.assertNotEqual(first, public_replay_seed("run", "G_tok", "yeast_q20", "watermarked"))
        self.assertTrue(0 <= first < 1 << 128)

    def test_seed_rejects_empty_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one seed part"):
            public_replay_seed()
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            public_replay_seed("run", "")


class GenerationResultTest(unittest.TestCase):
    def test_empty_step_record_reports_neutral_summaries(self) -> None:
        result = GenerationResult(scheme=ORDINARY_SCHEME, tokens=("ATCGGC",), steps=())
        self.assertEqual(result.agreement_rate, 0.0)
        self.assertEqual(result.expected_agreement_rate, 0.0)
        self.assertEqual(result.bases, 6)
        self.assertEqual(result.dna, "ATCGGC")


if __name__ == "__main__":
    unittest.main()
