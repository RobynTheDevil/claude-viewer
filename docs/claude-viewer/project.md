# claude-viewer

A terminal viewer for Claude Code session transcripts, for Robyn, replacing Mantra. It shows a
session the way Claude Code's detailed `/resume` view does, adds colored diffs and expand or
collapse of every call to one tool, and exports to Markdown. Working: built and installed with
`tools/build.sh claude-viewer`.

Open work is in [todo.md](todo.md).

## Invariants

- **The view is virtual.** `TranscriptView` draws only the lines on screen from a per-block
  cache of rendered strips. Do not mount a widget per block: a 1,000-block session then takes
  seconds to open.
- **The scrollbar gutter is reserved.** `scrollbar-gutter: stable` keeps the content width
  fixed whether the scrollbar shows or not. Without it the first layout renders 2 cells too
  wide, and the next resize re-renders every block.
- **Per-line overlays are drawn in `render_line`, never cached.** Match highlights and the
  gutter go on the strip as it is drawn, so a new query or a cursor move re-renders nothing.
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

## Behaviour

| | |
|---|---|
| Command | `claude-viewer` |
| Opening | No argument: a picker of the current directory's project sessions, like `/resume`; `--all` lists every project. A session ID, ID prefix or `.jsonl` path opens that session. |
| Default view | Prompts and replies in full, each tool call on one line with its output collapsed, file-edit diffs open. |
| Similar calls | Calls to the same tool: every Bash, every Read, every Edit. `e`/`c` act on them together. |
| Shown collapsed | Thinking blocks, attachments (one line with the file name), per-message token usage and model. |
| Not shown | System reminders, `isMeta` text, subagent turns. |

Keys, less/vim style. Arrow keys work as `j`/`k`.

| Key | Action |
|---|---|
| `j`/`k` | scroll one line |
| `ctrl+d`/`ctrl+u` | scroll half a page; the cursor keeps its screen row |
| PgDn/PgUp | scroll a page, the same way |
| `}`/`{` | next or previous block |
| `]]`/`[[` | next or previous prompt, scrolled to the top |
| `gg`/`G` | top and bottom; Home and End too |
| Enter, click | toggle the block |
| `e`/`c` | expand or collapse every call to the cursor block's tool |
| `E`/`C` | expand or collapse every block |
| `f` | cycle the filter: all, read-only, changes |
| `u` | show or hide token usage lines |
| `/`, `n`/`N` | find by regular expression, next and previous match |
| Esc | clear the match highlights, or back when there are none |
| `q` | back, or quit |

The block cursor stays on screen: any scroll that would leave it off moves it to the first
visible block going down or the last going up. Two-key motions go through a prefix handler
in `TranscriptView.on_key`; a first key followed by anything else, or by nothing for 1 s,
does nothing.

**Hidden blocks take no lines.** The filter and the usage toggle set `TranscriptView.shown`;
a hidden block's strips are empty, so `bisect_right` over the offsets lands on the visible
block after a run of hidden ones. Motions, search and `e`/`c`/`E`/`C` skip hidden blocks, and
the blank line after a block depends on the next shown one, so a change of visibility clears
the whole cache. A call is a change when its result has a `structuredPatch`; every other call
is read-only, Bash included, whatever it ran. Prompts and replies show under every filter,
thinking and notes only under all, and a usage line only while a block of its message shows.
`--no-usage` starts with usage hidden and leaves it out of `--print` and `--export`. No
settings file exists; an alias carries the flag.

Search is a Python regular expression with smart case: it ignores case unless the query has
an uppercase letter. It matches a block's text, its header as drawn (`Bash(git status)`),
its result and its string inputs. Every match on screen is highlighted, more strongly in the
cursor block. A match wrapped across two lines, or inside a collapsed body, is not
highlighted.

Not built and not yet in the todo: HTML export, search across sessions, live follow, nested
subagent transcripts.

## Stack

Python with Textual for the interactive view and Rich for rendering, packaged with `uv`.
Chosen over Rust because Python 3.14 and `uv` are installed here and Rust is not, and
because speed is not the limit at this data size:

- Filtering and parsing every local transcript (177 files, largest 37 MB) in Python takes
  0.8 s, measured. Search across sessions is to shell out to `rg`. Move it to Rust only if
  search over a full history passes about 1 s.
- The largest session (1,068 blocks) opens in 0.8 s and expands fully in 1.2 s, measured.
- Edit results carry `structuredPatch`, so diffs come from the transcript and are not
  recomputed.
- `--print` writes the default view through Rich alone, for pipes and `less -R`.

## Build and deploy

`tools/build.sh claude-viewer` runs the tests with `uv run pytest` and, when they pass,
installs the package with `uv tool install --force --reinstall`. The command lands in
`~/.local/bin/claude-viewer`. The build refuses while a copy is running, unless `--force`.

## Open design decisions

- **Confirmation.** Who confirms a change works, and how. Settles `confirm` in
  `docs/workflow.json`.
