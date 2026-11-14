#!/usr/bin/env python3
"""Emit (and verify) the synthid.v5.* ledger entries from the compact v5 result files.

Every number in an entry's ``value``, ``counts`` and ``uncertainty`` is a reference (``D`` for the
derived JSON, ``F`` for a compact study summary) that is resolved by path when the entry is built;
nothing is typed in. The script

* builds the entries and renders them as YAML text;
* parses that text back and checks that every referenced number equals the number found at its
  cited path in the cited file (``--verify``), and that the cited digests are current;
* appends the block to ``evidence/measurements.yaml`` (``--append``), refusing to run twice.

Usage:
    .venv/bin/python scripts/emit_synthid_v5_ledger.py --verify --out /tmp/ledger_v5.yaml
    .venv/bin/python scripts/emit_synthid_v5_ledger.py --append
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "evidence" / "derived" / "synthid_v5"
LEDGER = ROOT / "evidence" / "measurements.yaml"
DERIVED_NAME = "synthid_v5_derived_2026_11_13.json"
PROTOCOL = "docs/research/synthid_v5_review_studies_protocol_2026_11_12.md"
EXECUTION = "docs/research/synthid_v5_review_studies_execution_2026_11_13.md"
DERIVE_COMMAND = "PYTHONPATH=src .venv/bin/python scripts/derive_synthid_v5_evidence.py"
MODELS = ("carbon", "generator")
MODEL_ID = {
    "carbon": "HuggingFaceBio/Carbon-500M",
    "generator": "GenerTeam/GENERator-v2-eukaryote-1.2b-base",
}
REVISION = {
    "carbon": "9796b752108258c1d365089f842e62e6c0547704",
    "generator": "c41b0018da9ee13b9e96ee54647de8da381ccd72",
}
POLICY = {"carbon": "C_tok", "generator": "G_tok"}
FAMILY_SUFFIX = {
    "watermarked_correct_key": "correct_key_rate",
    "ordinary_corresponding_key": "ordinary_rate",
    "watermarked_wrong_key": "wrong_key_rate",
}
FAMILY_TEXT = {
    "watermarked_correct_key": "correct-key SynthID",
    "ordinary_corresponding_key": "ordinary output under the corresponding key",
    "watermarked_wrong_key": "SynthID output checked with the other draw's key",
}
SERIES_TEXT = {
    "A": "read is the 384-base prompt followed by the first l bases of the continuation",
    "B": (
        "6,144-base read: natural left flank of 1,536 bases, marked region of l bases, natural "
        "right flank filling the rest"
    ),
    "C": (
        "l of 768 or 3,072 bases, natural left flank of 384 + o bases (o 0 to 5), natural right "
        "flank of 384 bases, read supplied forward (fw) or reverse-complemented (rc)"
    ),
    "D": "l of 768 or 3,072 bases with natural flanks of f bases on each side",
    "E": "l of 768 bases at region start s in a 6,144-base read, natural DNA elsewhere",
    "F": "contiguous crop of c bases of the reference read, start drawn by public hash",
}
DETECTORS = ("aligned_oracle", "phase_only", "verifier", "fine_grid")


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


CACHE: dict[str, Any] = {}


def document(name: str) -> Any:
    if name not in CACHE:
        CACHE[name] = load(DIR / name)
    return CACHE[name]


def resolve(doc: Any, path: str) -> Any:
    """Resolve ``a.b[3].c`` (dict keys and list indices) in a JSON document."""
    node = doc
    for part in path.split("."):
        name = part
        indices: list[int] = []
        while name.endswith("]"):
            name, _, tail = name.rpartition("[")
            indices.insert(0, int(tail[:-1]))
        if name:
            node = node[name]
        for index in indices:
            node = node[index]
    return node


@dataclass(frozen=True)
class Ref:
    """A number (or small object) read from a compact result file at a JSON path."""

    file: str
    path: str

    def value(self) -> Any:
        return resolve(document(self.file), self.path)


def D(path: str) -> Ref:  # noqa: N802
    return Ref(DERIVED_NAME, path)


def F(file: str, path: str) -> Ref:  # noqa: N802
    return Ref(file, path)


def materialize(
    node: Any, trail: tuple[str, ...], leaves: list[tuple[tuple[str, ...], Ref]]
) -> Any:
    if isinstance(node, Ref):
        leaves.append((trail, node))
        return node.value()
    if isinstance(node, dict):
        return {k: materialize(v, (*trail, str(k)), leaves) for k, v in node.items()}
    if isinstance(node, list):
        return [materialize(v, (*trail, str(i)), leaves) for i, v in enumerate(node)]
    return node


# ---------------------------------------------------------------------------------------------
# YAML rendering
# ---------------------------------------------------------------------------------------------

_BARE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-/]*$")


def key_text(key: Any) -> str:
    text = str(key)
    return text if _BARE.match(text) else json.dumps(text)


def flow(value: Any) -> str:
    return json.dumps(value)


_PLAIN = re.compile(r"^[A-Za-z0-9_./][A-Za-z0-9_./\-]*$")
_RESERVED = {"true", "false", "null", "yes", "no", "on", "off", "y", "n", "~"}


def plain_text(value: str) -> str | None:
    """Bare scalar for paths, digests, and simple words (the evidence checker needs them bare)."""
    if not _PLAIN.match(value) or value.lower() in _RESERVED:
        return None
    try:
        float(value)
    except ValueError:
        return value
    return None


def folded(text: str, indent: int) -> list[str]:
    pad = " " * indent
    lines = textwrap.wrap(" ".join(text.split()), width=100 - indent)
    return [f"{pad}{line}" for line in lines]


def render(value: dict[str, Any], indent: int) -> list[str]:
    pad = " " * indent
    out: list[str] = []
    for key, item in value.items():
        if isinstance(item, dict) and item:
            simple = all(not isinstance(v, dict | list) for v in item.values())
            if simple and len(flow(item)) <= 88:
                out.append(f"{pad}{key_text(key)}: {flow(item)}")
            else:
                out.append(f"{pad}{key_text(key)}:")
                out.extend(render(item, indent + 2))
        elif isinstance(item, list):
            if len(flow(item)) <= 88:
                out.append(f"{pad}{key_text(key)}: {flow(item)}")
            else:
                out.append(f"{pad}{key_text(key)}:")
                out.extend(f"{pad}  - {flow(element)}" for element in item)
        elif isinstance(item, dict):
            out.append(f"{pad}{key_text(key)}: {{}}")
        else:
            bare = plain_text(item) if isinstance(item, str) else None
            out.append(f"{pad}{key_text(key)}: {bare if bare is not None else flow(item)}")
    return out


class Emitter:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []
        self.lines: list[str] = []
        self.anchors: set[str] = set()

    @staticmethod
    def summary_source(name: str, command: str) -> dict[str, Any]:
        return {
            "summary_artifact": rel(DIR / name),
            "summary_sha256": sha(DIR / name),
            "protocol": PROTOCOL,
            "execution": EXECUTION,
            "command": command,
        }

    @staticmethod
    def derived_source(summaries: list[str]) -> dict[str, Any]:
        source: dict[str, Any] = {
            "artifact": rel(DIR / DERIVED_NAME),
            "sha256": sha(DIR / DERIVED_NAME),
        }
        for index, name in enumerate(summaries):
            if index == 0:
                source["summary_artifact"] = rel(DIR / name)
                source["summary_sha256"] = sha(DIR / name)
            else:
                source[f"also_summary_{index}"] = rel(DIR / name)
        source["protocol"] = PROTOCOL
        source["execution"] = EXECUTION
        source["command"] = DERIVE_COMMAND
        return source

    def add(
        self,
        *,
        id: str,
        status: str,
        value: Any,
        unit: str,
        quantity: str,
        scope: dict[str, Any],
        scope_anchor: str,
        source: dict[str, Any],
        source_anchor: str,
        json_path: str | None,
        notes: str,
        counts: dict[str, Any] | None = None,
        derivation: str | None = None,
        uncertainty: dict[str, Any] | None = None,
    ) -> None:
        if any(r["id"] == id for r in self.records):
            raise SystemExit(f"duplicate id {id}")
        leaves: list[tuple[tuple[str, ...], Ref]] = []
        value = materialize(value, ("value",), leaves)
        counts = materialize(counts, ("counts",), leaves) if counts is not None else None
        uncertainty = (
            materialize(uncertainty, ("uncertainty",), leaves) if uncertainty is not None else None
        )
        self.records.append({"id": id, "leaves": leaves, "source": source, "value": value})
        out = self.lines
        out.append(f"  - id: {id}")
        out.append(f"    status: {status}")
        if isinstance(value, dict):
            out.append("    value:")
            out.extend(render(value, 6))
        else:
            out.append(f"    value: {flow(value)}")
        out.append(f"    unit: {flow(unit)}")
        out.append("    quantity: >-")
        out.extend(folded(quantity, 6))
        if counts is not None:
            out.append("    counts:")
            out.extend(render(counts, 6))
        if derivation is not None:
            out.append("    derivation: >-")
            out.extend(folded(derivation, 6))
        if json_path is not None:
            out.append(f"    json_path: {flow(json_path)}")
        if uncertainty is not None:
            out.append("    uncertainty:")
            out.extend(render(uncertainty, 6))
        if scope_anchor in self.anchors:
            out.append(f"    scope: *{scope_anchor}")
        else:
            self.anchors.add(scope_anchor)
            out.append(f"    scope: &{scope_anchor}")
            out.extend(render(scope, 6))
        if source_anchor in self.anchors:
            out.append(f"    source: *{source_anchor}")
        else:
            self.anchors.add(source_anchor)
            out.append(f"    source: &{source_anchor}")
            out.extend(render(source, 6))
        out.append("    notes: >-")
        out.extend(folded(notes, 6))
        out.append("")


def model_scope(model: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    scope = {
        "model": MODEL_ID[model],
        "revision": REVISION[model],
        "policy_id": POLICY[model],
        "watermark": "synthid-tournament-v1",
        "detector": "synthid-position-independent-detector-v1",
        "detector_unchanged_from_admitted_runs": True,
        "window_base_lengths": [384, 768, 1536, 3072],
        "orientations": 2,
        "target_sequence_false_positive_rate": 0.01,
        "cohort": "ncbi_refseq_eukaryote_windows_fpr_v2_1608",
        "evaluated_prompts": 512,
        "draws_per_prompt": 2,
        "experiment_label": f"{model}-synthid-local-v5",
        "fixture_keys": "public reproducibility material",
        "generation_device": "Apple M5 Pro, PyTorch MPS, bfloat16",
        "second_execution_not_independent_replication": True,
    }
    if extra:
        scope.update(extra)
    return scope


def build() -> Emitter:
    em = Emitter()
    derived = document(DERIVED_NAME)

    # ---- cohort identity and generation -------------------------------------------------------
    em.add(
        id="synthid.v5.cohort.identity",
        status="V",
        value=D("identity.evaluated_prompts"),
        unit="prompts",
        quantity=(
            "locally regenerated evaluation cohort of the v5 review studies: the first 512 "
            "held-out prompts in split-rank order, two draws and two arms per prompt and model"
        ),
        counts={
            "cohort_prompts": D("identity.cohort_prompts"),
            "held_out_prompts": D("identity.held_out_prompts"),
            "evaluated_prompts": D("identity.evaluated_prompts"),
        },
        uncertainty={
            "prompts_file_sha256": D("identity.prompts_jsonl_sha256_current"),
            "prompts_file_sha256_matches_protocol_and_summaries": D(
                "identity.prompts_jsonl_matches"
            ),
            "cohort_content_sha256": D("identity.cohort_content_sha256_expected_by_protocol"),
            "protocol_sha256": D("identity.protocol_sha256_current"),
            "protocol_sha256_matches_summaries": D("identity.protocol_sha256_matches"),
            "evaluated_case_ids_sha256": D("identity.evaluated_case_ids_sha256"),
            "evaluated_ids_equal_rederived_first_512_held_out": D(
                "identity.evaluated_ids_equal_rederived_first_512_held_out"
            ),
            "prompt_bases": D("identity.prompt_bases"),
            "continuation_bases": D("identity.continuation_bases"),
        },
        scope={
            "cohort": "ncbi_refseq_eukaryote_windows_fpr_v2_1608",
            "provenance": "accession-versioned non-human RefSeq chromosomes, locally regenerated",
            "split_rule": (
                "rank sha256(frozen label, case_id); first 64 reserved, next 512 evaluated, "
                "every other prompt not evaluated"
            ),
            "split_label": "carbon_synthid_validation_v1/prompt-split/v1",
            "environment": "Apple M5 Pro (18 cores, 48 GiB), macOS, PyTorch MPS, bfloat16",
        },
        scope_anchor="v5_cohort_scope",
        source=em.derived_source([]),
        source_anchor="v5_derived_source",
        json_path="identity",
        notes=(
            "Same prompts and split rule as the detection cohort; new experiment labels give new "
            "keyed functions and sampling seeds. A second execution by the same authors with the "
            "same code in a different environment, not an independent replication. No v2 "
            "sequence is reused."
        ),
    )
    for model in MODELS:
        name = f"{model}_generation_summary.json"
        em.add(
            id=f"synthid.v5.{model}.generation.throughput",
            status="V",
            value=F(name, "generated_bp_per_second"),
            unit="generated bases per summed process-second (3 processes, one MPS device)",
            quantity=(
                "generation throughput of the local v5 cohort: 2,048 sequences of 3,072 bases "
                "(1,024 SynthID, 1,024 ordinary) over three concurrent processes"
            ),
            counts={
                "sequences": F(name, "sequence_count"),
                "watermarked_sequences": F(name, "watermarked_sequence_count"),
                "ordinary_sequences": F(name, "ordinary_sequence_count"),
                "total_generated_bases": F(name, "total_generated_bases"),
            },
            uncertainty={
                "model_generation_seconds_summed_over_sessions": F(
                    name, "model_generation_seconds"
                ),
                "known_successful_session_wall_seconds": F(
                    name, "known_successful_session_wall_seconds"
                ),
                "job_wall_generated_bp_per_second": F(name, "job_wall_generated_bp_per_second"),
                "sequences_per_second": F(name, "sequences_per_second"),
                "complete": F(name, "complete"),
                "unique_sequence_identities": F(name, "unique_sequence_identities"),
                "dispersion": "single execution; not estimated",
            },
            scope=model_scope(model, {"generation_processes": 3, "dtype": "bfloat16"}),
            scope_anchor=f"v5_{model}_scope",
            source=em.summary_source(
                name, f"bash scripts/local/run_synthid_v5_generation.sh {model}"
            ),
            source_anchor=f"v5_{model}_generation_source",
            json_path="generated_bp_per_second",
            notes=(
                "Total generated bases divided by the process-seconds summed over six sessions "
                "(three processes, two draws) sharing one accelerator. GENERator's studies ran "
                "while Carbon was generating, which affects wall time only."
            ),
        )

    # ---- S0 -------------------------------------------------------------------------------------
    for model in MODELS:
        s0_name = f"{model}_s0_position_independent_summary.json"
        s0_scope = model_scope(
            model,
            {
                "layout": "384-base prompt followed by the 3,072-base continuation (reference)",
                "detection_device": "Apple M5 Pro CPU, 12 worker processes",
            },
        )
        rows = derived["s0"][model]["rows"]
        for index, row in enumerate(rows):
            family = row["family"]
            condition = row["condition"]
            base = f"s0.{model}.rows[{index}]"
            is_control = family != "watermarked_correct_key"
            em.add(
                id=f"synthid.v5.{model}.detector.{condition}.{FAMILY_SUFFIX[family]}",
                status="V",
                value=D(f"{base}.prompt_any_draw.rate"),
                unit="fraction of prompts",
                quantity=(
                    f"position-independent prompt-level detection rate for {FAMILY_TEXT[family]} "
                    f"on a {condition.replace('_', ' ')} read, local v5 cohort"
                ),
                counts={
                    "prompt_positives": D(f"{base}.prompt_any_draw.positives"),
                    "prompt_clusters": D(f"{base}.prompt_any_draw.trials"),
                    "read_detections": D(f"{base}.reads_detected"),
                    "read_trials": D(f"{base}.reads"),
                },
                derivation=(
                    "a prompt counts as positive when either of its two draws is detected; read "
                    "counts are the underlying per-draw decisions; prompts positive on both "
                    "draws are given in uncertainty"
                ),
                uncertainty={
                    "independent_unit": "prompt",
                    "prompt_clusters": D(f"{base}.prompt_any_draw.trials"),
                    "read_rate": D(f"{base}.read_rate"),
                    "exact_two_sided_95_interval": D(
                        f"{base}.prompt_any_draw.exact_two_sided_95_interval"
                    ),
                    "exact_one_sided_95_upper": D(
                        f"{base}.prompt_any_draw.exact_one_sided_95_upper_bound"
                    ),
                    "prompt_positives_both_draws": D(f"{base}.prompt_both_draws.positives"),
                    "median_strength_neg_log10_smallest_window_p": D(
                        f"{base}.median_strength_neg_log10_smallest_window_p"
                    ),
                    "winning_window_base_length_counts": D(
                        f"{base}.winning_window_base_length_counts"
                    ),
                },
                scope=s0_scope,
                scope_anchor=f"v5_{model}_s0_scope",
                source=em.derived_source([s0_name]),
                source_anchor=f"v5_{model}_s0_source",
                json_path=base,
                notes=(
                    (
                        "Control family: the one-sided 95% upper bound is the quantity the "
                        "detection-cohort protocol predeclared; at 512 prompts zero positives give "
                        "0.58%. "
                        if is_control
                        else "Correct-key detection; the lower exact bound is the informative end. "
                    )
                    + "Upper bounds are recomputed by the derivation script as "
                    "Beta^-1(0.95; positives + 1, prompts - positives) and checked against the "
                    "stored two-sided interval."
                ),
            )
        em.add(
            id=f"synthid.v5.{model}.detector.correct_key_strength_by_condition",
            status="A",
            value={
                row["condition"]: D(
                    f"s0.{model}.rows[{i}].median_strength_neg_log10_smallest_window_p"
                )
                for i, row in enumerate(rows)
                if row["family"] == "watermarked_correct_key"
            },
            unit="median -log10 of the smallest window P-value (uncorrected for the search)",
            quantity=(
                "median correct-key window strength on the local v5 cohort, unedited and after "
                "one substitution, insertion, or deletion (1,024 reads per cell)"
            ),
            derivation=(
                "recompute each read's strength from its stored minimum local log P-value in the "
                "digest-checked S0 trials file and take the median per condition"
            ),
            uncertainty={
                "independent_unit": "prompt",
                "prompt_clusters": 512,
                "reads_per_cell": 1024,
                "confidence_interval": "not estimated for these descriptive medians",
            },
            scope=s0_scope,
            scope_anchor=f"v5_{model}_s0_scope",
            source=em.derived_source([s0_name]),
            source_anchor=f"v5_{model}_s0_source",
            json_path=f"s0.{model}.rows",
            notes=(
                "Same definition as the strength reported for the detection cohort and as the S1 "
                "strength; S1 Series A at l = 3,072 reproduces the unedited value exactly."
            ),
        )

    # ---- S1 -------------------------------------------------------------------------------------
    for model in MODELS:
        name = f"{model}_s1_layout_summary.json"
        x = derived["s1"][model]
        scope = model_scope(
            model,
            {
                "families": ["watermarked_correct_key", "ordinary_corresponding_key"],
                "flank_dna": "natural genomic sequence from the 1,608 public source spans",
                "hash_label": "synthid-review-v5",
                "cells": 54,
                "detection_device": "Apple M5 Pro CPU, 12 worker processes",
            },
        )
        common = {
            "scope": scope,
            "scope_anchor": f"v5_{model}_s1_scope",
            "source": em.derived_source([name]),
            "source_anchor": f"v5_{model}_s1_source",
        }
        base = f"s1.{model}"
        em.add(
            id=f"synthid.v5.{model}.s1.validity_checks",
            status="V",
            value={
                "check_1": D(f"{base}.check_1.status"),
                "check_2": D(f"{base}.check_2.status"),
            },
            unit="status",
            quantity=(
                "S1 pre-declared validity checks: Series A at l = 3,072 reproduces the S0 "
                "unedited decisions, and every Series C read and its reverse complement give the "
                "same smallest window P-value and window count"
            ),
            counts={
                "check_1_compared": D(f"{base}.check_1.compared"),
                "check_1_mismatches": D(f"{base}.check_1.mismatches"),
                "check_2_pairs": D(f"{base}.check_2.pairs"),
                "check_2_mismatches": D(f"{base}.check_2.mismatches"),
                "check_2_unpaired": D(f"{base}.check_2.unpaired"),
            },
            uncertainty={
                "check_1_max_abs_log_p_difference": D(f"{base}.check_1.max_abs_log_p_difference"),
                "validity_failures": D(f"{base}.validity_failures"),
                "total_decisions": D(f"{base}.total_decisions"),
            },
            json_path=base,
            notes=(
                "Protocol Section 5 checks 1 and 2 gate admission; both pass, so the study is "
                "valid and its results are admitted."
            ),
            **common,
        )
        for series in ("A", "B", "C", "D", "E", "F"):
            cells = [k for k, v in x["cells"].items() if v["series"] == series]
            em.add(
                id=f"synthid.v5.{model}.s1.series_{series.lower()}.marked_detection",
                status="A",
                value={
                    cell: {
                        "reads_detected": D(f"{base}.cells.{cell}.marked.reads_detected"),
                        "reads": D(f"{base}.cells.{cell}.marked.reads"),
                        "prompts_both_draws_detected": D(
                            f"{base}.cells.{cell}.marked.prompts_both_draws_detected"
                        ),
                        "prompts": D(f"{base}.cells.{cell}.marked.prompts"),
                        "median_strength": D(f"{base}.cells.{cell}.marked.median_strength"),
                    }
                    for cell in cells
                },
                unit="reads and prompts detected per cell; median -log10 smallest window P",
                quantity=(
                    f"S1 Series {series} marked-read detection by cell ({SERIES_TEXT[series]}); "
                    "correct key, 512 prompts, two draws"
                ),
                derivation=(
                    "per cell: marked reads detected of 1,024, prompts detected on both draws of "
                    "512, and the median strength, reshaped from the S1 summary"
                ),
                uncertainty={
                    "independent_unit": "prompt",
                    "prompts_per_cell": 512,
                    "reads_per_cell": 1024,
                    "intervals": "exact intervals per cell are in the cited summary",
                },
                json_path=f"{base}.cells",
                notes=(
                    "No pass threshold applies to marked rates; they are the result (protocol "
                    "Section 5, rule 4)."
                ),
                **common,
            )
            em.add(
                id=f"synthid.v5.{model}.s1.series_{series.lower()}.ordinary_control",
                status="A",
                value={
                    cell: {
                        "reads_positive": D(f"{base}.cells.{cell}.ordinary.reads_positive"),
                        "reads": D(f"{base}.cells.{cell}.ordinary.reads"),
                        "prompts_any_draw_positive": D(
                            f"{base}.cells.{cell}.ordinary.prompts_any_draw_positive"
                        ),
                        "prompts": D(f"{base}.cells.{cell}.ordinary.prompts"),
                        "prompt_any_draw_exact_one_sided_95_upper_bound": D(
                            f"{base}.cells.{cell}.ordinary."
                            "prompt_any_draw_exact_one_sided_95_upper_bound"
                        ),
                    }
                    for cell in cells
                },
                unit="reads and prompts positive per cell",
                quantity=(
                    f"S1 Series {series} ordinary-control detections by cell (same layout and "
                    "flanks as the marked read, ordinary continuation, corresponding key)"
                ),
                derivation=(
                    "per cell: ordinary reads positive of 1,024 and prompts with either draw "
                    "positive of 512, with the exact one-sided 95% upper bound on the prompt "
                    "rate, reshaped from the S1 summary"
                ),
                uncertainty={
                    "independent_unit": "prompt",
                    "prompts_per_cell": 512,
                    "reads_per_cell": 1024,
                    "any_draw_is_a_union_over_two_reads": True,
                },
                json_path=f"{base}.cells",
                notes=(
                    "The pre-declared rule (at or below 1% in every cell) is read per read; the "
                    "prompt-level any-draw rate is a union over two reads and can reach twice the "
                    "read rate. Both are reported as observed."
                ),
                **common,
            )
        em.add(
            id=f"synthid.v5.{model}.s1.ordinary_read_rate_maximum",
            status="A",
            value=D(f"{base}.ordinary_read_level_maximum.rate"),
            unit="fraction of reads",
            quantity=(
                "largest ordinary-control read-level positive rate over the 54 S1 cells "
                "(1,024 reads per cell)"
            ),
            derivation="maximum over cells of ordinary reads positive divided by 1,024",
            uncertainty={
                "cells_at_maximum": D(f"{base}.ordinary_read_level_maximum.cells"),
                "ordinary_cells_above_target_per_summary": D(
                    f"{base}.ordinary_cells_above_target_per_summary"
                ),
            },
            json_path=f"{base}.ordinary_read_level_maximum.rate",
            notes=(
                "Protocol Section 5 rule 3 (ordinary rate at or below 1% in every cell) holds at "
                "read level in every cell: the maximum is below 0.01."
            ),
            **common,
        )
        em.add(
            id=f"synthid.v5.{model}.s1.ordinary_any_draw_prompt_cells_above_0_01",
            status="A",
            value=len(x["ordinary_any_draw_prompt_rate_above_0_01"]),
            unit="cells (of 54)",
            quantity=(
                "S1 cells whose ordinary-control prompt-level any-draw positive rate exceeds 1% "
                "(512 prompts)"
            ),
            derivation="count cells with prompts positive on either draw divided by 512 above 0.01",
            uncertainty={
                "cells": D(f"{base}.ordinary_any_draw_prompt_rate_above_0_01"),
                "any_draw_prompt_rate_maximum": D(f"{base}.ordinary_any_draw_prompt_rate_maximum"),
                "any_draw_is_a_union_over_two_reads": True,
            },
            json_path=f"{base}.ordinary_any_draw_prompt_rate_above_0_01",
            notes=(
                "Reported as observed, not as a failure of the read-level rule: a prompt is "
                "positive if either of two reads is, so the prompt-level rate is a union. The "
                "marked rate of a cell listed here carries this caveat. A value of zero means no "
                "cell exceeds 1% at prompt level."
            ),
            **common,
        )
        em.add(
            id=f"synthid.v5.{model}.s1.marked_minimum_read_rate",
            status="A",
            value=D(f"{base}.marked_minimum_read_rate"),
            unit="fraction of reads",
            quantity="lowest marked-read detection rate over the 54 S1 cells (1,024 reads each)",
            derivation="minimum over cells of marked reads detected divided by 1,024",
            uncertainty={
                "lowest_prompts_both_draws_rate": D(
                    f"{base}.marked_minimum_prompt_both_draws_rate"
                ),
                "cells_with_a_missed_read_and_missed_counts": D(
                    f"{base}.marked_cells_with_a_missed_read"
                ),
            },
            json_path=f"{base}.marked_minimum_read_rate",
            notes=(
                "Each missed read is one read of 1,024 in its cell; no length or layout in the "
                "grid reduced detection below this rate."
            ),
            **common,
        )

    # ---- S2 -------------------------------------------------------------------------------------
    for model in MODELS:
        detect_name = f"{model}_s2_detectors_summary.json"
        timing_name = f"{model}_s2_timing_summary.json"
        base = f"s2.{model}"
        cells = list(derived["s2"][model]["cells"])
        scope = model_scope(
            model,
            {
                "evaluated_prompts": 256,
                "evaluated_prompts_note": "first 256 evaluated prompts in split-rank order",
                "families": ["watermarked_correct_key", "ordinary_corresponding_key"],
                "cells": cells,
                "detectors": list(DETECTORS),
                "comparison_baselines_do_not_replace_the_verifier": True,
                "detection_device": "Apple M5 Pro CPU",
            },
        )
        common = {
            "scope": scope,
            "scope_anchor": f"v5_{model}_s2_scope",
            "source": em.derived_source([detect_name, timing_name]),
            "source_anchor": f"v5_{model}_s2_source",
            "json_path": f"{base}.cells",
        }

        def grid(
            fields: dict[str, str], *, base: str = base, cells: list[str] = cells
        ) -> dict[str, Any]:
            return {
                cell: {
                    det: {
                        name: D(f"{base}.cells.{cell}.{det}.{path}")
                        for name, path in fields.items()
                    }
                    for det in DETECTORS
                }
                for cell in cells
            }

        em.add(
            id=f"synthid.v5.{model}.s2.marked_detection",
            status="A",
            value=grid(
                {
                    "prompts_both_draws_detected": "marked.prompts_both_draws_detected",
                    "prompts": "marked.prompts",
                    "reads_detected": "marked.reads_detected",
                    "reads": "marked.reads",
                }
            ),
            unit="prompts and reads detected",
            quantity=(
                "S2 marked-read detection by cell and detector at the shared 0.01 sequence-level "
                "target, each detector corrected for its own search (256 prompts, two draws)"
            ),
            derivation=(
                "prompt positive when both draws are detected; read counts are per draw; "
                "reshaped from the S2 summary"
            ),
            uncertainty={
                "independent_unit": "prompt",
                "prompts": 256,
                "reads": 512,
                "intervals": "exact intervals per cell and detector are in the cited summary",
                "pairs_with_nonoverlapping_prompt_level_intervals": D(
                    f"{base}.pairs_with_nonoverlapping_prompt_level_intervals"
                ),
            },
            notes=(
                "Descriptive. By the protocol, no detector is declared better from a difference "
                "whose exact 95% intervals overlap. After one insertion the oracle is told the "
                "original region, not the edit."
            ),
            **common,
        )
        em.add(
            id=f"synthid.v5.{model}.s2.ordinary_control",
            status="A",
            value=grid(
                {
                    "prompts_any_draw_positive": "ordinary.prompts_any_draw_positive",
                    "prompts": "ordinary.prompts",
                    "prompt_exact_one_sided_95_upper_bound": (
                        "ordinary.prompt_exact_one_sided_95_upper_bound"
                    ),
                    "reads_positive": "ordinary.reads_positive",
                    "reads": "ordinary.reads",
                }
            ),
            unit="prompts and reads positive",
            quantity=(
                "S2 ordinary-control positives by cell and detector at the shared 0.01 "
                "sequence-level target (256 prompts, two draws, corresponding key)"
            ),
            derivation=(
                "prompt positive when either draw is positive; exact one-sided 95% upper bound "
                "on the prompt rate recomputed and checked against the summary"
            ),
            uncertainty={
                "independent_unit": "prompt",
                "prompts": 256,
                "reads": 512,
                "read_rate_above_0_01": D(f"{base}.ordinary_read_rate_above_0_01"),
                "prompt_any_draw_rate_above_0_01": D(
                    f"{base}.ordinary_prompt_any_draw_rate_above_0_01"
                ),
            },
            notes=(
                "Rates above 1% at either level are reported as observed. The aligned oracle "
                "searches one window, so its nominal read-level rate is 1% by construction, and "
                "the prompt-level any-draw rate is a union over two reads."
            ),
            **common,
        )
        em.add(
            id=f"synthid.v5.{model}.s2.median_corrected_strength",
            status="A",
            value=grid(
                {
                    "marked": "marked.median_corrected_strength",
                    "ordinary": "ordinary.median_corrected_strength",
                }
            ),
            unit="median -log10 of the corrected sequence-level P-value before capping at 1",
            quantity=(
                "S2 median corrected strength by cell and detector, marked and ordinary reads "
                "(512 reads each)"
            ),
            derivation="reshaped from the S2 summary; negative values are corrected P above 1",
            uncertainty={"reads_per_cell_and_family": 512, "confidence_interval": "not estimated"},
            notes="Each detector's strength includes the correction for its own search.",
            **common,
        )
        em.add(
            id=f"synthid.v5.{model}.s2.windows_searched",
            status="A",
            value=grid(
                {
                    "min": "marked.windows_searched_min",
                    "max": "marked.windows_searched_max",
                }
            ),
            unit="windows (hypotheses) searched per read",
            quantity="S2 number of windows searched per read by cell and detector",
            derivation="minimum and maximum over the marked reads of each cell (S2 summary)",
            uncertainty={"reads_per_cell_and_family": 512},
            notes=(
                "The same count is the correction factor of each detector; the minimum equals "
                "the maximum in every cell."
            ),
            **common,
        )
        em.add(
            id=f"synthid.v5.{model}.s2.single_process_median_ms_per_read",
            status="A",
            value=grid(
                {
                    "marked": "marked.median_ms_per_read_single_process",
                    "ordinary": "ordinary.median_ms_per_read_single_process",
                }
            ),
            unit="milliseconds per read (median of one single-threaded detection call)",
            quantity=(
                "S2 single-process median detection time per read by cell and detector on "
                "Apple M5 Pro (32 prompts, 64 reads per cell and family)"
            ),
            derivation=(
                "median_seconds_per_read of the --timing-only run (one worker, run last) times "
                "1,000"
            ),
            uncertainty={
                "timing_prompts": D(f"{base}.timing_prompts"),
                "reads_per_cell_and_family": 64,
                "workers": 1,
                "parallel_run_medians_are_an_upper_bound": True,
                "confidence_interval": "not estimated",
            },
            notes=(
                "Wall seconds of one detection call (perf_counter) in the single-process run; "
                "the 12-worker run's medians are larger and are in the derived file. Machine "
                "idleness during the run is not independently verified."
            ),
            **common,
        )

    # ---- S3 -------------------------------------------------------------------------------------
    family_text = {
        "ordinary_model_output": "ordinary model output (draw 0 ordinary read, reference layout)",
        "marked_independent_key": (
            "SynthID output checked with 64 keys never used in generation (draw 0 marked read, "
            "reference layout)"
        ),
        "natural_dna": "natural genomic DNA that no model generated (1,608 source spans)",
    }
    targets: list[tuple[str, str | None, str, str]] = []
    for family in ("ordinary_model_output", "marked_independent_key"):
        for model in MODELS:
            targets.append(
                (family, model, f"{model}_s3_null_{family}_summary.json", f"s3.{family}.{model}")
            )
    targets.append(
        ("natural_dna", None, "shared_s3_null_natural_dna_summary.json", "s3.natural_dna")
    )
    for family, model, name, dpath in targets:
        block = resolve(derived, dpath)
        tag = f"{model}.s3.{family}" if model else f"shared.s3.{family}"
        if model:
            scope = model_scope(model, {"null_keys": 64, "null_domain": "synthid-review-v5/null"})
        else:
            scope = {
                "cohort": "ncbi_refseq_eukaryote_windows_fpr_v2_1608",
                "source": "1,608 public source spans of 3,072 canonical bases, as retrieved",
                "detector": "synthid-position-independent-detector-v1",
                "window_base_lengths": [384, 768, 1536, 3072],
                "orientations": 2,
                "null_keys": 64,
                "null_domain": "synthid-review-v5/null",
                "target_sequence_false_positive_rate": 0.01,
                "fixture_keys": "public reproducibility material",
                "detection_device": "Apple M5 Pro CPU, 12 worker processes",
            }
        scope = dict(scope)
        scope["family"] = family_text[family]
        scope["null_key_derivation"] = "SHA-256 of synthid-review-v5/null-key/<i>, i in 0..63"
        scope["windows_per_read"] = block["hypotheses_searched_counts"]
        anchor = "v5_" + tag.replace(".", "_")
        base = f"synthid.v5.{tag}"
        common = {
            "scope": scope,
            "scope_anchor": f"{anchor}_scope",
            "source": em.summary_source(
                name,
                (
                    f"bash scripts/local/run_synthid_v5_studies.sh detect {model}"
                    if model
                    else "bash scripts/local/run_synthid_v5_studies.sh final"
                ),
            ),
            "source_anchor": f"{anchor}_source",
        }
        dependence_note = (
            "Pooled read-by-key counts treat decisions as independent although decisions share "
            "reads and keys; the pooled lower bound is therefore anti-conservative as evidence "
            "against validity, and the read-level and per-key summaries are reported beside it."
        )
        em.add(
            id=f"{base}.pooled_rate",
            status="V",
            value=F(name, "rate_at_0_01"),
            unit="fraction of read-by-key decisions",
            quantity=(
                f"sequence-level positive rate at the 0.01 target for {family_text[family]}, "
                "pooled over 64 independent null keys"
            ),
            counts={
                "positives": F(name, "positives_at_0_01"),
                "decisions": F(name, "decisions"),
                "reads": F(name, "reads"),
                "keys": F(name, "keys"),
            },
            uncertainty={
                "exact_two_sided_95_interval": F(name, "exact_two_sided_95_interval_at_0_01"),
                "exact_one_sided_95_upper": F(name, "exact_one_sided_95_upper_bound_at_0_01"),
                "interval_note": "pooled decisions share reads and keys; see notes",
            },
            json_path="rate_at_0_01",
            notes=dependence_note,
            **common,
        )
        em.add(
            id=f"{base}.per_key_rate",
            status="V",
            value={
                "minimum": F(name, "per_key_rate_min"),
                "median": F(name, "per_key_rate_median"),
                "maximum": F(name, "per_key_rate_max"),
            },
            unit="fraction of reads, per key",
            quantity=(
                "distribution over 64 null keys of the positive rate at the 0.01 target for "
                f"{family_text[family]}"
            ),
            counts={
                "reads_per_key": F(name, "reads"),
                "keys": F(name, "keys"),
                "keys_with_zero_positives": D(f"{dpath}.keys_with_zero_positives"),
                "largest_positives_under_one_key": D(f"{dpath}.per_key_max_positives"),
            },
            uncertainty={"per_key_exact_intervals": "in the cited summary, per_key list"},
            json_path="per_key",
            notes="Each key tests the same reads; per-key rates are not independent samples.",
            **common,
        )
        em.add(
            id=f"{base}.reads_positive_under_any_key",
            status="V",
            value=F(name, "reads_positive_under_at_least_one_key.fraction"),
            unit="fraction of reads",
            quantity=(
                "fraction of reads positive under at least one of 64 null keys, "
                f"{family_text[family]}"
            ),
            counts={
                "reads_positive": F(name, "reads_positive_under_at_least_one_key.count"),
                "reads": F(name, "reads_positive_under_at_least_one_key.reads"),
                "keys": F(name, "keys"),
            },
            uncertainty={
                "exact_two_sided_95_interval": F(
                    name, "reads_positive_under_at_least_one_key.exact_two_sided_95_interval"
                )
            },
            json_path="reads_positive_under_at_least_one_key",
            notes=(
                "The read-level summary the protocol requires beside the pooled count. With 64 "
                "keys a read can be positive under any of them, so this is a union over keys, "
                "not a per-decision rate."
            ),
            **common,
        )
        levels = block["calibration"]
        em.add(
            id=f"{base}.calibration",
            status="V",
            value={
                f"{level['nominal_level']}": F(name, f"calibration_table[{i}].fraction")
                for i, level in enumerate(levels)
            },
            unit="fraction of decisions with sequence-level P-value at or below the nominal level",
            quantity=(
                "calibration of the sequence-level P-value at nominal levels 0.01, 0.05, 0.10, "
                f"0.25, and 0.50 for {family_text[family]}"
            ),
            counts={
                f"{level['nominal_level']}": F(name, f"calibration_table[{i}].count")
                for i, level in enumerate(levels)
            },
            uncertainty={
                "decisions": F(name, "decisions"),
                "exact_one_sided_95_lower_bound_by_level": {
                    f"{level['nominal_level']}": F(
                        name, f"calibration_table[{i}].exact_one_sided_95_lower_bound"
                    )
                    for i, level in enumerate(levels)
                },
                "exact_two_sided_95_interval_by_level": {
                    f"{level['nominal_level']}": F(
                        name, f"calibration_table[{i}].exact_two_sided_95_interval"
                    )
                    for i, level in enumerate(levels)
                },
                "any_level_exceeds_nominal": D(f"{dpath}.any_calibration_level_exceeds_nominal"),
            },
            json_path="calibration_table",
            notes=(
                dependence_note
                + " Protocol rule: the P-value is supported as valid where every observed "
                "fraction is at or below its nominal level; a fraction whose one-sided 95% lower "
                "bound exceeds its nominal level would count against validity for that family."
            ),
            **common,
        )

    # ---- S4 -------------------------------------------------------------------------------------
    analysis = "shared_s4_entropy_analysis_summary.json"
    for model in MODELS:
        x = derived["s4"]["models"][model]
        path = f"models.{model}"
        scope = model_scope(
            model,
            {
                "entropy_definition": (
                    "Shannon entropy in nats of the canonical 4,096-token next-token distribution, "
                    "temperature 1, teacher-forced on prompt + continuation, float64"
                ),
                "entropy_device": f"Apple M5 Pro, PyTorch {x['torch_version']} MPS, bfloat16",
                "positions_per_sequence": x["positions_per_sequence"],
                "sequences": x["sequences"],
                "bootstrap": "percentile 95%, 10,000 replicates over prompts, both draws together",
            },
        )
        common = {
            "scope": scope,
            "scope_anchor": f"v5_{model}_s4_scope",
            "source": em.summary_source(
                analysis, "bash scripts/local/run_synthid_v5_studies.sh final"
            ),
            "source_anchor": f"v5_{model}_s4_source",
        }
        em.add(
            id=f"synthid.v5.{model}.s4.mean_entropy",
            status="V",
            value={
                "marked_mean": F(analysis, f"{path}.mean_entropy_nats.marked.mean"),
                "ordinary_mean": F(analysis, f"{path}.mean_entropy_nats.ordinary.mean"),
            },
            unit="nats per generated position (per-sequence mean, averaged over sequences)",
            quantity=(
                "per-sequence mean Shannon entropy of the generating model over the generated "
                "positions, for SynthID and ordinary continuations of the 512 evaluated prompts"
            ),
            counts={
                "marked_sequences": F(analysis, f"{path}.mean_entropy_nats.marked.count"),
                "ordinary_sequences": F(analysis, f"{path}.mean_entropy_nats.ordinary.count"),
            },
            uncertainty={
                "marked_std": F(analysis, f"{path}.mean_entropy_nats.marked.std"),
                "ordinary_std": F(analysis, f"{path}.mean_entropy_nats.ordinary.std"),
                "marked_quantiles": F(analysis, f"{path}.mean_entropy_nats.marked.quantiles"),
                "ordinary_quantiles": F(analysis, f"{path}.mean_entropy_nats.ordinary.quantiles"),
                "ln_4096_nats": D(f"s4.models.{model}.ln_4096_nats"),
            },
            json_path=f"{path}.mean_entropy_nats",
            notes=(
                "Entropy is of the model's canonical distribution at each position, not of the "
                "watermarked sampling distribution. The sampling-path cross-check of the entropy "
                "alignment is not part of this entry."
            ),
            **common,
        )
        for key, label, target in (
            ("spearman_entropy_vs_s0_strength", "S0 unedited correct-key strength", "strength"),
            (
                "spearman_entropy_vs_mark_bit_fraction",
                "fraction of mark bits equal to 1 in the full continuation window",
                "mark_bits",
            ),
        ):
            em.add(
                id=f"synthid.v5.{model}.s4.spearman_entropy_vs_{target}",
                status="V",
                value=F(analysis, f"{path}.{key}.estimate"),
                unit="Spearman rank correlation",
                quantity=(
                    "Spearman correlation between a SynthID continuation's mean entropy and its "
                    f"{label}"
                ),
                counts={
                    "sequences": F(analysis, f"{path}.{key}.sequences"),
                    "prompts": F(analysis, f"{path}.{key}.prompts"),
                },
                uncertainty={
                    "bootstrap_95_interval": F(analysis, f"{path}.{key}.bootstrap_95_interval"),
                    "bootstrap_valid_replicates": F(
                        analysis, f"{path}.{key}.bootstrap_valid_replicates"
                    ),
                    "prior_expectation": F(analysis, f"{path}.prior_expectation"),
                },
                json_path=f"{path}.{key}",
                notes=(
                    "Descriptive association across sequences; not a causal attribution. The "
                    "result is reported whatever its sign."
                ),
                **common,
            )
    return em


def header() -> list[str]:
    return [
        "",
        "  # ---------------------------------------------------------------------------",
        "  # synthid.v5: local review studies (S0 to S4) on a locally regenerated 512-prompt",
        "  # cohort, Apple M5 Pro. Protocol:",
        "  # docs/research/synthid_v5_review_studies_protocol_2026_11_12.md",
        "  # Execution record: docs/research/synthid_v5_review_studies_execution_2026_11_13.md",
        "  # A second execution of the same watermark, control, and verifier by the same authors;",
        "  # not an independent replication. Verifier settings were not tuned.",
        "  # ---------------------------------------------------------------------------",
        "",
    ]


def yaml_text(em: Emitter) -> str:
    return "\n".join(header() + em.lines) + "\n"


def verify(em: Emitter, text: str) -> int:
    parsed_doc = yaml.safe_load("measurements:\n" + text)
    parsed = {m["id"]: m for m in parsed_doc["measurements"]}
    failures = 0
    leaf_count = 0
    if len(parsed) != len(em.records):
        print("entry count differs after parsing")
        failures += 1
    for record in em.records:
        item = parsed[record["id"]]
        if item["value"] != record["value"]:
            print(f"value changed on round trip: {record['id']}")
            failures += 1
        source = item["source"]
        for path_field, digest_field in (
            ("artifact", "sha256"),
            ("summary_artifact", "summary_sha256"),
        ):
            if path_field in source and sha(ROOT / source[path_field]) != source[digest_field]:
                print(f"digest mismatch: {record['id']} {source[path_field]}")
                failures += 1
        for trail, ref in record["leaves"]:
            node: Any = item
            for part in trail:
                node = node[int(part)] if isinstance(node, list) else node[part]
            leaf_count += 1
            if node != ref.value():
                print(f"differs from {ref.file}:{ref.path}: {record['id']} {'/'.join(trail)}")
                failures += 1
    print(
        f"verified {leaf_count} referenced numbers across {len(em.records)} entries; "
        f"failures {failures}"
    )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    em = build()
    text = yaml_text(em)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    if args.print:
        sys.stdout.write(text)
    status = 0
    if args.verify or args.append:
        status = verify(em, text)
    if args.append:
        if status:
            raise SystemExit("verification failed; not appending")
        current = LEDGER.read_text(encoding="utf-8")
        if "synthid.v5." in current:
            raise SystemExit("ledger already contains synthid.v5 entries; refusing to append twice")
        if not current.endswith("\n"):
            current += "\n"
        LEDGER.write_text(current + text, encoding="utf-8")
        print(f"appended {len(em.records)} entries to {rel(LEDGER)}")
    print(f"entries: {len(em.records)}", file=sys.stderr)
    return status


if __name__ == "__main__":
    sys.exit(main())
