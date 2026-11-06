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

## ./src/claude_viewer, ./tests, ./pyproject.toml
    claude-viewer, the viewer for Claude Code session transcripts, a Python CLI on Textual
    and Rich. The repo holds this one project. Working. Read docs/claude-viewer/project.md
    before editing it. README.md and LICENSE at the root are for its users.

## ./ref
    External reference material. Untracked and never edited.

## ./docs/<project>
    One directory per project for the reusable documentation and issues for each.

## ./docs/<project>/issues
    One report per item, open ones here and closed ones in `done/`. Written and closed only
    through the skills; workflow.md says which.

# Project Documentation:

## claude-viewer:

### ./docs/claude-viewer/project.md
    Source guide for claude-viewer: invariants, structure, design and build. Read before
    editing it.

### ./docs/claude-viewer/todo.md
    Open work on claude-viewer: defects being tested, enhancements, features. Each item links its
    report in ./docs/claude-viewer/issues.

### ./docs/claude-viewer/done.md
    One line per closed claude-viewer item. History, not reference.

# Essential Reading:

## ./docs/workflow.md
@./docs/workflow.md

## ./docs/architecture.md
@./docs/architecture.md

## ./docs/tooling.md
@./docs/tooling.md
