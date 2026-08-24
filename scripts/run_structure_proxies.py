#!/usr/bin/env python3
"""E15: price the E12 removal attack with the two declared order-sensitive measures.

Model-free. Reads a generated sequences file, rebuilds the E12 attacks with the same
public replay seeds, and computes open reading frame summaries and an
independent-model score before and after each attack.

The reference Markov model is fitted only on cohort prompts that no detection
experiment used, and the runner refuses to proceed if that separation does not hold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.attacks import (  # noqa: E402
    BLOCK_SHUFFLE_ATTACK,
    SHUFFLE_ATTACK,
    SPLICE_ATTACK,
    block_shuffle,
    positional_shuffle,
    positional_splice,
)
from genomic_watermarks.pilot import (  # noqa: E402
    cohort_case_digest,
    load_context_cases_jsonl,
    numeric_summary,
)
from genomic_watermarks.sequence_proxies import (  # noqa: E402
    PROXY_METRICS,
    exact_sign_flip_test,
    proxy_metrics,
)
from genomic_watermarks.structure_proxies import (  # noqa: E402
    MINIMUM_ORF_CODONS,
    STRUCTURE_METRICS,
    fit_reference,
    relative_shift,
    structure_metrics,
)
from genomic_watermarks.watermark import PARTITION_MC_SCHEME, public_replay_seed  # noqa: E402

DEFAULT_COHORT = ROOT / "data/processed/ncbi_refseq_eukaryote_windows_v2/prompts.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequences", type=Path, required=True)
    parser.add_argument("--cohort-jsonl", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--cohort-manifest", type=Path)
    parser.add_argument("--markov-orders", type=int, nargs="+", default=(3, 5))
    parser.add_argument("--block-widths", type=int, nargs="+", default=(2, 3, 4, 6, 8, 16, 32))
    parser.add_argument("--donor-counts", type=int, nargs="+", default=(2, 4, 8))
    parser.add_argument("--splice-draws", type=int, default=8)
    parser.add_argument("--minimum-orf-codons", type=int, default=MINIMUM_ORF_CODONS)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to replace existing output: {args.output}")
    orders = tuple(sorted({int(v) for v in args.markov_orders}))
    widths = tuple(sorted({int(v) for v in args.block_widths}))
    donor_counts = tuple(sorted({int(v) for v in args.donor_counts}))
    if any(v < 2 for v in widths):
        raise ValueError("block widths must be at least two tokens")
    if any(v < 2 for v in donor_counts):
        raise ValueError("splicing needs at least two donors")

    records = tuple(
        json.loads(line)
        for line in args.sequences.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    watermarked = {
        r["case_id"]: r["generated_dna"] for r in records if r["scheme"] == PARTITION_MC_SCHEME
    }
    if not watermarked:
        raise ValueError("the sequences file holds no watermarked arm")
    policy_id = records[0]["policy_id"]
    cohort_id = records[0]["cohort_id"]
    experiment_label = records[0]["experiment_label"]
    case_ids = tuple(sorted(watermarked))
    if max(donor_counts) > len(case_ids):
        raise ValueError("a donor count exceeds the number of available outputs")

    cases = load_context_cases_jsonl(args.cohort_jsonl)
    # The reference model must not see anything the attack touches.
    held_out = [case.sequence for case in cases if case.case_id not in set(case_ids)]
    held_out_ids = [case.case_id for case in cases if case.case_id not in set(case_ids)]
    if len(held_out) < 4:
        raise ValueError("too few held-out prompts to fit a reference model")
    if set(held_out_ids) & set(case_ids):
        raise ValueError("the reference model would see a scored prompt")

    run_started = time.perf_counter()
    references = {order: fit_reference(held_out, order=order) for order in orders}

    def measure(sequence: str) -> dict[str, Any]:
        out: dict[str, Any] = {"composition": proxy_metrics(sequence)}
        for order, model in references.items():
            out[f"structure_order_{order}"] = structure_metrics(
                sequence, model, minimum_codons=args.minimum_orf_codons
            )
        return out

    baseline = {case_id: measure(watermarked[case_id]) for case_id in case_ids}

    rows: list[dict[str, Any]] = []

    def record(attack: str, parameter: Any, case_id: str, attacked: str, label: str) -> None:
        measured = measure(attacked)
        row: dict[str, Any] = {
            "attack": attack,
            "parameter": parameter,
            "case_id": case_id,
            "reference_case_id": label,
        }
        reference = baseline[label]
        for order in orders:
            key = f"structure_order_{order}"
            row[key] = measured[key]
            row[f"{key}_reference"] = reference[key]
            row[f"{key}_relative_shift"] = relative_shift(measured[key], reference[key])
        row["composition_relative_shift"] = {
            metric: abs(measured["composition"][metric] - reference["composition"][metric])
            / (abs(reference["composition"][metric]) or 1.0)
            for metric in PROXY_METRICS
        }
        rows.append(row)

    for case_id in case_ids:
        source = watermarked[case_id]
        rng = random.Random(public_replay_seed("e11-shuffle", policy_id, case_id))
        attacked, _ = positional_shuffle(source, rng)
        record(SHUFFLE_ATTACK, None, case_id, attacked, case_id)
        for width in widths:
            rng = random.Random(public_replay_seed("e11-block", policy_id, case_id, str(width)))
            attacked, _ = block_shuffle(source, width, rng)
            record(BLOCK_SHUFFLE_ATTACK, width, case_id, attacked, case_id)

    for donors in donor_counts:
        for replicate in range(args.splice_draws):
            rng = random.Random(
                public_replay_seed("e11-splice", policy_id, str(donors), str(replicate))
            )
            chosen = rng.sample(case_ids, donors)
            forged, _ = positional_splice([watermarked[c] for c in chosen], rng)
            record(SPLICE_ATTACK, donors, f"splice_{donors}_{replicate}", forged, chosen[0])

    summaries: list[dict[str, Any]] = []
    for attack, parameter in (
        [(SHUFFLE_ATTACK, None)]
        + [(BLOCK_SHUFFLE_ATTACK, width) for width in widths]
        + [(SPLICE_ATTACK, donors) for donors in donor_counts]
    ):
        selected = [r for r in rows if r["attack"] == attack and r["parameter"] == parameter]
        if not selected:
            continue
        entry: dict[str, Any] = {"attack": attack, "parameter": parameter, "trials": len(selected)}
        composition = {
            metric: numeric_summary(r["composition_relative_shift"][metric] for r in selected)
            for metric in PROXY_METRICS
        }
        entry["composition_relative_shift"] = composition
        entry["largest_composition_shift"] = max(
            composition[metric]["mean"] for metric in PROXY_METRICS
        )
        entry["largest_composition_metric"] = max(
            PROXY_METRICS, key=lambda metric: composition[metric]["mean"]
        )
        for order in orders:
            key = f"structure_order_{order}"
            shift = {
                metric: numeric_summary(r[f"{key}_relative_shift"][metric] for r in selected)
                for metric in STRUCTURE_METRICS
            }
            block: dict[str, Any] = {"relative_shift": shift}
            # A paired sign-flip test over prompts is only meaningful for the
            # per-prompt attacks; a splice has no single source sequence.
            if attack != SPLICE_ATTACK:
                for metric in STRUCTURE_METRICS:
                    differences = [r[key][metric] - r[f"{key}_reference"][metric] for r in selected]
                    block.setdefault("sign_flip", {})[metric] = exact_sign_flip_test(differences)
            entry[key] = block
        summaries.append(entry)

    report: dict[str, Any] = {
        "schema_version": 1,
        "classification": "engineering_pilot_not_paper_evidence",
        "complete": True,
        "policy_id": policy_id,
        "cohort_id": cohort_id,
        "experiment_label": experiment_label,
        "watermark_method": PARTITION_MC_SCHEME,
        "case_count": len(case_ids),
        "case_ids": list(case_ids),
        "attacks": [SHUFFLE_ATTACK, BLOCK_SHUFFLE_ATTACK, SPLICE_ATTACK],
        "block_widths": list(widths),
        "donor_counts": list(donor_counts),
        "splice_draws_per_donor_count": args.splice_draws,
        "markov_orders": list(orders),
        "minimum_orf_codons": args.minimum_orf_codons,
        "composition_metrics": list(PROXY_METRICS),
        "structure_metrics": list(STRUCTURE_METRICS),
        "reference_model": {
            "kind": "order-k Markov over DNA with Laplace smoothing",
            "fitted_on": "cohort prompts not used by any detection experiment",
            "held_out_prompt_count": len(held_out),
            "held_out_prompt_ids": held_out_ids,
            "overlaps_scored_prompts": False,
            "contexts_by_order": {str(order): references[order].contexts for order in orders},
        },
        "sequences": {
            "path": str(args.sequences),
            "sha256": hashlib.sha256(args.sequences.read_bytes()).hexdigest(),
        },
        "cohort": {
            "prompts_path": str(args.cohort_jsonl),
            "prompts_file_sha256": hashlib.sha256(args.cohort_jsonl.read_bytes()).hexdigest(),
            "cohort_content_sha256": cohort_case_digest(cases),
            "manifest_path": str(args.cohort_manifest) if args.cohort_manifest else None,
            "manifest_sha256": (
                hashlib.sha256(args.cohort_manifest.read_bytes()).hexdigest()
                if args.cohort_manifest
                else None
            ),
        },
        "row_count": len(rows),
        "rows": rows,
        "summaries": summaries,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "wall_seconds": time.perf_counter() - run_started,
        "interpretation_boundary": (
            "The reading-frame measures are structural sequence statistics. On high-entropy DNA a "
            "long open reading frame is largely a chance event, so a drop in it is evidence that "
            "sequence order changed and is NOT evidence of functional, translational, viability, "
            "or"
            "safety consequences. The independent-model score is fitted on held-out public DNA and "
            "is independent of the generator and the key; it is not an independent biological "
            "model,"
            "and a low score means only that local statistics differ from the reference cohort."
        ),
        "boundary": (
            "This experiment prices attacks whose detection outcome E12 already measured. It "
            "changes"
            "no detection number. Public benign DNA and proxy metrics only."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "policy_id": policy_id,
                "rows": len(rows),
                "wall_seconds": report["wall_seconds"],
                "summary": [
                    {
                        "attack": s["attack"],
                        "parameter": s["parameter"],
                        "largest_composition_shift": round(s["largest_composition_shift"], 4),
                        "longest_orf_shift": round(
                            s[f"structure_order_{orders[0]}"]["relative_shift"][
                                "longest_orf_bases"
                            ]["mean"],
                            4,
                        ),
                        "independent_model_shift": round(
                            s[f"structure_order_{orders[0]}"]["relative_shift"][
                                "independent_model_mean_log2_probability"
                            ]["mean"],
                            4,
                        ),
                    }
                    for s in summaries
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
