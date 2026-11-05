# claude-viewer

A viewer for Claude Code session transcripts, for Robyn. It replaces Mantra, which falls short,
and other viewers, which are too basic. Proposed: there is no code yet.

Open work is in [todo.md](todo.md).

## Goals

- Colored diff output for commands that change files.
- Expand and collapse all similar commands at once.
## Design

A simple terminal CLI. Its output matches the detailed transcript view Claude Code shows
for a session opened with `/resume`, so a session reads the way it did in Claude Code. The
goals above go on top of that view.

## Open design decisions

- **Stack.** The language for the CLI. Settles `tools/build.sh`, the `.gitignore` build
  patterns and `deploy` in `docs/workflow.json`.
- **Confirmation.** Who confirms a change works, and how. Settles `confirm` in
  `docs/workflow.json`.
