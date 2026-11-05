# claude-viewer

A viewer for Claude Code session transcripts, for Robyn. It replaces Mantra, which falls short,
and other viewers, which are too basic. Proposed: there is no code yet.

Open work is in [todo.md](todo.md).

## Goals

- Colored diff output for commands that change files.
- Expand and collapse all similar commands at once.
- A CLI.

## Open design decisions

- **Stack.** Language and UI (terminal, web or both). Settles `tools/build.sh`, the
  `.gitignore` build patterns and `deploy` in `docs/workflow.json`.
- **Confirmation.** Who confirms a change works, and how. Settles `confirm` in
  `docs/workflow.json`.
