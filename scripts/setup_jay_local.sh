#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORP_ROOT="${1:-$HOME/.team-agents-corp}"
USER_ROOT="${2:-$HOME/.team-agents-user}"
CACHE_ROOT="${3:-$HOME/.team-agents/cache}"
SOURCE_SKILLS_ROOT="${4:-$HOME/.agents/skills}"
VENV_PATH="${5:-$ROOT/.venv}"

bash "$ROOT/scripts/install_local.sh" "$VENV_PATH" >/dev/null

"$VENV_PATH/bin/team-agents" setup \
  --corp-repo "$CORP_ROOT" \
  --user-overrides "$USER_ROOT" \
  --cache-root "$CACHE_ROOT" \
  --init-corp-if-missing \
  --init-user-if-missing \
  --import-codex-skills-from "$SOURCE_SKILLS_ROOT"

cat <<EOF
Jay local setup complete.

Corp root: $CORP_ROOT
User overrides: $USER_ROOT
Cache root: $CACHE_ROOT
Imported source skills: $SOURCE_SKILLS_ROOT
Virtualenv: $VENV_PATH

Next commands:
  $VENV_PATH/bin/team-agents status --workspace "$ROOT" --json
  $VENV_PATH/bin/team-agents doctor --workspace "$ROOT"
EOF
