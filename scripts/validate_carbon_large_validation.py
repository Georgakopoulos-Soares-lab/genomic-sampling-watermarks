#!/usr/bin/env python3
"""Strict end-to-end validator for Carbon SynthID validation artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from genomic_watermarks.detector.search import (  # noqa: E402
    analytic_normal_threshold,
    binomial_standardized_exceedance_probability,
    calibrate_threshold,
)
from genomic_watermarks.large_validation import (  # noqa: E402
    deterministic_prompt_split,
    poisson_binomial_two_sided_p_value,
    sequence_identity,
    sha256_file,
)
from genomic_watermarks.synthid import SYNTHID_SCHEME  # noqa: E402
from genomic_watermarks.watermark import (  # noqa: E402
    ORDINARY_SCHEME,
    public_replay_seed,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--expected-prompts", type=int, default=256)
    parser.add_argument("--expected-draws", type=int, default=2)
    parser.add_argument("--expected-generated-tokens", type=int, default=512)
    parser.add_argument("--expected-states", type=int, default=256)
    parser.add_argument("--calibration-prompts", type=int, default=64)
    parser.add_argument("--require-figures", action="store_true")
    parser.add_argument("--require-report", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> int:
    args = parse_args()
    if (
        min(
            args.expected_prompts,
            args.expected_draws,
            args.expected_generated_tokens,
            args.expected_states,
        )
        <= 0
    ):
        raise ValueError("expected counts must be positive")
    required = (
        "cohort_manifest.yaml",
        "prompts.jsonl",
        "generation/generation_summary.json",
        "distribution/state_manifest.jsonl",
        "distribution/fixed_state_trials.parquet",
        "distribution/distribution_summary.json",
        "sequence_comparison/sequence_metrics.parquet",
        "sequence_comparison/sequence_comparison_summary.json",
        "detection/calibration_trials.parquet",
        "detection/evaluation_trials.parquet",
        "detection/detection_summary.json",
    )
    if args.expected_prompts == 256:
        required += ("detection/detector_comparison.json",)
    for relative in required:
        require((args.output_root / relative).is_file(), f"missing required artifact: {relative}")
    prompts = load_jsonl(args.output_root / "prompts.jsonl")
    prompt_ids = [str(row["prompt_id"]) for row in prompts]
    require(len(prompts) == 256, "the frozen cohort copy must retain all 256 prompts")
    require(len(set(prompt_ids)) == 256, "prompt IDs are not unique")
    require(all(len(str(row["sequence"])) == 384 for row in prompts), "a prompt is not 384 bp")
    require(
        all(set(str(row["sequence"])) <= set("ACGT") for row in prompts),
        "a prompt is not canonical DNA",
    )
    require(
        len({str(row["sequence"]) for row in prompts}) == 256,
        "prompt sequences are not unique",
    )
    for row in prompts:
        require(
            hashlib.sha256(str(row["sequence"]).encode("ascii")).hexdigest()
            == str(row["sequence_sha256"]),
            "a prompt checksum does not match",
        )

    generation = load_json(args.output_root / "generation" / "generation_summary.json")
    require(int(generation["case_count"]) == args.expected_prompts, "wrong generated prompt count")
    require(int(generation["draws_per_case"]) == args.expected_draws, "wrong draw count")
    require(
        int(generation["generated_tokens_per_sequence"]) == args.expected_generated_tokens,
        "wrong generated token length",
    )
    records: list[dict[str, Any]] = []
    for draw_id in range(args.expected_draws):
        path = args.output_root / "generation" / f"draw_{draw_id:02d}_sequences.jsonl"
        require(path.is_file(), f"missing draw sequence file {draw_id}")
        draw_records = load_jsonl(path)
        require(
            len(draw_records) == args.expected_prompts * 2,
            f"draw {draw_id} has the wrong sequence count",
        )
        records.extend(draw_records)
    identities = [sequence_identity(row) for row in records]
    require(len(set(identities)) == len(identities), "sequence identities collapsed a draw or arm")
    require(
        len(records) == args.expected_prompts * args.expected_draws * 2,
        "generated corpus has wrong total size",
    )
    require(
        {str(row["scheme"]) for row in records} == {SYNTHID_SCHEME, ORDINARY_SCHEME},
        "generated corpus does not contain exactly the SynthID and ordinary arms",
    )
    require(
        all(
            len(str(row["generated_dna"])) == args.expected_generated_tokens * 6 for row in records
        ),
        "a generated DNA length is wrong",
    )
    require(
        all(set(str(row["generated_dna"])) <= set("ACGT") for row in records),
        "a generated sequence is not canonical",
    )
    replay_seeds = {
        (
            str(row["case_id"]),
            int(row["draw_id"]),
            str(row["scheme"]),
        ): public_replay_seed(
            str(row["experiment_label"]),
            "C_tok",
            str(row["case_id"]),
            f"draw={int(row['draw_id'])}",
            str(row["scheme"]),
        )
        for row in records
    }
    require(
        len(set(replay_seeds.values())) == len(replay_seeds),
        "watermarked/ordinary or multi-draw replay streams collide",
    )

    try:
        import pandas as pd
    except ImportError as error:
        raise RuntimeError("install the optional 'analysis' dependencies first") from error
    distribution = pd.read_parquet(args.output_root / "distribution" / "fixed_state_trials.parquet")
    require(len(distribution) == args.expected_states, "wrong fixed-state count")
    require(
        all(sum(values) > 0 for values in distribution["watermarked_counts"]),
        "a fixed-state watermarked arm is empty",
    )
    distribution_summary = load_json(
        args.output_root / "distribution" / "distribution_summary.json"
    )
    require(
        int(distribution_summary["negative_control"]["state_count"]) > 0,
        "the deliberately broken sampler was not run",
    )
    require(
        distribution_summary["experiment_id"] == "carbon_synthid_validation_v1",
        "distribution artifact has the wrong experiment identity",
    )

    metrics = pd.read_parquet(args.output_root / "sequence_comparison" / "sequence_metrics.parquet")
    require(len(metrics) == len(records), "sequence metrics do not cover every sequence")
    require(
        len(metrics[["case_id", "draw_id", "scheme"]].drop_duplicates()) == len(metrics),
        "sequence metrics collapse explicit draw identity",
    )
    sequence_summary = load_json(
        args.output_root / "sequence_comparison" / "sequence_comparison_summary.json"
    )
    require(
        int(sequence_summary["prompt_count"]) == args.expected_prompts,
        "sequence comparison uses the wrong prompt-cluster count",
    )
    require(
        sequence_summary["statistical_cluster"] == "case_id",
        "sequence comparison does not cluster at prompt level",
    )

    split = deterministic_prompt_split(prompt_ids, calibration_prompts=args.calibration_prompts)
    calibration_ids = {case_id for case_id, value in split.items() if value == "calibration"}
    evaluation_ids = {case_id for case_id, value in split.items() if value == "evaluation"}
    require(not calibration_ids & evaluation_ids, "calibration and evaluation prompts overlap")
    calibration = pd.read_parquet(args.output_root / "detection" / "calibration_trials.parquet")
    evaluation = pd.read_parquet(args.output_root / "detection" / "evaluation_trials.parquet")
    require(
        set(calibration["case_id"]) <= calibration_ids,
        "calibration trials contain held-out prompts",
    )
    require(
        set(evaluation["case_id"]) <= evaluation_ids,
        "evaluation trials contain calibration prompts",
    )
    require(not set(calibration["case_id"]) & set(evaluation["case_id"]), "split leakage")
    detection = load_json(args.output_root / "detection" / "detection_summary.json")
    if args.expected_prompts == 256:
        detector_comparison = load_json(args.output_root / "detection" / "detector_comparison.json")
        require(
            detector_comparison["selection_split"] == "calibration only"
            and int(detector_comparison["calibration_prompts"]) == args.calibration_prompts,
            "detector comparison does not use only the frozen calibration prompts",
        )
        require(
            detector_comparison["selected_detector"] == "mean",
            "calibration-only detector comparison does not select the declared mean detector",
        )
    require(
        detection["detector"]["hypotheses_searched"] == 1
        and detection["detector"]["offset_search"] is False,
        "clean detector unexpectedly searches an alignment or offset",
    )
    require(
        {str(entry["calibration"].get("source", "")) for entry in detection["lengths"]}
        == {"analytic_standard_normal"},
        "Carbon SynthID validation must use the frozen analytic standard-normal threshold",
    )
    analytic_null_fit_by_bases: dict[str, dict[str, float | int]] = {}
    for entry in detection["lengths"]:
        length = int(entry["token_length"])
        calibration_scores = calibration.loc[
            calibration["token_length"] == length, "statistic"
        ].tolist()
        stored_calibration = entry["calibration"]
        threshold_source = str(stored_calibration.get("source", ""))
        if threshold_source == "analytic_standard_normal":
            resolved = analytic_normal_threshold(calibration_scores, 0.01)
        elif threshold_source == "empirical_null_order_statistic":
            resolved = calibrate_threshold(calibration_scores, 0.01)
        else:
            raise ValueError(f"unknown detector threshold source: {threshold_source!r}")
        require(
            abs(float(stored_calibration["threshold"]) - resolved.threshold) < 1e-12,
            "stored detector threshold does not recompute from its declared source",
        )
        held_out = evaluation[evaluation["token_length"] == length]
        correct = held_out[held_out["family"] == "watermarked_correct_key"]
        wrong = held_out[held_out["family"] == "watermarked_wrong_key"]
        require(len(correct) == len(wrong) > 0, "correct/wrong-key trials are incomplete")
        require(
            statistics.fmean(correct["statistic"]) > statistics.fmean(wrong["statistic"]),
            "wrong-key detector scores did not fall below correct-key scores",
        )
        require(
            all(correct["key_index"] == correct["draw_id"]),
            "a positive was not scored with its draw's correct fixture key",
        )
        require(
            all(wrong["key_index"] != wrong["draw_id"]),
            "a wrong-key trial accidentally used the correct fixture key",
        )
        if threshold_source == "analytic_standard_normal":
            primary = held_out[held_out["family"] == "ordinary_corresponding_key"]
            calibration_at_length = calibration[calibration["token_length"] == length]
            null_rows = pd.concat((calibration_at_length, primary), ignore_index=True)
            fit_check = entry.get("empirical_null_fit_check")
            require(isinstance(fit_check, dict), "analytic threshold has no null fit check")
            require(
                int(fit_check["trials"]) == len(calibration_scores) + len(primary),
                "analytic null fit check does not cover every corresponding-key ordinary score",
            )
            observed_rate = sum(
                float(value) > resolved.threshold
                for value in [*calibration_scores, *primary["statistic"].tolist()]
            ) / int(fit_check["trials"])
            require(
                abs(float(fit_check["rate"]) - observed_rate) < 1e-12,
                "analytic null fit-check rate does not recompute",
            )
            fit_totals = [
                *calibration_at_length["g_total"].tolist(),
                *primary["g_total"].tolist(),
            ]
            exact_expected = statistics.fmean(
                binomial_standardized_exceedance_probability(int(total), resolved.threshold)
                for total in fit_totals
            )
            require(
                abs(float(fit_check["exact_binomial_expected_rate"]) - exact_expected) < 1e-12,
                "analytic null fit-check expectation does not recompute",
            )
            if args.expected_prompts == 256:
                prompt_probabilities: list[float] = []
                observed_prompt_exceedances = 0
                for _case_id, prompt_rows in null_rows.groupby("case_id"):
                    require(
                        len(prompt_rows) == args.expected_draws,
                        "analytic null fit check has the wrong draws per prompt",
                    )
                    trial_probabilities = [
                        binomial_standardized_exceedance_probability(int(total), resolved.threshold)
                        for total in prompt_rows["g_total"]
                    ]
                    prompt_probabilities.append(
                        1.0 - math.prod(1.0 - p for p in trial_probabilities)
                    )
                    observed_prompt_exceedances += int(
                        any(float(value) > resolved.threshold for value in prompt_rows["statistic"])
                    )
                require(
                    len(prompt_probabilities) == args.expected_prompts,
                    "analytic null fit check does not cover every prompt cluster",
                )
                exact_cluster_p_value = poisson_binomial_two_sided_p_value(
                    prompt_probabilities, observed_prompt_exceedances
                )
                require(
                    exact_cluster_p_value >= 0.05,
                    "corresponding-key ordinary scores fail the analytic-null fit check",
                )
                analytic_null_fit_by_bases[str(length * 6)] = {
                    "observed_positive_prompts": observed_prompt_exceedances,
                    "prompt_clusters": len(prompt_probabilities),
                    "expected_positive_prompts": math.fsum(prompt_probabilities),
                    "two_sided_poisson_binomial_p_value": exact_cluster_p_value,
                }

    if args.require_figures:
        figure_manifest = load_json(args.output_root / "figures" / "manifest.json")
        require(len(figure_manifest["figures"]) == 10, "the ten required figures are incomplete")
        for artifact in figure_manifest["figures"].values():
            for kind in ("png", "pdf"):
                path = Path(artifact[kind])
                require(path.is_file(), f"missing figure {path}")
                require(
                    sha256_file(str(path)) == artifact[f"{kind}_sha256"],
                    f"figure checksum mismatch: {path}",
                )
    if args.require_report:
        require((args.output_root / "report.md").is_file(), "report.md is missing")

    digest_paths = [args.output_root / relative for relative in required]
    digest_paths.extend(
        args.output_root / "generation" / f"draw_{draw_id:02d}_sequences.jsonl"
        for draw_id in range(args.expected_draws)
    )
    if args.require_figures:
        digest_paths.extend((args.output_root / "figures").glob("*.png"))
        digest_paths.extend((args.output_root / "figures").glob("*.pdf"))
    if args.require_report:
        digest_paths.append(args.output_root / "report.md")
    manifest = {
        "schema_version": 1,
        "classification": "validation_artifact_not_admitted_evidence",
        "valid": True,
        "checks": {
            "prompt_count": args.expected_prompts,
            "draw_count": args.expected_draws,
            "sequence_count": len(records),
            "state_count": args.expected_states,
            "explicit_draw_identity": True,
            "distinct_replay_streams": True,
            "generated_lengths": True,
            "correct_key_positives": True,
            "wrong_key_scores_fall": True,
            "mean_detector_selected_on_calibration_only": args.expected_prompts == 256,
            "prompt_level_clustering": True,
            "calibration_evaluation_disjoint": True,
            "threshold_recomputed_from_declared_source": True,
            "analytic_null_fit_check_recomputed": True,
            "analytic_null_fit_check_passed": args.expected_prompts == 256,
            "analytic_null_fit_method": "two-sided prompt-level Poisson-binomial",
            "analytic_null_fit_by_bases": analytic_null_fit_by_bases,
        },
        "artifacts": {
            str(path.relative_to(args.output_root)): sha256_file(str(path))
            for path in sorted(set(digest_paths))
        },
        "evidence_ledger_modified": False,
    }
    output = args.output_root / "artifact_digests.json"
    serialized = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if output.exists() and output.read_text(encoding="utf-8") != serialized:
        raise FileExistsError(f"refusing to replace different digest manifest: {output}")
    if not output.exists():
        output.write_text(serialized, encoding="utf-8")
    print(json.dumps(manifest["checks"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
