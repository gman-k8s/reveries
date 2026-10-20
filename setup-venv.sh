#!/bin/sh
# Legt .venv mit PyYAML und pytest an – nur für die Entwicklung.
# Auf Home Assistant nicht nötig: PyYAML ist im Core-Container bereits vorhanden.
set -eu
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e '.[dev]'
echo "Fertig. Tests: .venv/bin/pytest   Lint: .venv/bin/python -m reveries lint"
