#!/usr/bin/env bash
set -euo pipefail

TEAM_AGENTS_ROOT="${TEAM_AGENTS_ROOT:-$HOME/.team-agents}"
TEAM_AGENTS_BIN_DIR="${TEAM_AGENTS_BIN_DIR:-$HOME/.local/bin}"
TEAM_AGENTS_WRAPPER="$TEAM_AGENTS_BIN_DIR/team-agents"

rm -f "$TEAM_AGENTS_WRAPPER"
rm -rf "$TEAM_AGENTS_ROOT/venv"

cat <<EOF
Uninstall complete.

Removed:
  $TEAM_AGENTS_WRAPPER
  $TEAM_AGENTS_ROOT/venv

Preserved:
  $TEAM_AGENTS_ROOT/config.toml
  $TEAM_AGENTS_ROOT/cache
  $TEAM_AGENTS_ROOT/library

To wipe all local state too, remove:
  $TEAM_AGENTS_ROOT
EOF
