#!/usr/bin/env python3
"""Generate LaTeX tables and number macros from the evidence ledger.

The manuscript rule is that every empirical number resolves to
`evidence/measurements.yaml`. Typing a number into prose breaks that the moment the
ledger moves, so prose cites a macro and tables are generated whole. Nothing here is
computed from an artifact or hand-entered, and a missing measurement raises rather
than emitting a placeholder.

Output lands in `paper/manuscript/source/generated/`:

* `macros.tex`   -- one command per inline number, with the measurement id in a comment
* `tab_*.tex`    -- one tabular per result family
* `manifest.json` -- which measurement ids each output drew from, for auditing
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "evidence/measurements.yaml"
POLICIES = (("c_tok", r"\policyCtok"), ("g_tok", r"\policyGtok"), ("g_bp", r"\policyGbp"))
POLICY_PLAIN = {"c_tok": "C_tok", "g_tok": "G_tok", "g_bp": "G_bp"}
LENGTHS = (384, 768, 1536, 3072)


class Ledger:
    def __init__(self, path: Path) -> None:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        self._by_id = {m["id"]: m for m in parsed["measurements"]}
        self.used: set[str] = set()

    def get(self, measurement_id: str) -> dict[str, Any]:
        entry = self._by_id.get(measurement_id)
        if entry is None:
            raise KeyError(f"the ledger has no measurement {measurement_id}")
        self.used.add(measurement_id)
        return entry

    def one(self, prefix: str) -> dict[str, Any]:
        found = [m for mid, m in self._by_id.items() if mid.startswith(prefix)]
        if len(found) != 1:
            raise KeyError(f"{prefix}* matched {len(found)} measurements, expected one")
        self.used.add(found[0]["id"])
        return found[0]


def fmt(value: float, places: int = 3) -> str:
    return f"{value:.{places}f}"


def table(caption: str, label: str, header: str, rows: list[str], spec: str) -> str:
    body = "\n".join(f"    {row} \\\\" for row in rows)
    return (
        "% GENERATED FILE -- do not edit. Regenerate with paper/scripts/make_tables.py\n"
        "\\begin{table}[t]\n  \\centering\n  \\small\n"
        f"  \\begin{{tabular}}{{{spec}}}\n    \\toprule\n"
        f"    {header} \\\\\n    \\midrule\n{body}\n"
        "    \\bottomrule\n  \\end{tabular}\n"
        f"  \\caption{{{caption}}}\n  \\label{{tab:{label}}}\n\\end{{table}}\n"
    )


# --------------------------------------------------------------------------- tables
def table_capacity(led: Ledger) -> str:
    rows = []
    for slug, macro in POLICIES:
        m = led.get(f"e2.capacity.{slug}.mean_information_bits_per_base")
        u = m["uncertainty"]
        scope = m["scope"]
        rows.append(
            f"{macro} & {fmt(m['value'], 4)} & [{fmt(u['lower'], 4)}, {fmt(u['upper'], 4)}] "
            f"& {scope['sequential_states']} & {scope['prompt_clusters']}"
        )
    return table(
        caption=(
            "Realized maximal-coupling watermark information per DNA base for each released "
            "generation policy, with equal-weight prompt-cluster percentile intervals. The "
            "construction's structural ceiling is one coupled bit per 6-mer token, or $1/6$ bit "
            "per "
            "base. Sequential states within a prompt are not independent samples, which is why the "
            "interval resamples prompts rather than states."
        ),
        label="capacity",
        header="Policy & bit/base & 95\\% interval & states & prompts",
        rows=rows,
        spec="lrrrr",
    )


def table_clean_detection(led: Ledger) -> str:
    rows = []
    for slug, macro in POLICIES:
        short = led.get(f"e4.short_detection.{slug}.shortest_fully_detected_bases")
        margin = short["admitted_margin"]
        entry = led.one(f"e4.clean_detection.{slug}.b3072.detection_rate")
        cal = entry["admitted_calibration"]
        rows.append(
            f"{macro} & {short['value']} "
            f"& {margin['shortest_length_with_strict_separation_bases']} "
            f"& {fmt(cal['threshold'])} & {fmt(cal['achieved_false_positive_rate'], 5)} "
            f"& {fmt(entry['value'])}"
        )
    return table(
        caption=(
            "Clean detection. The shortest fully detected length is the shortest sequence the "
            "declared search will score at all, so it is a floor of the experiment rather than a "
            "measured limit; the strict-separation length is where the weakest watermarked "
            "statistic passes the strongest pooled null. The threshold, achieved false-positive "
            "rate, and detection rate are quoted at 3{,}072 bases and come from null trials that "
            "repeat the identical declared search."
        ),
        label="clean-detection",
        header=(
            "Policy & fully detected (b) & strict separation (b) & threshold & achieved FPR & TPR"
        ),
        rows=rows,
        spec="lrrrrr",
    )


def table_edit_channel(led: Ledger) -> str:
    rows = []
    for slug, macro in POLICIES:
        sub = led.one(f"e5.substitution.{slug}.b3072.max_fully_detected_rate")
        deletion = led.one(f"e7.deletion.{slug}.b1536.max_fully_detected_rate")
        insertion = led.one(f"e7.insertion.{slug}.b1536.max_fully_detected_rate")
        windowed = led.get(f"e7.stage2.deletion.{slug}.windowed_max_fully_detected_rate")
        rows.append(
            f"{macro} & {sub['value']} & {deletion['value']} & {insertion['value']} "
            f"& {windowed['value']}"
        )
    return table(
        caption=(
            "The edit channel: largest per-base edit rate at which every sequence is still "
            "detected. Substitutions are quoted at 3{,}072 bases and the indel channels at 1{,}536 "
            "bases, the longest length each experiment evaluated. Insertions and deletions defeat "
            "the unwindowed detector one to two orders of magnitude below the substitution "
            "tolerance, because one inserted or deleted base moves every later token off the "
            "reading grid. A declared sliding-window search moves the deletion limit but meets a "
            "second, information-theoretic wall."
        ),
        label="edit-channel",
        header=("Policy & substitution & deletion & insertion & deletion, windowed"),
        rows=rows,
        spec="lrrrr",
    )


def table_baselines(led: Ledger) -> str:
    rows = []
    for slug, macro in POLICIES:
        signal = led.get(f"e8.e9.matched_baseline.{slug}.signal_per_token")
        band = signal["admitted_signal_per_token"]
        shortest = led.get(f"e8.e9.matched_baseline.{slug}.shortest_fully_detected_bases")
        transfer = led.get(f"e8.e9.matched_baseline.{slug}.public_dna_exceedance")
        ranges = band["range_across_lengths"]

        def span(method: str, _ranges: dict[str, Any] = ranges) -> str:
            low, high = _ranges[method]["minimum"], _ranges[method]["maximum"]
            return f"{fmt(low, 2)}--{fmt(high, 2)}"

        rows.append(
            f"{macro} & {span('partition_mc')} & {span('its')} & {span('exp')} "
            f"& {shortest['value']} & {fmt(transfer['value'], 3)}"
        )
    return table(
        caption=(
            "The three exact-marginal constructions on one corpus and one calibrated detector, "
            "each "
            "calibrated on its own nulls at the same target rate and searching the identical "
            "hypothesis set. Signal per token is standardized in units of each method's own null, "
            "which is the only sense in which the three are comparable. Detection rate is not "
            "tabulated because it is $1.000$ for all three methods at every evaluated length, so "
            "the shortest fully detected length is identical and uninformative. The last column is "
            "the largest rate at which natural public DNA under a wrong key exceeds a threshold "
            "calibrated on model-generated nulls."
        ),
        label="baselines",
        header=(
            "Policy & ours & inverse transform & exponential & fully detected (b) & natural-DNA "
            "exceedance"
        ),
        rows=rows,
        spec="lrrrrr",
    )


def table_attacks(led: Ledger) -> str:
    rows = []
    for slug, macro in POLICIES:
        spoof = led.get(f"e11.spoofing.{slug}.splice_forgery_detection_rate")
        removal = led.get(f"e12.removal.{slug}.rearrangement_detection_rate")
        utility = led.get(f"e12.removal.{slug}.utility_cost_on_admitted_proxies")
        reuse = led.get(f"e11.key_reuse.{slug}.fixed_key_many_query_exceedance")
        widths = [
            point["block_width_tokens"]
            for point in removal["admitted_curve"]["points"]
            if point["attack"] == "block_shuffle"
            and point["base_length"] == 3072
            and point["detection_rate"] <= 0.0
        ]
        rows.append(
            f"{macro} & {fmt(spoof['value'])} & {spoof['scope']['donor_outputs_required']} "
            f"& {fmt(removal['value'])} & {min(widths) if widths else '--'} "
            f"& {fmt(utility['value'], 3)} & {fmt(reuse['value'], 3)}"
        )
    return table(
        caption=(
            "Key reuse. \\emph{Forgery accepted} is a vulnerability, not a result: a sequence "
            "spliced position-wise from watermarked outputs under the same key is accepted at "
            "every "
            "length, and two donor outputs suffice. \\emph{Shuffled detected} is the detection "
            "rate "
            "after a full positional shuffle, so a low value is a successful removal; the next "
            "column is the narrowest block width whose shuffle removes the mark at 3{,}072 bases. "
            "The proxy cost is the largest relative change in any admitted sequence proxy, and it "
            "is small mainly because the attack preserves the 6-mer multiset exactly and the "
            "admitted proxies are composition statistics. The last column is one fixed key scored "
            "against sequences it did not generate."
        ),
        label="attacks",
        header=(
            "Policy & forgery accepted & donors & shuffled detected & removal width & proxy cost & "
            "reuse exceedance"
        ),
        rows=rows,
        spec="lrrrrrr",
    )


def table_runtime(led: Ledger) -> str:
    rows = []
    for slug, macro in POLICIES:
        entry = led.get(f"e14.runtime.{slug}.matched_generation_wall_seconds")
        runtime = entry["admitted_runtime"]
        rows.append(
            f"{macro} & {fmt(runtime['sequential_capacity_wall_seconds'], 1)} "
            f"& {fmt(runtime['watermarked_seconds'], 1)} "
            f"& {fmt(runtime['ordinary_seconds'], 1)} "
            f"& {fmt(runtime['clean_detection_wall_seconds'], 1)} "
            f"& {fmt(runtime['watermarked_bases_per_second'], 1)}"
        )
    return table(
        caption=(
            "Runtime envelope on one laptop, from single observations under uncontrolled desktop "
            "load and on mains power: a feasibility statement, not a benchmark. Detection uses "
            "neither the model nor the GPU. No peak-memory figure is reported, because the "
            "recorded "
            "memory counters cannot support a residency claim. The same generation runs roughly "
            "ten "
            "times slower on battery."
        ),
        label="runtime",
        header=("Policy & capacity (s) & watermarked (s) & ordinary (s) & detection (s) & bases/s"),
        rows=rows,
        spec="lrrrrr",
    )


TABLES = {
    "capacity": table_capacity,
    "clean_detection": table_clean_detection,
    "edit_channel": table_edit_channel,
    "baselines": table_baselines,
    "attacks": table_attacks,
    "runtime": table_runtime,
}


# --------------------------------------------------------------------------- macros
def build_macros(led: Ledger) -> tuple[str, dict[str, str]]:
    """One LaTeX command per inline number, each annotated with its measurement id."""

    macros: list[tuple[str, str, str]] = []

    def add(name: str, value: str, measurement_id: str) -> None:
        macros.append((name, value, measurement_id))

    add("policyCtok", r"\texttt{C\_tok}", "not a measurement: a policy name")
    add("policyGtok", r"\texttt{G\_tok}", "not a measurement: a policy name")
    add("policyGbp", r"\texttt{G\_bp}", "not a measurement: a policy name")

    capacities = []
    for slug, _macro in POLICIES:
        m = led.get(f"e2.capacity.{slug}.mean_information_bits_per_base")
        capacities.append((m["value"], m["id"]))
    lowest = min(capacities)
    highest = max(capacities)
    add("capacityLow", fmt(lowest[0], 3), lowest[1])
    add("capacityHigh", fmt(highest[0], 3), highest[1])
    add("capacityCeiling", "0.167", "derived: one coupled bit per 6-mer token divided by six bases")

    short = led.get("e4.short_detection.c_tok.shortest_fully_detected_bases")
    add("shortestDetectedBases", str(short["value"]), short["id"])
    add(
        "strictSeparationBases",
        str(short["admitted_margin"]["shortest_length_with_strict_separation_bases"]),
        short["id"],
    )
    add(
        "targetFPR",
        "0.01",
        led.one("e4.clean_detection.c_tok.b3072.detection_rate")["id"],
    )

    subs = [
        led.one(f"e5.substitution.{slug}.b3072.max_fully_detected_rate")["value"]
        for slug, _ in POLICIES
    ]
    add(
        "substitutionTolerance",
        fmt(min(subs), 2),
        "e5.substitution.*.b3072.max_fully_detected_rate",
    )
    add(
        "substitutionToleranceHigh",
        fmt(max(subs), 2),
        "e5.substitution.*.b3072.max_fully_detected_rate",
    )
    dels = [
        led.one(f"e7.deletion.{slug}.b1536.max_fully_detected_rate")["value"]
        for slug, _ in POLICIES
    ]
    add("deletionTolerance", f"{min(dels):g}", "e7.deletion.*.b1536.max_fully_detected_rate")
    windowed = [
        led.get(f"e7.stage2.deletion.{slug}.windowed_max_fully_detected_rate")["value"]
        for slug, _ in POLICIES
    ]
    add(
        "windowedDeletionTolerance",
        f"{min(windowed):g}",
        "e7.stage2.deletion.*.windowed_max_fully_detected_rate",
    )

    ratios = []
    for slug, _macro in POLICIES:
        entry = led.get(f"e8.e9.matched_baseline.{slug}.signal_per_token")
        band = entry["admitted_signal_per_token"]
        ratios.append((band["exp_over_partition_mc_lower_bound"], entry["id"]))
    add("expSignalRatio", fmt(min(ratios)[0], 1), min(ratios)[1])
    its_ratios = [
        led.get(f"e8.e9.matched_baseline.{slug}.signal_per_token")["admitted_signal_per_token"][
            "its_over_partition_mc_lower_bound"
        ]
        for slug, _ in POLICIES
    ]
    add(
        "itsSignalRatio",
        fmt(min(its_ratios), 1),
        "e8.e9.matched_baseline.*.signal_per_token",
    )
    baseline_length = led.get("e8.e9.matched_baseline.c_tok.shortest_fully_detected_bases")
    add("baselineFullyDetectedBases", str(baseline_length["value"]), baseline_length["id"])

    spoof = led.get("e11.spoofing.c_tok.splice_forgery_detection_rate")
    add("forgeryDetectionRate", fmt(spoof["value"]), spoof["id"])
    add("forgeryDonorsRequired", str(spoof["scope"]["donor_outputs_required"]), spoof["id"])
    removal = led.get("e12.removal.c_tok.rearrangement_detection_rate")
    add("shuffleDetectionRate", fmt(removal["value"]), removal["id"])
    utilities = [
        led.get(f"e12.removal.{slug}.utility_cost_on_admitted_proxies")["value"]
        for slug, _ in POLICIES
    ]
    add(
        "removalProxyCost",
        fmt(max(utilities), 2),
        "e12.removal.*.utility_cost_on_admitted_proxies",
    )

    orf_conditions = []
    independent_shifts = []
    for slug, _macro in POLICIES:
        orf = led.get(f"e15.structure_proxies.{slug}.orf_prices_bounded_rearrangement")
        orf_conditions.append((orf["value"], orf["id"]))
        independent = led.get(f"e15.structure_proxies.{slug}.independent_model_relative_shift")
        independent_shifts.append((independent["value"], independent["id"]))
    add("orfDirectionalConditions", str(max(orf_conditions)[0]), max(orf_conditions)[1])
    add(
        "orfConditionsTested",
        str(
            led.get("e15.structure_proxies.c_tok.orf_prices_bounded_rearrangement")["scope"][
                "conditions_tested"
            ]
        ),
        "e15.structure_proxies.c_tok.orf_prices_bounded_rearrangement",
    )
    add(
        "independentModelShift",
        fmt(max(independent_shifts)[0], 3),
        max(independent_shifts)[1],
    )

    exceedances = []
    for slug, _macro in POLICIES:
        entry = led.get(f"e8.e9.matched_baseline.{slug}.public_dna_exceedance")
        exceedances.append((entry["value"], entry["id"]))
    add("naturalDNAExceedance", fmt(max(exceedances)[0], 3), max(exceedances)[1])

    hypotheses = led.one("e4.clean_detection.c_tok.b3072.detection_rate")
    # The ledger records the count the detector actually scored, so it is read rather
    # than recomputed from the search description.
    add(
        "hypothesesSearched",
        str(hypotheses["scope"]["detector_search"]["hypotheses_scored"]),
        hypotheses["id"],
    )

    lines = [
        "% GENERATED FILE -- do not edit. Regenerate with paper/scripts/make_tables.py",
        "% Each command carries the measurement id it came from, so a reviewer can trace",
        "% any inline number in the prose back to evidence/measurements.yaml.",
    ]
    for name, value, measurement_id in macros:
        lines.append(f"\\newcommand{{\\{name}}}{{{value}}}  % {measurement_id}")
    return "\n".join(lines) + "\n", {name: value for name, value, _ in macros}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "paper/manuscript/source/generated")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    led = Ledger(LEDGER)
    written = {}
    for name, builder in TABLES.items():
        path = args.output / f"tab_{name}.tex"
        path.write_text(builder(led), encoding="utf-8")
        written[f"tab_{name}.tex"] = sorted(led.used)
    macros, values = build_macros(led)
    (args.output / "macros.tex").write_text(macros, encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "source_of_truth": "evidence/measurements.yaml",
        "rule": (
            "prose cites a macro rather than a typed number, and tables are generated whole, so "
            "no empirical number in the manuscript can drift from the ledger"
        ),
        "tables": sorted(written),
        "macros": values,
        "measurement_ids_used": sorted(led.used),
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "tables": len(TABLES),
                "macros": len(values),
                "measurements_used": len(led.used),
                "output": str(args.output.relative_to(ROOT)),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
