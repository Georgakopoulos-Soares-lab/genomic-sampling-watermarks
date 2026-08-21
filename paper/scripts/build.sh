#!/usr/bin/env bash
set -euo pipefail

paper_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="$paper_root/manuscript/source"
build_dir="$paper_root/manuscript/build"
mkdir -p "$build_dir"

if command -v tectonic >/dev/null 2>&1; then
  (cd "$source_dir" && tectonic main.tex --outdir "$build_dir")
elif command -v latexmk >/dev/null 2>&1; then
  (cd "$source_dir" && latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir="$build_dir" main.tex)
else
  echo "No TeX engine found. Install tectonic or latexmk." >&2
  exit 1
fi

echo "$build_dir/main.pdf"

