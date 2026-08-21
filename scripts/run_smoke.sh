#!/usr/bin/env bash
set -euo pipefail

PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/check_evidence.py
python3 scripts/doctor.py

