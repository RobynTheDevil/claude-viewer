#!/usr/bin/env bash
# Build one project and deploy it where it is used. Copy to build.sh and fill in.
#
#   tools/build.sh <project>
#   tools/build.sh <project> --force     deploy even while the target is in use
#
# This is the contract buildseries.sh and the issue loop depend on. Everything about the
# toolchain, the platform boundary and the deploy target lives here, and is documented in
# docs/tooling.md rather than in this comment.
#
# Two rules that are easy to get wrong:
#
#   1. Exit non-zero when the build fails, and DO NOT deploy. A pipeline whose exit status
#      comes from the last stage rather than the compiler reports success and silently
#      redeploys the previous artefact. If the build output has to be filtered, capture the
#      status first and filter afterwards.
#
#   2. Deploying over a file something else holds open is its own problem. Refuse by default,
#      say what holds it, and let --force do the replace-in-use dance (unlink and retry, or
#      rename the locked file aside). Say in the output that a restart is still required if
#      the consumer only loads at startup.

set -euo pipefail

PROJECT="${1:?usage: tools/build.sh <project> [--force]}"
FORCE=0
[[ "${2:-}" == "--force" ]] && FORCE=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SRC="$ROOT"
grep -q "^name = \"$PROJECT\"" "$SRC/pyproject.toml" || { echo "no such project: $PROJECT" >&2; exit 2; }

# 1. Build. Capture the status before any filtering.
status=0
uv run --quiet --project "$SRC" --directory "$SRC" pytest -q || status=$?
[[ $status -eq 0 ]] || { echo "build failed, not deploying" >&2; exit "$status"; }

# 2. Refuse to deploy into something in use, unless forced.
pids="$(pgrep -f "uv/tools/$PROJECT/bin/" || true)"
if [[ -n "$pids" && $FORCE -eq 0 ]]; then
    echo "$PROJECT is running (pid $(echo $pids)). Quit it, or pass --force; a running copy keeps the old code until restarted." >&2
    exit 3
fi

# 3. Deploy: the artefact, plus whatever the consumer reads alongside it (data, licences,
#    assets). Note that a deploy overwrites what the repo ships, so anything a user edits
#    belongs somewhere the deploy does not reach.
uv tool install --quiet --force --reinstall "$SRC"

echo "deployed $PROJECT"
