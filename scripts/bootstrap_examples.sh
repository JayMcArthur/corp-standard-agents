#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXAMPLES_ROOT="$ROOT/examples"
RUNTIME_ROOT="${1:-/tmp/team-agents-example-env}"
HOME_ROOT="$RUNTIME_ROOT/home"
WORKSPACES_ROOT="$RUNTIME_ROOT/workspaces"
CORP_RUNTIME="$RUNTIME_ROOT/corp-control"
USER_RUNTIME="$RUNTIME_ROOT/user-layer"
EXTERNAL_RUNTIME="$RUNTIME_ROOT/external-source"
VENV_ROOT="$RUNTIME_ROOT/.venv"

mkdir -p "$RUNTIME_ROOT" "$HOME_ROOT" "$WORKSPACES_ROOT"
rm -rf "$CORP_RUNTIME" "$USER_RUNTIME" "$EXTERNAL_RUNTIME" "$VENV_ROOT" "$WORKSPACES_ROOT"
mkdir -p "$WORKSPACES_ROOT"
cp -R "$EXAMPLES_ROOT/corp-control" "$CORP_RUNTIME"
cp -R "$EXAMPLES_ROOT/user-layer" "$USER_RUNTIME"
cp -R "$EXAMPLES_ROOT/external-source" "$EXTERNAL_RUNTIME"

git -C "$EXTERNAL_RUNTIME" init -b main >/dev/null
git -C "$EXTERNAL_RUNTIME" config user.email "example@example.com"
git -C "$EXTERNAL_RUNTIME" config user.name "Example User"
git -C "$EXTERNAL_RUNTIME" config commit.gpgsign false
git -C "$EXTERNAL_RUNTIME" add .
git -C "$EXTERNAL_RUNTIME" -c core.hooksPath=/dev/null commit --no-verify -m "example external source" >/dev/null
EXTERNAL_COMMIT="$(git -C "$EXTERNAL_RUNTIME" rev-parse HEAD)"
EXTERNAL_URL="$EXTERNAL_RUNTIME"
INTERNAL_APP_REMOTE="git@github.com:acme/internal-app.git"
CLIENT_PRIVATE_REMOTE="https://github.com/acme/client-private.git"
CLIENT_TRACKED_REMOTE="https://github.com/acme/client-tracked.git"

python3 - "$CORP_RUNTIME/org/sources/shared-ext.toml" "$EXTERNAL_URL" "$EXTERNAL_COMMIT" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
url = sys.argv[2]
commit = sys.argv[3]
text = path.read_text(encoding="utf-8")
text = text.replace("__EXTERNAL_SOURCE_URL__", url)
text = text.replace("__EXTERNAL_SOURCE_COMMIT__", commit)
path.write_text(text, encoding="utf-8")
PY

PYTHONPATH="$ROOT/src" python3 - "$CORP_RUNTIME" <<'PY'
from pathlib import Path
import sys

from team_agents.git_tools import normalize_remote

corp = Path(sys.argv[1])
replacements = {
    "__INTERNAL_APP_REMOTE__": normalize_remote("git@github.com:acme/internal-app.git"),
    "__CLIENT_PRIVATE_REMOTE__": normalize_remote("https://github.com/acme/client-private.git"),
    "__CLIENT_TRACKED_REMOTE__": normalize_remote("https://github.com/acme/client-tracked.git"),
}
for path in [
    corp / "repos" / "internal-app" / "config.toml",
    corp / "repos" / "client-private" / "config.toml",
    corp / "repos" / "client-tracked" / "config.toml",
]:
    text = path.read_text(encoding="utf-8")
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    path.write_text(text, encoding="utf-8")
PY

mkdir -p "$WORKSPACES_ROOT/internal-app" "$WORKSPACES_ROOT/client-private" "$WORKSPACES_ROOT/client-tracked" "$WORKSPACES_ROOT/unknown-repo" "$WORKSPACES_ROOT/non-git-bound"

init_repo() {
  local repo_path="$1"
  local remote_url="$2"
  local tracked_agents="${3:-}"
  git -C "$repo_path" init -b main >/dev/null
  git -C "$repo_path" config user.email "example@example.com"
  git -C "$repo_path" config user.name "Example User"
  git -C "$repo_path" config commit.gpgsign false
  printf "# %s\n" "$(basename "$repo_path")" > "$repo_path/README.md"
  if [[ -n "$tracked_agents" ]]; then
    printf "%s\n" "$tracked_agents" > "$repo_path/AGENTS.md"
  fi
  git -C "$repo_path" add .
  git -C "$repo_path" -c core.hooksPath=/dev/null commit --no-verify -m "init" >/dev/null
  git -C "$repo_path" remote add origin "$remote_url"
}

init_repo "$WORKSPACES_ROOT/internal-app" "$INTERNAL_APP_REMOTE"
init_repo "$WORKSPACES_ROOT/client-private" "$CLIENT_PRIVATE_REMOTE"
init_repo "$WORKSPACES_ROOT/client-tracked" "$CLIENT_TRACKED_REMOTE" "Tracked client agents"
init_repo "$WORKSPACES_ROOT/unknown-repo" "https://github.com/acme/unknown.git"

cat >> "$USER_RUNTIME/config.toml" <<EOF

[[workspace_binding]]
name = "example-non-git"
path = "$WORKSPACES_ROOT/non-git-bound"
repo_group_id = "platform"
EOF

if python3 -m venv "$VENV_ROOT" >/dev/null 2>&1; then
  TEAM_AGENTS_PY="$VENV_ROOT/bin/python"
  VENV_STATUS="$VENV_ROOT"
else
  TEAM_AGENTS_PY="python3"
  VENV_STATUS="not created; using system python with PYTHONPATH"
fi

HOME="$HOME_ROOT" PYTHONPATH="$ROOT/src" "$TEAM_AGENTS_PY" -m team_agents setup \
  --corp-repo "$CORP_RUNTIME" \
  --user-path "$USER_RUNTIME" \
  --cache-root "$HOME_ROOT/.team-agents/cache"

cat <<EOF
Bootstrap complete.

Runtime root: $RUNTIME_ROOT
Machine config: $HOME_ROOT/.team-agents/config.toml
Virtualenv: $VENV_STATUS

Example commands:
  HOME="$HOME_ROOT" PYTHONPATH="$ROOT/src" "$TEAM_AGENTS_PY" -m team_agents status --workspace "$WORKSPACES_ROOT/internal-app" --json
  HOME="$HOME_ROOT" PYTHONPATH="$ROOT/src" "$TEAM_AGENTS_PY" -m team_agents sync --workspace "$WORKSPACES_ROOT/internal-app"
  HOME="$HOME_ROOT" PYTHONPATH="$ROOT/src" "$TEAM_AGENTS_PY" -m team_agents status --workspace "$WORKSPACES_ROOT/non-git-bound" --json
EOF
