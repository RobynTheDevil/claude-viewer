# Repo-wide workflow

How work is branched, committed and worked, and why. The steps themselves go through the `workflow`
skill's `wf`: `new`, `commit`, `sync`, `land`, `remove`, and `claim`, `report` and `close` for
items. Do not do them with raw git.

A refusal is the answer, from `wf` or from git. Stop and report the message. Do not route
around it with `checkout --orphan`, `update-ref`, `read-tree`, `commit-tree`, `branch -f` or
`reset --hard`: those skip the check that just fired. A rebase that conflicts is a decision
to hand back.

## Branch structure

Three levels, and the level decides the base.

- `main` is the library: the shared `docs/` and `tools/`, and every project that has landed.
  Nothing is committed to it directly and no work starts on it.
- A **project branch** per project, named for the project. This is that project's pseudo-main
  and it is permanent. Routine issue work commits here.
- A **topic branch** per piece of work worth isolating, named `<project>-<topic>`. It is cut
  from its project branch and never from `main`, because the work needs the project's
  unlanded code. It is deleted once it lands.
- **Other people's branches.** Treat any branch belonging to another developer exactly as
  that: do not check one out, do not land into one, do not merge or rebase it, and do not
  report on one in a status survey. It may carry your commits, sit ahead of or behind a
  project branch, or have uncommitted work in the main checkout, and none of that is an
  agent's to reconcile.

## Enforced rules

- **Never commit directly to `main`.** Work goes on a project branch, a topic branch, or a
  branch of its own cut from `main`.
- **Always use a worktree**, made with `wf new` before the first edit. Do not edit, build or
  commit in the main checkout: other people are using it.
- **Work only committed todo items.** An item that exists only in someone's uncommitted
  working tree is not ready to be worked. Wait for the commit. From a worktree this is a
  correctness rule rather than a courtesy: the tree is pinned to a commit, so the branch's
  copy of the todo is the old one, and a report or a fix written against the uncommitted text
  is built on something the branch does not contain. Seeing the text in a diff is not the
  same as the branch having it. Nor may a topic branch edit a file someone has uncommitted
  changes in; hand over the lines to paste instead.
- **Sync before every edit.** If a commit on any branch, yours or someone else's, builds off
  your branch, fast-forward or rebase onto it before continuing.
- **Use atomic commits.** Each update that builds is a new commit. Put the relevant docs in
  the same commit as the change they describe. Tools get their own commit unless they are
  directly related to or depended on by a change. Split commits by topic or issue.
- **Run the prose pass before merging.** Every prose change gets it once, before the branch
  merges: docs, source comments, log strings, a report. Running it over a whole feature's
  writing is expensive, so it is one job at the merge rather than a tax on every commit.
  Notes:
    - **Do not batch punctuation edits with a regex.** A dash is a colon, a comma, a bracket
      or a full stop depending on the clause after it, so a single substitution leaves paired
      dashes missing one end and explanatory dashes as comma splices.
    - **Trimming is not always right, and the skill says to say so and stop.** Dense
      reference prose gives up 1.5%, against the 20-40% the skill expects. Report the
      judgement instead of cutting to hit a number.
- **Merge to `main` is fast-forward only.** No merge commits. Once one project branch lands,
  every other is behind `main` and has to rebase before it can fast-forward; `wf land` does
  that rebase.
- **Land at every green milestone**: a coherent group of issues closed, the project builds,
  the confirmation step passes. A topic branch lands into its project branch; a project
  branch lands into `main`.
- **Rebase onto `main` when work resumes on a branch**, not because `main` moved. Leave older
  branches alone until then. `main` carries the shared docs and tools, and they reach a
  project only by rebase. A project branch sitting behind `main` with nothing of its own on
  it is not a state to fix. Rebasing a project branch rewrites the commits its topic branches
  are cut from, so the project branch goes first and then each topic onto it. `wf new`
  fast-forwards a branch with nothing of its own and refuses a diverged one, since that
  rebase is a decision.

### Every commit builds

Order the series so each commit compiles on its own. It is what makes `git bisect` worth
anything. The dependencies that decide the order are the ones that cross files: a call added
in one issue and used by another, a helper made private, a diagnostic's signature. Put a new
call in the commit that introduces it, together with every caller.

`wf land` checks the series with `tools/buildseries.sh` before it lands, after its rebase,
because a rebase makes new commits on new parents and an earlier result no longer describes
them. [tooling.md](tooling.md#buildseriessh-build-every-commit-in-a-series) has the script.

### Every commit stays under the comment budget

Source is code and reasoning belongs under `docs/`. Do not use source comments as a notebook.
Move documentation to the document that owns it. What earns a source comment:

- A trap that a naive edit can easily reintroduce, in one sentence.
- A magic constant whose value was measured.
- A link to the document that holds the reasoning.

What does not: why the code is shaped this way, what was tried before, what the last test
showed, or restating a mechanism a document already describes.

### Commit messages

- **Very terse.** One line, under about ten words, no trailer.
- **Prefixed** with the project or topic (`<project>:`, `docs:`, `tools:`). Documentation
  belonging to a project uses the project's name.
- **Name the artifact and the operation**, not the reason. The message summarises the diff,
  not the story of the session. Do not reference todo processes or test results.

  ```
  "the front-facing stated item closes on its test"  ->  "rename front-facing issue report"
  "prose pass over the release and preview writing"  ->  "trim release and preview prose"
  "add the setting that settles whether X happens"   ->  "add Auto Turn setting"
  ```

  One sentence carrying two changes is two commits:

  ```
  "the place being offered decides the facing, and the drop releases the statement"
      -> "ask the candidate place for facing"
      -> "release the statement at the drop"
      -> "log a facing change"
  ```

### Worktrees

The person keeps the main checkout and an agent job goes to a worktree, not the reverse.
Whatever is gitignored and machine-specific lives in the main checkout, and `buildseries.sh`
deletes and rewrites the project directory on every iteration, which is not something to run
under an open editor.

**Make trees with `wf new`, never an agent's own worktree command.** Those pick their own
path, branch name and base, record neither the project nor the topic, and do none of the
wiring. The `workflow` skill says how to enter the tree afterwards.

A branch lands from inside its tree with `wf land`. When `main` is checked out in the main
checkout, landing on it is handed back to the person. If builds deploy to one shared
location, whoever built last owns the test; that is deliberately not enforced.

## Items

Load the global `issues` skill before working an item: it has the loop, the report naming,
diagnostics, generalising and closing. What stays in view all session:

- **Never hand-write, rename or move a report.** `root-cause-analysis` writes a defect's and
  `enhancement-report` anything else's; `wf close` closes one.
- **The claim is the status**, set with `wf claim` from the tree working the item. The todo
  line carries no marker.
- **Only the person confirms.** The claim moves to `x` on their word, never on a build
  passing. `confirm` in `docs/workflow.json` says who confirms and how.

## Splitting a working set that has already grown

When needed, split by hunk rather than by file. `git add -p` is not available to an agent,
but `git apply --cached` is.

The technique: take `git diff -U0 -- <file>`, split it at the `@@` lines, and apply the
chosen hunks to the index. `-U0` gives one hunk per contiguous change, which is fine enough
to separate issues that interleave inside a function.

**Apply one hunk per `git apply` invocation.** With `--unidiff-zero` and several hunks in one
patch, git trusts the new-side line numbers in each header, and those numbers describe the
finished file rather than the partial one being staged. The result is silent: the patch
applies, and a block of code lands ten lines from where it belongs, inside the body above it.
Recompute the diff after each application and locate the next hunk by its content.

`tools/` holds no script for this on purpose. It is a recovery from a mistake, not a
workflow.

## What does not get committed

Build output, machine-specific build configuration, fetched or decompiled reference material,
and generated corpora. All are regenerable or machine-specific and all belong in `.gitignore`
already. The person's own tracker is a symlink into `../_notes`, which is committed there by them.
