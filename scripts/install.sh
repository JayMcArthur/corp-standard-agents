#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="${TEAM_AGENTS_VENV_PATH:-$HOME/.team-agents/venv}"
BIN_DIR="${TEAM_AGENTS_BIN_DIR:-$HOME/.local/bin}"
CACHE_ROOT="${TEAM_AGENTS_CACHE_ROOT:-$HOME/.team-agents/cache}"
WRAPPER_PATH="$BIN_DIR/team-agents"

mkdir -p "$CACHE_ROOT" "$BIN_DIR"

python3 -m venv --system-site-packages "$VENV_PATH"
"$VENV_PATH/bin/python" -m pip install --no-build-isolation -e "$ROOT"

cat >"$WRAPPER_PATH" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "$VENV_PATH/bin/team-agents" "\$@"
EOF
chmod +x "$WRAPPER_PATH"

cat <<EOF
Install complete.

Virtualenv: $VENV_PATH
Wrapper: $WRAPPER_PATH

Next step:
  team-agents setup --corp-repo /path/to/corp-control --user <username>
EOF
