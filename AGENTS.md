<!-- SEED:
    Delete this block once filled in.

    You are the first agent in a freshly-templated environment for a new project.

    Your job is to initialize the workspace project according to the given template and user
    instruction. README.md at the repo root holds the seeding procedure, and
    tools/template-seed.sh does the mechanical half of it and then removes itself. Both are
    for that one run: a repo that still has either has not finished seeding.

    This file, AGENTS.md, is the root instruction file for future agents, read
    in full at the start of every session. It is an index, not a manual: it
    says what each path is for and which document owns each subject. Replace
    every <placeholder>. Delete any section the repo does not have rather than
    leaving it empty.

    Both agent runtimes read a file like this. Keep AGENTS.md as the real file and make
    .claude/CLAUDE.md a copy or a link to it, so the two cannot drift.

    The @-includes at the bottom are loaded in full. Keep that list short: four documents is
    a session's worth of context and a fifth is usually a sign one of them should be trimmed
    or split.

-->

This file should contain references to generated documentation and reusable information.

# Writing Rules:

Prose belongs in `docs/`, and each fact lives in exactly one place.
Documentation is a reference, not a session log. Present tense, what is true
now. Tracking "this was attempted N times", "the last build", etc. is not relevant information.

# Top Level Paths:

## ./
    The workspace root. All work is done in here. Do not use ../

## ./_p.md
    The person's project tracker. A gitignored symlink into ../_notes, a repo of its own, so
    this repo holds no copy of it. Do not edit, and do not run anything in the main checkout
    that could rewrite it.

## ./docs
    Analysis and findings. Tracked. The top level is shared across all projects; each
    project's own documentation is in ./docs/<project>.

## ./tools
    Scripts for searching, checking and building. Tracked, shared across all projects.
    docs/tooling.md documents them and is loaded in full below.

## ./<projects>
    One subfolder per project. Tracked, except build output (<generated paths>) which is
    generated or machine-specific.

## ./<projects>/<project>
    <One or two lines: what it does, its state, and the source guide to read before
    editing it.>

## ./ref
    External reference material. Untracked and never edited.

## ./docs/<project>
    One directory per project for the reusable documentation and issues for each.

## ./docs/<project>/issues
    One report per item, open ones here and closed ones in `done/`. Written and closed only
    through the skills; workflow.md says which.

# Libraries and Protocol Documentation:

<One entry per external system, library or protocol the repo depends on. Each names the
document and summarises it in two or three lines, so a session knows whether to open it.>

## ./docs/<library>.md
    <What it covers.>

# Project Documentation:

<One group per project, under `./docs/<project>/`: `project.md`, `todo.md` and `done.md` for
the source guide, the open list and the closed list. Then any generated documents, with a
note that they are generated and rebuilt on request only.>

## <Project>:

### ./docs/<project>/project.md
    Source guide for <project>. <What it covers.> Read before editing that project.

### ./docs/<project>/todo.md
    Open work on <project>: defects being tested, enhancements, features. Each item links its
    report in ./docs/<project>/issues.

### ./docs/<project>/done.md
    One line per closed <project> item. History, not reference.

# Other Documentation:

<Anything that belongs to no single project: publishing, feasibility notes, cross-project
findings.>

# Essential Reading:

## ./docs/workflow.md
@./docs/workflow.md

## ./docs/architecture.md
@./docs/architecture.md

## ./docs/tooling.md
@./docs/tooling.md
