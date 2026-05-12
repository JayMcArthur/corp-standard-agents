#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="${1:-$ROOT/.venv}"

python3 -m venv --system-site-packages "$VENV_PATH"
"$VENV_PATH/bin/python" -m pip install --no-build-isolation -e "$ROOT"

cat <<EOF
Local install complete.

Virtualenv: $VENV_PATH
CLI:
  $VENV_PATH/bin/team-agents --help
EOF
