#!/usr/bin/env python3
"""S3 null calibration for the SynthID v5 review studies (protocol Section 7).

The unchanged position-independent verifier scores every read under 64 null keys that
were never used in generation.  Three read families are supported:

* ``ordinary_model_output``: draw-0 ordinary read (prompt + continuation, 3,456 bases).
* ``natural_dna``: the cohort's public 3,072-base source spans (no model involved).
* ``marked_independent_key``: draw-0 marked read (prompt + continuation, 3,456 bases).

Each read is an immutable resumable shard holding its 64 decisions.  Key bytes are never
written; rows carry only the key index.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import platform
import re
import shlex
import statistics
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from run_carbon_synthid_position_independent import exact_interval  # noqa: E402

from genomic_watermarks.large_validation import (  # noqa: E402
    CALIBRATION_SPLIT_LABEL,
    deterministic_prompt_split,
    sha256_file,
)
from genomic_watermarks.pilot import load_context_cases_jsonl  # noqa: E402
from genomic_watermarks.synthid import SYNTHID_SCHEME  # noqa: E402
from genomic_watermarks.synthid_position_independent import (  # noqa: E402
    POSITION_INDEPENDENT_SYNTHID_DETECTOR,
    PositionIndependentSynthIDConfig,
    detect_synthid_position_independent,
)
from genomic_watermarks.watermark import ORDINARY_SCHEME  # noqa: E402

EXPERIMENT_ID = "synthid.v5.s3_null_calibration"
PROTOCOL_ID = "synthid_v5_review_studies_protocol_2026_11_12"
DEFAULT_PROTOCOL = ROOT / f"docs/research/{PROTOCOL_ID}.md"
DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_fpr_v2_1608/prompts.jsonl"
DEFAULT_SPAN_DIR = ROOT / "data/raw/ncbi_refseq_eukaryote_windows_fpr_v2_1608"
DEFAULT_COHORT_ID = "ncbi_refseq_eukaryote_windows_fpr_v2_1608"

NULL_KEY_LABEL = "synthid-review-v5/null-key"
NULL_DOMAIN = "synthid-review-v5/null"
KEY_COUNT = 64
NOMINAL_LEVELS = (0.01, 0.05, 0.10, 0.25, 0.50)
TARGET_LEVEL = 0.01
PROMPT_BASES = 384
CONTINUATION_BASES = 3072
READ_BASES = PROMPT_BASES + CONTINUATION_BASES
SPAN_BASES = 3072
EXPECTED_SPANS = 1608
CALIBRATION_PROMPTS = 64
WINDOW_BASE_LENGTHS = (384, 768, 1536, 3072)
EXPECTED_WINDOWS = {SPAN_BASES: 13_064, READ_BASES: 16_136}

FAMILY_ORDINARY = "ordinary_model_output"
FAMILY_NATURAL = "natural_dna"
FAMILY_MARKED = "marked_independent_key"
FAMILIES = (FAMILY_ORDINARY, FAMILY_NATURAL, FAMILY_MARKED)
MODEL_POLICIES = {"carbon": "C_tok", "generator": "G_tok"}
MODEL_DEFAULT_GENERATION_IDS = {
    "carbon": "carbon_synthid_validation_v1",
    "generator": "generator_synthid_validation_v1",
}
FAMILY_SCHEME = {FAMILY_ORDINARY: ORDINARY_SCHEME, FAMILY_MARKED: SYNTHID_SCHEME}

CODE_FILES = (
    "scripts/run_synthid_v5_null_calibration.py",
    "scripts/run_carbon_synthid_position_independent.py",
    "src/genomic_watermarks/synthid_position_independent.py",
    "src/genomic_watermarks/synthid_boundary.py",
    "src/genomic_watermarks/synthid.py",
    "src/genomic_watermarks/dna.py",
    "src/genomic_watermarks/pilot.py",
    "src/genomic_watermarks/large_validation.py",
    "src/genomic_watermarks/watermark.py",
)


# --------------------------------------------------------------------------- keys


def null_key_bytes(index: int) -> bytes:
    """SHA-256 digest of ``synthid-review-v5/null-key/<index>`` (protocol Section 7)."""

    if not 0 <= index < KEY_COUNT:
        raise ValueError(f"null key index must lie in [0, {KEY_COUNT})")
    return hashlib.sha256(f"{NULL_KEY_LABEL}/{index}".encode()).digest()


# --------------------------------------------------------------------------- statistics


def _beta_ppf(probability: float, shape_a: float, shape_b: float) -> float:
    from scipy.stats import beta

    return float(beta.ppf(probability, shape_a, shape_b))


def exact_lower_bound(successes: int, trials: int, confidence: float = 0.95) -> float:
    """Exact (Clopper-Pearson) one-sided lower confidence bound for a binomial rate."""

    if not 0 <= successes <= trials or trials <= 0:
        raise ValueError("invalid exact-bound counts")
    if successes == 0:
        return 0.0
    return _beta_ppf(1.0 - confidence, successes, trials - successes + 1)


def calibration_table(
    sequence_log_p_values: list[float], levels: tuple[float, ...] = NOMINAL_LEVELS
) -> list[dict[str, Any]]:
    """Fraction of decisions with sequence-level P at or below each nominal level.

    ``exceeds_nominal`` is the protocol Section 7 rule: the exact one-sided 95% lower
    bound of the observed fraction is above the nominal level.
    """

    decisions = len(sequence_log_p_values)
    if decisions <= 0:
        raise ValueError("calibration needs at least one decision")
    table: list[dict[str, Any]] = []
    for level in levels:
        threshold = math.log(level)
        count = sum(1 for value in sequence_log_p_values if value <= threshold)
        lower = exact_lower_bound(count, decisions)
        table.append(
            {
                "nominal_level": level,
                "count": count,
                "decisions": decisions,
                "fraction": count / decisions,
                "exact_two_sided_95_interval": exact_interval(count, decisions),
                "exact_one_sided_95_lower_bound": lower,
                "exceeds_nominal": lower > level,
            }
        )
    return table


POOLED_BOUNDS_NOTE = (
    "Pooled read x key exact intervals and bounds, including the calibration table, treat the "
    "decisions as independent trials although decisions share reads and keys. The pooled "
    "lower bound is therefore anti-conservative as evidence against validity; read the "
    "read-level summary (reads_positive_under_at_least_one_key) and the per-key rates beside "
    "it."
)


def summarize_trials(rows: list[dict[str, Any]], key_count: int = KEY_COUNT) -> dict[str, Any]:
    """Aggregate the decision rows of one family (and model)."""

    decisions = len(rows)
    if decisions == 0:
        raise ValueError("no decisions to summarize")
    positives = sum(1 for row in rows if row["detected"])
    per_key_reads: Counter[int] = Counter()
    per_key_positives: Counter[int] = Counter()
    read_positive: dict[tuple[str, Any], bool] = {}
    for row in rows:
        key_index = int(row["key_index"])
        per_key_reads[key_index] += 1
        per_key_positives[key_index] += int(bool(row["detected"]))
        identity = (str(row["case_id"]), row["draw_id"])
        read_positive[identity] = read_positive.get(identity, False) or bool(row["detected"])
    if sorted(per_key_reads) != list(range(key_count)):
        raise ValueError("decision rows do not cover every null key")
    per_key = [
        {
            "key_index": index,
            "reads": per_key_reads[index],
            "positives": per_key_positives[index],
            "rate": per_key_positives[index] / per_key_reads[index],
            "exact_95_interval": exact_interval(per_key_positives[index], per_key_reads[index]),
        }
        for index in range(key_count)
    ]
    rates = [entry["rate"] for entry in per_key]
    reads = len(read_positive)
    any_positive = sum(read_positive.values())
    return {
        "decisions": decisions,
        "reads": reads,
        "keys": key_count,
        "pooled_bounds_note": POOLED_BOUNDS_NOTE,
        "positives_at_0_01": positives,
        "rate_at_0_01": positives / decisions,
        "exact_two_sided_95_interval_at_0_01": exact_interval(positives, decisions),
        "exact_one_sided_95_upper_bound_at_0_01": _upper_bound(positives, decisions),
        "per_key": per_key,
        "per_key_rate_min": min(rates),
        "per_key_rate_median": statistics.median(rates),
        "per_key_rate_max": max(rates),
        "reads_positive_under_at_least_one_key": {
            "count": any_positive,
            "reads": reads,
            "fraction": any_positive / reads,
            "exact_two_sided_95_interval": exact_interval(any_positive, reads),
        },
        "calibration_table": calibration_table([float(r["sequence_log_p_value"]) for r in rows]),
        "hypotheses_searched_counts": {
            str(count): number
            for count, number in sorted(
                Counter(int(r["hypotheses_searched"]) for r in rows).items()
            )
        },
        "read_bases_counts": {
            str(count): number
            for count, number in sorted(Counter(int(r["read_bases"]) for r in rows).items())
        },
    }


def _upper_bound(successes: int, trials: int, confidence: float = 0.95) -> float:
    if successes == trials:
        return 1.0
    return _beta_ppf(confidence, successes + 1, trials - successes)


# --------------------------------------------------------------------------- scoring


def score_read_under_keys(
    sequence: str,
    *,
    case_id: str,
    draw_id: int | None,
    family: str,
    model: str | None,
    key_indices: tuple[int, ...],
    keys: dict[int, bytes] | None = None,
    domain: str = NULL_DOMAIN,
) -> list[dict[str, Any]]:
    """Score one read under each key with the unchanged verifier; return decision rows.

    The plain verifier call costs about 50 ms per read on an Apple M5 Pro (about 3 s for
    64 keys).  Tokenisation is key independent but is under 10% of that cost, so nothing
    is shared between keys and every decision is exactly the library call.
    """

    config = PositionIndependentSynthIDConfig()
    rows: list[dict[str, Any]] = []
    for key_index in key_indices:
        key = keys[key_index] if keys is not None else null_key_bytes(key_index)
        result = detect_synthid_position_independent(
            sequence, key=key, domain=domain, config=config
        )
        rows.append(
            {
                "case_id": case_id,
                "draw_id": draw_id,
                "family": family,
                "model": model,
                "key_index": key_index,
                "read_bases": len(sequence),
                "hypotheses_searched": result.hypotheses_searched,
                "detected": bool(result.detected),
                "sequence_log_p_value": result.sequence_log_p_value,
                "minimum_local_log_p_value": result.minimum_local_log_p_value,
            }
        )
    return rows


def expected_windows(read_bases: int) -> int:
    return 2 * sum(
        read_bases - length + 1 for length in WINDOW_BASE_LENGTHS if length <= read_bases
    )


def check_window_counts(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        bases = int(row["read_bases"])
        expected = expected_windows(bases)
        if bases in EXPECTED_WINDOWS and expected != EXPECTED_WINDOWS[bases]:
            raise AssertionError("window-count arithmetic disagrees with the protocol")
        if int(row["hypotheses_searched"]) != expected:
            raise AssertionError(
                f"read of {bases} bases searched {row['hypotheses_searched']} windows, "
                f"expected {expected}"
            )


def evaluate_read(work: dict[str, Any]) -> dict[str, Any]:
    """Process-pool entry point: score one read under every key and return its shard."""

    started = time.perf_counter()
    sequence = str(work["sequence"])
    rows = score_read_under_keys(
        sequence,
        case_id=str(work["case_id"]),
        draw_id=work["draw_id"],
        family=str(work["family"]),
        model=work["model"],
        key_indices=tuple(work["key_indices"]),
    )
    check_window_counts(rows)
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "family": work["family"],
        "model": work["model"],
        "case_id": work["case_id"],
        "draw_id": work["draw_id"],
        "read_sha256": hashlib.sha256(sequence.encode("ascii")).hexdigest(),
        "read_bases": len(sequence),
        "complete": True,
        "runtime_seconds": time.perf_counter() - started,
        "rows": rows,
    }


def validate_shard(shard: dict[str, Any], work: dict[str, Any]) -> None:
    """Reject a shard that does not belong to this read, family, model and key set."""

    expected = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "family": work["family"],
        "model": work["model"],
        "case_id": work["case_id"],
        "draw_id": work["draw_id"],
        "read_sha256": hashlib.sha256(str(work["sequence"]).encode("ascii")).hexdigest(),
        "read_bases": len(str(work["sequence"])),
        "complete": True,
    }
    for field, value in expected.items():
        if shard.get(field) != value:
            raise ValueError(f"shard for {work['case_id']} has inconsistent {field}")
    rows = shard.get("rows")
    key_indices = tuple(work["key_indices"])
    if not isinstance(rows, list) or [r.get("key_index") for r in rows] != list(key_indices):
        raise ValueError(f"shard for {work['case_id']} does not cover the declared keys")
    check_window_counts(rows)


# --------------------------------------------------------------------------- inputs


def evaluated_case_ids(case_ids: list[str], n_eval: int) -> list[str]:
    """First ``n_eval`` held-out prompts in split-rank order (protocol Section 3)."""

    if n_eval <= 0:
        raise ValueError("the number of evaluated prompts must be positive")
    ranked = sorted(
        (str(case_id) for case_id in case_ids),
        key=lambda case_id: (
            hashlib.sha256(f"{CALIBRATION_SPLIT_LABEL}\x00{case_id}".encode()).digest(),
            case_id,
        ),
    )
    held_out = ranked[CALIBRATION_PROMPTS:]
    assignments = deterministic_prompt_split(
        ranked, calibration_prompts=CALIBRATION_PROMPTS, label=CALIBRATION_SPLIT_LABEL
    )
    if set(held_out) != {c for c, a in assignments.items() if a == "evaluation"}:
        raise RuntimeError("split ranking disagrees with deterministic_prompt_split")
    if n_eval > len(held_out):
        raise ValueError(f"requested {n_eval} evaluated prompts, only {len(held_out)} held out")
    return held_out[:n_eval]


_FASTA_BASES = re.compile(r"[ACGT]+")


def parse_fasta_sequence(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or not lines[0].startswith(">"):
        raise ValueError("FASTA record must begin with a header line")
    if any(line.startswith(">") for line in lines[1:]):
        raise ValueError("FASTA file must hold exactly one record")
    return "".join(lines[1:])


def load_natural_spans(
    span_dir: Path, prompts: dict[str, str], case_ids: list[str] | None = None
) -> dict[str, str]:
    """Load and verify the public source spans (3,072 canonical bases; prompt prefix)."""

    spans: dict[str, str] = {}
    for case_id in case_ids if case_ids is not None else sorted(prompts):
        path = span_dir / f"{case_id}.fasta"
        if not path.is_file():
            raise FileNotFoundError(f"missing source span: {path}")
        sequence = parse_fasta_sequence(path.read_text(encoding="utf-8"))
        if len(sequence) != SPAN_BASES or _FASTA_BASES.fullmatch(sequence) is None:
            raise ValueError(f"span {case_id} is not {SPAN_BASES} canonical bases")
        if sequence[:PROMPT_BASES] != prompts[case_id]:
            raise ValueError(f"span {case_id} does not begin with its prompt")
        spans[case_id] = sequence
    return spans


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def load_draw0_reads(
    *,
    sequences_path: Path,
    scheme: str,
    prompts: dict[str, str],
    prompt_digests: dict[str, str],
    evaluated: list[str],
    experiment_label: str,
    experiment_id: str,
    default_experiment_id: str,
    cohort_id: str,
    policy_id: str,
) -> dict[str, str]:
    """Return ``{case_id: prompt + continuation}`` for the draw-0 arm ``scheme``."""

    wanted = set(evaluated)
    reads: dict[str, str] = {}
    for row in load_jsonl(sequences_path):
        if str(row["case_id"]) not in wanted or int(row["draw_id"]) != 0:
            continue
        if str(row["scheme"]) != scheme:
            continue
        if (
            str(row.get("experiment_id", default_experiment_id)) != experiment_id
            or str(row.get("experiment_label")) != experiment_label
            or str(row.get("policy_id")) != policy_id
            or str(row.get("cohort_id")) != cohort_id
        ):
            raise ValueError("generation record does not belong to the requested run")
        case_id = str(row["case_id"])
        continuation = str(row["generated_dna"])
        if len(continuation) != CONTINUATION_BASES or set(continuation) - set("ACGT"):
            raise ValueError(f"record {case_id} is not {CONTINUATION_BASES} canonical bases")
        if hashlib.sha256(continuation.encode("ascii")).hexdigest() != str(row["sequence_sha256"]):
            raise ValueError(f"record {case_id} fails its sequence checksum")
        if str(row["prompt_sequence_sha256"]) != prompt_digests[case_id]:
            raise ValueError(f"record {case_id} was generated from a different prompt")
        if case_id in reads:
            raise ValueError(f"duplicate draw-0 {scheme} record for {case_id}")
        reads[case_id] = prompts[case_id] + continuation
    missing = sorted(wanted - set(reads))
    if missing:
        raise ValueError(f"{len(missing)} evaluated prompt(s) have no draw-0 {scheme} record")
    return reads


# --------------------------------------------------------------------------- outputs


def atomic_write_text(path: Path, payload: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to replace existing artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def write_trials_gz(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write rows as a deterministic (mtime 0) gzip JSON-lines file, never overwriting."""

    if path.exists():
        raise FileExistsError(f"refusing to replace existing artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as handle:
            for row in rows:
                handle.write((json.dumps(row, sort_keys=True) + "\n").encode("utf-8"))
    os.replace(temporary, path)


def cpu_model() -> str:
    if sys.platform == "darwin":
        try:
            return subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            pass
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor() or platform.machine()


def digest_manifest(entries: list[tuple[str, str]]) -> str:
    payload = "".join(f"{name} {digest}\n" for name, digest in sorted(entries))
    return hashlib.sha256(payload.encode()).hexdigest()


# --------------------------------------------------------------------------- main


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", choices=FAMILIES, required=True)
    parser.add_argument(
        "--model", choices=tuple(MODEL_POLICIES), help="required for model families"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--cohort-id", default=DEFAULT_COHORT_ID)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--span-dir", type=Path, default=DEFAULT_SPAN_DIR)
    parser.add_argument(
        "--generation-root", type=Path, help="holds generation/draw_00_sequences.jsonl"
    )
    parser.add_argument("--sequences", type=Path, help="explicit draw-0 sequences file")
    parser.add_argument("--experiment-label", help="e.g. carbon-synthid-local-v5")
    parser.add_argument("--generation-experiment-id", help="id recorded in generation rows")
    parser.add_argument("--policy-id", help="defaults to the model's policy (C_tok or G_tok)")
    parser.add_argument("--n-eval", type=int, help="evaluated prompts (model families)")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--keys", type=int, default=KEY_COUNT, help="smoke tests only")
    parser.add_argument("--case-id", action="append", help="restrict to these ids (smoke test)")
    parser.add_argument("--limit", type=int, help="first N reads only (smoke test)")
    return parser.parse_args(argv)


def build_works(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Return the per-read work items and the input-file records of this run."""

    key_indices = tuple(range(args.keys))
    inputs: list[dict[str, str]] = [
        {
            "role": "cohort_prompts",
            "path": str(args.cohort_jsonl.resolve()),
            "sha256": sha256_file(str(args.cohort_jsonl)),
        }
    ]
    cases = load_context_cases_jsonl(args.cohort_jsonl)
    prompts = {case.case_id: case.sequence for case in cases}
    prompt_digests = {case.case_id: case.sequence_sha256 for case in cases}
    if any(len(prompt) != PROMPT_BASES for prompt in prompts.values()):
        raise ValueError(f"every prompt must contain {PROMPT_BASES} bases")

    if args.family == FAMILY_NATURAL:
        ids = sorted(prompts)
        if args.case_id:
            ids = [i for i in ids if i in set(args.case_id)]
        if args.limit:
            ids = ids[: args.limit]
        partial = bool(args.case_id or args.limit)
        if not partial and len(ids) != EXPECTED_SPANS:
            raise ValueError(f"expected {EXPECTED_SPANS} spans, found {len(ids)}")
        spans = load_natural_spans(args.span_dir, prompts, ids)
        manifest = [
            (f"{case_id}.fasta", sha256_file(str(args.span_dir / f"{case_id}.fasta")))
            for case_id in ids
        ]
        inputs.append(
            {
                "role": "natural_span_manifest",
                "path": str(args.span_dir.resolve()),
                "files": len(manifest),
                "manifest_sha256": digest_manifest(manifest),
                "per_file_sha256": [[name, digest] for name, digest in manifest],  # type: ignore[dict-item]
            }
        )
        works = [
            {
                "family": FAMILY_NATURAL,
                "model": None,
                "case_id": i,
                "draw_id": None,
                "sequence": spans[i],
                "key_indices": key_indices,
            }
            for i in ids
        ]
        return works, inputs

    if args.model is None:
        raise ValueError("--model is required for model-output families")
    if args.n_eval is None:
        raise ValueError("--n-eval is required for model-output families")
    if not args.experiment_label:
        raise ValueError("--experiment-label is required for model-output families")
    policy_id = args.policy_id or MODEL_POLICIES[args.model]
    if policy_id != MODEL_POLICIES[args.model]:
        raise ValueError("--policy-id disagrees with --model")
    default_id = MODEL_DEFAULT_GENERATION_IDS[args.model]
    experiment_id = args.generation_experiment_id or default_id
    sequences_path = args.sequences
    if sequences_path is None:
        if args.generation_root is None:
            raise ValueError("give --generation-root or --sequences")
        sequences_path = args.generation_root / "generation" / "draw_00_sequences.jsonl"
    evaluated = evaluated_case_ids(sorted(prompts), args.n_eval)
    reads = load_draw0_reads(
        sequences_path=sequences_path,
        scheme=FAMILY_SCHEME[args.family],
        prompts=prompts,
        prompt_digests=prompt_digests,
        evaluated=evaluated,
        experiment_label=args.experiment_label,
        experiment_id=experiment_id,
        default_experiment_id=default_id,
        cohort_id=args.cohort_id,
        policy_id=policy_id,
    )
    inputs.append(
        {
            "role": "draw0_sequences",
            "path": str(sequences_path.resolve()),
            "sha256": sha256_file(str(sequences_path)),
        }
    )
    ids = evaluated
    if args.case_id:
        ids = [i for i in ids if i in set(args.case_id)]
    if args.limit:
        ids = ids[: args.limit]
    works = [
        {
            "family": args.family,
            "model": args.model,
            "case_id": i,
            "draw_id": 0,
            "sequence": reads[i],
            "key_indices": key_indices,
        }
        for i in ids
    ]
    return works, inputs


def run_works(works: list[dict[str, Any]], shards_dir: Path, workers: int) -> None:
    pending: list[dict[str, Any]] = []
    for work in works:
        path = shards_dir / f"{work['case_id']}.json"
        if path.exists():
            validate_shard(json.loads(path.read_text(encoding="utf-8")), work)
        else:
            pending.append(work)
    completed = len(works) - len(pending)

    def store(shard: dict[str, Any]) -> None:
        nonlocal completed
        atomic_write_text(
            shards_dir / f"{shard['case_id']}.json", json.dumps(shard, sort_keys=True) + "\n"
        )
        completed += 1
        print(json.dumps({"completed_reads": completed, "total_reads": len(works)}), flush=True)

    if workers <= 1:
        for work in pending:
            store(evaluate_read(work))
        return
    with ProcessPoolExecutor(max_workers=workers) as executor:
        for future in as_completed([executor.submit(evaluate_read, w) for w in pending]):
            store(future.result())


def finalize(
    args: argparse.Namespace,
    works: list[dict[str, Any]],
    inputs: list[dict[str, str]],
    started: float,
) -> Path:
    shards_dir = args.output_dir / "shards"
    rows: list[dict[str, Any]] = []
    worker_seconds = 0.0
    for work in works:
        shard = json.loads((shards_dir / f"{work['case_id']}.json").read_text(encoding="utf-8"))
        validate_shard(shard, work)
        rows.extend(shard["rows"])
        worker_seconds += float(shard["runtime_seconds"])
    rows.sort(key=lambda r: (str(r["case_id"]), int(r["key_index"])))
    if len(rows) != len(works) * args.keys:
        raise RuntimeError("decision count disagrees with reads x keys")
    check_window_counts(rows)
    trials_path = args.output_dir / "trials.jsonl.gz"
    write_trials_gz(trials_path, rows)
    protocol_sha = sha256_file(str(args.protocol))
    summary: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "classification": "review_study_result_pending_evidence_admission",
        "protocol": {
            "id": PROTOCOL_ID,
            "path": str(args.protocol.resolve()),
            "sha256": protocol_sha,
            "section": "7 S3 null calibration",
        },
        "family": args.family,
        "model": args.model if args.family != FAMILY_NATURAL else None,
        "policy_id": (
            None if args.family == FAMILY_NATURAL else args.policy_id or MODEL_POLICIES[args.model]
        ),
        "experiment_label": args.experiment_label,
        "cohort_id": args.cohort_id,
        "evaluated_prompts": args.n_eval,
        "partial_run": bool(args.case_id or args.limit or args.keys != KEY_COUNT),
        "detector_id": POSITION_INDEPENDENT_SYNTHID_DETECTOR,
        "null_key_derivation": (
            f"SHA-256 of '{NULL_KEY_LABEL}/<i>' (UTF-8), i in 0..{KEY_COUNT - 1}"
        ),
        "null_domain": NULL_DOMAIN,
        "keys": args.keys,
        "key_bytes_recorded": False,
        "target_sequence_false_positive_rate": TARGET_LEVEL,
        "window_count_note": (
            "A 3,072-base span searches 13,064 windows; a 3,456-base read (384-base prompt "
            "plus 3,072-base continuation) searches 16,136. Each sequence-level P-value "
            "uses its own count; both counts are asserted on every decision."
        ),
        "expected_windows_by_read_bases": {str(k): v for k, v in EXPECTED_WINDOWS.items()},
        "decision_note": (
            "Decisions on one read under different keys share the read; the read-level "
            "summary is reported beside the pooled count."
        ),
        **summarize_trials(rows, args.keys),
        "worker_runtime_seconds_sum": worker_seconds,
        "finalization_wall_seconds": time.perf_counter() - started,
        "trials_artifact": {
            "path": str(trials_path.resolve()),
            "sha256": sha256_file(str(trials_path)),
        },
        "inputs": inputs,
        "code_sha256": {name: sha256_file(str(ROOT / name)) for name in CODE_FILES},
        "provenance": {
            "command": shlex.join([sys.executable, *sys.argv]),
            "workers": args.workers,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_model": cpu_model(),
        },
        "flags": [
            "Null keys are public fixtures; no secret-key claim follows from this study.",
            "Rows hold key indices only; key bytes are never written.",
        ],
    }
    summary_path = args.output_dir / "summary.json"
    atomic_write_text(summary_path, json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary_path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.workers <= 0 or not 0 < args.keys <= KEY_COUNT:
        raise ValueError("workers must be positive and keys must lie in [1, 64]")
    if not args.protocol.is_file():
        raise FileNotFoundError(args.protocol)
    if (args.output_dir / "summary.json").exists():
        raise FileExistsError("refusing to replace an existing finalized result")
    started = time.perf_counter()
    works, inputs = build_works(args)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_works(works, args.output_dir / "shards", args.workers)
    path = finalize(args, works, inputs, started)
    print(json.dumps({"summary": str(path), "reads": len(works)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
