from __future__ import annotations

import hashlib
import json
import math
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

try:
    import torch
except ImportError:  # pragma: no cover - torch is an optional extra
    torch = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import analyze_synthid_v5_entropy as analysis  # noqa: E402
import run_synthid_v5_entropy as runner  # noqa: E402

from genomic_watermarks.dna import canonical_kmers  # noqa: E402
from genomic_watermarks.large_validation import fixture_key  # noqa: E402
from genomic_watermarks.synthid import SYNTHID_SCHEME, KeyedTournament  # noqa: E402
from genomic_watermarks.synthid_boundary import score_synthid_unknown_boundaries  # noqa: E402
from genomic_watermarks.synthid_position_independent import (  # noqa: E402
    PositionIndependentSynthIDConfig,
    detect_synthid_position_independent,
)


def random_dna(length: int, seed: int) -> str:
    rng = random.Random(seed)
    return "".join(rng.choice("ACGT") for _ in range(length))


class SpearmanTest(unittest.TestCase):
    def test_hand_computed_cases(self) -> None:
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertAlmostEqual(analysis.spearman(x, x**3), 1.0)
        self.assertAlmostEqual(analysis.spearman(x, -x), -1.0)
        # Classic textbook example without ties: d^2 = 1+1+0+0+1... -> 1 - 6*sum(d^2)/(n(n^2-1)).
        y = np.array([2.0, 1.0, 4.0, 3.0, 5.0])
        self.assertAlmostEqual(analysis.spearman(x, y), 1 - 6 * 4 / (5 * 24))

    def test_ties_use_average_ranks(self) -> None:
        values = np.array([10.0, 20.0, 20.0, 30.0])
        self.assertEqual(analysis.average_ranks(values).tolist(), [1.0, 2.5, 2.5, 4.0])
        # x ranks 1,2.5,2.5,4 ; y ranks 1,2,3,4 : Pearson of ranks computed by hand.
        x, y = values, np.array([1.0, 2.0, 3.0, 4.0])
        rx, ry = np.array([1, 2.5, 2.5, 4]), np.array([1, 2, 3, 4])
        mx, my = rx.mean(), ry.mean()
        expected = ((rx - mx) * (ry - my)).sum() / math.sqrt(
            ((rx - mx) ** 2).sum() * ((ry - my) ** 2).sum()
        )
        self.assertAlmostEqual(expected, 0.9486832980505138)
        self.assertAlmostEqual(analysis.spearman(x, y), expected)

    def test_constant_input_is_nan_and_shape_checked(self) -> None:
        self.assertTrue(math.isnan(analysis.spearman(np.ones(4), np.arange(4.0))))
        with self.assertRaises(ValueError):
            analysis.spearman(np.arange(3.0), np.arange(4.0))
        with self.assertRaises(ValueError):
            analysis.spearman(np.arange(1.0), np.arange(1.0))

    def test_matches_scipy_when_available(self) -> None:
        try:
            from scipy.stats import spearmanr
        except ImportError:  # pragma: no cover
            self.skipTest("scipy not installed")
        rng = np.random.default_rng(3)
        x = np.round(rng.normal(size=60), 1)
        y = np.round(x + rng.normal(size=60), 1)
        self.assertAlmostEqual(analysis.spearman(x, y), float(spearmanr(x, y).statistic), places=12)


class BootstrapTest(unittest.TestCase):
    def _data(self) -> tuple[np.ndarray, np.ndarray, list[str]]:
        rng = np.random.default_rng(1)
        x = rng.normal(size=60)
        y = 0.5 * x + rng.normal(size=60)
        groups = [f"p{i // 2:02d}" for i in range(60)]
        return x, y, groups

    def test_deterministic_and_seed_sensitive(self) -> None:
        x, y, groups = self._data()
        a = analysis.bootstrap_spearman(x, y, groups, replicates=200, seed=7)
        b = analysis.bootstrap_spearman(x, y, groups, replicates=200, seed=7)
        c = analysis.bootstrap_spearman(x, y, groups, replicates=200, seed=8)
        self.assertEqual(a, b)
        self.assertNotEqual(a["bootstrap_95_interval"], c["bootstrap_95_interval"])
        low, high = a["bootstrap_95_interval"]
        self.assertLess(low, a["estimate"])
        self.assertGreater(high, a["estimate"])
        self.assertEqual(a["prompts"], 30)

    def test_draws_stay_together(self) -> None:
        # With one prompt contributing two identical rows each time, a resample that keeps
        # prompts whole can never produce an odd number of rows from a two-draw prompt.
        x, y, groups = self._data()
        members: dict[str, list[int]] = {}
        for index, group in enumerate(groups):
            members.setdefault(group, []).append(index)
        self.assertTrue(all(len(v) == 2 for v in members.values()))
        result = analysis.bootstrap_spearman(x, y, groups, replicates=50, seed=1)
        self.assertEqual(result["sequences"], 60)

    def test_input_validation(self) -> None:
        x, y, groups = self._data()
        with self.assertRaises(ValueError):
            analysis.bootstrap_spearman(x, y, groups, replicates=0, seed=1)
        with self.assertRaises(ValueError):
            analysis.bootstrap_spearman(x[:2], y[:2], ["a", "a"], replicates=5, seed=1)


class JoinTest(unittest.TestCase):
    def _entropy_rows(self) -> list[dict[str, object]]:
        rows = []
        for case in ("p1", "p2"):
            for draw in (0, 1):
                for scheme in ("marked", "ordinary"):
                    rows.append(
                        {
                            "case_id": case,
                            "draw_id": draw,
                            "scheme": scheme,
                            "mean_entropy_nats": 1.0 + draw + (scheme == "ordinary"),
                        }
                    )
        return rows

    def test_s0_index_filters_family_and_condition(self) -> None:
        rows = [
            {
                "case_id": "p1",
                "draw_id": 0,
                "family": analysis.POSITIVE_FAMILY,
                "condition": "clean",
                "minimum_local_log_p_value": -math.log(10.0) * 7,
            },
            {
                "case_id": "p1",
                "draw_id": 0,
                "family": analysis.POSITIVE_FAMILY,
                "condition": "insertion_1nt",
                "minimum_local_log_p_value": -1.0,
            },
            {
                "case_id": "p1",
                "draw_id": 0,
                "family": "ordinary_corresponding_key",
                "condition": "clean",
                "minimum_local_log_p_value": -2.0,
            },
        ]
        index = analysis.s0_strength_index(rows)
        self.assertEqual(list(index), [("p1", 0)])
        self.assertAlmostEqual(index[("p1", 0)], 7.0)
        with self.assertRaises(ValueError):
            analysis.s0_strength_index([rows[0], rows[0]])

    def test_join_keeps_marked_only_and_is_strict(self) -> None:
        strengths = {(c, d): 3.0 + d for c in ("p1", "p2") for d in (0, 1)}
        marks = {
            k: {"g_ones": 5, "g_total": 10, "scored_tokens": 1, "mark_bit_fraction": 0.5}
            for k in strengths
        }
        joined = analysis.join_rows(self._entropy_rows(), strengths, marks)  # type: ignore[arg-type]
        self.assertEqual(
            [(r["case_id"], r["draw_id"]) for r in joined],
            [("p1", 0), ("p1", 1), ("p2", 0), ("p2", 1)],
        )
        self.assertEqual([r["mean_entropy_nats"] for r in joined], [1.0, 2.0, 1.0, 2.0])
        self.assertEqual(joined[1]["s0_strength_neg_log10_smallest_window_p"], 4.0)
        del strengths[("p2", 1)]
        with self.assertRaises(ValueError):
            analysis.join_rows(self._entropy_rows(), strengths, marks)  # type: ignore[arg-type]

    def test_mark_bit_fraction_uses_verifier_window_scorer(self) -> None:
        dna = random_dna(3072, 21)
        key, domain = fixture_key(0), "toy-label/toy/C_tok"
        result = analysis.mark_bit_fraction(dna, key=key, domain=domain)
        score = score_synthid_unknown_boundaries(
            dna, base_lengths=(3072,), tournament=KeyedTournament(key=key, domain=domain)
        )[3072][0]
        self.assertEqual(result["g_ones"], score.g_ones)
        self.assertEqual(result["g_total"], score.g_total)
        self.assertEqual(result["scored_tokens"], 512 - 4 - score.repeated_contexts)
        self.assertAlmostEqual(result["mark_bit_fraction"], score.g_ones / score.g_total)
        # Random DNA is unmarked: the fraction sits near one half.
        self.assertAlmostEqual(result["mark_bit_fraction"], 0.5, delta=0.03)
        # The single window is exactly what the verifier scores at oriented start 0 / 3072.
        detection = detect_synthid_position_independent(
            dna, key=key, domain=domain, config=PositionIndependentSynthIDConfig()
        )
        self.assertEqual(detection.window_base_lengths_searched, (384, 768, 1536, 3072))
        with self.assertRaises(ValueError):
            analysis.mark_bit_fraction(dna[:-6], key=key, domain=domain)

    def test_distribution_quantiles(self) -> None:
        stats = analysis.distribution([1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertEqual(stats["quantiles"]["0"], 1.0)
        self.assertEqual(stats["quantiles"]["0.5"], 3.0)
        self.assertEqual(stats["quantiles"]["1"], 5.0)
        self.assertEqual(stats["count"], 5)


@unittest.skipIf(torch is None, "requires the optional 'models' extra")
class EntropyFunctionTest(unittest.TestCase):
    def test_uniform_is_log_vocabulary_and_one_hot_is_zero(self) -> None:
        uniform = torch.zeros(3, 4096)
        values = runner.entropy_nats_from_logits(uniform)
        self.assertEqual(values.dtype, torch.float64)
        for value in values.tolist():
            self.assertAlmostEqual(value, math.log(4096), places=12)
        one_hot_inf = torch.full((2, 4096), float("-inf"))
        one_hot_inf[:, 17] = 0.0
        one_hot_big = torch.zeros(2, 4096)
        one_hot_big[:, 5] = 1e4
        for batch in (one_hot_inf, one_hot_big):
            for value in runner.entropy_nats_from_logits(batch).tolist():
                self.assertEqual(value, 0.0)

    def test_matches_direct_formula_and_is_shift_invariant(self) -> None:
        generator = torch.Generator().manual_seed(4)
        logits = torch.randn(5, 4096, generator=generator) * 3.0
        values = runner.entropy_nats_from_logits(logits).tolist()
        array = logits.double().numpy()
        for row, value in zip(array, values, strict=True):
            probabilities = np.exp(row - row.max())
            probabilities /= probabilities.sum()
            self.assertAlmostEqual(value, float(-(probabilities * np.log(probabilities)).sum()), 10)
        shifted = runner.entropy_nats_from_logits(logits.double() + 123.0).tolist()
        for a, b in zip(values, shifted, strict=True):
            self.assertAlmostEqual(a, b, places=9)

    def test_bf16_logits_are_processed_in_float64(self) -> None:
        logits = (torch.randn(2, 4096, generator=torch.Generator().manual_seed(9)) * 4).bfloat16()
        direct = runner.entropy_nats_from_logits(logits.float().double())
        self.assertEqual(runner.entropy_nats_from_logits(logits).tolist(), direct.tolist())


if torch is not None:

    class FakeTokenizer:
        """Carbon-shaped tokenizer: '<dna>' is one token, then one id per canonical 6-mer."""

        k = 6
        prefix_id = 3

        def __init__(self) -> None:
            self.kmers = canonical_kmers(6)
            self.dna_token_to_id = {kmer: 10 + i for i, kmer in enumerate(self.kmers)}
            self._inverse = {v: k for k, v in self.dna_token_to_id.items()}

        def convert_ids_to_tokens(self, token_id: int) -> str:
            return self._inverse[token_id]

        def __call__(self, text: str, return_tensors: str, add_special_tokens: bool):
            assert text.startswith("<dna>") and return_tensors == "pt" and not add_special_tokens
            dna = text[len("<dna>") :]
            ids = [self.prefix_id] + [
                self.dna_token_to_id[dna[i : i + 6]] for i in range(0, len(dna), 6)
            ]
            return {"input_ids": torch.tensor([ids])}

    class FakeOutput:
        def __init__(self, logits: torch.Tensor) -> None:
            self.logits = logits

    class FakeModel:
        """Deterministic logits that depend on the prefix, so a wrong slice would be caught."""

        vocab = 10 + 4096 + 7

        def __call__(self, input_ids: torch.Tensor, return_dict: bool) -> FakeOutput:
            assert return_dict
            length = input_ids.shape[1]
            rows = []
            for position in range(length):
                seed = int(input_ids[0, : position + 1].sum()) * 1009 + position
                generator = torch.Generator().manual_seed(seed)
                rows.append(torch.randn(self.vocab, generator=generator) * 2.0)
            return FakeOutput(torch.stack(rows).unsqueeze(0))


@unittest.skipIf(torch is None, "requires the optional 'models' extra")
class TeacherForcedTest(unittest.TestCase):
    def _adapter(self):
        from genomic_watermarks.models.huggingface import HuggingFaceDNAAdapter

        return HuggingFaceDNAAdapter(
            "C_tok",
            tokenizer=FakeTokenizer(),
            model=FakeModel(),
            device="cpu",
            dtype_name="float32",
        )

    def test_matches_adapter_nll_and_independent_computation(self) -> None:
        adapter = self._adapter()
        prompt, continuation = random_dna(60, 1), random_dna(96, 2)
        forced = runner.teacher_forced_entropy_and_nll(adapter, prompt, continuation)
        self.assertEqual(len(forced.entropies), 16)
        stats = runner.sequence_statistics(forced)
        reference = adapter.continuation_likelihood(prompt, continuation)
        self.assertAlmostEqual(stats["mean_nll_nats"], reference.mean_negative_log_likelihood, 6)

        # Independent recomputation straight from the fake model's logits.
        tokenizer = adapter._tokenizer
        ids = tokenizer("<dna>" + prompt + continuation, "pt", False)["input_ids"]
        logits = FakeModel()(ids, True).logits[0]
        first = 1 + len(prompt) // 6
        entropies, nlls = [], []
        for offset in range(16):
            row = logits[first - 1 + offset, 10 : 10 + 4096].double().numpy()
            probabilities = np.exp(row - row.max())
            probabilities /= probabilities.sum()
            entropies.append(float(-(probabilities * np.log(probabilities)).sum()))
            target = int(ids[0, first + offset]) - 10
            nlls.append(float(-np.log(probabilities[target])))
        for got, want in zip(forced.entropies, entropies, strict=True):
            self.assertAlmostEqual(got, want, places=5)
        for got, want in zip(forced.nlls, nlls, strict=True):
            self.assertAlmostEqual(got, want, places=5)
        self.assertAlmostEqual(stats["mean_entropy_nats"], sum(entropies) / 16, places=5)
        self.assertLessEqual(stats["min_entropy_nats"], stats["median_entropy_nats"])
        self.assertLessEqual(stats["median_entropy_nats"], stats["max_entropy_nats"])
        self.assertLessEqual(stats["max_entropy_nats"], math.log(4096) + 1e-9)

    def test_rejects_bad_lengths(self) -> None:
        adapter = self._adapter()
        with self.assertRaises(ValueError):
            runner.teacher_forced_entropy_and_nll(adapter, random_dna(60, 1), random_dna(7, 2))
        with self.assertRaises(ValueError):
            runner.teacher_forced_entropy_and_nll(adapter, random_dna(60, 1), "")

    def test_sequence_statistics_validation(self) -> None:
        with self.assertRaises(ValueError):
            runner.sequence_statistics(runner.TeacherForced((), ()))
        with self.assertRaises(ValueError):
            runner.sequence_statistics(runner.TeacherForced((float("nan"),), (1.0,)))


class GenerationRecordTest(unittest.TestCase):
    def test_records_validated_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "generation").mkdir()
            prompt_digest = {"p1": "d" * 64}
            for draw in (0, 1):
                lines = []
                for scheme in (SYNTHID_SCHEME, runner.ORDINARY_SCHEME):
                    dna = random_dna(3072, draw * 2 + len(lines))
                    lines.append(
                        json.dumps(
                            {
                                "case_id": "p1",
                                "draw_id": draw,
                                "scheme": scheme,
                                "cohort_id": "toy",
                                "policy_id": "C_tok",
                                "experiment_label": "L",
                                "generated_dna": dna,
                                "sequence_sha256": hashlib.sha256(dna.encode()).hexdigest(),
                                "prompt_sequence_sha256": "d" * 64,
                            }
                        )
                    )
                (root / "generation" / f"draw_{draw:02d}_sequences.jsonl").write_text(
                    "\n".join(lines) + "\n"
                )
            kwargs = dict(
                root=root,
                evaluated=["p1"],
                experiment_label="L",
                experiment_id="carbon_synthid_validation_v1",
                default_experiment_id="carbon_synthid_validation_v1",
                cohort_id="toy",
                policy_id="C_tok",
                prompt_digests=prompt_digest,
            )
            records, paths = runner.load_generation_records(**kwargs)  # type: ignore[arg-type]
            self.assertEqual(len(records), 4)
            self.assertEqual(len(paths), 2)
            with self.assertRaises(ValueError):
                runner.load_generation_records(**{**kwargs, "experiment_label": "other"})  # type: ignore[arg-type]
            with self.assertRaises(ValueError):
                runner.load_generation_records(**{**kwargs, "prompt_digests": {"p1": "e" * 64}})  # type: ignore[arg-type]
            with self.assertRaises(ValueError):
                runner.load_generation_records(
                    **{
                        **kwargs,
                        "evaluated": ["p1", "p2"],
                        "prompt_digests": {"p1": "d" * 64, "p2": "d" * 64},
                    }
                )  # type: ignore[arg-type]


@unittest.skipIf(torch is None, "requires the optional 'models' extra")
class RunnerEndToEndTest(unittest.TestCase):
    """Run the runner's main with the mocked model on a synthetic cohort (2 prompts)."""

    def _setup(self, base: Path):
        ids = [f"p{i:03d}" for i in range(70)]
        prompts = {c: random_dna(384, 100 + i) for i, c in enumerate(ids)}
        (base / "prompts.jsonl").write_text(
            "".join(
                json.dumps(
                    {
                        "prompt_id": c,
                        "sequence": prompts[c],
                        "cohort_id": "toy",
                        "organism": "x",
                        "accession": "A",
                        "start": 1,
                        "stop": 384,
                        "sequence_sha256": hashlib.sha256(prompts[c].encode()).hexdigest(),
                    }
                )
                + "\n"
                for c in ids
            )
        )
        evaluated = runner.evaluated_case_ids(ids, 2)
        (base / "gen" / "generation").mkdir(parents=True)
        for draw in (0, 1):
            lines = []
            for i, c in enumerate(evaluated):
                for scheme in (SYNTHID_SCHEME, runner.ORDINARY_SCHEME):
                    dna = random_dna(3072, 1000 + draw * 100 + i * 2 + (scheme != SYNTHID_SCHEME))
                    lines.append(
                        json.dumps(
                            {
                                "case_id": c,
                                "draw_id": draw,
                                "scheme": scheme,
                                "cohort_id": "toy",
                                "policy_id": "C_tok",
                                "experiment_label": "toy-label",
                                "generated_dna": dna,
                                "sequence_sha256": hashlib.sha256(dna.encode()).hexdigest(),
                                "prompt_sequence_sha256": hashlib.sha256(
                                    prompts[c].encode()
                                ).hexdigest(),
                            }
                        )
                    )
            (base / "gen" / "generation" / f"draw_{draw:02d}_sequences.jsonl").write_text(
                "\n".join(lines) + "\n"
            )
        return evaluated

    def test_main_with_mocked_adapter_and_resume(self) -> None:
        from genomic_watermarks.models.huggingface import HuggingFaceDNAAdapter

        def fake_load(*_args, **_kwargs):
            return HuggingFaceDNAAdapter(
                "C_tok",
                tokenizer=FakeTokenizer(),
                model=FakeModel(),
                device="cpu",
                dtype_name="float32",
            )

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            evaluated = self._setup(base)
            out = base / "out"
            argv = [
                "--model", "carbon", "--generation-root", str(base / "gen"),
                "--output-dir", str(out), "--cohort-jsonl", str(base / "prompts.jsonl"),
                "--cohort-id", "toy", "--experiment-label", "toy-label", "--n-eval", "2",
                "--device", "cpu", "--dtype", "float32", "--crosscheck-nll",
            ]  # fmt: skip
            with mock.patch("genomic_watermarks.models.huggingface.load_adapter", fake_load):
                self.assertEqual(runner.main(argv), 0)
                summary = json.loads((out / "summary.json").read_text())
                self.assertEqual(summary["sequences"], 8)
                self.assertFalse(summary["partial_run"])
                self.assertLess(summary["crosscheck_max_abs_difference"], 1e-5)
                rows = [json.loads(x) for x in (out / "sequences.jsonl").read_text().splitlines()]
                self.assertEqual(len(rows), 8)
                self.assertEqual({r["scheme"] for r in rows}, {"marked", "ordinary"})
                self.assertEqual({r["draw_id"] for r in rows}, {0, 1})
                self.assertEqual({r["case_id"] for r in rows}, set(evaluated))
                self.assertEqual(rows[0]["positions"], 512)
                for r in rows:
                    self.assertLessEqual(r["max_entropy_nats"], math.log(4096) + 1e-9)
                # Finalized results are not replaced; shards resume without recomputation.
                with self.assertRaises(FileExistsError):
                    runner.main(argv)
                (out / "summary.json").unlink()
                with mock.patch.object(runner, "teacher_forced_entropy_and_nll") as never:
                    self.assertEqual(runner.main(argv), 0)
                    never.assert_not_called()
                # A shard that no longer matches the generation records is rejected.
                shard = out / "shards" / f"{evaluated[0]}.json"
                payload = json.loads(shard.read_text())
                payload["sequences"][0]["sequence_sha256"] = "0" * 64
                shard.write_text(json.dumps(payload))
                (out / "summary.json").unlink()
                with self.assertRaises(ValueError):
                    runner.main(argv)


class AnalysisEndToEndTest(unittest.TestCase):
    """Run the analysis script's main on synthetic entropy, S0 and generation files."""

    def test_main_on_synthetic_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "ent").mkdir()
            (base / "gen" / "generation").mkdir(parents=True)
            entropy_rows, s0_rows = [], []
            for p in range(6):
                case = f"p{p}"
                for draw in (0, 1):
                    for _raw, scheme in (
                        (SYNTHID_SCHEME, "marked"),
                        ("ordinary", "ordinary"),
                    ):
                        dna = random_dna(3072, p * 10 + draw * 2 + (scheme == "ordinary"))
                        sha = hashlib.sha256(dna.encode()).hexdigest()
                        entropy_rows.append(
                            {
                                "case_id": case,
                                "draw_id": draw,
                                "scheme": scheme,
                                "sequence_sha256": sha,
                                "mean_entropy_nats": 1.0 + 0.1 * p + 0.01 * draw,
                            }
                        )
                        if scheme == "marked":
                            s0_rows.append(
                                {
                                    "case_id": case,
                                    "draw_id": draw,
                                    "family": analysis.POSITIVE_FAMILY,
                                    "condition": "clean",
                                    "minimum_local_log_p_value": -5.0 - p,
                                }
                            )
                            with (
                                base / "gen" / "generation" / f"draw_{draw:02d}_sequences.jsonl"
                            ).open("a") as h:
                                h.write(
                                    json.dumps(
                                        {
                                            "case_id": case,
                                            "draw_id": draw,
                                            "scheme": SYNTHID_SCHEME,
                                            "sequence_sha256": sha,
                                            "generated_dna": dna,
                                            "fixture_key_index": draw,
                                            "stream_domain": "L/toy/C_tok",
                                        }
                                    )
                                    + "\n"
                                )
            (base / "ent" / "sequences.jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in entropy_rows)
            )
            (base / "s0.jsonl").write_text("".join(json.dumps(r) + "\n" for r in s0_rows))
            argv = [
                "--carbon-entropy-dir",
                str(base / "ent"),
                "--carbon-s0-trials",
                str(base / "s0.jsonl"),
                "--carbon-generation-root",
                str(base / "gen"),
                "--output-dir",
                str(base / "out"),
                "--bootstrap-replicates",
                "100",
            ]
            self.assertEqual(analysis.main(argv), 0)
            summary = json.loads((base / "out" / "summary.json").read_text())
            carbon = summary["models"]["carbon"]
            self.assertEqual(carbon["spearman_entropy_vs_s0_strength"]["sequences"], 12)
            # entropy increases with p and strength increases with p: positive correlation.
            self.assertGreater(carbon["spearman_entropy_vs_s0_strength"]["estimate"], 0.9)
            self.assertEqual(carbon["mean_entropy_nats"]["marked"]["count"], 12)
            self.assertEqual(carbon["mean_entropy_nats"]["ordinary"]["count"], 12)
            joined = (base / "out" / "marked_sequences_joined.jsonl").read_text().splitlines()
            self.assertEqual(len(joined), 12)
            with self.assertRaises(FileExistsError):
                analysis.main(argv)
            leftovers = [p.name for p in (base / "out").iterdir() if p.name.startswith(".")]
            self.assertEqual(leftovers, [])

            # An interrupted run left the joined file but no summary: identical content is
            # accepted, differing content is refused and nothing is replaced.
            (base / "out" / "summary.json").unlink()
            joined_path = base / "out" / "marked_sequences_joined.jsonl"
            joined_before = joined_path.read_bytes()
            self.assertEqual(analysis.main(argv), 0)
            self.assertEqual(joined_path.read_bytes(), joined_before)
            (base / "out" / "summary.json").unlink()
            joined_path.write_text("tampered\n")
            with self.assertRaises(FileExistsError):
                analysis.main(argv)
            self.assertEqual(joined_path.read_text(), "tampered\n")
            self.assertFalse((base / "out" / "summary.json").exists())


class WriteOnceTest(unittest.TestCase):
    def test_write_once_is_atomic_and_never_replaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "artifact.txt"
            analysis.write_once(path, "one\n")
            self.assertEqual(path.read_text(), "one\n")
            self.assertEqual([p.name for p in path.parent.iterdir()], ["artifact.txt"])
            with self.assertRaises(FileExistsError):
                analysis.write_once(path, "one\n")
            analysis.write_once(path, "one\n", allow_identical=True)
            with self.assertRaises(FileExistsError):
                analysis.write_once(path, "two\n", allow_identical=True)
            self.assertEqual(path.read_text(), "one\n")
            with mock.patch.object(analysis.os, "replace", side_effect=OSError("boom")):
                with self.assertRaises(OSError):
                    analysis.write_once(path.with_name("other.txt"), "x")
            self.assertFalse(path.with_name("other.txt").exists())


if __name__ == "__main__":
    unittest.main()
