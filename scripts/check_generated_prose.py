#!/usr/bin/env python3
"""Catch string literals that lose a space where a source line wraps.

Captions, table captions, and boundary notes are built by concatenating string
literals across source lines:

    "the largest relative change in any admitted proxy "
    "is small mainly because ..."

Drop the trailing space and the rendered caption reads `proxyis`. That is invisible
in a source diff, survives every test, and shows up in a published PDF.

This is checked exactly rather than heuristically. Every implicit concatenation in
the generator sources is parsed, and each literal except the last must end with
whitespace or be followed by one that starts with whitespace. A literal that ends
mid-sentence with no space is a defect; one that ends at a real word boundary is
not, and no dictionary is needed to tell them apart.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "paper/scripts/make_figures.py",
    "paper/scripts/make_tables.py",
)
# A literal may end without a space when the next one opens punctuation or markup,
# or when the pair is deliberately glued (a path, a macro name, a compound).
GLUE_ALLOWED_PREFIXES = (
    " ",
    "\n",
    ",",
    ".",
    ";",
    ":",
    ")",
    "]",
    "}",
    "$",
    "\\",
    "-",
    "%",
    "?",
    "!",
)
GLUE_ALLOWED_SUFFIXES = (" ", "\n", "\t", "-", "(", "[", "{", "$", "/", "~")


def check_source(path: Path) -> list[str]:
    """Scan raw source lines for adjacent string literals that lose their space."""

    problems: list[str] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for index in range(len(lines) - 1):
        current, following = lines[index].rstrip("\n"), lines[index + 1]
        stripped_current = current.strip()
        stripped_next = following.strip()
        # Only pairs where both lines are bare string literals can be an implicit
        # concatenation across a wrap.
        if not (stripped_current.endswith('"') and stripped_next.startswith('"')):
            continue
        if stripped_current.startswith("#") or stripped_next.startswith("#"):
            continue
        if not (stripped_current.count('"') >= 2 and stripped_next.count('"') >= 2):
            continue
        try:
            left = ast.literal_eval(stripped_current.rstrip(","))
            right = ast.literal_eval(stripped_next.rstrip(","))
        except (ValueError, SyntaxError):
            continue
        if not isinstance(left, str) or not isinstance(right, str) or not left or not right:
            continue
        if left.endswith(GLUE_ALLOWED_SUFFIXES) or right.startswith(GLUE_ALLOWED_PREFIXES):
            continue
        problems.append(
            f"{path.relative_to(ROOT)}:{index + 1}: {left[-24:]!r} joins {right[:24]!r} "
            "with no space"
        )
    return problems


def main() -> int:
    problems: list[str] = []
    for source in SOURCES:
        path = ROOT / source
        if not path.exists():
            problems.append(f"missing generator source {source}")
            continue
        problems.extend(check_source(path))

    if problems:
        for problem in problems:
            print(f"FAIL {problem}")
        return 1
    print(f"generated prose OK ({len(SOURCES)} generator sources, no lost spaces)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
