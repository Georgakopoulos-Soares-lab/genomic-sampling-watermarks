#!/usr/bin/env python3
"""S4 analysis (CPU, no model): per-sequence mean entropy against strength and mark-bit rate.

Joins the per-sequence entropy of ``run_synthid_v5_entropy.py`` with the S0 unedited
strength of the correct-key family and with the fraction of mark bits equal to 1 in the
full 3,072-base continuation window.  Spearman correlations carry 95% percentile intervals
from a bootstrap over prompts that keeps both draws of a prompt together.  Spearman is
implemented here (average ranks, Pearson on ranks); SciPy is not used.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import platform
import shlex
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.large_validation import fixture_key, sha256_file  # noqa: E402
from genomic_watermarks.synthid import SYNTHID_SCHEME, KeyedTournament  # noqa: E402
from genomic_watermarks.synthid_boundary import score_synthid_unknown_boundaries  # noqa: E402
from genomic_watermarks.watermark import public_replay_seed  # noqa: E402

EXPERIMENT_ID = "synthid.v5.s4_entropy_analysis"
PROTOCOL_ID = "synthid_v5_review_studies_protocol_2026_11_12"
DEFAULT_PROTOCOL = ROOT / f"docs/research/{PROTOCOL_ID}.md"
POSITIVE_FAMILY = "watermarked_correct_key"
CLEAN = "clean"
CONTINUATION_BASES = 3072
QUANTILES = (0.0, 0.05, 0.25, 0.50, 0.75, 0.95, 1.0)
BOOTSTRAP_LABEL = "synthid-review-v5/s4-bootstrap"
MODELS = ("carbon", "generator")
CODE_FILES = (
    "scripts/analyze_synthid_v5_entropy.py",
    "src/genomic_watermarks/synthid_boundary.py",
    "src/genomic_watermarks/synthid.py",
    "src/genomic_watermarks/large_validation.py",
)


# --------------------------------------------------------------------------- statistics


def average_ranks(values: np.ndarray) -> np.ndarray:
    """1-based ranks, ties receiving the mean of the ranks they span."""

    _, inverse, counts = np.unique(values, return_inverse=True, return_counts=True)
    upper = np.cumsum(counts)
    return (upper - (counts - 1) / 2.0)[inverse]


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    """Spearman rank correlation; ``nan`` when either variable is constant."""

    if x.shape != y.shape or x.ndim != 1 or x.size < 2:
        raise ValueError("need two aligned vectors of at least two values")
    rx, ry = average_ranks(x) - (x.size + 1) / 2.0, average_ranks(y) - (x.size + 1) / 2.0
    denominator = math.sqrt(float(rx @ rx) * float(ry @ ry))
    if denominator == 0.0:
        return float("nan")
    return float(rx @ ry) / denominator


def bootstrap_spearman(
    x: np.ndarray,
    y: np.ndarray,
    groups: list[str],
    *,
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    """Prompt-level bootstrap of Spearman(x, y); rows sharing a group stay together."""

    if replicates <= 0:
        raise ValueError("replicates must be positive")
    order: dict[str, list[int]] = {}
    for index, group in enumerate(groups):
        order.setdefault(group, []).append(index)
    members = [np.array(indices) for indices in order.values()]
    if len(members) < 2:
        raise ValueError("at least two prompts are required")
    rng = np.random.default_rng(seed)
    estimates: list[float] = []
    for _ in range(replicates):
        chosen = rng.integers(0, len(members), size=len(members))
        rows = np.concatenate([members[i] for i in chosen])
        value = spearman(x[rows], y[rows])
        if not math.isnan(value):
            estimates.append(value)
    if not estimates:
        raise ValueError("every bootstrap replicate was degenerate")
    low, high = np.quantile(np.array(estimates), [0.025, 0.975])
    return {
        "estimate": spearman(x, y),
        "bootstrap_95_interval": [float(low), float(high)],
        "bootstrap_replicates": replicates,
        "bootstrap_valid_replicates": len(estimates),
        "prompts": len(members),
        "sequences": int(x.size),
    }


def distribution(values: list[float]) -> dict[str, Any]:
    array = np.array(values, dtype=float)
    return {
        "count": int(array.size),
        "mean": float(array.mean()),
        "std": float(array.std(ddof=1)) if array.size > 1 else 0.0,
        "quantiles": {f"{q:g}": float(np.quantile(array, q)) for q in QUANTILES},
    }


# --------------------------------------------------------------------------- inputs


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def s0_strength_index(rows: list[dict[str, Any]]) -> dict[tuple[str, int], float]:
    """Unedited strength, -log10 of the smallest window P, for the correct-key family."""

    index: dict[tuple[str, int], float] = {}
    for row in rows:
        if row["family"] != POSITIVE_FAMILY or row["condition"] != CLEAN:
            continue
        key = (str(row["case_id"]), int(row["draw_id"]))
        if key in index:
            raise ValueError(f"duplicate S0 row for {key}")
        index[key] = -float(row["minimum_local_log_p_value"]) / math.log(10.0)
    return index


def mark_bit_fraction(dna: str, *, key: bytes, domain: str) -> dict[str, Any]:
    """g_ones / g_total of the continuation scored as one aligned window from base 0.

    Uses the verifier's own window scorer (``score_synthid_unknown_boundaries``), so the
    context warm-up, repeated-context masking and depth are those of the detector.
    """

    if len(dna) != CONTINUATION_BASES:
        raise ValueError(f"continuation must have {CONTINUATION_BASES} bases")
    tournament = KeyedTournament(key=key, domain=domain)
    (score,) = score_synthid_unknown_boundaries(
        dna, base_lengths=(CONTINUATION_BASES,), tournament=tournament
    )[CONTINUATION_BASES]
    if score.base_start != 0:
        raise RuntimeError("the full-length window must start at base 0")
    return {
        "g_ones": score.g_ones,
        "g_total": score.g_total,
        "scored_tokens": score.scored_tokens,
        "mark_bit_fraction": score.g_ones / score.g_total,
    }


def join_rows(
    entropy_rows: list[dict[str, Any]],
    strengths: dict[tuple[str, int], float],
    marks: dict[tuple[str, int], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Marked sequences with entropy, S0 strength and mark-bit fraction; strict inner join."""

    joined: list[dict[str, Any]] = []
    for row in entropy_rows:
        if row["scheme"] != "marked":
            continue
        key = (str(row["case_id"]), int(row["draw_id"]))
        if key not in strengths:
            raise ValueError(f"no S0 unedited correct-key row for {key}")
        if key not in marks:
            raise ValueError(f"no mark-bit score for {key}")
        joined.append(
            {
                "case_id": key[0],
                "draw_id": key[1],
                "mean_entropy_nats": float(row["mean_entropy_nats"]),
                "s0_strength_neg_log10_smallest_window_p": strengths[key],
                **marks[key],
            }
        )
    joined.sort(key=lambda r: (r["case_id"], r["draw_id"]))
    return joined


def analyze_model(
    *,
    model: str,
    entropy_rows: list[dict[str, Any]],
    strengths: dict[tuple[str, int], float],
    marks: dict[tuple[str, int], dict[str, Any]],
    replicates: int,
    analysis_seed: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    joined = join_rows(entropy_rows, strengths, marks)
    if not joined:
        raise ValueError(f"no marked sequences for {model}")
    entropy = np.array([r["mean_entropy_nats"] for r in joined])
    strength = np.array([r["s0_strength_neg_log10_smallest_window_p"] for r in joined])
    fraction = np.array([r["mark_bit_fraction"] for r in joined])
    groups = [r["case_id"] for r in joined]
    seed = public_replay_seed(BOOTSTRAP_LABEL, model, analysis_seed)
    summary = {
        "model": model,
        "mean_entropy_nats": {
            "marked": distribution(
                [float(r["mean_entropy_nats"]) for r in entropy_rows if r["scheme"] == "marked"]
            ),
            "ordinary": distribution(
                [float(r["mean_entropy_nats"]) for r in entropy_rows if r["scheme"] == "ordinary"]
            ),
        },
        "spearman_entropy_vs_s0_strength": bootstrap_spearman(
            entropy, strength, groups, replicates=replicates, seed=seed
        ),
        "spearman_entropy_vs_mark_bit_fraction": bootstrap_spearman(
            entropy, fraction, groups, replicates=replicates, seed=seed
        ),
        "s0_strength_neg_log10_smallest_window_p": distribution(strength.tolist()),
        "mark_bit_fraction": distribution(fraction.tolist()),
        "scored_tokens_per_continuation": distribution([r["scored_tokens"] for r in joined]),
        "bootstrap_seed_label": f"{BOOTSTRAP_LABEL}/{model}/{analysis_seed}",
        "prior_expectation": "positive (protocol Section 8); reported whatever its sign",
    }
    return summary, joined


# --------------------------------------------------------------------------- main


def load_marks(
    *, generation_root: Path, entropy_rows: list[dict[str, Any]]
) -> tuple[dict[tuple[str, int], dict[str, Any]], list[Path]]:
    wanted = {
        (str(r["case_id"]), int(r["draw_id"])): str(r["sequence_sha256"])
        for r in entropy_rows
        if r["scheme"] == "marked"
    }
    marks: dict[tuple[str, int], dict[str, Any]] = {}
    paths: list[Path] = []
    for draw in sorted({draw for _, draw in wanted}):
        path = generation_root / "generation" / f"draw_{draw:02d}_sequences.jsonl"
        paths.append(path)
        for record in load_jsonl(path):
            key = (str(record["case_id"]), int(record["draw_id"]))
            if key not in wanted or str(record["scheme"]) != SYNTHID_SCHEME:
                continue
            if str(record["sequence_sha256"]) != wanted[key]:
                raise ValueError(f"entropy rows and generation records disagree for {key}")
            if int(record["fixture_key_index"]) != key[1]:
                raise ValueError(f"unexpected fixture key index for {key}")
            marks[key] = mark_bit_fraction(
                str(record["generated_dna"]),
                key=fixture_key(int(record["fixture_key_index"])),
                domain=str(record["stream_domain"]),
            )
    return marks, paths


def write_once(path: Path, payload: str, *, allow_identical: bool = False) -> None:
    """Write ``payload`` to a new path atomically (temporary file, then ``os.replace``).

    An existing file is never replaced.  With ``allow_identical`` an existing file holding
    exactly ``payload`` is accepted (a deterministic artifact left by an interrupted run).
    """

    if path.exists():
        if allow_identical and path.read_text(encoding="utf-8") == payload:
            return
        raise FileExistsError(f"refusing to replace existing artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    for model in MODELS:
        parser.add_argument(f"--{model}-entropy-dir", type=Path, help="S4 runner output dir")
        parser.add_argument(f"--{model}-s0-trials", type=Path, help="S0 trials.jsonl[.gz]")
        parser.add_argument(f"--{model}-generation-root", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--bootstrap-replicates", type=int, default=10_000)
    parser.add_argument("--analysis-seed", default="2718", help="public bootstrap seed label")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.perf_counter()
    summary_path = args.output_dir / "summary.json"
    if summary_path.exists():
        raise FileExistsError("refusing to replace an existing result")
    results: dict[str, Any] = {}
    inputs: list[dict[str, str]] = []
    all_joined: list[dict[str, Any]] = []
    for model in MODELS:
        entropy_dir = getattr(args, f"{model}_entropy_dir")
        if entropy_dir is None:
            continue
        s0_path = getattr(args, f"{model}_s0_trials")
        root = getattr(args, f"{model}_generation_root")
        if s0_path is None or root is None:
            raise ValueError(f"--{model}-s0-trials and --{model}-generation-root are required")
        entropy_path = entropy_dir / "sequences.jsonl"
        entropy_rows = load_jsonl(entropy_path)
        strengths = s0_strength_index(load_jsonl(s0_path))
        marks, generation_paths = load_marks(generation_root=root, entropy_rows=entropy_rows)
        results[model], joined = analyze_model(
            model=model,
            entropy_rows=entropy_rows,
            strengths=strengths,
            marks=marks,
            replicates=args.bootstrap_replicates,
            analysis_seed=args.analysis_seed,
        )
        all_joined.extend({"model": model, **r} for r in joined)
        for role, path in (
            ("entropy_sequences", entropy_path),
            ("s0_trials", s0_path),
            *(("generation_draw", p) for p in generation_paths),
        ):
            inputs.append(
                {
                    "role": f"{model}_{role}",
                    "path": str(path.resolve()),
                    "sha256": sha256_file(str(path)),
                }
            )
    if not results:
        raise ValueError("give at least one model's inputs")
    joined_path = args.output_dir / "marked_sequences_joined.jsonl"
    write_once(
        joined_path,
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in all_joined),
        allow_identical=True,
    )
    summary = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "classification": "review_study_result_pending_evidence_admission",
        "protocol": {
            "id": PROTOCOL_ID,
            "path": str(args.protocol.resolve()),
            "sha256": sha256_file(str(args.protocol)),
            "section": "8 S4",
        },
        "models": results,
        "bootstrap": {
            "replicates": args.bootstrap_replicates,
            "unit": "prompt (both draws kept together)",
            "interval": "percentile 95%",
            "seed_label": BOOTSTRAP_LABEL,
        },
        "strength_definition": "-log10 of the smallest window P-value, S0 clean, correct key",
        "mark_bit_definition": (
            "g_ones/g_total of the 3,072-base continuation tokenised from its first base, "
            "scored with the generating fixture key and domain by the verifier's window scorer"
        ),
        "joined_artifact": {
            "path": str(joined_path.resolve()),
            "sha256": sha256_file(str(joined_path)),
        },
        "inputs": inputs,
        "code_sha256": {name: sha256_file(str(ROOT / name)) for name in CODE_FILES},
        "provenance": {
            "command": shlex.join([sys.executable, *sys.argv]),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
            "wall_seconds": time.perf_counter() - started,
        },
        "flags": [
            "A correlation is not a causal attribution.",
            "Keys are public fixtures; no secret-key claim follows.",
        ],
    }
    write_once(summary_path, json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"summary": str(summary_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
