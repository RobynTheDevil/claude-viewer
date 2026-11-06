#!/usr/bin/env bash
# Build every commit in a range, so a series can be landed knowing each commit compiles on
# its own. See docs/workflow.md, "Every commit builds".
#
#   tools/buildseries.sh <project> main
#   tools/buildseries.sh <project> main..HEAD
#   tools/buildseries.sh <project> HEAD~5 --keep-going
#   tools/buildseries.sh <project> main --test     any other --flag goes to the build
#
# Exits non-zero if any commit fails to build.

set -u

# The paths a build reads, and the one command that builds. See docs/tooling.md.
PROJECT_PATHS=(${PROJECT_PATHS:-src tests pyproject.toml uv.lock README.md LICENSE})
BUILD="${BUILD:-tools/build.sh}"
BUILD_TIMEOUT="${BUILD_TIMEOUT:-300}"

PROJECT=""
RANGE=""
KEEP=0
BUILD_ARGS=()

for arg in "$@"; do
    case "$arg" in
        --keep-going) KEEP=1 ;;
        -h|--help)
            sed -n '2,11p' "$0" | sed 's/^# \?//'
            exit 0 ;;
        --*) BUILD_ARGS+=("$arg") ;;
        *)
            if   [ -z "$PROJECT" ]; then PROJECT="$arg"
            elif [ -z "$RANGE" ];   then RANGE="$arg"
            else echo "unexpected argument: $arg" >&2; exit 2
            fi ;;
    esac
done

if [ -z "$PROJECT" ] || [ -z "$RANGE" ]; then
    echo "usage: tools/buildseries.sh <project> <base|range> [--keep-going] [--<build flag>...]" >&2
    exit 2
fi

cd "$(git rev-parse --show-toplevel)" || exit 2

[ -f pyproject.toml ] || { echo "no pyproject.toml at the repo root" >&2; exit 2; }

# The loop wipes and rewrites the project paths, so uncommitted work there would be lost.
if ! git diff --quiet -- "${PROJECT_PATHS[@]}" || ! git diff --cached --quiet -- "${PROJECT_PATHS[@]}"; then
    echo "refusing to run: ${PROJECT_PATHS[*]} has uncommitted changes." >&2
    echo "commit or stash them first; this script deletes and rewrites those paths." >&2
    exit 1
fi

case "$RANGE" in
    *..*) COMMITS=$(git rev-list --reverse "$RANGE") ;;
    *)    COMMITS=$(git rev-list --reverse "$RANGE..HEAD") ;;
esac

[ -n "$COMMITS" ] || { echo "no commits in range $RANGE"; exit 0; }
echo "==> $(echo "$COMMITS" | wc -l) commits, building $PROJECT at each"

clear_tracked() {
    # Not optional: git checkout <commit> -- <path> writes the files that exist at that commit
    # into the tree and the index, and leaves behind any file the previous iteration created.
    # A stale file then builds into a commit missing it, or is picked up by the next git add.
    git ls-files -z -- "${PROJECT_PATHS[@]}" | xargs -0 -r rm -f --
    git rm -rq --cached --ignore-unmatch -- "${PROJECT_PATHS[@]}"
    find src tests -mindepth 1 -type d -empty -delete 2>/dev/null
}

checkout_paths() {
    local present
    mapfile -t present < <(git ls-tree --name-only "$1" -- "${PROJECT_PATHS[@]}")
    git checkout -q "$1" -- "${present[@]}"
}

restore() {
    # Leave the tree and the deployed artefact matching HEAD, whatever happened above. The
    # loop deploys each commit, so without this the target is left holding whichever commit
    # was built last.
    clear_tracked
    checkout_paths HEAD
    echo "==> restoring HEAD's build"
    timeout "$BUILD_TIMEOUT" "$BUILD" "$PROJECT" --force >/dev/null 2>&1 \
        && echo "    deployed HEAD" \
        || echo "    WARNING: HEAD did not rebuild; run $BUILD $PROJECT yourself" >&2
}
trap restore EXIT

FAILED=0
for c in $COMMITS; do
    subject=$(git log -1 --format='%h %s' "$c")
    if ! git cat-file -e "$c:pyproject.toml" 2>/dev/null; then
        echo "skip $subject (no root pyproject.toml yet)"
        continue
    fi
    clear_tracked
    checkout_paths "$c"

    if timeout "$BUILD_TIMEOUT" "$BUILD" "$PROJECT" "${BUILD_ARGS[@]}" >/dev/null 2>&1; then
        echo "ok   $subject"
    else
        echo "FAIL $subject"
        FAILED=$((FAILED + 1))
        [ "$KEEP" -eq 1 ] || { echo "==> stopping at the first failure; --keep-going builds the rest"; break; }
    fi
done

if [ "$FAILED" -gt 0 ]; then
    echo "==> $FAILED commit(s) failed to build"
    exit 1
fi
echo "==> every commit builds"
