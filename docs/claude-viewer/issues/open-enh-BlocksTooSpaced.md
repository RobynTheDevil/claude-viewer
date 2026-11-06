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
- Every nested indent is one space, like the prompt's `> `: the elbow is ` ⎿ `, thinking and
  note bodies and usage rows indent 1, the usage head is ` · `.
- A collapsed block has no blank line after it; an expanded one keeps it.
- A collapsed result shows only `… +N lines` (`… +1 line`, `(no output)` when empty). A
  collapsed Read's `Read N lines` and an Edit's summary stay. The command under `• Bash`
  keeps its 3-line preview.
- `y` still copies without the markers.

## Design
### 1. Constants and one condition
Change the marker strings in `render.py` and the matching `MARKERS`/`MARKER_WIDTH` in
`selection.py`. Add `not block.collapsed` to the blank-line condition: the blank depends only
on the block itself, which a toggle re-renders. Replace the output preview with the count.

## Affected Code
- `src/claude-viewer/claude_viewer/render.py:28-30`, `:293-317`, `:360-377`
- `src/claude-viewer/claude_viewer/selection.py:12-13`
- `src/claude-viewer/claude_viewer/app.py:189`
- `src/claude-viewer/tests/test_viewer.py:49`, `:139`, `:245-247`

## Priority
Medium

## Related Files
- `docs/claude-viewer/project.md`: Behaviour table and the hidden-blocks paragraph
