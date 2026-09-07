#!/usr/bin/env python3
"""Render the GENERATOR SynthID validation report from immutable summaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def fmt(value: float | int | None, digits: int = 5) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int):
        return str(value)
    return f"{float(value):.{digits}g}"


def interval(paired: dict[str, Any]) -> str:
    return f"[{fmt(paired['interval_lower'])}, {fmt(paired['interval_upper'])}]"


def detector_separation(entry: dict[str, Any], detector: str) -> str:
    return fmt(entry[detector]["separation_in_ordinary_standard_deviations"])


def main() -> int:
    args = parse_args()
    generation = load_json(args.output_root / "generation" / "generation_summary.json")
    distribution = load_json(args.output_root / "distribution" / "distribution_summary.json")
    sequence = load_json(
        args.output_root / "sequence_comparison" / "sequence_comparison_summary.json"
    )
    detection = load_json(args.output_root / "detection" / "detection_summary.json")
    detector_comparison_path = args.output_root / "detection" / "detector_comparison.json"
    detector_comparison = (
        load_json(detector_comparison_path) if detector_comparison_path.is_file() else None
    )
    if detector_comparison is None and not args.smoke:
        raise FileNotFoundError(detector_comparison_path)
    nll = sequence["main_key_averaged"]["mean_negative_log_likelihood_per_token"]
    tv = distribution["paired_watermarked_minus_ordinary_error"]["total_variation_distance"]
    lines = [
        "# GENERator-v2 1.2B `G_tok` SynthID tournament validation"
        + (" — smoke QA" if args.smoke else ""),
        "",
        (
            "> This is the prescribed 4-prompt smoke validation of schemas, independence, "
            "clustering, and key alignment. It is not the 256-prompt scientific result."
            if args.smoke
            else (
                "> Validation report. Only values with explicit entries in "
                "`evidence/measurements.yaml` are admitted manuscript evidence."
            )
        ),
        "",
        "| Question | Metric | Watermarked | Ordinary/null | Difference | 95% CI | p-value |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        (
            "| One-step law | TV distance | n/a | n/a | "
            f"{fmt(tv['mean_difference'])} | {interval(tv)} | {fmt(tv['p_value'])} |"
        ),
        (
            "| Full sequence | Mean NLL/token | "
            f"{fmt(nll['watermarked']['mean'])} | {fmt(nll['ordinary']['mean'])} | "
            f"{fmt(nll['paired']['mean_difference'])} | {interval(nll['paired'])} | "
            f"{fmt(nll['paired']['p_value'])} |"
        ),
    ]
    for entry in detection["lengths"]:
        primary = entry["null_families"]["ordinary_corresponding_key"]
        paired = entry["separation"]["paired_score_watermarked_minus_ordinary"]
        lines.append(
            "| Clean detection | "
            f"TPR/FPR at {entry['base_length']} bp | {fmt(entry['positive']['rate'])} | "
            f"{fmt(primary['rate'])} | score Δ {fmt(paired['mean_difference'])} | "
            f"{interval(paired)} | {fmt(paired['p_value'])} |"
        )
    wm_family = distribution["watermarked_p_values"]
    broken = distribution["negative_control"]
    gof_resolution = 1.0 / (int(distribution["monte_carlo_replicates"]) + 1)
    gof_bonferroni_cutoff = float(wm_family["alpha"]) / int(distribution["state_count"])
    gof_resolution_note = (
        f"The Monte Carlo p-value floor {fmt(gof_resolution)} is too coarse for the "
        f"{distribution['state_count']}-state Bonferroni cutoff "
        f"{fmt(gof_bonferroni_cutoff)}, so zero Bonferroni rejections is not interpreted as "
        "evidence. "
        if gof_resolution > gof_bonferroni_cutoff
        else (
            f"The Monte Carlo p-value floor {fmt(gof_resolution)} resolves the "
            f"{distribution['state_count']}-state Bonferroni cutoff "
            f"{fmt(gof_bonferroni_cutoff)}. "
        )
    )
    key_average_replicates = int(distribution["tournament"]["key_average_replicates_per_state"])
    significant_proxies = [
        metric
        for metric, result in sequence["main_key_averaged"].items()
        if metric
        not in {
            "mean_negative_log_likelihood_per_token",
            "perplexity",
        }
        and float(result["paired"]["benjamini_hochberg_p_value"]) < 0.05
    ]
    state_rows = [
        json.loads(line)
        for line in (args.output_root / "distribution" / "state_manifest.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    weakest = sorted(
        state_rows,
        key=lambda row: float(row["key_averaged_total_variation_distance"]),
        reverse=True,
    )[:5]
    lowest = ", ".join(
        f"`{row['case_id']}` ({fmt(row['key_averaged_total_variation_distance'])} TV; "
        f"top-1 {fmt(row['top1_mass'])})"
        for row in weakest
    )
    lines.extend(
        [
            "",
            "## Explicit answers",
            "",
            f"1. **Unique prompts:** {generation['case_count']}.",
            (
                "2. **Generated sequences:** "
                f"{generation['watermarked_sequence_count']} watermarked and "
                f"{generation['ordinary_sequence_count']} ordinary."
            ),
            (
                "3. **Generated material:** "
                f"{generation['total_generated_bases']:,} bases and "
                f"{generation['total_generated_tokens']:,} generated 6-mer positions."
            ),
            (
                "4. **One-step reproduction:** "
                f"{int(wm_family['rejections_at_alpha'])} of {distribution['state_count']} "
                "watermarked arms reject their exact fixed-key tournament law at nominal "
                f"alpha {fmt(wm_family['alpha'])}, versus "
                f"{fmt(wm_family['expected_rejections_under_null'])} expected under the null. "
                + gof_resolution_note
                + "Fixed-key tournament laws are intentionally reweighted relative to G_tok; "
                f"{key_average_replicates}-key marginal errors are recorded separately."
            ),
            (
                "5. **Errors versus ordinary sampling:** mean paired TV difference "
                f"{fmt(tv['mean_difference'])}, 95% CI {interval(tv)}, p = {fmt(tv['p_value'])}."
            ),
            (
                "6. **GENERATOR NLL/perplexity:** mean NLL/token difference "
                f"{fmt(nll['paired']['mean_difference'])}, 95% CI {interval(nll['paired'])}, "
                f"BH-adjusted p = {fmt(nll['paired']['benjamini_hochberg_p_value'])}."
            ),
            (
                "7. **Sequence proxies after correction:** "
                + (
                    ", ".join(f"`{name}`" for name in significant_proxies)
                    if significant_proxies
                    else "none"
                )
                + "."
            ),
            "8. **Held-out TPR:** "
            + "; ".join(
                f"{entry['base_length']} bp: {fmt(entry['positive']['rate'])}"
                for entry in detection["lengths"]
            )
            + ".",
            "9. **Held-out primary FPR:** "
            + "; ".join(
                f"{entry['base_length']} bp: "
                f"{fmt(entry['null_families']['ordinary_corresponding_key']['rate'])}"
                for entry in detection["lengths"]
            )
            + ".",
            "10. **Analytic-null fit check:** "
            + "; ".join(
                f"{entry['base_length']} bp: "
                f"{fmt(entry['empirical_null_fit_check']['rate'])} over "
                f"{entry['empirical_null_fit_check']['trials']} trials "
                f"(exact-binomial expectation "
                f"{fmt(entry['empirical_null_fit_check']['exact_binomial_expected_rate'])})"
                for entry in detection["lengths"]
            )
            + ".",
            (
                "11. **Detector choice:** not evaluated in the four-prompt smoke."
                if detector_comparison is None
                else "11. **Detector choice:** calibration-only mean/weighted-mean separation was "
                + "; ".join(
                    f"{entry['base_length']} bp: "
                    f"{detector_separation(entry, 'mean')}/"
                    f"{detector_separation(entry, 'upstream_default_weighted_mean')} "
                    "ordinary-arm SD"
                    for entry in detector_comparison["lengths"]
                )
                + "; the mean detector was selected."
            ),
            "12. **Confidence intervals:** prompt-cluster 95% intervals are recorded for every "
            "TPR, null-family FPR, sequence metric, and paired score difference in the JSON "
            "summaries.",
            "13. **Matched detector-score significance:** "
            + "; ".join(
                f"{entry['base_length']} bp: Δ="
                f"{fmt(entry['separation']['paired_score_watermarked_minus_ordinary']['mean_difference'])}, "  # noqa: E501
                f"p={fmt(entry['separation']['paired_score_watermarked_minus_ordinary']['p_value'])}"
                for entry in detection["lengths"]
            )
            + ".",
            f"14. **Largest finite-key marginal errors:** {lowest}.",
            (
                "15. **Negative or unexpected results:** the deliberately broken sampler that "
                "skips the tournament was run on "
                f"{broken['state_count']} frozen states and produced "
                f"{int(broken['p_values']['rejections_at_alpha']) if broken['p_values'] else 0} "
                "nominal rejections. Ordinary size-control rejections and all unfavorable "
                "watermarked states remain in the artifacts."
            ),
            "",
            "## Claim separation",
            "",
            "- Experiment A checks ordinary samples against `G_tok`, tournament samples against "
            "their exact fixed-key reweighted law, and finite-key averaging separately.",
            "- Experiment B concerns matched full-continuation NLL and sequence-proxy shifts, "
            "clustered by prompt.",
            "- Experiment C uses the analytic standard-normal mean-g threshold. All prompts "
            "contribute corresponding-key ordinary scores to its empirical fit check; detection "
            "and null-family rates use only the disjoint evaluation prompts.",
            "",
            "These results must not be collapsed into the claim that the watermark ‘does not "
            "change GENERATOR.’ Fixture keys are public reproducibility material, and proxy "
            "similarity is not biological function, "
            "viability, or safety.",
            "",
            "## Artifact digests",
            "",
        ]
    )
    artifact_entries: list[tuple[str, str]] = []
    if detector_comparison is not None:
        artifact_entries.append(
            (
                str(detector_comparison_path),
                hashlib.sha256(detector_comparison_path.read_bytes()).hexdigest(),
            )
        )
    for summary in (generation, distribution, sequence, detection):
        for path, digest in summary.get("artifact_sha256", {}).items():
            artifact_entries.append((path, digest))
        artifacts = summary.get("artifacts", {})
        if isinstance(artifacts, dict):
            for value in artifacts.values():
                if isinstance(value, dict) and value.get("path") and value.get("sha256"):
                    artifact_entries.append((str(value["path"]), str(value["sha256"])))
        elif isinstance(artifacts, list):
            for value in artifacts:
                for prefix in ("sequences", "report"):
                    if value.get(f"{prefix}_path") and value.get(f"{prefix}_sha256"):
                        artifact_entries.append(
                            (
                                str(value[f"{prefix}_path"]),
                                str(value[f"{prefix}_sha256"]),
                            )
                        )
    for path, digest in sorted(set(artifact_entries)):
        lines.append(f"- `{path}` — `{digest}`")
    report_path = args.output_root / "report.md"
    payload = "\n".join(lines) + "\n"
    if report_path.exists() and report_path.read_text(encoding="utf-8") != payload:
        raise FileExistsError(f"refusing to replace different report: {report_path}")
    if not report_path.exists():
        report_path.write_text(payload, encoding="utf-8")
    print(json.dumps({"report": str(report_path), "lines": len(lines)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
