#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_ROOT="${1:-/tmp/team-agents-example-env-check}"
HOME_ROOT="$RUNTIME_ROOT/home"
WORKSPACES_ROOT="$RUNTIME_ROOT/workspaces"
VENV_ROOT="$RUNTIME_ROOT/.venv"

bash "$ROOT/scripts/bootstrap_examples.sh" "$RUNTIME_ROOT" >/dev/null

HOME="$HOME_ROOT" PYTHONPATH="$ROOT/src" "$VENV_ROOT/bin/python" -m team_agents status --workspace "$WORKSPACES_ROOT/internal-app" --json >/dev/null
HOME="$HOME_ROOT" PYTHONPATH="$ROOT/src" "$VENV_ROOT/bin/python" -m team_agents sync --workspace "$WORKSPACES_ROOT/internal-app" >/dev/null
HOME="$HOME_ROOT" PYTHONPATH="$ROOT/src" "$VENV_ROOT/bin/python" -m team_agents status --workspace "$WORKSPACES_ROOT/non-git-bound" --json >/dev/null

test -f "$WORKSPACES_ROOT/internal-app/.agents/index.md"
test -f "$WORKSPACES_ROOT/internal-app/.agents/resolution.json"

echo "example flow ok"
