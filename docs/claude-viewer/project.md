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
  Map a character index to a cell with `selection.index_to_cell`, not Textual's
  `Strip.index_to_cell_position`, which raises on the empty strip a blank line renders as.
- **Syntax colors are foreground only.** Pygments themes put their background on every
  token, which covers the diff's add and remove backgrounds. `highlight_lines` keeps each
  token's color, bold and italic and nothing else.
- **Pick a lexer by file name, never by content.** `Syntax.guess_lexer` with code imports
  every Pygments lexer, 3 s on `/mnt/c`. `lexer_for` looks up the suffix and caches it.
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
  Diffs and expanded Reads are colored by the file's language.
- `app.py`: the Textual app. `PickerScreen` lists sessions; `SessionScreen` holds
  `TranscriptView`, the status line and the find box.
- `export.py`: Markdown export. Tool output and thinking go in `<details>`, diffs in `diff`
  fences.
- `editor.py`: the file and line a call touched, and the editor command that opens it.
- `selection.py`: caret word motions, marker widths, the selection overlay and the
  Windows clipboard.
- `cli.py`: arguments and dispatch.

Tests are in `src/claude-viewer/tests/`. `conftest.py` builds a small transcript with every
record kind the parser handles.

## Behaviour

| | |
|---|---|
| Command | `claude-viewer` |
| Opening | No argument: a picker of the current directory's project sessions, like `/resume`; `--all` lists every project. A session ID, ID prefix or `.jsonl` path opens that session. |
| Default view | Prompts and replies in full, each tool call on one line with its output collapsed, file-edit diffs open. |
| Similar calls | Calls to the same tool: every Bash, every Read, every Edit. `O`/`X` act on them together. |
| Shown collapsed | Thinking blocks, attachments (one line with the file name), per-message token usage and model. |
| Not shown | System reminders, `isMeta` text, subagent turns. |

Keys, vim style. Arrow keys work as `h`/`j`/`k`/`l`.

| Key | Action |
|---|---|
| `j`/`k` | move the caret a line; the view scrolls at its edge |
| `h`/`l`, `w`/`b`, `0`/`^`/`$` | move the caret along the line, by word, or to its start, first non-blank or end |
| `ctrl+e`/`ctrl+y` | scroll one line |
| `ctrl+d`/`ctrl+u` | scroll half a page; the caret keeps its screen row |
| PgDn/PgUp | scroll a page, the same way |
| `v`/`V` | start a character or line selection; `y` copies it, Esc cancels |
| `}`/`{` | next or previous block; the caret goes to its first line |
| `]]`/`[[` | next or previous prompt, scrolled to the top |
| `gg`/`G` | top and bottom; Home and End too |
| `gf` | open a Read, Edit or Write's file in the editor at the line it touched |
| Enter, click | toggle the block |
| `o`/`x` | expand or collapse the block |
| `O`/`X` | expand or collapse every block of the cursor block's kind, or every call to its tool |
| `E`/`C` | expand or collapse every block |
| `f` | cycle the filter: all, read-only, changes |
| `u` | show or hide token usage lines |
| `t` | show or hide times: a prompt's local time, a call's duration, and the gap before either when over 5 s |
| `-` | the outline: a menu of every prompt; `j`/`k` and Enter jump, Esc, `q` or `-` close |
| `/`, `n`/`N` | find by regular expression, next and previous match |
| Esc | leave visual mode, else clear the match highlights, else back |
| `q` | back, or quit |

**The caret is the cursor.** Normal mode always shows a caret, a line and a character index into
that line's strip. The block cursor is the block holding it, so the status line, Enter, `o`/`x`
and `O`/`X` act on that block. A scroll by `ctrl+e`, page or wheel that would take the caret off
screen moves it to the nearest visible line. A block motion, a toggle or a filter change puts
the caret on the cursor block's first line. The caret and the selection are drawn per line in
`render_line`.

`y` copies the selection as drawn, a wrapped line as its own line, without the gutter or
the `⏺ ` and `  ⎿  ` markers and with trailing spaces removed. Rendered Markdown copies
with its bullets and indentation. The text goes to `App.copy_to_clipboard` (OSC 52) and,
under WSL, to `clip.exe` as UTF-16 LE with CRLF line ends and no BOM, since `clip.exe`
pastes a BOM as a character.

Two-key motions go through a prefix handler in `TranscriptView.on_key`; a first key followed
by anything else, or by nothing for 1 s, does nothing.

**Hidden blocks take no lines.** The filter and the usage toggle set `TranscriptView.shown`;
a hidden block's strips are empty, so `bisect_right` over the offsets lands on the visible
block after a run of hidden ones. Motions, search and `O`/`X`/`E`/`C` skip hidden blocks, and
the blank line after a block depends on the next shown one, so a change of visibility clears
the whole cache. A call is a change when its result has a `structuredPatch`; every other call
is read-only, Bash included, whatever it ran. Prompts and replies show under every filter,
thinking and notes only under all, and a usage line only while a block of its message shows.
`--no-usage` starts with usage hidden and leaves it out of `--print` and `--export`. No
settings file exists; an alias carries the flag.

The outline is an `OptionList` above the status line, at most 10 rows. It changes only the
view's height, so opening it re-renders nothing. It opens on the prompt containing the
cursor.

`gf` suspends the viewer and runs `$VISUAL`, then `$EDITOR`, then `nvim`, then `less`, with
`+N path`, or `-g path:N` for VS Code. The line is an Edit's first changed line, a Read's
`offset` or `startLine`, and 1 for a Write. A Windows path goes through `wslpath`. `nvr
--remote-wait +N` lands on line N and returns when the buffer is closed.

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
- The largest session (1,068 blocks) opens in 1.4 s and expands fully in 1.9 s, measured
  on the installed build. Of the open, 0.23 s is highlighting its 1,809 diff lines and up
  to 0.26 s loading the two lexers.
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
