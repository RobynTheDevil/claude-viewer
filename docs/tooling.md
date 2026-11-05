# Tools

Scripts in `tools/`, shared across every project. Run from the repo root. This document is
loaded in full at the start of a session, so it says what each tool is for and what it
refuses, not how it is implemented.

`buildseries.sh` is in the template because `wf land` runs it. Worktrees come from the
`workflow` skill, and only why this repo's are wired as they are lives here. The rest are
whatever this repo needs, and each earns a section here. The one exception is
`template-seed.sh`, which turns the template into a repo and deletes itself at the end of its
only run, so it is documented in the template's own README and never exists in a seeded repo.

## The build contract

`buildseries.sh` and the issue loop both need one command that builds and deploys a single
project:

```sh
tools/build.sh <project> [--force]
```

- Exit non-zero on a failed build, and **do not deploy** when the build failed. This is the
  failure that hides: a pipeline whose exit status comes from the last stage rather than the
  compiler quietly redeploys the previous artefact and reports success.
- `--force` deploys over a locked or running target, for iterating when a restart is coming
  anyway.
- Print enough that a caller can tell success from failure without parsing prose.

Everything about toolchains, cross-platform paths and deploy locations lives in that script
and in this document's repo-specific sections, not in `buildseries.sh` or the `workflow` skill.

## Worktrees: what a tree needs to build

A fresh tree cannot compile: everything the build needs is gitignored, so the new tree has
none of it. The `worktree` section of `docs/workflow.json` says what `wf new` links, copies
and runs; this section says why, for anything that is not obvious:

Nothing. `uv run` in `tools/build.sh` makes the tree's own `src/<project>/.venv` from
`uv.lock` on the first build, so the `worktree` section links and copies nothing.

Copying rather than linking is sometimes forced: a build that runs under a different
subsystem or platform layer cannot follow the host's symlinks.

## `buildseries.sh`: build every commit in a series

```sh
tools/buildseries.sh <project> main              # build each commit in main..HEAD
tools/buildseries.sh <project> main..HEAD        # the same, stated as a range
tools/buildseries.sh <project> HEAD~5 --keep-going
tools/buildseries.sh <project> main --test       # --test passed on to build.sh
```

Checks that every commit in a range compiles on its own, which is what makes `git bisect`
worth anything and what `workflow.md` requires before a branch lands. It checks out the
project directory at each commit, builds it with `tools/build.sh`, prints `ok` or `FAIL`
against the commit's subject, and exits non-zero if any failed. A commit from before the
project directory existed prints `skip` and is not built. It stops at the first failure
unless `--keep-going` is passed. Any other `--` flag is passed on to `tools/build.sh` at each
commit, for whatever flags this repo's build defines; the rebuild of HEAD on the way out
takes only `--force`.

Clearing every tracked file under the project directory from the tree and the index before
each checkout is why this is a script rather than a one-liner. `git checkout <commit> --
<path>` writes the files that exist at that commit into both and leaves behind any file the
previous iteration created, so a commit missing a source file builds against a later commit's
copy and reports a false pass. A leftover data file is worse: the next `git add` commits it
back, which is how a deleted file once reached `main`. The reverse mistake once made all
fourteen commits of a series report a false failure.

Two guards. It refuses to run while the project directory has uncommitted changes, since it
deletes and rewrites that directory. And it rebuilds and redeploys HEAD on the way out, on a
failure and on a Ctrl-C as well as on success, because each iteration deploys and would
otherwise leave an old artefact there for the next test.

`wf land` runs it after its rebase and before the fast-forward, as the `series` setting.

## Adding tools

Anything reusable across projects goes in `tools/` and gets a section here. Anything specific
to one project belongs in that project's folder.

Query scripts are read-only against fetched or generated reference material. Keep it that
way: no tool writes into the reference tree. The one exception a repo is allowed is a tool
that promotes values out of live user data, and it says so in its own section.

**Generated documents are for human use and on request.** A tool that draws a call graph,
extracts an API surface or tabulates patch sites is run when someone asks, not as part of
routine work, and its output says in the owning document that it is generated.
