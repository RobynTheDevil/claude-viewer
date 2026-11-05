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

## Stack

Python, with Textual for the interactive view and Rich for rendering. Packaged with `uv` and
installed with `uv tool install`.

- Rich renders the transcript markers (`⏺`, `⎿`), syntax-highlighted code and colored
  unified diffs. Edit results in the transcript carry `structuredPatch`, so diffs come from
  data and are not recomputed.
- Textual gives collapsible blocks and key bindings, which expand/collapse all similar
  commands needs. A plain `--print` mode writes the same output through Rich alone, for
  pipes and `less -R`.
- Python 3.14 and `uv` are installed here. Go and Rust are not.
- Search across sessions shells out to `rg` and parses only the matching lines. Python
  filtering and parsing every transcript on this machine (177 files, largest 37 MB) takes
  0.8 s, measured. Rust is the move only if search over a full history gets past about 1 s.
- A session view renders lazily, one visible block at a time. Rendering a 37 MB session
  eagerly is slow in any language.

## Open design decisions

- **Build and deploy.** What `tools/build.sh` runs, the `.gitignore` build patterns and
  `deploy` in `docs/workflow.json`. Settled by the first code.
- **Confirmation.** Who confirms a change works, and how. Settles `confirm` in
  `docs/workflow.json`.
