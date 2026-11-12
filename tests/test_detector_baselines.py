from __future__ import annotations

import functools
import gzip
import itertools
import json
import math
import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from genomic_watermarks.detector_baselines import (
    ALIGNED_ORACLE_DETECTOR,
    FINE_GRID_DETECTOR,
    PHASE_ONLY_DETECTOR,
    detect_aligned_oracle,
    detect_fine_grid,
    detect_phase_only,
    expected_fine_grid_windows,
    fine_grid_lengths,
)
from genomic_watermarks.dna import reverse_complement, tokenize_fixed
from genomic_watermarks.large_validation import deterministic_prompt_split, fixture_key
from genomic_watermarks.review_layouts import NaturalPool, build_read, cell_by_name
from genomic_watermarks.synthid import KeyedTournament, generate_synthid, score_synthid_tokens
from genomic_watermarks.synthid_boundary import (
    deterministic_single_base_edit,
    score_synthid_unknown_boundary,
)
from genomic_watermarks.synthid_position_independent import (
    PositionIndependentSynthIDConfig,
    detect_synthid_position_independent,
    fair_binomial_log_survival_probability,
)

KEY = b"public-detector-baselines-unit-test-key"
DOMAIN = "detector-baselines/unit-test"
MARKED_BASES = 384


def random_dna(length: int, seed: int) -> str:
    rng = random.Random(seed)
    return "".join(rng.choice("ACGT") for _ in range(length))


def marked_dna() -> str:
    kmers = itertools.islice(itertools.product("ACGT", repeat=6), 64)
    candidates = tuple("".join(kmer) for kmer in kmers)

    def uniform(_context: str) -> tuple[tuple[str, ...], tuple[float, ...]]:
        return candidates, tuple(1.0 for _ in candidates)

    result = generate_synthid(
        uniform,
        "",
        steps=MARKED_BASES // 6,
        tournament=KeyedTournament(key=KEY, domain=DOMAIN),
        rng=random.Random(20261112),
    )
    assert len(result.dna) == MARKED_BASES
    return result.dna


MARKED = marked_dna()


class AlignedOracleTest(unittest.TestCase):
    def test_equals_the_verifier_window_at_that_start_and_length(self) -> None:
        start = 54
        read = random_dna(start, 1) + MARKED + random_dna(90, 2)
        tournament = KeyedTournament(key=KEY, domain=DOMAIN)
        verifier_window = next(
            score
            for score in score_synthid_unknown_boundary(
                read, base_length=MARKED_BASES, tournament=tournament
            )
            if score.base_start == start
        )
        result = detect_aligned_oracle(
            read,
            key=KEY,
            domain=DOMAIN,
            region_start=start,
            region_length=MARKED_BASES,
            region_on_forward_strand=True,
        )
        window = result.best_window
        self.assertEqual(result.detector_id, ALIGNED_ORACLE_DETECTOR)
        self.assertEqual(
            (window.g_ones, window.g_total, window.scored_tokens, window.repeated_contexts),
            (
                verifier_window.g_ones,
                verifier_window.g_total,
                verifier_window.scored_tokens,
                verifier_window.repeated_contexts,
            ),
        )
        self.assertEqual(
            result.minimum_local_log_p_value,
            fair_binomial_log_survival_probability(verifier_window.g_ones, verifier_window.g_total),
        )
        self.assertEqual(result.hypotheses_searched, 1)
        self.assertEqual((window.original_start, window.original_stop), (start, start + 384))
        self.assertTrue(result.detected)

    def test_reverse_complemented_read_is_oriented_back(self) -> None:
        start = 30
        read = random_dna(start, 3) + MARKED + random_dna(66, 4)
        forward = detect_aligned_oracle(
            read,
            key=KEY,
            domain=DOMAIN,
            region_start=start,
            region_length=MARKED_BASES,
            region_on_forward_strand=True,
        )
        flipped_start = len(read) - start - MARKED_BASES
        flipped = detect_aligned_oracle(
            reverse_complement(read),
            key=KEY,
            domain=DOMAIN,
            region_start=flipped_start,
            region_length=MARKED_BASES,
            region_on_forward_strand=False,
        )
        self.assertEqual(flipped.minimum_local_log_p_value, forward.minimum_local_log_p_value)
        self.assertEqual(flipped.best_window.orientation, "reverse_complement")
        self.assertEqual(flipped.best_window.original_start, flipped_start)
        self.assertEqual(flipped.best_window.oriented_start, start)

    def test_region_is_floored_to_a_multiple_of_six_and_must_fit(self) -> None:
        read = random_dna(100, 5) + MARKED
        result = detect_aligned_oracle(
            read,
            key=KEY,
            domain=DOMAIN,
            region_start=100,
            region_length=MARKED_BASES - 4,
            region_on_forward_strand=True,
        )
        self.assertEqual(result.best_window.window_base_length, MARKED_BASES - 6)
        with self.assertRaises(ValueError):
            detect_aligned_oracle(
                read,
                key=KEY,
                domain=DOMAIN,
                region_start=100,
                region_length=MARKED_BASES + 1,
                region_on_forward_strand=True,
            )

    def test_told_region_after_an_insertion_keeps_the_original_length(self) -> None:
        read = random_dna(60, 6) + MARKED[:200] + "A" + MARKED[200:]
        result = detect_aligned_oracle(
            read,
            key=KEY,
            domain=DOMAIN,
            region_start=60,
            region_length=MARKED_BASES,
            region_on_forward_strand=True,
        )
        self.assertEqual(result.best_window.window_base_length, MARKED_BASES)
        self.assertEqual(result.hypotheses_searched, 1)


class PhaseOnlyTest(unittest.TestCase):
    def test_finds_a_region_filling_the_read_at_every_phase(self) -> None:
        tournament = KeyedTournament(key=KEY, domain=DOMAIN)
        aligned = score_synthid_tokens(tokenize_fixed(MARKED), tournament)
        for phase in range(6):
            read = random_dna(phase, 10 + phase) + MARKED
            result = detect_phase_only(read, key=KEY, domain=DOMAIN)
            window = result.best_window
            self.assertEqual(result.detector_id, PHASE_ONLY_DETECTOR)
            self.assertTrue(result.detected, phase)
            self.assertEqual(result.hypotheses_searched, 12)
            self.assertEqual((window.orientation, window.oriented_start), ("forward", phase))
            self.assertEqual(window.window_base_length, MARKED_BASES)
            self.assertEqual((window.g_ones, window.g_total), (aligned.g_ones, aligned.g_total))
            flipped = detect_phase_only(reverse_complement(read), key=KEY, domain=DOMAIN)
            self.assertTrue(flipped.detected, phase)
            self.assertEqual(flipped.minimum_local_log_p_value, result.minimum_local_log_p_value)
            self.assertEqual(flipped.hypotheses_searched, 12)

    def test_frame_count_is_the_number_of_frames_actually_scored(self) -> None:
        for length in (34, 35, 36, 37, 41, 100, 389):
            read = random_dna(length, length)
            frames = sum((length - phase) // 6 > 4 for phase in range(6))
            result = detect_phase_only(read, key=KEY, domain=DOMAIN)
            self.assertEqual(result.hypotheses_searched, 2 * frames, length)
        with self.assertRaises(ValueError):
            detect_phase_only(random_dna(28, 1), key=KEY, domain=DOMAIN)

    def test_reads_beyond_the_context_history_raise(self) -> None:
        longest_ok = (1024 + 4 + 1) * 6 - 1
        self.assertEqual(longest_ok, 6173)
        with self.assertRaises(ValueError):
            detect_phase_only(random_dna(longest_ok + 1, 1), key=KEY, domain=DOMAIN)

    def test_runs_on_the_longest_s2_read(self) -> None:
        result = detect_phase_only(random_dna(6144, 7), key=KEY, domain=DOMAIN)
        self.assertEqual(result.hypotheses_searched, 12)
        self.assertLessEqual(result.best_window.scored_tokens, 1020)


class FineGridTest(unittest.TestCase):
    def test_restricted_to_the_verifier_lengths_equals_the_verifier(self) -> None:
        read = random_dna(70, 20) + MARKED + random_dna(480, 21)
        lengths = (384, 768)
        config = PositionIndependentSynthIDConfig(window_base_lengths=lengths)
        verifier = detect_synthid_position_independent(read, key=KEY, domain=DOMAIN, config=config)
        grid = detect_fine_grid(
            read, key=KEY, domain=DOMAIN, config=config, window_base_lengths=lengths
        )
        best = verifier.best_hypothesis
        self.assertEqual(grid.detector_id, FINE_GRID_DETECTOR)
        self.assertEqual(grid.hypotheses_searched, verifier.hypotheses_searched)
        self.assertEqual(grid.minimum_local_log_p_value, verifier.minimum_local_log_p_value)
        self.assertEqual(grid.sequence_log_p_value, verifier.sequence_log_p_value)
        self.assertEqual(grid.detected, verifier.detected)
        window = grid.best_window
        self.assertEqual(
            (window.orientation, window.oriented_start, window.window_base_length),
            (best.orientation, best.oriented_start, best.window_base_length),
        )
        self.assertEqual(
            (window.g_ones, window.g_total, window.scored_tokens, window.repeated_contexts),
            (best.g_ones, best.g_total, best.scored_tokens, best.repeated_contexts),
        )
        self.assertEqual(
            (window.original_start, window.original_stop),
            (best.original_start, best.original_stop),
        )

    def test_default_grid_window_count_matches_the_closed_form(self) -> None:
        for read_length in (384, 500, 600, 960):
            read = random_dna(read_length, read_length)
            result = detect_fine_grid(read, key=KEY, domain=DOMAIN)
            self.assertEqual(result.hypotheses_searched, expected_fine_grid_windows(read_length))
            lengths = fine_grid_lengths(read_length)
            self.assertEqual(lengths[0], 384)
            self.assertTrue(all(b - a == 96 for a, b in zip(lengths, lengths[1:], strict=False)))
        self.assertEqual(
            expected_fine_grid_windows(3456), 2 * sum(3456 - 384 - 96 * j + 1 for j in range(33))
        )
        self.assertEqual(len(fine_grid_lengths(6144)), 61)

    def test_matches_brute_force_scoring_of_every_substring(self) -> None:
        config = PositionIndependentSynthIDConfig(depth=7)
        tournament = KeyedTournament(key=KEY, domain=DOMAIN, depth=7)
        lengths = (36, 48)
        reads = (
            random_dna(90, 30),
            "ACGTAC" * 8 + random_dna(30, 31) + "GGGTTT" * 5 + random_dna(18, 32),
        )
        for read in reads:
            best = math.inf
            count = 0
            for oriented in (read, reverse_complement(read)):
                for length in lengths:
                    for start in range(len(read) - length + 1):
                        score = score_synthid_tokens(
                            tokenize_fixed(oriented[start : start + length]), tournament
                        )
                        count += 1
                        best = min(
                            best,
                            fair_binomial_log_survival_probability(score.g_ones, score.g_total),
                        )
            result = detect_fine_grid(
                read, key=KEY, domain=DOMAIN, config=config, window_base_lengths=lengths
            )
            self.assertEqual(result.hypotheses_searched, count)
            self.assertEqual(result.minimum_local_log_p_value, best)

    def test_reads_beyond_the_context_history_raise(self) -> None:
        with self.assertRaises(ValueError):
            detect_fine_grid(random_dna(6240, 1), key=KEY, domain=DOMAIN)

    def test_finds_the_marked_region_inside_flanks(self) -> None:
        read = random_dna(100, 40) + MARKED + random_dna(200, 41)
        result = detect_fine_grid(read, key=KEY, domain=DOMAIN)
        self.assertTrue(result.detected)
        self.assertEqual(result.best_window.oriented_start % 6, 100 % 6)


class CorrectionRuleTest(unittest.TestCase):
    def test_decisions_follow_log_m_plus_min_log_p(self) -> None:
        reads = (
            random_dna(100, 50) + MARKED + random_dna(200, 51),
            random_dna(700, 52),
            reverse_complement(random_dna(90, 53) + MARKED + random_dna(30, 54)),
        )
        for target in (0.01, 1e-6, 0.5):
            config = PositionIndependentSynthIDConfig(target_false_positive_rate=target)
            for read in reads:
                results = (
                    detect_aligned_oracle(
                        read,
                        key=KEY,
                        domain=DOMAIN,
                        region_start=0,
                        region_length=384,
                        region_on_forward_strand=True,
                        config=config,
                    ),
                    detect_phase_only(read, key=KEY, domain=DOMAIN, config=config),
                    detect_fine_grid(read, key=KEY, domain=DOMAIN, config=config),
                )
                for result in results:
                    uncapped = (
                        math.log(result.hypotheses_searched) + result.minimum_local_log_p_value
                    )
                    self.assertAlmostEqual(result.uncapped_sequence_log_p_value, uncapped)
                    self.assertEqual(result.sequence_log_p_value, min(0.0, uncapped))
                    self.assertEqual(result.detected, uncapped <= math.log(target))
                    self.assertEqual(result.target_false_positive_rate, target)


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_synthid_v5_detector_comparison as s2  # noqa: E402

LABEL = "toy-synthid-local-v5"
COHORT = "toy_cohort"


@functools.cache
def toy_continuation(draw_id: int) -> str:
    kmers = tuple("".join(k) for k in itertools.islice(itertools.product("ACGT", repeat=6), 64))

    def uniform(_context: str) -> tuple[tuple[str, ...], tuple[float, ...]]:
        return kmers, tuple(1.0 for _ in kmers)

    return generate_synthid(
        uniform,
        "",
        steps=512,
        tournament=KeyedTournament(key=fixture_key(draw_id), domain=f"{LABEL}/{COHORT}/C_tok"),
        rng=random.Random(900 + draw_id),
    ).dna


def fast_fine_grid(sequence: str, **kwargs: object) -> object:
    return detect_fine_grid(sequence, window_base_lengths=(384, 768), **kwargs)  # type: ignore[arg-type]


class CountBlockTest(unittest.TestCase):
    def test_only_prompt_level_blocks_carry_the_one_sided_bound(self) -> None:
        reads = s2._count_block(1, 20, control=True, prompt_level=False)
        prompts = s2._count_block(1, 10, control=True)
        marked_reads = s2._count_block(15, 20, control=False, prompt_level=False)
        self.assertNotIn("exact_one_sided_95_upper_bound", reads)
        self.assertEqual(reads["unit_note"], s2.READ_LEVEL_UNIT_NOTE)
        self.assertEqual((reads["positives"], reads["trials"], reads["rate"]), (1, 20, 0.05))
        self.assertIn("exact_two_sided_95_interval", reads)
        self.assertEqual(marked_reads["unit_note"], s2.READ_LEVEL_UNIT_NOTE)
        self.assertIn("exact_one_sided_95_upper_bound", prompts)
        self.assertNotIn("unit_note", prompts)
        self.assertLess(prompts["exact_one_sided_95_upper_bound"], 1.0)


class StudyScriptTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.root = root
        rng = random.Random(7)
        ids = [f"toy{i:02d}" for i in range(8)]
        self.prompts = {i: random_dna(384, 100 + n) for n, i in enumerate(ids)}
        (root / "natural").mkdir()
        with (root / "prompts.jsonl").open("w") as stream:
            for i in ids:
                span = self.prompts[i] + random_dna(2688, 200 + int(i[3:]))
                (root / "natural" / f"{i}.fasta").write_text(f">{i}\n{span}\n")
                stream.write(
                    json.dumps({"prompt_id": i, "sequence": self.prompts[i], "cohort_id": COHORT})
                    + "\n"
                )
        self.order = s2.evaluation_order(ids, label="toy-split", calibration_prompts=5)
        self.selected = self.order[:1]
        rows = [[], []]
        for case in ids:
            for draw in (0, 1):
                for scheme, dna in (
                    (s2.SYNTHID_SCHEME, toy_continuation(draw)),
                    (s2.ORDINARY_SCHEME, random_dna(3072, rng.randrange(10**6))),
                ):
                    rows[draw].append(
                        {
                            "experiment_label": LABEL,
                            "policy_id": "C_tok",
                            "cohort_id": COHORT,
                            "case_id": case,
                            "draw_id": draw,
                            "scheme": scheme,
                            "stream_domain": f"{LABEL}/{COHORT}/C_tok",
                            "generated_dna": dna,
                        }
                    )
        self.files = []
        for draw in (0, 1):
            path = root / f"draw_{draw}.jsonl"
            path.write_text("".join(json.dumps(row) + "\n" for row in rows[draw]))
            self.files.append(path)
        (root / "protocol.md").write_text("toy protocol\n")

    def argv(self, out: str, *extra: str) -> list[str]:
        root = self.root
        return [
            "--sequence-file",
            str(self.files[0]),
            "--sequence-file",
            str(self.files[1]),
            "--cohort-jsonl",
            str(root / "prompts.jsonl"),
            "--natural-dir",
            str(root / "natural"),
            "--protocol",
            str(root / "protocol.md"),
            "--output-dir",
            str(root / out),
            "--experiment-label",
            LABEL,
            "--policy-id",
            "C_tok",
            "--split-label",
            "toy-split",
            "--calibration-prompts",
            "5",
            "--evaluated-prompts",
            "3",
            "--prompts",
            "1",
            *extra,
        ]

    def test_split_order_matches_the_repository_split(self) -> None:
        ids = list(self.prompts)
        assignments = deterministic_prompt_split(ids, calibration_prompts=5, label="toy-split")
        self.assertEqual(
            sorted(self.order), sorted(i for i, a in assignments.items() if a == "evaluation")
        )

    def test_reads_use_the_existing_layouts_and_insertion_rule(self) -> None:
        case = self.selected[0]
        pool = NaturalPool(
            {i: self.prompts[i] + random_dna(2688, 5 + n) for n, i in enumerate(self.prompts)}
        )
        continuation = toy_continuation(0)
        reads, position = s2.make_reads(
            prompt=self.prompts[case], continuation=continuation, pool=pool, case_id=case, draw_id=0
        )
        self.assertEqual(tuple(reads), s2.CELLS)
        edit = deterministic_single_base_edit(
            continuation, condition="insertion_1nt", case_id=case, draw_id=0
        )
        self.assertEqual(position, edit.position)
        self.assertEqual(reads["reference_insertion"].sequence, self.prompts[case] + edit.sequence)
        self.assertEqual(len(reads["reference_insertion"].sequence), 3457)
        for name in s2.EMBEDDED_CELLS:
            expected = build_read(
                cell_by_name(name),
                prompt=self.prompts[case],
                continuation=continuation,
                pool=pool,
                case_id=case,
                draw_id=0,
            )
            self.assertEqual(reads[name], expected)
            self.assertEqual(len(expected.sequence), 6144)
        self.assertEqual(
            reads["reference"],
            build_read(
                cell_by_name("A_l3072"),
                prompt=self.prompts[case],
                continuation=continuation,
                pool=pool,
                case_id=case,
                draw_id=0,
            ),
        )

    def test_end_to_end_run_resume_and_summary(self) -> None:
        with mock.patch.object(s2, "detect_fine_grid", fast_fine_grid):
            self.assertEqual(s2.main(self.argv("out")), 0)
        out = self.root / "out"
        summary = json.loads((out / "summary.json").read_text())
        with gzip.open(out / "trials.jsonl.gz", "rt") as stream:
            rows = [json.loads(line) for line in stream]
        self.assertEqual(len(rows), s2.ROWS_PER_PROMPT)
        self.assertEqual(summary["total_decisions"], len(rows))
        self.assertEqual(len(summary["cells_in_summary"]), 5 * 4 * 2)
        self.assertEqual(summary["classification"], "pending_evidence_admission")
        self.assertIn("cpu_model", summary["runtime"])
        self.assertFalse(summary["runtime"]["seconds_measured_under_parallel_workers"])
        self.assertEqual({r["case_id"] for r in rows}, set(self.selected))
        for row in rows:
            self.assertGreaterEqual(row["seconds"], 0.0)
            if row["cell"] == "reference_insertion":
                self.assertEqual(row["read_bases"], 3457)
            if row["cell"].startswith("B_"):
                self.assertEqual(row["read_bases"], 6144)
            if row["detector"] == "aligned_oracle":
                self.assertEqual(row["windows_searched"], 1)
                if not row["cell"].startswith("B_"):
                    self.assertEqual(
                        (row["told_region_start"], row["told_region_length"]), (384, 3072)
                    )
            if row["detector"] == "phase_only":
                self.assertEqual(row["windows_searched"], 12)
            if row["detector"] == "verifier":
                n = row["read_bases"]
                self.assertEqual(
                    row["windows_searched"], 2 * sum(n - L + 1 for L in (384, 768, 1536, 3072))
                )
            uncapped = math.log(row["windows_searched"]) + row["smallest_window_log_p"]
            self.assertAlmostEqual(row["corrected_log_p_uncapped"], uncapped)
            self.assertEqual(row["detected"], uncapped <= math.log(0.01))
            self.assertEqual(row["corrected_log_p"], min(0.0, uncapped))
        marked_reference = [
            r
            for r in rows
            if r["family"] == s2.POSITIVE
            and r["cell"] == "reference"
            and r["detector"] != "fine_grid"
        ]
        self.assertTrue(all(r["detected"] for r in marked_reference))
        block = next(
            c
            for c in summary["cells_in_summary"]
            if (c["cell"], c["detector"], c["family"]) == ("reference", "verifier", s2.POSITIVE)
        )
        self.assertEqual(block["reads"]["trials"], 2)
        self.assertEqual(block["prompt_level"]["trials"], 1)
        lo, hi = block["reads"]["exact_two_sided_95_interval"]
        self.assertTrue(lo <= block["reads"]["rate"] <= hi)
        control = next(
            c
            for c in summary["cells_in_summary"]
            if (c["cell"], c["detector"], c["family"]) == ("reference", "verifier", s2.CONTROL)
        )
        self.assertNotIn("exact_one_sided_95_upper_bound", control["reads"])
        self.assertEqual(control["reads"]["unit_note"], s2.READ_LEVEL_UNIT_NOTE)
        self.assertIn("exact_two_sided_95_interval", control["reads"])
        self.assertIn("exact_one_sided_95_upper_bound", control["prompt_level"])
        self.assertNotIn("unit_note", control["prompt_level"])
        self.assertNotIn("unit_note", block["prompt_level"])
        self.assertNotIn("exact_one_sided_95_upper_bound", block["reads"])

        # A timing-only run is flagged and forced to one process (shards copied: no recompute).
        shutil.copytree(out / "shards", self.root / "timing" / "shards")
        with mock.patch.object(s2, "detect_fine_grid", side_effect=AssertionError("rerun")):
            s2.main(self.argv("timing", "--timing-only", "--workers", "8"))
        timing = json.loads((self.root / "timing" / "summary.json").read_text())
        self.assertTrue(timing["runtime"]["timing_only"])
        self.assertEqual(timing["runtime"]["workers"], 1)

        # Resume: shards are kept, outputs may be rebuilt, nothing is overwritten.
        shard = out / "shards" / f"{self.selected[0]}.json"
        before = shard.read_bytes()
        (out / "summary.json").unlink()
        (out / "trials.jsonl.gz").unlink()
        with mock.patch.object(s2, "detect_fine_grid", side_effect=AssertionError("rerun")):
            self.assertEqual(s2.main(self.argv("out")), 0)
        self.assertEqual(shard.read_bytes(), before)
        with self.assertRaises(FileExistsError):
            s2.atomic_write_json(shard, {"x": 1})
        with self.assertRaises(FileExistsError):
            s2.main(self.argv("out", "--finalize-only"))

    def test_rejects_generation_rows_of_another_run(self) -> None:
        argv = self.argv("bad")
        argv[argv.index(LABEL)] = "other-label"
        with self.assertRaises(ValueError):
            s2.main(argv)


if __name__ == "__main__":
    unittest.main()
