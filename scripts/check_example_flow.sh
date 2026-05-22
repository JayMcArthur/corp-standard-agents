#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_ROOT="${1:-/tmp/team-agents-example-env-check}"
HOME_ROOT="$RUNTIME_ROOT/home"
WORKSPACES_ROOT="$RUNTIME_ROOT/workspaces"
VENV_ROOT="$RUNTIME_ROOT/.venv"

bash "$ROOT/scripts/bootstrap_examples.sh" "$RUNTIME_ROOT" >/dev/null

if [[ -x "$VENV_ROOT/bin/python" ]]; then
  TEAM_AGENTS_PY="$VENV_ROOT/bin/python"
else
  TEAM_AGENTS_PY="python3"
fi

HOME="$HOME_ROOT" PYTHONPATH="$ROOT/src" "$TEAM_AGENTS_PY" -m team_agents status --workspace "$WORKSPACES_ROOT/internal-app" --json >/dev/null
HOME="$HOME_ROOT" PYTHONPATH="$ROOT/src" "$TEAM_AGENTS_PY" -m team_agents sync --workspace "$WORKSPACES_ROOT/internal-app" >/dev/null
HOME="$HOME_ROOT" PYTHONPATH="$ROOT/src" "$TEAM_AGENTS_PY" -m team_agents status --workspace "$WORKSPACES_ROOT/non-git-bound" --json >/dev/null

test -f "$WORKSPACES_ROOT/internal-app/.agents/index.md"
test -f "$WORKSPACES_ROOT/internal-app/.agents/resolution.json"
grep -q -- "- Repo: \`internal-app\`" "$WORKSPACES_ROOT/internal-app/AGENTS.md"
grep -q -- "- Repo class: \`internal\`" "$WORKSPACES_ROOT/internal-app/AGENTS.md"
test "$(grep -c "<!-- team-agents:start -->" "$WORKSPACES_ROOT/internal-app/AGENTS.md")" -eq 1
test "$(grep -c "# Project Agent Guidance" "$WORKSPACES_ROOT/internal-app/AGENTS.md")" -eq 1
test "$(grep -c "<!-- team-agents:start -->" "$WORKSPACES_ROOT/internal-app/CLAUDE.md")" -eq 1

echo "example playbook ok"
