#!/usr/bin/env python3
"""Quantify how conservative the full-search Bonferroni correction is (L1-06).

Windows shifted by six bases share phase and nearly all tokens, so the per-window
binomial statistics are strongly positively correlated and the correction over
M searched hypotheses is conservative. This measures that headroom two ways on
unmarked reads, which are draws from the null:

  * the realized rate at which the corrected read-level decision fires, against
    the declared 0.01 target; and
  * an effective independent-window count M_eff implied by the observed
    per-read minimum local p-value.

Under the null, if a read's search behaved like M_eff independent uniform tests
then P(p_min > x) = (1 - x)^M_eff, whose maximum-likelihood estimate is
M_eff = -n / sum(log(1 - p_min)). Local p-values are discrete binomial tail
probabilities, so M_eff is an effective count, not a literal number of tests.

This does NOT change the decision rule. The reported rule remains the
full-search Bonferroni correction; these numbers quantify headroom only.
"""

from __future__ import annotations

import argparse
import gzip
import json
from math import log
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NULL_FAMILY = "ordinary_corresponding_key"
MODELS = ("carbon", "generator")


def read_trials(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def quantile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def effective_windows(p_minima: list[float]) -> float | None:
    """MLE of M_eff from P(p_min > x) = (1 - x)^M_eff."""
    total = 0.0
    for value in p_minima:
        if value >= 1.0:
            return None
        total += log(1.0 - value)
    if total >= 0.0:
        return None
    return -len(p_minima) / total


def summarize(rows: list[dict]) -> dict:
    fires = sum(1 for row in rows if row["detected"])
    p_minima = [float(row["minimum_local_p_value"]) for row in rows]
    searched = sorted({int(row["hypotheses_searched"]) for row in rows})
    prompts_fired = {row["case_id"] for row in rows if row["detected"]}
    m_eff = effective_windows(p_minima)
    target = float(rows[0]["target_false_positive_rate"])
    rate = fires / len(rows)
    return {
        "reads": len(rows),
        "reads_fired": fires,
        "empirical_familywise_rate": rate,
        "target_false_positive_rate": target,
        "conservatism_factor_vs_target": (target / rate) if rate > 0 else None,
        "prompts_fired": len(prompts_fired),
        "hypotheses_searched": searched[0] if len(searched) == 1 else searched,
        "effective_independent_windows": m_eff,
        "correction_inflation_factor": (
            (searched[0] / m_eff) if m_eff and len(searched) == 1 else None
        ),
        "minimum_local_p_value_quantiles": {
            "p05": quantile(p_minima, 0.05),
            "median": quantile(p_minima, 0.50),
            "p95": quantile(p_minima, 0.95),
        },
        # M_eff matches the mean of log(1 - p_min); it is not claimed to describe the
        # whole distribution. These ratios show how far the Beta(1, M_eff) model is from
        # the observed quantiles, so the limitation travels with the number.
        "beta_model_observed_over_predicted": (
            {
                key: (
                    quantile(p_minima, level) / (1.0 - (1.0 - level) ** (1.0 / m_eff))
                    if m_eff
                    else None
                )
                for key, level in (("p05", 0.05), ("median", 0.50), ("p95", 0.95))
            }
            if m_eff
            else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    payload: dict = {
        "schema_version": 1,
        "study": "L1-06 empirical family-wise error of the correlated window search",
        "family": NULL_FAMILY,
        "estimator": "M_eff = -n / sum(log(1 - p_min)); P(p_min > x) = (1 - x)^M_eff",
        "decision_rule_unchanged": (
            "the reported rule remains the full-search Bonferroni correction; these numbers "
            "quantify headroom and are not a replacement threshold"
        ),
        "models": {},
    }
    for model in MODELS:
        path = ROOT / f"outputs/{model}_synthid_v2_fpr_position_independent/trials.jsonl.gz"
        rows = [row for row in read_trials(path) if row["family"] == NULL_FAMILY]
        by_condition: dict[str, list[dict]] = {}
        for row in rows:
            by_condition.setdefault(row["condition"], []).append(row)
        payload["models"][model] = {
            "pooled": summarize(rows),
            "by_condition": {k: summarize(v) for k, v in sorted(by_condition.items())},
        }

    if args.check:
        for model, block in payload["models"].items():
            pooled = block["pooled"]
            assert pooled["reads"] == 1544 * 2 * 4, f"{model} read count"
            assert pooled["empirical_familywise_rate"] < pooled["target_false_positive_rate"], (
                f"{model} fires at or above target"
            )
            assert pooled["effective_independent_windows"] is not None, f"{model} M_eff"
        print(json.dumps({"check": "ok"}))
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
