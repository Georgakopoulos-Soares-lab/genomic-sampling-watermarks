from __future__ import annotations

import gzip
import hashlib
import itertools
import json
import math
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_synthid_v5_null_calibration as s3  # noqa: E402

from genomic_watermarks.synthid import KeyedTournament, generate_synthid  # noqa: E402
from genomic_watermarks.synthid_position_independent import (  # noqa: E402
    PositionIndependentSynthIDConfig,
    detect_synthid_position_independent,
)


def random_dna(length: int, seed: int) -> str:
    rng = random.Random(seed)
    return "".join(rng.choice("ACGT") for _ in range(length))


class KeyDerivationTest(unittest.TestCase):
    def test_matches_formula(self) -> None:
        for index in (0, 1, 17, 63):
            expected = hashlib.sha256(f"synthid-review-v5/null-key/{index}".encode()).digest()
            self.assertEqual(s3.null_key_bytes(index), expected)
            self.assertEqual(s3.null_key_bytes(index), s3.null_key_bytes(index))

    def test_sixty_four_distinct_keys_and_range_check(self) -> None:
        keys = {s3.null_key_bytes(i) for i in range(64)}
        self.assertEqual(len(keys), 64)
        with self.assertRaises(ValueError):
            s3.null_key_bytes(64)
        with self.assertRaises(ValueError):
            s3.null_key_bytes(-1)

    def test_fixed_labels(self) -> None:
        self.assertEqual(s3.NULL_DOMAIN, "synthid-review-v5/null")
        self.assertEqual(s3.KEY_COUNT, 64)
        self.assertEqual(s3.expected_windows(3072), 13_064)
        self.assertEqual(s3.expected_windows(3456), 16_136)


class ExactBoundTest(unittest.TestCase):
    def test_zero_and_full_counts(self) -> None:
        lower, upper = s3.exact_interval(0, 100)
        self.assertEqual(lower, 0.0)
        self.assertAlmostEqual(upper, 1.0 - 0.025 ** (1 / 100), places=9)
        lower, upper = s3.exact_interval(100, 100)
        self.assertEqual(upper, 1.0)
        self.assertAlmostEqual(lower, 0.025 ** (1 / 100), places=9)
        self.assertEqual(s3.exact_lower_bound(0, 100), 0.0)
        self.assertAlmostEqual(s3.exact_lower_bound(100, 100), 0.05 ** (1 / 100), places=9)

    def test_known_interval(self) -> None:
        lower, upper = s3.exact_interval(5, 10)
        self.assertAlmostEqual(lower, 0.18708, places=4)
        self.assertAlmostEqual(upper, 0.81292, places=4)

    def test_one_sided_lower_solves_the_binomial_tail(self) -> None:
        for successes, trials in ((1, 20), (5, 10), (30, 250)):
            lower = s3.exact_lower_bound(successes, trials)
            tail = sum(
                math.comb(trials, k) * lower**k * (1 - lower) ** (trials - k)
                for k in range(successes, trials + 1)
            )
            self.assertAlmostEqual(tail, 0.05, places=9)
        self.assertLess(s3.exact_lower_bound(5, 10), s3.exact_interval(5, 10)[0] + 0.1)
        self.assertGreater(s3.exact_lower_bound(5, 10), s3.exact_interval(5, 10)[0])

    def test_invalid_counts(self) -> None:
        with self.assertRaises(ValueError):
            s3.exact_lower_bound(3, 2)
        with self.assertRaises(ValueError):
            s3.exact_lower_bound(0, 0)


class CalibrationTableTest(unittest.TestCase):
    def test_counts_on_synthetic_p_values(self) -> None:
        p_values = [0.005, 0.01, 0.02, 0.05, 0.07, 0.10, 0.2, 0.25, 0.4, 0.5, 0.9, 1.0]
        table = s3.calibration_table([math.log(p) for p in p_values])
        counts = {row["nominal_level"]: row["count"] for row in table}
        # P <= t is inclusive; log(0.01) is the same float the detector threshold uses.
        self.assertEqual(counts, {0.01: 2, 0.05: 4, 0.10: 6, 0.25: 8, 0.50: 10})
        for row in table:
            self.assertEqual(row["decisions"], 12)
            self.assertAlmostEqual(row["fraction"], row["count"] / 12)
            self.assertLessEqual(row["exact_two_sided_95_interval"][0], row["fraction"])
            self.assertGreaterEqual(row["exact_two_sided_95_interval"][1], row["fraction"])

    def test_exceeds_nominal_rule(self) -> None:
        # Exactly uniform P-values: no level can be exceeded.
        uniform = [math.log((i + 0.5) / 2000) for i in range(2000)]
        for row in s3.calibration_table(uniform):
            self.assertFalse(row["exceeds_nominal"], row)
            self.assertLess(row["exact_one_sided_95_lower_bound"], row["nominal_level"])
        # Everything tiny: lower bound far above every nominal level.
        tiny = [math.log(1e-6)] * 200
        for row in s3.calibration_table(tiny):
            self.assertTrue(row["exceeds_nominal"], row)
        # A 3% rate at 0.01 over 5,000 decisions has a lower bound above 0.01.
        mixed = [math.log(0.005)] * 150 + [math.log(0.9)] * 4850
        first = s3.calibration_table(mixed)[0]
        self.assertTrue(first["exceeds_nominal"])
        self.assertEqual(first["count"], 150)

    def test_empty_input_rejected(self) -> None:
        with self.assertRaises(ValueError):
            s3.calibration_table([])


class ScoringTest(unittest.TestCase):
    def test_plain_call_equivalence_and_key_independence_of_rows(self) -> None:
        read = random_dna(768, 11)
        rows = s3.score_read_under_keys(
            read,
            case_id="x",
            draw_id=0,
            family=s3.FAMILY_ORDINARY,
            model="carbon",
            key_indices=(0, 1, 2),
        )
        self.assertEqual([r["key_index"] for r in rows], [0, 1, 2])
        for row in rows:
            direct = detect_synthid_position_independent(
                read,
                key=s3.null_key_bytes(row["key_index"]),
                domain=s3.NULL_DOMAIN,
                config=PositionIndependentSynthIDConfig(),
            )
            self.assertEqual(row["detected"], direct.detected)
            self.assertEqual(row["sequence_log_p_value"], direct.sequence_log_p_value)
            self.assertEqual(row["minimum_local_log_p_value"], direct.minimum_local_log_p_value)
            self.assertEqual(row["hypotheses_searched"], direct.hypotheses_searched)
            self.assertEqual(row["read_bases"], 768)
        s3.check_window_counts(rows)

    def test_marked_read_detected_only_under_its_own_key(self) -> None:
        candidates = tuple(
            "".join(chars) for chars in itertools.islice(itertools.product("ATCG", repeat=6), 64)
        )

        def uniform(_context: str) -> tuple[tuple[str, ...], tuple[float, ...]]:
            return candidates, tuple(1.0 for _ in candidates)

        tournament = KeyedTournament(key=s3.null_key_bytes(0), domain=s3.NULL_DOMAIN)
        marked = generate_synthid(
            uniform, "", steps=256, tournament=tournament, rng=random.Random(5)
        ).dna
        rows = s3.score_read_under_keys(
            marked,
            case_id="m",
            draw_id=0,
            family=s3.FAMILY_MARKED,
            model="carbon",
            key_indices=(0, 1, 2),
        )
        detected = {r["key_index"]: r["detected"] for r in rows}
        self.assertEqual(detected, {0: True, 1: False, 2: False})

    def test_window_count_assertion_fires(self) -> None:
        rows = s3.score_read_under_keys(
            random_dna(768, 3),
            case_id="x",
            draw_id=None,
            family=s3.FAMILY_NATURAL,
            model=None,
            key_indices=(0,),
        )
        rows[0]["hypotheses_searched"] += 1
        with self.assertRaises(AssertionError):
            s3.check_window_counts(rows)


class SummaryTest(unittest.TestCase):
    def _rows(self, keys: int = 3) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for read in range(40):
            for key in range(keys):
                hit = read == 0 and key == 1
                rows.append(
                    {
                        "case_id": f"c{read:02d}",
                        "draw_id": 0,
                        "family": "f",
                        "model": "m",
                        "key_index": key,
                        "read_bases": 3456,
                        "hypotheses_searched": 16136,
                        "detected": hit,
                        "sequence_log_p_value": math.log(0.004 if hit else 0.6),
                        "minimum_local_log_p_value": -3.0,
                    }
                )
        return rows

    def test_summary_fields(self) -> None:
        summary = s3.summarize_trials(self._rows(), key_count=3)  # type: ignore[arg-type]
        self.assertEqual(summary["decisions"], 120)
        self.assertEqual(summary["reads"], 40)
        self.assertEqual(summary["positives_at_0_01"], 1)
        self.assertIn("anti-conservative", summary["pooled_bounds_note"])
        self.assertIn("share reads and keys", summary["pooled_bounds_note"])
        self.assertEqual(summary["per_key"][1]["positives"], 1)
        self.assertEqual(summary["per_key_rate_min"], 0.0)
        self.assertEqual(summary["per_key_rate_max"], 1 / 40)
        self.assertEqual(summary["per_key_rate_median"], 0.0)
        anyk = summary["reads_positive_under_at_least_one_key"]
        self.assertEqual((anyk["count"], anyk["reads"]), (1, 40))
        self.assertEqual(summary["calibration_table"][0]["count"], 1)
        self.assertEqual(summary["hypotheses_searched_counts"], {"16136": 120})

    def test_missing_key_rejected(self) -> None:
        rows = [r for r in self._rows() if r["key_index"] != 2]
        with self.assertRaises(ValueError):
            s3.summarize_trials(rows, key_count=3)  # type: ignore[arg-type]


class InputLoadingTest(unittest.TestCase):
    def test_fasta_parser(self) -> None:
        self.assertEqual(s3.parse_fasta_sequence(">h\nACG\nTT\n"), "ACGTT")
        with self.assertRaises(ValueError):
            s3.parse_fasta_sequence("ACG\n")
        with self.assertRaises(ValueError):
            s3.parse_fasta_sequence(">a\nAC\n>b\nGT\n")

    def test_span_verification(self) -> None:
        prompt = random_dna(384, 1)
        span = prompt + random_dna(2688, 2)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "p1.fasta").write_text(f">p1\n{span}\n")
            self.assertEqual(s3.load_natural_spans(directory, {"p1": prompt}), {"p1": span})
            (directory / "p1.fasta").write_text(f">p1\n{span[:-6]}\n")
            with self.assertRaises(ValueError):
                s3.load_natural_spans(directory, {"p1": prompt})
            (directory / "p1.fasta").write_text(f">p1\n{span[:-1]}N\n")
            with self.assertRaises(ValueError):
                s3.load_natural_spans(directory, {"p1": prompt})
            (directory / "p1.fasta").write_text(f">p1\n{random_dna(3072, 9)}\n")
            with self.assertRaises(ValueError):
                s3.load_natural_spans(directory, {"p1": prompt})
            with self.assertRaises(FileNotFoundError):
                s3.load_natural_spans(directory, {"p2": prompt})

    def test_evaluated_prompts_are_held_out_in_rank_order(self) -> None:
        ids = [f"p{i:03d}" for i in range(80)]
        first = s3.evaluated_case_ids(ids, 5)
        self.assertEqual(first, s3.evaluated_case_ids(ids, 16)[:5])
        assignments = s3.deterministic_prompt_split(
            ids, calibration_prompts=64, label=s3.CALIBRATION_SPLIT_LABEL
        )
        self.assertTrue(all(assignments[i] == "evaluation" for i in s3.evaluated_case_ids(ids, 16)))
        with self.assertRaises(ValueError):
            s3.evaluated_case_ids(ids, 17)


class EndToEndTest(unittest.TestCase):
    """A tiny run of the script on synthetic cohort files with three keys."""

    def _write_cohort(self, directory: Path) -> tuple[list[str], dict[str, str]]:
        ids = [f"p{i:03d}" for i in range(70)]
        prompts = {case_id: random_dna(384, 100 + i) for i, case_id in enumerate(ids)}
        lines = []
        for case_id in ids:
            sequence = prompts[case_id]
            lines.append(
                json.dumps(
                    {
                        "prompt_id": case_id,
                        "sequence": sequence,
                        "cohort_id": "toy",
                        "organism": "x",
                        "accession": "A",
                        "start": 1,
                        "stop": 384,
                        "sequence_sha256": hashlib.sha256(sequence.encode()).hexdigest(),
                    }
                )
            )
        (directory / "prompts.jsonl").write_text("\n".join(lines) + "\n")
        return ids, prompts

    def _generation(self, directory: Path, evaluated: list[str], prompts: dict[str, str]) -> Path:
        records = []
        for i, case_id in enumerate(evaluated):
            for scheme in (s3.SYNTHID_SCHEME, s3.ORDINARY_SCHEME):
                dna = random_dna(3072, 500 + 2 * i + (scheme == s3.ORDINARY_SCHEME))
                records.append(
                    {
                        "case_id": case_id,
                        "draw_id": 0,
                        "scheme": scheme,
                        "cohort_id": "toy",
                        "policy_id": "C_tok",
                        "experiment_label": "toy-label",
                        "generated_dna": dna,
                        "sequence_sha256": hashlib.sha256(dna.encode()).hexdigest(),
                        "prompt_sequence_sha256": hashlib.sha256(
                            prompts[case_id].encode()
                        ).hexdigest(),
                    }
                )
        path = directory / "draw_00_sequences.jsonl"
        path.write_text("".join(json.dumps(r) + "\n" for r in records))
        return path

    def test_model_family_run_resume_and_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ids, prompts = self._write_cohort(base)
            evaluated = s3.evaluated_case_ids(ids, 2)
            sequences = self._generation(base, evaluated, prompts)
            out = base / "out"
            argv = [
                "--family",
                s3.FAMILY_ORDINARY,
                "--model",
                "carbon",
                "--cohort-jsonl",
                str(base / "prompts.jsonl"),
                "--cohort-id",
                "toy",
                "--sequences",
                str(sequences),
                "--experiment-label",
                "toy-label",
                "--n-eval",
                "2",
                "--keys",
                "3",
                "--output-dir",
                str(out),
                "--workers",
                "1",
            ]
            self.assertEqual(s3.main(argv), 0)
            summary = json.loads((out / "summary.json").read_text())
            self.assertEqual(summary["decisions"], 6)
            self.assertEqual(summary["reads"], 2)
            self.assertEqual(summary["keys"], 3)
            self.assertTrue(summary["partial_run"])
            self.assertEqual(summary["hypotheses_searched_counts"], {"16136": 6})
            self.assertEqual(len(summary["per_key"]), 3)
            self.assertEqual(len(summary["calibration_table"]), 5)
            self.assertEqual(summary["protocol"]["id"], s3.PROTOCOL_ID)
            self.assertIn("python", summary["provenance"])
            self.assertIn("cpu_model", summary["provenance"])
            self.assertIn("scripts/run_synthid_v5_null_calibration.py", summary["code_sha256"])
            with gzip.open(out / "trials.jsonl.gz", "rt") as handle:
                rows = [json.loads(line) for line in handle]
            self.assertEqual(len(rows), 6)
            self.assertEqual(
                set(rows[0]),
                {
                    "case_id",
                    "draw_id",
                    "family",
                    "model",
                    "key_index",
                    "read_bases",
                    "hypotheses_searched",
                    "detected",
                    "sequence_log_p_value",
                    "minimum_local_log_p_value",
                },
            )
            # No key material anywhere in the outputs.
            blob = (out / "summary.json").read_text() + gzip.open(
                out / "trials.jsonl.gz"
            ).read().decode()
            for shard in (out / "shards").iterdir():
                blob += shard.read_text()
            for index in range(3):
                self.assertNotIn(s3.null_key_bytes(index).hex(), blob)
            # Rerun refuses to replace a finalized result; shards resume only when identical.
            with self.assertRaises(FileExistsError):
                s3.main(argv)
            (out / "summary.json").unlink()
            (out / "trials.jsonl.gz").unlink()
            self.assertEqual(s3.main(argv), 0)
            shard = next((out / "shards").iterdir())
            payload = json.loads(shard.read_text())
            payload["read_sha256"] = "0" * 64
            shard.write_text(json.dumps(payload))
            (out / "summary.json").unlink()
            (out / "trials.jsonl.gz").unlink()
            with self.assertRaises(ValueError):
                s3.main(argv)

    def test_wrong_label_rejected_and_natural_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ids, prompts = self._write_cohort(base)
            evaluated = s3.evaluated_case_ids(ids, 2)
            sequences = self._generation(base, evaluated, prompts)
            common = [
                "--cohort-jsonl",
                str(base / "prompts.jsonl"),
                "--cohort-id",
                "toy",
                "--keys",
                "3",
            ]
            with self.assertRaises(ValueError):
                s3.main(
                    [
                        "--family",
                        s3.FAMILY_MARKED,
                        "--model",
                        "carbon",
                        "--sequences",
                        str(sequences),
                        "--experiment-label",
                        "other-label",
                        "--n-eval",
                        "2",
                        "--output-dir",
                        str(base / "bad"),
                        *common,
                    ]
                )
            span_dir = base / "spans"
            span_dir.mkdir()
            for case_id in ids[:2]:
                (span_dir / f"{case_id}.fasta").write_text(
                    f">{case_id}\n{prompts[case_id]}{random_dna(2688, int(case_id[1:]))}\n"
                )
            out = base / "natural"
            self.assertEqual(
                s3.main(
                    [
                        "--family",
                        s3.FAMILY_NATURAL,
                        "--span-dir",
                        str(span_dir),
                        "--limit",
                        "2",
                        "--output-dir",
                        str(out),
                        "--workers",
                        "2",
                        *common,
                    ]
                ),
                0,
            )
            summary = json.loads((out / "summary.json").read_text())
            self.assertEqual(summary["decisions"], 6)
            self.assertEqual(summary["hypotheses_searched_counts"], {"13064": 6})
            self.assertIsNone(summary["model"])
            manifest = [i for i in summary["inputs"] if i["role"] == "natural_span_manifest"][0]
            self.assertEqual(manifest["files"], 2)


if __name__ == "__main__":
    unittest.main()
