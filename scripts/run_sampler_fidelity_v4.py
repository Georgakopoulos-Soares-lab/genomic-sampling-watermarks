#!/usr/bin/env python3
"""Sampler-fidelity test that exercises the generation code path (synthid.v4).

The version-one test drew marked samples with ``random.choices`` from the computed fixed-key
law and tested them against that same law, so it checked the draw call, not the sampler that
generated the reads. This test instead draws through the generation sampler's own routines and
compares the draws with an independently coded reference law.

For each selected second-cohort prompt and model:

1. Build a generation-regime state: the cohort prompt plus a fresh 64-token ordinary
   continuation drawn with ``generate_ordinary`` (the generation script's ordinary path) from a
   public replay seed. The watermark context is the last four generated tokens.
2. Compute the fixed-key law ``p_k`` with the NumPy path used by ``_tournament_step`` and with the
   pure-Python ``tournament_distribution_reference``; record their largest difference.
3. Marked arm: 5,000 draws with ``_sample_index_numpy`` on the NumPy law, which is exactly what
   ``_tournament_step`` does on each call; G-test against the reference law.
4. Ordinary arm: 5,000 draws with ``sample_categorical``, the generation script's ordinary
   sampler; G-test against ``p``.
5. Negative control at hash-selected states: ordinary draws tested against the reference ``p_k``.
6. Integration check at hash-selected states: 200 direct ``_tournament_step`` calls must equal,
   draw for draw, the efficient path under the same random seed.
7. Key-averaged identity: the mean of ``p_k`` over 256 fresh keys, compared with ``p``.

The keyed functions are the second cohort's draw-zero generation functions:
``fixture_key(0)`` with domain ``<experiment label>/<cohort id>/<policy id>``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import resource
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.gof import monte_carlo_goodness_of_fit  # noqa: E402
from genomic_watermarks.large_validation import (  # noqa: E402
    CALIBRATION_SPLIT_LABEL,
    deterministic_prompt_split,
    fixture_key,
)
from genomic_watermarks.pilot import load_context_cases_jsonl  # noqa: E402
from genomic_watermarks.sampling.partition import sample_categorical  # noqa: E402
from genomic_watermarks.synthid import (  # noqa: E402
    KeyedTournament,
    _sample_index_numpy,
    _tournament_probabilities_numpy,
    _tournament_step,
    tournament_distribution_reference,
)
from genomic_watermarks.watermark import generate_ordinary, public_replay_seed  # noqa: E402

RUN_LABEL = "synthid-v4-sampler-fidelity"
EXPERIMENT_LABELS = {"C_tok": "carbon-synthid-fpr-v2", "G_tok": "generator-synthid-fpr-v2"}
DEPTH = 30
CONTEXT_TOKENS = 4
HISTORY = 1024
EXACTNESS_TOLERANCE = 1e-12


def rank(label: str, case_ids: list[str]) -> list[str]:
    """Order case IDs by a public SHA-256 rank under ``label``."""
    return sorted(
        case_ids,
        key=lambda case_id: (hashlib.sha256(f"{label}\x00{case_id}".encode()).digest(), case_id),
    )


def select_states(
    case_ids: list[str], *, states: int, negative: int, integration: int
) -> tuple[list[str], set[str], set[str]]:
    """Predeclared selection from the cohort's evaluation prompts."""
    split = deterministic_prompt_split(
        case_ids, calibration_prompts=64, label=CALIBRATION_SPLIT_LABEL
    )
    evaluation = [case_id for case_id in case_ids if split[case_id] == "evaluation"]
    chosen = rank(f"{RUN_LABEL}/states", evaluation)[:states]
    negatives = set(rank(f"{RUN_LABEL}/negative-control", chosen)[:negative])
    integrations = set(rank(f"{RUN_LABEL}/integration", chosen)[:integration])
    return chosen, negatives, integrations


def sparse_counts(indices: list[int]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for index in indices:
        counts[str(index)] = counts.get(str(index), 0) + 1
    return counts


def dense(counts: dict[str, int], size: int) -> list[int]:
    out = [0] * size
    for index, count in counts.items():
        out[int(index)] = count
    return out


def total_variation(left, right) -> float:
    return 0.5 * float(sum(abs(a - b) for a, b in zip(left, right, strict=True)))


def evaluate_state(
    *,
    items: tuple[str, ...],
    probabilities: tuple[float, ...],
    recent: tuple[str, ...],
    tournament: KeyedTournament,
    seed_parts: tuple[str, ...],
    draws: int,
    replicates: int,
    key_replicates: int,
    negative_control: bool,
    integration_draws: int,
    numpy,
) -> dict[str, Any]:
    """Run every per-state check. Model-free, so unit tests can drive it."""
    seed = lambda *parts: public_replay_seed(RUN_LABEL, *seed_parts, *parts)  # noqa: E731
    numpy_law, _masses, _bits = _tournament_probabilities_numpy(
        items, probabilities, recent, tournament, numpy
    )
    reference_law = tournament_distribution_reference(items, probabilities, recent, tournament)
    reference = tuple(reference_law.probabilities)
    exactness = float(numpy.max(numpy.abs(numpy_law - numpy.asarray(reference))))

    marked_rng = random.Random(seed("marked"))
    marked = [_sample_index_numpy(numpy_law, marked_rng, numpy) for _ in range(draws)]
    index_of = {item: index for index, item in enumerate(items)}
    ordinary_rng = random.Random(seed("ordinary"))
    ordinary = [
        index_of[sample_categorical(items, probabilities, ordinary_rng)] for _ in range(draws)
    ]

    def gof(indices: list[int], law: tuple[float, ...], arm: str) -> dict[str, Any]:
        counts = dense(sparse_counts(indices), len(items))
        result = monte_carlo_goodness_of_fit(
            counts, law, replicates=replicates, seed=seed("gof", arm)
        )
        return {"g_statistic": result.statistic, "p_value": result.p_value}

    record: dict[str, Any] = {
        "numpy_vs_reference_max_abs": exactness,
        "marked": {**gof(marked, reference, "marked"), "counts": sparse_counts(marked)},
        "ordinary": {**gof(ordinary, probabilities, "ordinary"), "counts": sparse_counts(ordinary)},
        "negative_control": None,
        "integration": None,
    }
    if negative_control:
        broken_rng = random.Random(seed("negative-control"))
        broken = [
            index_of[sample_categorical(items, probabilities, broken_rng)] for _ in range(draws)
        ]
        record["negative_control"] = gof(broken, reference, "negative-control")
    if integration_draws:
        direct_rng = random.Random(seed("integration"))
        direct = [
            index_of[_tournament_step(items, probabilities, recent, tournament, direct_rng)[0]]
            for _ in range(integration_draws)
        ]
        efficient_rng = random.Random(seed("integration"))
        efficient = [
            _sample_index_numpy(numpy_law, efficient_rng, numpy) for _ in range(integration_draws)
        ]
        record["integration"] = {"draws": integration_draws, "identical": direct == efficient}

    accumulated = numpy.zeros(len(items))
    tv_at: dict[str, float] = {}
    for key_index in range(key_replicates):
        derived = hashlib.sha256(
            tournament.key
            + b"\x00"
            + RUN_LABEL.encode()
            + b"\x00key-average\x00"
            + "\x00".join(seed_parts).encode()
            + key_index.to_bytes(8, "big")
        ).digest()
        keyed = KeyedTournament(
            key=derived,
            domain=tournament.domain,
            depth=tournament.depth,
            context_tokens=tournament.context_tokens,
            context_history_size=tournament.context_history_size,
        )
        law, _m, _b = _tournament_probabilities_numpy(items, probabilities, recent, keyed, numpy)
        accumulated += law
        if key_index + 1 in (1, 16, 64, 256) or key_index + 1 == key_replicates:
            tv_at[str(key_index + 1)] = total_variation(
                accumulated / (key_index + 1), probabilities
            )
    record["key_average"] = {
        "replicates": key_replicates,
        "total_variation_by_keys": tv_at,
        "max_abs_error": float(
            numpy.max(numpy.abs(accumulated / key_replicates - numpy.asarray(probabilities)))
        ),
    }
    record["entropy_bits"] = -sum(p * math.log2(p) for p in probabilities if p > 0.0)
    record["top1_mass"] = max(probabilities)
    return record


def run(args: argparse.Namespace) -> int:
    import numpy
    import torch

    from genomic_watermarks.models.huggingface import load_adapter

    torch.set_num_threads(args.threads)
    protocol_sha = hashlib.sha256(args.protocol.read_bytes()).hexdigest()
    cases = {case.case_id: case for case in load_context_cases_jsonl(args.cohort_jsonl)}
    chosen, negatives, integrations = select_states(
        list(cases),
        states=args.states,
        negative=args.negative_states,
        integration=args.integration_states,
    )
    if args.limit:
        chosen = chosen[: args.limit]
    out = args.output_root / args.policy
    shards = out / "state_shards"
    shards.mkdir(parents=True, exist_ok=True)
    pending = [case_id for case_id in chosen if not (shards / f"{case_id}.json").exists()]
    print(
        json.dumps({"policy": args.policy, "selected": len(chosen), "pending": len(pending)}),
        flush=True,
    )
    if not pending:
        return 0
    adapter = load_adapter(
        args.policy,
        device="cpu",
        dtype=args.dtype,
        allow_cpu_fallback=False,
        cache_dir=args.cache_dir,
        local_files_only=args.local_files_only,
    )
    cohort_id = next(iter(cases.values())).cohort_id
    domain = f"{EXPERIMENT_LABELS[args.policy]}/{cohort_id}/{args.policy}"
    tournament = KeyedTournament(
        key=fixture_key(0),
        domain=domain,
        depth=DEPTH,
        context_tokens=CONTEXT_TOKENS,
        context_history_size=HISTORY,
    )

    def next_distribution(context: str):
        state = adapter.next_distribution(context)
        return tuple(state.tokens), tuple(float(p) for p in state.probabilities)

    for done, case_id in enumerate(pending, start=1):
        started = time.perf_counter()
        case = cases[case_id]
        adapter.reset_incremental_cache()
        prefix_rng = random.Random(
            public_replay_seed(RUN_LABEL, args.policy, case_id, "ordinary-prefix")
        )
        prefix = generate_ordinary(
            next_distribution, case.sequence, steps=args.prefix_tokens, rng=prefix_rng
        )
        items, probabilities = next_distribution(case.sequence + prefix.dna)
        recent = tuple(prefix.tokens[-CONTEXT_TOKENS:])
        earlier = {
            tuple(prefix.tokens[i : i + CONTEXT_TOKENS])
            for i in range(len(prefix.tokens) - CONTEXT_TOKENS)
        }
        model_seconds = time.perf_counter() - started
        record = evaluate_state(
            items=items,
            probabilities=probabilities,
            recent=recent,
            tournament=tournament,
            seed_parts=(args.policy, case_id),
            draws=args.draws,
            replicates=args.replicates,
            key_replicates=args.key_replicates,
            negative_control=case_id in negatives,
            integration_draws=args.integration_draws if case_id in integrations else 0,
            numpy=numpy,
        )
        record.update(
            {
                "schema_version": 1,
                "classification": "synthid.v4 sampler-fidelity state shard",
                "policy_id": args.policy,
                "model_id": adapter.policy.model_id,
                "revision": adapter.policy.revision,
                "cohort_id": cohort_id,
                "case_id": case_id,
                "prompt_sequence_sha256": case.sequence_sha256,
                "prefix_sha256": hashlib.sha256(prefix.dna.encode()).hexdigest(),
                "prefix_tokens": args.prefix_tokens,
                "context": list(recent),
                "context_seen_earlier_in_prefix": recent in earlier,
                "tournament_domain": domain,
                "key": "fixture_key(0), the second cohort's draw-zero generation key",
                "model_distribution_sha256": hashlib.sha256(
                    json.dumps([items, probabilities]).encode()
                ).hexdigest(),
                "draws_per_arm": args.draws,
                "monte_carlo_replicates": args.replicates,
                "protocol_sha256": protocol_sha,
                "model_seconds": model_seconds,
                "state_seconds": time.perf_counter() - started,
            }
        )
        tmp = shards / f"{case_id}.json.tmp"
        tmp.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, shards / f"{case_id}.json")
        print(
            json.dumps(
                {
                    "done": done,
                    "of": len(pending),
                    "case_id": case_id,
                    "state_seconds": round(record["state_seconds"], 1),
                    "peak_rss_gib": round(
                        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20, 2
                    ),
                }
            ),
            flush=True,
        )
    return 0


def binomial_upper_tail(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))


def benjamini_hochberg_rejections(p_values: list[float], alpha: float) -> int:
    ordered = sorted(p_values)
    m = len(ordered)
    passed = [i + 1 for i, p in enumerate(ordered) if p <= (i + 1) * alpha / m]
    return max(passed) if passed else 0


def decile_uniformity(p_values: list[float]) -> dict[str, float]:
    """Chi-square test of p-value deciles against uniform, with a Monte Carlo reference."""
    n = len(p_values)

    def statistic(values):
        bins = [0] * 10
        for v in values:
            bins[min(int(v * 10), 9)] += 1
        return sum((b - n / 10) ** 2 / (n / 10) for b in bins)

    observed = statistic(p_values)
    rng = random.Random(public_replay_seed(RUN_LABEL, "decile-uniformity", str(n)))
    # Monte Carlo p-values are discrete on a 1/1000 grid; simulate on that grid.
    exceed = sum(
        statistic([(1 + int(rng.random() * 1000)) / 1000 for _ in range(n)]) >= observed
        for _ in range(9999)
    )
    return {"chi_square": observed, "p_value": (1 + exceed) / 10000}


def finalize(args: argparse.Namespace) -> int:
    summary: dict[str, Any] = {
        "schema_version": 1,
        "analysis": RUN_LABEL,
        "protocol": str(args.protocol.relative_to(ROOT)),
        "protocol_sha256": hashlib.sha256(args.protocol.read_bytes()).hexdigest(),
        "models": {},
    }
    for policy in ("C_tok", "G_tok"):
        shard_dir = args.output_root / policy / "state_shards"
        rows = [json.loads(p.read_text()) for p in sorted(shard_dir.glob("*.json"))]
        if not rows:
            continue
        if any(row["protocol_sha256"] != summary["protocol_sha256"] for row in rows):
            raise ValueError(f"{policy}: a shard was produced under a different protocol")
        n = len(rows)
        model: dict[str, Any] = {
            "states": n,
            "model_id": rows[0]["model_id"],
            "revision": rows[0]["revision"],
        }
        for arm in ("marked", "ordinary"):
            p = [row[arm]["p_value"] for row in rows]
            k = sum(v <= 0.05 for v in p)
            model[arm] = {
                "nominal_rejections_at_0.05": k,
                "expected_under_null": 0.05 * n,
                "binomial_upper_tail_p": binomial_upper_tail(k, n, 0.05),
                "benjamini_hochberg_rejections": benjamini_hochberg_rejections(p, 0.05),
                "decile_uniformity": decile_uniformity(p),
            }
        negatives = [row["negative_control"] for row in rows if row["negative_control"]]
        model["negative_control"] = {
            "states": len(negatives),
            "rejected_after_bonferroni": sum(
                r["p_value"] <= 0.05 / max(1, len(negatives)) for r in negatives
            ),
            "rejected_at_0.05": sum(r["p_value"] <= 0.05 for r in negatives),
            "max_p_value": max((r["p_value"] for r in negatives), default=None),
        }
        integrations = [row["integration"] for row in rows if row["integration"]]
        model["integration"] = {
            "states": len(integrations),
            "all_identical": all(r["identical"] for r in integrations),
        }
        model["exactness_max_abs"] = max(row["numpy_vs_reference_max_abs"] for row in rows)
        model["exactness_pass"] = model["exactness_max_abs"] <= EXACTNESS_TOLERANCE
        tv = {
            k: sorted(row["key_average"]["total_variation_by_keys"][k] for row in rows)
            for k in rows[0]["key_average"]["total_variation_by_keys"]
        }
        model["key_average_total_variation_median"] = {k: v[len(v) // 2] for k, v in tv.items()}
        model["context_seen_earlier_in_prefix"] = sum(
            row["context_seen_earlier_in_prefix"] for row in rows
        )
        model["median_entropy_bits"] = sorted(row["entropy_bits"] for row in rows)[n // 2]
        model["median_state_seconds"] = sorted(row["state_seconds"] for row in rows)[n // 2]
        summary["models"][policy] = model
    family = [
        m[arm]["binomial_upper_tail_p"]
        for m in summary["models"].values()
        for arm in ("marked", "ordinary")
    ]
    summary["primary_family"] = {
        "tests": len(family),
        "bonferroni_threshold": 0.05 / max(1, len(family)),
        "any_rejected": any(p < 0.05 / max(1, len(family)) for p in family),
    }
    summary["environment"] = {"python": platform.python_version(), "machine": platform.machine()}
    try:
        import numpy  # noqa: E401
        import torch
        import transformers

        summary["environment"].update(
            {
                "numpy": numpy.__version__,
                "torch": torch.__version__,
                "transformers": transformers.__version__,
            }
        )
    except ImportError:
        pass
    path = args.output_root / "summary.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "models"}, indent=1))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=("C_tok", "G_tok"))
    parser.add_argument(
        "--cohort-jsonl",
        type=Path,
        default=ROOT / "data/processed/ncbi_refseq_eukaryote_windows_fpr_v2_1608/prompts.jsonl",
    )
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument(
        "--output-root", type=Path, default=ROOT / "outputs/synthid_v4_sampler_fidelity"
    )
    parser.add_argument("--states", type=int, default=256)
    parser.add_argument("--negative-states", type=int, default=8)
    parser.add_argument("--integration-states", type=int, default=32)
    parser.add_argument("--integration-draws", type=int, default=200)
    parser.add_argument("--prefix-tokens", type=int, default=64)
    parser.add_argument("--draws", type=int, default=5000)
    parser.add_argument("--replicates", type=int, default=999)
    parser.add_argument("--key-replicates", type=int, default=256)
    parser.add_argument(
        "--limit", type=int, default=0, help="smoke runs only: process the first N states"
    )
    parser.add_argument("--dtype", default="bfloat16")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--cache-dir", default=".cache/huggingface")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    if args.finalize:
        return finalize(args)
    if not args.policy:
        parser.error("--policy is required unless --finalize")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
