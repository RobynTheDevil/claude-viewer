# claude-viewer

A viewer for Claude Code session transcripts, for Robyn. It replaces Mantra, which falls short,
and other viewers, which are too basic. Working: the first version is built and installed
with `tools/build.sh claude-viewer`.

Open work is in [todo.md](todo.md).

## Goals

- Colored diff output for commands that change files.
- Expand and collapse all similar commands at once.
- A CLI.

## Invariants

- **The view is virtual.** `TranscriptView` draws only the lines on screen from a per-block
  cache of rendered strips. Do not mount a widget per block: a 1,000-block session then takes
  seconds to open.
- **Tool output can hold ANSI escapes.** The terminal view parses them with
  `Text.from_ansi`; the export strips them. Plain `Text(...)` shows them as raw `[33m`.
- **The transcript is not the conversation.** Filter records as
  [architecture.md](../architecture.md) says, or skill bodies, reminders and subagent turns
  leak into the view.

## Structure

All under `src/claude-viewer/claude_viewer/`.

- `transcript.py`: reads a `.jsonl` into `Block`s, pairs each tool call with its result,
  places a usage block after each message, and finds and lists sessions.
- `render.py`: one Rich renderable per block, in the `/resume` style. `--print` uses it.
- `app.py`: the Textual app. `PickerScreen` lists sessions; `SessionScreen` holds
  `TranscriptView`, the status line and the find box.
- `export.py`: Markdown export. Tool output and thinking go in `<details>`, diffs in `diff`
  fences.
- `cli.py`: arguments and dispatch.

Tests are in `src/claude-viewer/tests/`. `conftest.py` builds a small transcript with every
record kind the parser handles.

## Design

A simple terminal CLI. Its output matches the detailed transcript view Claude Code shows
for a session opened with `/resume`, so a session reads the way it did in Claude Code. The
goals above go on top of that view.

### Opening a session

With no argument, a picker lists sessions like `/resume` does, scoped to the current
directory's project. A flag widens it to every project. A session ID or `.jsonl` path opens
that session directly.

### Default view

Matches `/resume`: prompts and replies in full, each tool call on one line with its output
collapsed, and file-edit diffs open.

### Similar commands

Calls are similar when they use the same tool: every Bash call, every Read, every Edit.
Expand all and collapse all act on one tool's calls.

### Hidden content

Shown collapsed: thinking blocks, attachments (one placeholder line with the file name) and
per-turn token usage with the model name. System reminders are not shown.

### Keys

less/vim style: `j`/`k` move, `/` finds, `n`/`N` step through matches, `g`/`G` go to top and
bottom, Enter or a click toggles a block, `e`/`c` expand or collapse every call of the
selected block's tool, `E`/`C` every block, `q` goes back or quits. Arrow keys also work.

### Command

`claude-viewer`.

### First version

The view above, plus export of a session to Markdown, with diffs in `diff` fences. HTML
export, search across sessions, live follow and nested subagent transcripts come later.

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
- The session view draws only the lines on screen. The largest session (1,068 blocks)
  opens in 0.8 s and expands fully in 1.2 s, measured.

## Build and deploy

`tools/build.sh claude-viewer` runs the tests with `uv run pytest` and, when they pass,
installs the package with `uv tool install --force --reinstall`. The command lands in
`~/.local/bin/claude-viewer`. The build refuses while a copy is running, unless `--force`.

## Open design decisions

- **Confirmation.** Who confirms a change works, and how. Settles `confirm` in
  `docs/workflow.json`.
