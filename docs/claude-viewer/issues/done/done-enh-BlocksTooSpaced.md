# Enhancement: Blocks Too Spaced

## Goal
Fit more of a session on screen: smaller indents, and collapsed blocks packed together.

## Current Behaviour
- The result elbow is `  ⎿  `, 5 cells (`render.py:30`). Thinking and note bodies indent 2
  (`render.py:363`, `:377`), usage rows 4 (`:369`), the usage head starts `  · ` (`:365`).
- Every shown block ends with a blank line unless a usage line follows it
  (`TranscriptView._strips`, `app.py:189`).
- A collapsed tool result shows its first 3 lines then `… +N lines` (`render.py:314-317`).

## Desired Behaviour
- Every nested indent is one space, like the prompt's `> `: the elbow is ` ⎿ ` and note
  bodies indent 1.
- A collapsed block has no blank line after it and an expanded one keeps it, except that a
  shell call always keeps it and an attachment never has one.
- On open, Read calls, read-only shell calls, attachments and usage lines are collapsed and
  everything else is open.
- The `image` kind is `attachment`, since it also covers files, PDFs and directories.
- A collapsed result shows only `> N lines` at column 0, level with a command's `$`
  (`> 1 line`, `> no output` when empty). A
  collapsed Read's `Read N lines` and an Edit's summary stay. A Bash command keeps its
  3-line preview.
- The cursor gutter is one column: `▌` on the cursor block, a space elsewhere.
- A Bash call reads `$ <command>`, the `$` in the dot's color, continuation lines under the
  command. Replies, thinking and usage start with the dot, white for a reply and thinking:
  `• Thinking…`, `• <model> · …`. `⏺` read as `@` in Robyn's font.
- A tool's argument wraps instead of being cut at 100 characters with `…`. A command wraps
  at spaces; a word wider than the window is split at the edge by character instead, so
  `grep -n "long|pattern"` keeps the pattern on the `$` line and nothing is cut.
- `y` still copies without the markers, `$ ` included.

## Design
### 1. Constants and one condition
Change the marker strings in `render.py` and the matching `MARKERS`/`MARKER_WIDTH` in
`selection.py`. `render.spaced` decides the blank line from the block itself, which a toggle
re-renders, and `--print` uses it too. Replace the output preview with the count.

## Affected Code
- `src/claude-viewer/claude_viewer/render.py:28-30`, `:293-317`, `:360-377`
- `src/claude-viewer/claude_viewer/selection.py:12-13`
- `src/claude-viewer/claude_viewer/app.py:189`
- `src/claude-viewer/tests/test_viewer.py:49`, `:139`, `:245-247`

## Priority
Medium

## Related Files
- `docs/claude-viewer/project.md`: Behaviour table and the hidden-blocks paragraph
