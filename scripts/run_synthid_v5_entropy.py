#!/usr/bin/env python3
"""S4 entropy of the v5 review studies (protocol Section 8): model-backed pass.

For every marked and ordinary continuation of the evaluated prompts (both draws) one
teacher-forced forward pass of the generating model records, at each of the 512 generated
positions, the Shannon entropy in nats of the model's next-token distribution restricted to
the 4,096 canonical DNA 6-mer tokens and normalised once at temperature 1.0.  That is the
distribution ``p`` the samplers use (``canonical_softmax`` followed by the identity policy
``apply_generation_policy`` for C_tok and G_tok).  Tokenisation, the prompt builder, the
canonical-id gather and the forward call replicate
``HuggingFaceDNAAdapter.continuation_likelihood``; entropy and negative log-likelihood are
computed in float64 from the float32 canonical logits.  One immutable shard per prompt
makes the run resumable.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import platform
import shlex
import statistics
import sys
import time
from pathlib import Path
from typing import Any, NamedTuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from run_synthid_v5_null_calibration import (  # noqa: E402
    DEFAULT_COHORT,
    DEFAULT_COHORT_ID,
    MODEL_DEFAULT_GENERATION_IDS,
    MODEL_POLICIES,
    atomic_write_text,
    cpu_model,
    evaluated_case_ids,
    load_jsonl,
)

from genomic_watermarks.dna import normalize_dna  # noqa: E402
from genomic_watermarks.large_validation import sha256_file  # noqa: E402
from genomic_watermarks.pilot import load_context_cases_jsonl  # noqa: E402
from genomic_watermarks.synthid import SYNTHID_SCHEME  # noqa: E402
from genomic_watermarks.watermark import ORDINARY_SCHEME  # noqa: E402

EXPERIMENT_ID = "synthid.v5.s4_entropy"
PROTOCOL_ID = "synthid_v5_review_studies_protocol_2026_11_12"
DEFAULT_PROTOCOL = ROOT / f"docs/research/{PROTOCOL_ID}.md"
GENERATED_TOKENS = 512
CONTINUATION_BASES = GENERATED_TOKENS * 6
PROMPT_BASES = 384
DRAWS = (0, 1)
SCHEME_LABEL = {SYNTHID_SCHEME: "marked", ORDINARY_SCHEME: "ordinary"}
CODE_FILES = (
    "scripts/run_synthid_v5_entropy.py",
    "scripts/run_synthid_v5_null_calibration.py",
    "src/genomic_watermarks/models/huggingface.py",
    "src/genomic_watermarks/models/policy_math.py",
    "src/genomic_watermarks/models/vocabulary.py",
    "src/genomic_watermarks/models/runtime.py",
    "src/genomic_watermarks/pilot.py",
)


class TeacherForced(NamedTuple):
    """Per-position results of one teacher-forced pass over a continuation."""

    entropies: tuple[float, ...]
    nlls: tuple[float, ...]


def entropy_nats_from_logits(logits: Any) -> Any:
    """Shannon entropy in nats of ``softmax(logits)`` per row, in float64.

    ``logits`` has shape ``(positions, tokens)``.  Zero probabilities contribute zero, so a
    one-hot distribution (including ``-inf`` logits) has entropy 0 and a uniform one has
    ``ln(tokens)``.
    """

    import torch

    log_probabilities = torch.log_softmax(logits.double(), dim=-1)
    probabilities = log_probabilities.exp()
    terms = torch.where(
        probabilities > 0.0,
        probabilities * log_probabilities,
        torch.zeros_like(probabilities),
    )
    return -terms.sum(dim=-1)


def realised_nll_from_logits(logits: Any, target_indices: Any) -> Any:
    """Negative log-probability of each realised canonical token, float64."""

    import torch

    log_probabilities = torch.log_softmax(logits.double(), dim=-1)
    positions = torch.arange(log_probabilities.shape[0], device=log_probabilities.device)
    return -log_probabilities[positions, target_indices.to(log_probabilities.device)]


def teacher_forced_entropy_and_nll(
    adapter: Any, prompt_dna: str, continuation_dna: str
) -> TeacherForced:
    """One forward pass; entropy and NLL at every continuation position.

    Mirrors ``HuggingFaceDNAAdapter.continuation_likelihood`` step for step (same prompt
    builder, tokenisation checks, canonical-id gather and forward call).  It reads the
    adapter's tokenizer, model, device and prompt builder, which that method reads too.
    """

    import torch

    if adapter.policy.policy_id not in {"C_tok", "G_tok"}:
        raise ValueError("entropy requires a direct-token policy")
    prompt = normalize_dna(prompt_dna)
    continuation = normalize_dna(continuation_dna)
    if len(prompt) % 6 or len(continuation) % 6:
        raise ValueError("prompt and continuation lengths must be divisible by six")
    if not continuation:
        raise ValueError("continuation must not be empty")
    tokenizer = adapter._tokenizer
    model = adapter._model
    device = adapter._device
    build = adapter._spec.prompt_builder
    canonical_ids = list(adapter.canonical_vocabulary.ids)
    prompt_inputs = tokenizer(build(prompt), return_tensors="pt", add_special_tokens=False)
    full_inputs = tokenizer(
        build(prompt + continuation), return_tensors="pt", add_special_tokens=False
    )
    prompt_ids = prompt_inputs["input_ids"][0]
    full_ids = full_inputs["input_ids"][0]
    prompt_tokens = int(prompt_ids.shape[0])
    full_tokens = int(full_ids.shape[0])
    expected = len(continuation) // 6
    if full_tokens - prompt_tokens != expected:
        raise RuntimeError("model tokenization did not preserve the declared 6-mer boundary")
    if not torch.equal(full_ids[:prompt_tokens], prompt_ids):
        raise RuntimeError("model prompt tokenization is not a prefix of the full sequence")
    position_of = {token_id: index for index, token_id in enumerate(canonical_ids)}
    try:
        targets = [position_of[int(token_id)] for token_id in full_ids[prompt_tokens:].tolist()]
    except KeyError as error:
        raise RuntimeError("continuation tokenized outside the canonical vocabulary") from error
    device_inputs = {name: value.to(device) for name, value in full_inputs.items()}
    with torch.inference_mode():
        outputs = model(**device_inputs, return_dict=True)
        canonical_logits = outputs.logits[0, prompt_tokens - 1 : full_tokens - 1, canonical_ids]
        logits64 = canonical_logits.float().cpu().double()
        entropies = entropy_nats_from_logits(logits64)
        nlls = realised_nll_from_logits(logits64, torch.tensor(targets))
    return TeacherForced(tuple(float(v) for v in entropies), tuple(float(v) for v in nlls))


def sequence_statistics(result: TeacherForced) -> dict[str, Any]:
    """Per-sequence summary: mean/min/median/max entropy and mean NLL."""

    entropies, nlls = result.entropies, result.nlls
    if not entropies or len(entropies) != len(nlls):
        raise ValueError("entropy and NLL must be non-empty and aligned")
    if any(not math.isfinite(v) or v < -1e-12 for v in entropies):
        raise ValueError("entropy values must be finite and non-negative")
    return {
        "positions": len(entropies),
        "mean_entropy_nats": math.fsum(entropies) / len(entropies),
        "min_entropy_nats": min(entropies),
        "median_entropy_nats": statistics.median(entropies),
        "max_entropy_nats": max(entropies),
        "mean_nll_nats": math.fsum(nlls) / len(nlls),
    }


# --------------------------------------------------------------------------- inputs


def load_generation_records(
    *,
    root: Path,
    evaluated: list[str],
    experiment_label: str,
    experiment_id: str,
    default_experiment_id: str,
    cohort_id: str,
    policy_id: str,
    prompt_digests: dict[str, str],
) -> tuple[dict[tuple[str, int, str], dict[str, Any]], list[Path]]:
    """Return ``{(case_id, draw, scheme): record}`` for every evaluated prompt."""

    wanted = set(evaluated)
    records: dict[tuple[str, int, str], dict[str, Any]] = {}
    paths: list[Path] = []
    for draw in DRAWS:
        path = root / "generation" / f"draw_{draw:02d}_sequences.jsonl"
        paths.append(path)
        for row in load_jsonl(path):
            case_id = str(row["case_id"])
            if case_id not in wanted:
                continue
            if (
                str(row.get("experiment_id", default_experiment_id)) != experiment_id
                or str(row.get("experiment_label")) != experiment_label
                or str(row.get("policy_id")) != policy_id
                or str(row.get("cohort_id")) != cohort_id
                or int(row["draw_id"]) != draw
            ):
                raise ValueError("generation record does not belong to the requested run")
            scheme = str(row["scheme"])
            dna = str(row["generated_dna"])
            if scheme not in SCHEME_LABEL:
                raise ValueError(f"unknown scheme {scheme!r}")
            if len(dna) != CONTINUATION_BASES or set(dna) - set("ACGT"):
                raise ValueError(f"record {case_id} is not {CONTINUATION_BASES} canonical bases")
            if hashlib.sha256(dna.encode("ascii")).hexdigest() != str(row["sequence_sha256"]):
                raise ValueError(f"record {case_id} fails its sequence checksum")
            if str(row["prompt_sequence_sha256"]) != prompt_digests[case_id]:
                raise ValueError(f"record {case_id} was generated from a different prompt")
            key = (case_id, draw, scheme)
            if key in records:
                raise ValueError(f"duplicate generation record {key}")
            records[key] = row
    missing = [
        (case_id, draw, scheme)
        for case_id in evaluated
        for draw in DRAWS
        for scheme in SCHEME_LABEL
        if (case_id, draw, scheme) not in records
    ]
    if missing:
        raise ValueError(f"{len(missing)} evaluated sequence(s) missing, first {missing[0]}")
    return records, paths


def shard_path(shards_dir: Path, case_id: str) -> Path:
    return shards_dir / f"{case_id}.json"


def validate_shard(
    shard: dict[str, Any],
    case_id: str,
    args: argparse.Namespace,
    expected_sha: dict[tuple[int, str], str],
) -> None:
    expected = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "model": args.model,
        "case_id": case_id,
        "device": args.device,
        "dtype": args.dtype,
        "complete": True,
    }
    for field, value in expected.items():
        if shard.get(field) != value:
            raise ValueError(f"entropy shard {case_id} has inconsistent {field}")
    rows = shard.get("sequences")
    if not isinstance(rows, list) or len(rows) != len(expected_sha):
        raise ValueError(f"entropy shard {case_id} has the wrong sequence count")
    seen = {(int(r["draw_id"]), str(r["scheme_raw"])): str(r["sequence_sha256"]) for r in rows}
    if seen != expected_sha:
        raise ValueError(f"entropy shard {case_id} does not match the generation records")


# --------------------------------------------------------------------------- main


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=tuple(MODEL_POLICIES), required=True)
    parser.add_argument(
        "--generation-root",
        type=Path,
        required=True,
        help="holds generation/draw_00_sequences.jsonl and draw_01",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--cohort-id", default=DEFAULT_COHORT_ID)
    parser.add_argument("--experiment-label", required=True)
    parser.add_argument("--generation-experiment-id")
    parser.add_argument("--policy-id")
    parser.add_argument("--n-eval", type=int, required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--device", choices=("mps", "cuda", "cpu"), default="mps")
    parser.add_argument("--dtype", choices=("bfloat16", "float16", "float32"), default="bfloat16")
    parser.add_argument("--cache-dir", default=str(ROOT / ".cache/huggingface"))
    parser.add_argument(
        "--allow-download", action="store_true", help="default is offline: local files only"
    )
    parser.add_argument("--case-id", action="append", help="restrict to these ids (smoke test)")
    parser.add_argument("--limit", type=int, help="first N evaluated prompts only (smoke test)")
    parser.add_argument(
        "--crosscheck-nll",
        action="store_true",
        help="also call the adapter's own continuation_likelihood on every "
        "sequence and record the difference (doubles the cost)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.perf_counter()
    if not args.protocol.is_file():
        raise FileNotFoundError(args.protocol)
    if (args.output_dir / "summary.json").exists():
        raise FileExistsError("refusing to replace an existing finalized result")
    policy_id = args.policy_id or MODEL_POLICIES[args.model]
    if policy_id != MODEL_POLICIES[args.model]:
        raise ValueError("--policy-id disagrees with --model")
    default_id = MODEL_DEFAULT_GENERATION_IDS[args.model]
    generation_id = args.generation_experiment_id or default_id
    cases = load_context_cases_jsonl(args.cohort_jsonl)
    prompts = {case.case_id: case.sequence for case in cases}
    digests = {case.case_id: str(case.sequence_sha256) for case in cases}
    if any(len(prompt) != PROMPT_BASES for prompt in prompts.values()):
        raise ValueError(f"every prompt must contain {PROMPT_BASES} bases")
    evaluated = evaluated_case_ids(sorted(prompts), args.n_eval)
    records, generation_paths = load_generation_records(
        root=args.generation_root,
        evaluated=evaluated,
        experiment_label=args.experiment_label,
        experiment_id=generation_id,
        default_experiment_id=default_id,
        cohort_id=args.cohort_id,
        policy_id=policy_id,
        prompt_digests=digests,
    )
    selected = evaluated
    if args.case_id:
        selected = [c for c in selected if c in set(args.case_id)]
    if args.limit:
        selected = selected[: args.limit]
    partial = len(selected) != len(evaluated)
    shards_dir = args.output_dir / "shards"
    shards_dir.mkdir(parents=True, exist_ok=True)

    def expected_sha(case_id: str) -> dict[tuple[int, str], str]:
        return {
            (draw, scheme): str(records[(case_id, draw, scheme)]["sequence_sha256"])
            for draw in DRAWS
            for scheme in SCHEME_LABEL
        }

    pending: list[str] = []
    for case_id in selected:
        path = shard_path(shards_dir, case_id)
        if path.exists():
            validate_shard(
                json.loads(path.read_text(encoding="utf-8")), case_id, args, expected_sha(case_id)
            )
        else:
            pending.append(case_id)

    session: dict[str, Any] = {"computed_now": len(pending)}
    if pending:
        import torch

        from genomic_watermarks.models.huggingface import load_adapter

        if args.device == "mps" and not torch.backends.mps.is_available():
            raise RuntimeError("MPS is unavailable")
        if args.device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable")
        load_started = time.perf_counter()
        adapter = load_adapter(
            policy_id,
            device=args.device,
            dtype=args.dtype,
            allow_cpu_fallback=False,
            cache_dir=args.cache_dir,
            local_files_only=not args.allow_download,
        )
        session["model_load_seconds"] = time.perf_counter() - load_started
        run_started = time.perf_counter()
        for done, case_id in enumerate(pending, start=1):
            rows: list[dict[str, Any]] = []
            for draw in DRAWS:
                for scheme in (SYNTHID_SCHEME, ORDINARY_SCHEME):
                    record = records[(case_id, draw, scheme)]
                    continuation = str(record["generated_dna"])
                    tick = time.perf_counter()
                    forced = teacher_forced_entropy_and_nll(adapter, prompts[case_id], continuation)
                    seconds = time.perf_counter() - tick
                    row: dict[str, Any] = {
                        "case_id": case_id,
                        "draw_id": draw,
                        "scheme": SCHEME_LABEL[scheme],
                        "scheme_raw": scheme,
                        "sequence_sha256": str(record["sequence_sha256"]),
                        **sequence_statistics(forced),
                        "forward_seconds": seconds,
                    }
                    if args.crosscheck_nll:
                        likelihood = adapter.continuation_likelihood(prompts[case_id], continuation)
                        row["adapter_mean_nll_nats"] = likelihood.mean_negative_log_likelihood
                        row["adapter_nll_abs_difference"] = abs(
                            likelihood.mean_negative_log_likelihood - row["mean_nll_nats"]
                        )
                    rows.append(row)
            shard = {
                "schema_version": 1,
                "experiment_id": EXPERIMENT_ID,
                "model": args.model,
                "case_id": case_id,
                "device": args.device,
                "dtype": args.dtype,
                "complete": True,
                "sequences": rows,
            }
            atomic_write_text(
                shard_path(shards_dir, case_id), json.dumps(shard, sort_keys=True) + "\n"
            )
            print(
                json.dumps(
                    {
                        "completed_in_session": done,
                        "pending": len(pending) - done,
                        "case_id": case_id,
                    }
                ),
                flush=True,
            )
        session["run_seconds"] = time.perf_counter() - run_started
        session["sequences"] = len(pending) * len(DRAWS) * len(SCHEME_LABEL)
        session["seconds_per_sequence"] = session["run_seconds"] / session["sequences"]
        session.update(torch_version=torch.__version__)
        adapter = None
        gc.collect()
        if args.device == "mps":
            torch.mps.empty_cache()
        elif args.device == "cuda":
            torch.cuda.empty_cache()

    # Assemble final outputs from the shards (resumed and new alike).
    rows_out: list[dict[str, Any]] = []
    for case_id in selected:
        shard = json.loads(shard_path(shards_dir, case_id).read_text(encoding="utf-8"))
        validate_shard(shard, case_id, args, expected_sha(case_id))
        rows_out.extend(shard["sequences"])
    rows_out.sort(key=lambda r: (r["case_id"], r["draw_id"], r["scheme"]))
    sequences_path = args.output_dir / "sequences.jsonl"
    sequences_text = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows_out)
    if sequences_path.exists():
        if sequences_path.read_text(encoding="utf-8") != sequences_text:
            raise FileExistsError(f"refusing to replace different artifact: {sequences_path}")
    else:
        atomic_write_text(sequences_path, sequences_text)
    differences = [
        r["adapter_nll_abs_difference"] for r in rows_out if "adapter_nll_abs_difference" in r
    ]
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
        "model": args.model,
        "policy_id": policy_id,
        "experiment_label": args.experiment_label,
        "cohort_id": args.cohort_id,
        "evaluated_prompts": args.n_eval,
        "selected_prompts": len(selected),
        "partial_run": partial,
        "sequences": len(rows_out),
        "positions_per_sequence": GENERATED_TOKENS,
        "entropy_definition": (
            "Shannon entropy in nats of the canonical 4,096-token next-token distribution "
            "(log-softmax over the canonical logits, temperature 1.0, normalised once), "
            "float64, teacher-forced on prompt + continuation"
        ),
        "device": args.device,
        "dtype": args.dtype,
        "crosscheck_nll": args.crosscheck_nll,
        "crosscheck_max_abs_difference": max(differences) if differences else None,
        "session": session,
        "mean_forward_seconds_per_sequence": statistics.fmean(
            r["forward_seconds"] for r in rows_out
        ),
        "sequences_artifact": {
            "path": str(sequences_path.resolve()),
            "sha256": sha256_file(str(sequences_path)),
        },
        "inputs": [
            {
                "role": "cohort_prompts",
                "path": str(args.cohort_jsonl.resolve()),
                "sha256": sha256_file(str(args.cohort_jsonl)),
            },
            *(
                {"role": "generation_draw", "path": str(p.resolve()), "sha256": sha256_file(str(p))}
                for p in generation_paths
            ),
        ],
        "code_sha256": {name: sha256_file(str(ROOT / name)) for name in CODE_FILES},
        "provenance": {
            "command": shlex.join([sys.executable, *sys.argv]),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_model": cpu_model(),
            "wall_seconds": time.perf_counter() - started,
        },
    }
    atomic_write_text(
        args.output_dir / "summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(
        json.dumps({"sequences": len(rows_out), "summary": str(args.output_dir / "summary.json")})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
