#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXAMPLES_ROOT="$ROOT/examples"
RUNTIME_ROOT="${1:-/tmp/team-agents-example-env}"
HOME_ROOT="$RUNTIME_ROOT/home"
WORKSPACES_ROOT="$RUNTIME_ROOT/workspaces"
CORP_RUNTIME="$RUNTIME_ROOT/corp-control"
EXTERNAL_RUNTIME="$RUNTIME_ROOT/external-source"
VENV_ROOT="$RUNTIME_ROOT/.venv"

mkdir -p "$RUNTIME_ROOT" "$HOME_ROOT" "$WORKSPACES_ROOT"
rm -rf "$CORP_RUNTIME" "$EXTERNAL_RUNTIME" "$VENV_ROOT" "$WORKSPACES_ROOT"
mkdir -p "$WORKSPACES_ROOT"
cp -R "$EXAMPLES_ROOT/corp-control" "$CORP_RUNTIME"
cp -R "$EXAMPLES_ROOT/external-source" "$EXTERNAL_RUNTIME"

git -C "$EXTERNAL_RUNTIME" init >/dev/null
git -C "$EXTERNAL_RUNTIME" config user.email "example@example.com"
git -C "$EXTERNAL_RUNTIME" config user.name "Example User"
git -C "$EXTERNAL_RUNTIME" config commit.gpgsign false
git -C "$EXTERNAL_RUNTIME" add .
git -C "$EXTERNAL_RUNTIME" -c core.hooksPath=/dev/null commit --no-verify -m "example external source" >/dev/null
EXTERNAL_COMMIT="$(git -C "$EXTERNAL_RUNTIME" rev-parse HEAD)"
EXTERNAL_URL="$EXTERNAL_RUNTIME"

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

mkdir -p "$WORKSPACES_ROOT/internal-app" "$WORKSPACES_ROOT/client-private" "$WORKSPACES_ROOT/client-tracked" "$WORKSPACES_ROOT/unknown-repo" "$WORKSPACES_ROOT/non-git-bound"

init_repo() {
  local repo_path="$1"
  local remote_url="$2"
  local tracked_agents="${3:-}"
  git -C "$repo_path" init >/dev/null
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

init_repo "$WORKSPACES_ROOT/internal-app" "git@git.example.test:demo/internal-app.git"
init_repo "$WORKSPACES_ROOT/client-private" "https://git.example.test/demo/client-private.git"
init_repo "$WORKSPACES_ROOT/client-tracked" "https://git.example.test/demo/client-tracked.git" "Tracked client agents"
init_repo "$WORKSPACES_ROOT/unknown-repo" "https://git.example.test/demo/unknown.git"

cat >> "$CORP_RUNTIME/users/alice/config.toml" <<EOF

[[workspace_binding]]
name = "example-non-git"
path = "$WORKSPACES_ROOT/non-git-bound"
repo_group_id = "platform"
EOF

python3 -m venv "$VENV_ROOT"
HOME="$HOME_ROOT" PYTHONPATH="$ROOT/src" "$VENV_ROOT/bin/python" -m team_agents setup \
  --corp-repo "$CORP_RUNTIME" \
  --user "alice" \
  --cache-root "$HOME_ROOT/.team-agents/cache"

cat <<EOF
Bootstrap complete.

Runtime root: $RUNTIME_ROOT
Machine config: $HOME_ROOT/.team-agents/config.toml
Virtualenv: $VENV_ROOT

Example commands:
  HOME="$HOME_ROOT" PYTHONPATH="$ROOT/src" "$VENV_ROOT/bin/python" -m team_agents status --workspace "$WORKSPACES_ROOT/internal-app" --json
  HOME="$HOME_ROOT" PYTHONPATH="$ROOT/src" "$VENV_ROOT/bin/python" -m team_agents sync --workspace "$WORKSPACES_ROOT/internal-app"
  HOME="$HOME_ROOT" PYTHONPATH="$ROOT/src" "$VENV_ROOT/bin/python" -m team_agents status --workspace "$WORKSPACES_ROOT/non-git-bound" --json
EOF
