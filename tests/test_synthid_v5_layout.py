"""Tests for the v5 layout-study runner (``scripts/run_synthid_v5_layout.py``), on toy data."""

from __future__ import annotations

import contextlib
import gzip
import hashlib
import io
import itertools
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_synthid_v5_layout as runner  # noqa: E402

from genomic_watermarks.dna import reverse_complement  # noqa: E402
from genomic_watermarks.large_validation import (  # noqa: E402
    CALIBRATION_SPLIT_LABEL,
    fixture_key,
)
from genomic_watermarks.review_layouts import (  # noqa: E402
    NaturalPool,
    build_read,
    cell_by_name,
    layout_cells,
)
from genomic_watermarks.synthid import (  # noqa: E402
    SYNTHID_SCHEME,
    KeyedTournament,
    generate_synthid,
)
from genomic_watermarks.synthid_position_independent import (  # noqa: E402
    PositionIndependentSynthIDConfig,
    detect_synthid_position_independent,
)
from genomic_watermarks.watermark import ORDINARY_SCHEME  # noqa: E402

LABEL = "toy-synthid-local-v5"
COHORT = "toy_cohort_v5"
POLICY = "C_tok"
DOMAIN = f"{LABEL}/{COHORT}/{POLICY}"
CASES = tuple(f"toy{index:02d}" for index in range(6))
CALIBRATION = 2
SMALL = ("A_l0768",)
TOY_CELLS = (
    "A_l3072",
    "A_l0768",
    "C_l0768_o1_fw",
    "C_l0768_o1_rc",
    "D_l0768_f0000",
    "F_c0768",
)


def random_dna(length: int, seed: int) -> str:
    rng = random.Random(seed)
    return "".join(rng.choice("ACGT") for _ in range(length))


def toy_marked(draw_id: int, seed: int) -> str:
    candidates = tuple(
        "".join(chars) for chars in itertools.islice(itertools.product("ATCG", repeat=6), 64)
    )

    def uniform(_context: str) -> tuple[tuple[str, ...], tuple[float, ...]]:
        return candidates, tuple(1.0 for _ in candidates)

    tournament = KeyedTournament(key=fixture_key(draw_id), domain=DOMAIN)
    return generate_synthid(
        uniform, "", steps=512, tournament=tournament, rng=random.Random(seed)
    ).dna


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class World:
    """A six-prompt synthetic cohort with generation rows for the evaluated prompts."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.prompts = {case: random_dna(384, 10 + index) for index, case in enumerate(CASES)}
        self.spans = {
            case: self.prompts[case] + random_dna(2688, 50 + index)
            for index, case in enumerate(CASES)
        }
        self.cohort = root / "prompts.jsonl"
        write_jsonl(
            self.cohort,
            [
                {
                    "prompt_id": case,
                    "sequence": self.prompts[case],
                    "cohort_id": COHORT,
                    "organism": "toy",
                    "accession": "TOY.1",
                    "start": 1,
                    "stop": 384,
                    "sequence_sha256": hashlib.sha256(self.prompts[case].encode()).hexdigest(),
                }
                for case in CASES
            ],
        )
        self.natural = root / "natural"
        self.natural.mkdir()
        for case, span in self.spans.items():
            wrapped = "\n".join(span[i : i + 70] for i in range(0, len(span), 70))
            (self.natural / f"{case}.fasta").write_text(f">{case} toy\n{wrapped}\n")
        self.evaluated = runner.held_out_order(
            CASES, calibration_prompts=CALIBRATION, label=CALIBRATION_SPLIT_LABEL
        )[:2]
        self.marked: dict[tuple[str, int], str] = {}
        self.ordinary: dict[tuple[str, int], str] = {}
        generation: dict[int, list[dict[str, Any]]] = {0: [], 1: []}
        for index, case in enumerate(self.evaluated):
            for draw in (0, 1):
                self.marked[(case, draw)] = toy_marked(draw, 1000 + 10 * index + draw)
                self.ordinary[(case, draw)] = random_dna(3072, 2000 + 10 * index + draw)
                for scheme, dna in (
                    (SYNTHID_SCHEME, self.marked[(case, draw)]),
                    (ORDINARY_SCHEME, self.ordinary[(case, draw)]),
                ):
                    generation[draw].append(
                        {
                            "case_id": case,
                            "draw_id": draw,
                            "cohort_id": COHORT,
                            "policy_id": POLICY,
                            "experiment_label": LABEL,
                            "scheme": scheme,
                            "stream_domain": DOMAIN,
                            "generated_dna": dna,
                        }
                    )
        self.sequence_files = []
        for draw, rows in generation.items():
            path = root / f"generation/draw_{draw:02d}_sequences.jsonl"
            write_jsonl(path, rows)
            self.sequence_files.append(path)
        self.s0 = root / "s0_trials.jsonl.gz"
        self.write_s0(self.s0, flip=False)

    def write_s0(self, path: Path, *, flip: bool) -> None:
        rows = []
        for case in self.evaluated:
            for draw in (0, 1):
                for family, dna in (
                    (runner.POSITIVE, self.marked[(case, draw)]),
                    (runner.PRIMARY_NULL, self.ordinary[(case, draw)]),
                ):
                    result = detect_synthid_position_independent(
                        self.prompts[case] + dna, key=fixture_key(draw), domain=DOMAIN
                    )
                    rows.append(
                        {
                            "case_id": case,
                            "draw_id": draw,
                            "condition": "clean",
                            "family": family,
                            "detected": (not result.detected) if flip else result.detected,
                            "hypotheses_searched": result.hypotheses_searched,
                            "minimum_local_log_p_value": result.minimum_local_log_p_value,
                            "best_hypothesis": {
                                "g_ones": result.best_hypothesis.g_ones,
                                "g_total": result.best_hypothesis.g_total,
                            },
                        }
                    )
        rows.append(
            {**rows[0], "condition": "substitution_1nt", "detected": not rows[0]["detected"]}
        )
        text = "".join(json.dumps(row) + "\n" for row in rows)
        if path.suffix == ".gz":
            with gzip.open(path, "wt", encoding="utf-8") as handle:
                handle.write(text)
        else:
            path.write_text(text, encoding="utf-8")

    def argv(
        self,
        output: str,
        *extra: str,
        s0: bool | Path | None = True,
        cells: tuple[str, ...] = TOY_CELLS,
    ) -> list[str]:
        """``s0``: True = the matching S0 file, a Path = that file, False = --no-s0-check,
        None = neither option (invalid)."""

        command = [
            "--sequence-file", str(self.sequence_files[0]),
            "--sequence-file", str(self.sequence_files[1]),
            "--cohort-jsonl", str(self.cohort),
            "--expected-cohort-jsonl-sha256", "",
            "--natural-dir", str(self.natural),
            "--experiment-label", LABEL,
            "--cohort-id", COHORT,
            "--policy-id", POLICY,
            "--evaluated-prompts", "2",
            "--calibration-prompts", str(CALIBRATION),
            "--output-dir", str(self.root / output),
            "--cells", *cells,
        ]  # fmt: skip
        if s0 is True:
            command += ["--s0-trials", str(self.s0)]
        elif isinstance(s0, Path):
            command += ["--s0-trials", str(s0)]
        elif s0 is False:
            command += ["--no-s0-check"]
        return [*command, *extra]


class RunnerTestCase(unittest.TestCase):
    world: World
    temporary: tempfile.TemporaryDirectory[str]

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.world = World(Path(cls.temporary.name))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()


class PromptOrderAndInputsTest(RunnerTestCase):
    def test_held_out_order_is_split_rank_order_without_calibration_prompts(self) -> None:
        order = runner.held_out_order(
            CASES, calibration_prompts=CALIBRATION, label=CALIBRATION_SPLIT_LABEL
        )
        self.assertEqual(len(order), len(CASES) - CALIBRATION)
        ranked = sorted(
            CASES,
            key=lambda case: hashlib.sha256(
                f"{CALIBRATION_SPLIT_LABEL}\x00{case}".encode()
            ).digest(),
        )
        self.assertEqual(order, ranked[CALIBRATION:])
        self.assertEqual(
            order,
            runner.held_out_order(
                list(reversed(CASES)),
                calibration_prompts=CALIBRATION,
                label=CALIBRATION_SPLIT_LABEL,
            ),
        )

    def test_natural_spans_require_the_prompt_as_their_first_384_bases(self) -> None:
        cases = runner.load_context_cases_jsonl(self.world.cohort)
        spans, digests = runner.load_natural_spans(self.world.natural, cases)
        self.assertEqual(spans, self.world.spans)
        self.assertEqual(set(digests), set(CASES))
        with tempfile.TemporaryDirectory() as directory:
            broken = Path(directory)
            for case in CASES:
                (broken / f"{case}.fasta").write_text(f">x\n{self.world.spans[case]}\n")
            (broken / "toy00.fasta").write_text(">x\n" + "A" * 3072 + "\n")
            with self.assertRaises(ValueError):
                runner.load_natural_spans(broken, cases)
            (broken / "toy00.fasta").unlink()
            with self.assertRaises(FileNotFoundError):
                runner.load_natural_spans(broken, cases)

    def test_generation_records_are_verified(self) -> None:
        records = runner.load_generation_records(
            self.world.sequence_files,
            selected=self.world.evaluated,
            prompts=self.world.prompts,
            label=LABEL,
            cohort_id=COHORT,
            policy_id=POLICY,
            generation_experiment_id=None,
        )
        case = self.world.evaluated[0]
        self.assertEqual(records[case][1]["watermarked"], self.world.marked[(case, 1)])
        self.assertEqual(records[case][0]["domain"], DOMAIN)
        with self.assertRaises(ValueError):
            runner.load_generation_records(
                self.world.sequence_files,
                selected=self.world.evaluated,
                prompts=self.world.prompts,
                label="another-label",
                cohort_id=COHORT,
                policy_id=POLICY,
                generation_experiment_id=None,
            )
        with self.assertRaises(ValueError):  # a prompt with no generation rows
            runner.load_generation_records(
                self.world.sequence_files,
                selected=[*self.world.evaluated, "toy05"],
                prompts=self.world.prompts,
                label=LABEL,
                cohort_id=COHORT,
                policy_id=POLICY,
                generation_experiment_id=None,
            )

    def test_cell_selection(self) -> None:
        self.assertEqual(len(runner.selected_cells(None)), 54)
        self.assertEqual(
            [cell.cell for cell in runner.selected_cells(["F_c0768,A_l0768"])],
            ["A_l0768", "F_c0768"],
        )
        with self.assertRaises(ValueError):
            runner.selected_cells(["A_l9999"])


class ReadBuildingTest(RunnerTestCase):
    def test_strand_twins_are_exact_reverse_complements_with_mirrored_region(self) -> None:
        pool = NaturalPool(self.world.spans)
        prompt = self.world.prompts["toy00"]
        continuation = random_dna(3072, 5)
        for cell in layout_cells():
            if not cell.reverse_complemented:
                continue
            twin = cell_by_name(cell.cell.removesuffix("_rc") + "_fw")
            arguments = {
                "prompt": prompt,
                "continuation": continuation,
                "pool": pool,
                "case_id": "toy00",
                "draw_id": 1,
            }
            forward = runner.build_cell_read(twin, **arguments)
            reverse = runner.build_cell_read(cell, **arguments)
            self.assertEqual(forward, build_read(twin, **arguments))
            self.assertEqual(reverse.sequence, reverse_complement(forward.sequence))
            self.assertFalse(reverse.region_on_forward_strand)
            piece = reverse.sequence[
                reverse.region_start : reverse.region_start + reverse.region_length
            ]
            self.assertEqual(reverse_complement(piece), continuation[: cell.region_bases])

    def test_non_reverse_cells_are_built_by_build_read(self) -> None:
        pool = NaturalPool(self.world.spans)
        prompt = self.world.prompts["toy00"]
        continuation = random_dna(3072, 6)
        for cell in layout_cells():
            if cell.reverse_complemented:
                continue
            arguments = {
                "prompt": prompt,
                "continuation": continuation,
                "pool": pool,
                "case_id": "toy00",
                "draw_id": 0,
            }
            self.assertEqual(
                runner.build_cell_read(cell, **arguments), build_read(cell, **arguments)
            )

    def test_region_overlap_is_measured_in_supplied_read_coordinates(self) -> None:
        pool = NaturalPool(self.world.spans)
        arguments = {
            "prompt": self.world.prompts["toy00"],
            "continuation": self.world.marked[(self.world.evaluated[0], 0)],
            "pool": pool,
            "case_id": "toy00",
            "draw_id": 0,
        }
        config = PositionIndependentSynthIDConfig()
        for cell_name in ("A_l3072", "C_l0768_o1_fw", "C_l0768_o1_rc"):
            read = runner.build_cell_read(cell_by_name(cell_name), **arguments)
            detection = detect_synthid_position_independent(
                read.sequence, key=fixture_key(0), domain=DOMAIN, config=config
            )
            best = detection.best_hypothesis
            expected = len(
                set(range(best.original_start, best.original_stop))
                & set(range(read.region_start, read.region_start + read.region_length))
            )
            self.assertEqual(runner.region_overlap(detection, read), expected, cell_name)


class StatisticsTest(unittest.TestCase):
    def test_one_sided_bound_matches_closed_form_at_zero_and_full(self) -> None:
        self.assertAlmostEqual(runner.one_sided_upper_bound(0, 100), 1 - 0.05 ** (1 / 100))
        self.assertEqual(runner.one_sided_upper_bound(100, 100), 1.0)
        with self.assertRaises(ValueError):
            runner.one_sided_upper_bound(5, 4)

    def test_count_summary_carries_two_sided_interval_and_optional_upper_bound(self) -> None:
        marked = runner.count_summary(7, 10, one_sided=False)
        control = runner.count_summary(0, 10, one_sided=True)
        self.assertNotIn("exact_one_sided_95_upper_bound", marked)
        low, high = marked["exact_two_sided_95_interval"]
        self.assertAlmostEqual(low, 0.3475, places=3)
        self.assertAlmostEqual(high, 0.9333, places=3)
        self.assertEqual(control["exact_two_sided_95_interval"][0], 0.0)
        self.assertLess(control["exact_one_sided_95_upper_bound"], high)

    def test_read_level_summary_has_descriptive_interval_and_no_one_sided_bound(self) -> None:
        block = runner.read_level_summary(2, 40)
        self.assertEqual((block["positives"], block["trials"], block["rate"]), (2, 40, 0.05))
        self.assertEqual(block["exact_two_sided_95_interval"], runner.exact_interval(2, 40))
        self.assertEqual(block["unit_note"], runner.READ_LEVEL_UNIT_NOTE)
        self.assertNotIn("exact_one_sided_95_upper_bound", block)


def check_row(
    case: str,
    draw: int,
    family: str,
    cell: str,
    p: float,
    hypotheses: int,
    detected: bool = False,
    g_counts: tuple[int, int] = (60, 100),
) -> dict[str, Any]:
    return {
        "case_id": case,
        "draw_id": draw,
        "family": family,
        "cell": cell,
        "series": cell[0],
        "detected": detected,
        "minimum_local_log_p_value": p,
        "hypotheses_searched": hypotheses,
        "best_g_ones": g_counts[0],
        "best_g_total": g_counts[1],
    }


def s0_row(row: dict[str, Any]) -> dict[str, Any]:
    """The S0 runner's row shape: window counts sit under ``best_hypothesis``."""

    return {
        "case_id": row["case_id"],
        "draw_id": row["draw_id"],
        "family": row["family"],
        "condition": "clean",
        "detected": row["detected"],
        "hypotheses_searched": row["hypotheses_searched"],
        "minimum_local_log_p_value": row["minimum_local_log_p_value"],
        "best_hypothesis": {"g_ones": row["best_g_ones"], "g_total": row["best_g_total"]},
    }


class ValidityCheckTest(unittest.TestCase):
    def test_check_two_passes_fails_and_reports_unpaired_reads(self) -> None:
        rows = [
            check_row("a", 0, runner.POSITIVE, "C_l0768_o2_fw", -3.5, 100),
            check_row("a", 0, runner.POSITIVE, "C_l0768_o2_rc", -3.5, 100),
        ]
        self.assertEqual(runner.check_strand_pairs(rows)["status"], "pass")
        self.assertEqual(runner.check_strand_pairs([])["status"], "not_run")
        rows[1]["minimum_local_log_p_value"] = -3.4999999999
        failed = runner.check_strand_pairs(rows)
        self.assertEqual((failed["status"], failed["mismatches"]), ("fail", 1))
        rows[1] = check_row("a", 0, runner.POSITIVE, "C_l0768_o2_rc", -3.5, 99)
        self.assertEqual(runner.check_strand_pairs(rows)["status"], "fail")
        self.assertEqual(runner.check_strand_pairs(rows[:1])["status"], "fail")

    def test_check_one_requires_agreement_on_decisions_and_integer_window_counts(self) -> None:
        order = ["a"]
        rows, s0 = [], []
        for draw in (0, 1):
            for family in runner.FAMILIES:
                rows.append(check_row("a", draw, family, "A_l3072", -2.0 - draw, 16136))
                s0.append(s0_row(rows[-1]))
        s0.append({**s0[0], "condition": "insertion_1nt", "detected": True})
        result = runner.check_reference_against_s0(rows, s0, order)
        self.assertEqual((result["status"], result["compared"]), ("pass", 4))
        self.assertEqual(result["max_abs_log_p_difference"], 0.0)
        self.assertEqual(runner.check_reference_against_s0(rows, None, order)["status"], "not_run")

        flipped = [dict(row) for row in s0]
        flipped[1]["detected"] = True
        self.assertEqual(runner.check_reference_against_s0(rows, flipped, order)["status"], "fail")

        searched = [dict(row) for row in s0]
        searched[1]["hypotheses_searched"] = 16135
        self.assertEqual(runner.check_reference_against_s0(rows, searched, order)["status"], "fail")

        for field in ("g_ones", "g_total"):
            counts = [dict(row, best_hypothesis=dict(row["best_hypothesis"])) for row in s0]
            counts[2]["best_hypothesis"][field] += 1
            result = runner.check_reference_against_s0(rows, counts, order)
            self.assertEqual((result["status"], result["mismatches"]), ("fail", 1), field)
            self.assertEqual(result["mismatch_examples"][0]["layout"]["g_ones"], 60)

        no_counts = [{k: v for k, v in row.items() if k != "best_hypothesis"} for row in s0]
        result = runner.check_reference_against_s0(rows, no_counts, order)
        self.assertEqual(result["status"], "fail")

        # Float noise alone is not a mismatch: it is reported as a number.
        shifted = [dict(row) for row in s0]
        shifted[2]["minimum_local_log_p_value"] = -3.0000001
        result = runner.check_reference_against_s0(rows, shifted, order)
        self.assertEqual(result["status"], "pass")
        self.assertAlmostEqual(result["max_abs_log_p_difference"], 1e-7, places=12)

        result = runner.check_reference_against_s0(rows, s0[1:], order)
        self.assertEqual((result["status"], result["missing_in_s0"]), ("fail", 1))


class LoadTrialsTest(unittest.TestCase):
    def test_opener_follows_the_gz_suffix(self) -> None:
        rows = [{"a": 1}, {"a": 2}]
        text = "".join(json.dumps(row) + "\n" for row in rows)
        with tempfile.TemporaryDirectory() as directory:
            plain = Path(directory) / "trials.jsonl"
            plain.write_text(text)
            zipped = Path(directory) / "trials.jsonl.gz"
            with gzip.open(zipped, "wt") as handle:
                handle.write(text)
            self.assertEqual(runner.load_trials(plain), rows)
            self.assertEqual(runner.load_trials(zipped), rows)


class EndToEndTest(RunnerTestCase):
    def load_summary(self, name: str) -> dict[str, Any]:
        return json.loads((self.world.root / name / "summary.json").read_text())

    def test_toy_run_writes_trials_summary_and_passes_both_checks(self) -> None:
        self.assertEqual(runner.main(self.world.argv("run_main")), 0)
        summary = self.load_summary("run_main")
        self.assertTrue(summary["valid"], summary["validity_failures"])
        self.assertEqual(summary["total_decisions"], 2 * 2 * 2 * len(TOY_CELLS))
        self.assertEqual(
            summary["cells_run"], [c.cell for c in layout_cells() if c.cell in TOY_CELLS]
        )
        self.assertEqual(summary["model"]["policy_id"], POLICY)
        self.assertEqual(summary["protocol"]["id"], runner.PROTOCOL_ID)
        self.assertEqual(len(summary["protocol"]["sha256"]), 64)
        self.assertIn("cpu_model", summary["provenance"])
        self.assertTrue(summary["provenance"]["code"]["src/genomic_watermarks/review_layouts.py"])
        checks = summary["validity_checks"]
        self.assertEqual(
            checks["check_1_reference_layout_reproduces_s0_unedited"]["status"], "pass"
        )
        self.assertEqual(checks["check_1_reference_layout_reproduces_s0_unedited"]["compared"], 8)
        self.assertEqual(checks["check_2_series_c_strand_pairs_identical"]["pairs"], 8)

        with gzip.open(self.world.root / "run_main/trials.jsonl.gz", "rt") as handle:
            rows = [json.loads(line) for line in handle]
        self.assertEqual(len(rows), summary["total_decisions"])
        expected_keys = {
            "case_id", "draw_id", "family", "cell", "series", "key_index", "read_bases",
            "region_start", "region_length", "detected", "sequence_p_value",
            "sequence_log_p_value", "strength", "hypotheses_searched", "best_orientation",
            "best_original_start", "best_original_stop", "best_window_base_length",
            "region_overlap_bases", "marked_bases_retained",
        }  # fmt: skip
        self.assertLessEqual(expected_keys, set(rows[0]))
        self.assertNotIn("key", " ".join(rows[0]).replace("key_index", ""))
        for row in rows:
            self.assertEqual(row["key_index"], row["draw_id"])
            self.assertEqual(row["marked_bases_retained"] is not None, row["series"] == "F")
            self.assertGreaterEqual(row["strength"], 0.0)
        reference = [r for r in rows if r["cell"] == "A_l3072" and r["family"] == runner.POSITIVE]
        self.assertTrue(all(r["detected"] for r in reference))
        self.assertTrue(all(r["read_bases"] == 3456 for r in reference))
        ordinary = [
            r for r in rows if r["cell"] == "A_l3072" and r["family"] == runner.PRIMARY_NULL
        ]
        self.assertFalse(any(r["detected"] for r in ordinary))
        for row in rows:
            if row["family"] == runner.POSITIVE and row["cell"] == "A_l3072":
                self.assertGreater(row["region_overlap_bases"], 0)

        cells = {cell["cell"]: cell for cell in summary["cells"]}
        marked = cells["A_l3072"]["families"][runner.POSITIVE]
        control = cells["A_l3072"]["families"][runner.PRIMARY_NULL]
        self.assertEqual(marked["sequence_level"]["positives"], 4)
        self.assertEqual(marked["prompt_both_draws"]["positives"], 2)
        self.assertEqual(control["prompt_any_draw"]["positives"], 0)
        self.assertNotIn("exact_one_sided_95_upper_bound", control["sequence_level"])
        self.assertNotIn("exact_one_sided_95_upper_bound", marked["sequence_level"])
        self.assertEqual(control["sequence_level"]["unit_note"], runner.READ_LEVEL_UNIT_NOTE)
        self.assertEqual(marked["sequence_level"]["unit_note"], runner.READ_LEVEL_UNIT_NOTE)
        for name in ("prompt_any_draw", "prompt_both_draws"):
            self.assertIn("exact_one_sided_95_upper_bound", control[name])
            self.assertNotIn("exact_one_sided_95_upper_bound", marked[name])
            self.assertNotIn("unit_note", control[name])
        self.assertEqual(control["prompt_any_draw"]["trials"], 2)
        self.assertFalse(summary["s0_check_skipped"])
        self.assertFalse(summary["results_withheld"])
        identity = json.loads((self.world.root / "run_main/run_identity.json").read_text())
        self.assertFalse(identity["no_s0_check"])
        self.assertEqual(sum(marked["strongest_window_length_counts"].values()), 4)
        self.assertGreater(marked["median_region_overlap_bases"], 0)
        self.assertEqual(
            cells["F_c0768"]["families"][runner.POSITIVE]["median_region_bases_retained"] >= 384,
            True,
        )
        self.assertEqual(summary["ordinary_cells_above_target"], [])

    def test_failed_reference_check_withholds_results_and_returns_nonzero(self) -> None:
        tampered = self.world.root / "s0_tampered.jsonl.gz"
        self.world.write_s0(tampered, flip=True)
        argv = self.world.argv("run_bad", s0=tampered, cells=("A_l3072",))
        self.assertEqual(runner.main(argv), 1)
        summary = self.load_summary("run_bad")
        self.assertFalse(summary["valid"])
        self.assertTrue(summary["results_withheld"])
        check = summary["validity_checks"]["check_1_reference_layout_reproduces_s0_unedited"]
        self.assertEqual(check["status"], "fail")
        self.assertGreater(check["mismatches"], 0)
        self.assertTrue(check["mismatch_examples"])
        self.assertIn("check 1 fail", summary["validity_failures"])
        self.assertNotIn("cells", summary)
        self.assertNotIn("ordinary_cells_above_target", summary)
        self.assertTrue((self.world.root / "run_bad/trials.jsonl.gz").is_file())

    def test_plain_jsonl_s0_file_is_accepted(self) -> None:
        plain = self.world.root / "s0_plain" / "trials.jsonl"
        plain.parent.mkdir()
        self.world.write_s0(plain, flip=False)
        self.assertEqual(
            runner.main(self.world.argv("run_plain_s0", s0=plain, cells=("A_l3072",))), 0
        )
        summary = self.load_summary("run_plain_s0")
        check = summary["validity_checks"]["check_1_reference_layout_reproduces_s0_unedited"]
        self.assertEqual((check["status"], check["compared"]), ("pass", 8))
        self.assertFalse(summary["results_withheld"])

    def test_s0_trials_is_required_unless_no_s0_check_is_given(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                runner.main(self.world.argv("run_no_option", s0=None, cells=SMALL))
            with self.assertRaises(SystemExit):  # the two options exclude each other
                runner.main(self.world.argv("run_both", "--no-s0-check", cells=SMALL))
        self.assertFalse((self.world.root / "run_no_option").exists())

    def test_unreadable_s0_file_stops_before_any_scoring(self) -> None:
        missing = self.world.root / "does_not_exist.jsonl.gz"
        with self.assertRaises(FileNotFoundError):
            runner.main(self.world.argv("run_missing_s0", s0=missing, cells=SMALL))
        self.assertFalse((self.world.root / "run_missing_s0").exists())
        corrupt = self.world.root / "corrupt.jsonl.gz"
        corrupt.write_bytes(b"not a gzip file")
        with self.assertRaises(OSError):
            runner.main(self.world.argv("run_corrupt_s0", s0=corrupt, cells=SMALL))
        self.assertFalse((self.world.root / "run_corrupt_s0").exists())

    def test_no_s0_check_is_recorded_and_marks_check_one_not_run(self) -> None:
        self.assertEqual(
            runner.main(self.world.argv("run_nos0", s0=False, cells=("A_l3072",))), 0
        )
        summary = self.load_summary("run_nos0")
        self.assertFalse(summary["valid"])
        self.assertTrue(summary["s0_check_skipped"])
        self.assertTrue(any("--no-s0-check" in flag for flag in summary["flags"]))
        self.assertEqual(
            summary["validity_checks"]["check_1_reference_layout_reproduces_s0_unedited"]["status"],
            "not_run",
        )
        identity = json.loads((self.world.root / "run_nos0/run_identity.json").read_text())
        self.assertTrue(identity["no_s0_check"])

    def test_resume_skips_valid_shards_and_never_overwrites_results(self) -> None:
        runner.main(self.world.argv("run_resume", s0=False, cells=SMALL))
        output = self.world.root / "run_resume"
        shards = sorted((output / "shards").glob("*.json"))
        self.assertEqual(len(shards), 2)
        before = {path: json.loads(path.read_text())["rows"] for path in shards}
        trials = (output / "trials.jsonl.gz").read_bytes()
        with self.assertRaises(FileExistsError):
            runner.main(self.world.argv("run_resume", s0=False, cells=SMALL))
        (output / "summary.json").unlink()
        shards[0].unlink()
        runner.main(self.world.argv("run_resume", s0=False, cells=SMALL))
        self.assertEqual(json.loads(shards[1].read_text())["rows"], before[shards[1]])
        self.assertEqual(json.loads(shards[0].read_text())["rows"], before[shards[0]])
        self.assertEqual((output / "trials.jsonl.gz").read_bytes(), trials)

    def test_foreign_or_incomplete_shards_are_rejected(self) -> None:
        runner.main(self.world.argv("run_foreign", s0=False, cells=SMALL))
        output = self.world.root / "run_foreign"
        (output / "summary.json").unlink()
        shard = sorted((output / "shards").glob("*.json"))[0]
        payload = json.loads(shard.read_text())
        payload["rows"].pop()
        shard.write_text(json.dumps(payload))
        with self.assertRaises(ValueError):
            runner.main(self.world.argv("run_foreign", s0=False, cells=SMALL))
        other_cells = self.world.argv("run_foreign", s0=False, cells=("A_l0768", "A_l0384"))
        with self.assertRaises(FileExistsError):  # different cells change the run identity
            runner.main(other_cells)

    def test_parallel_workers_give_the_same_decisions(self) -> None:
        extra = ["--workers", "2"]
        runner.main(self.world.argv("run_parallel", *extra, s0=False, cells=SMALL))
        runner.main(self.world.argv("run_serial", s0=False, cells=SMALL))
        left = gzip.open(self.world.root / "run_parallel/trials.jsonl.gz", "rt").read()
        right = gzip.open(self.world.root / "run_serial/trials.jsonl.gz", "rt").read()
        self.assertEqual(left, right)

    def test_rejects_bad_arguments(self) -> None:
        with self.assertRaises(ValueError):
            runner.main(self.world.argv("run_bad_args", "--workers", "0"))
        bad = self.world.argv("run_bad_n")
        bad[bad.index("--evaluated-prompts") + 1] = "5"
        with self.assertRaises(ValueError):
            runner.main(bad)
        with self.assertRaises(ValueError):  # cohort digest mismatch
            runner.main(
                [arg if arg != "" else "0" * 64 for arg in self.world.argv("run_bad_digest")]
            )


if __name__ == "__main__":
    unittest.main()
