# Enhancement: Highlight Matches

## Goal
See every search match on screen, not just which block the cursor landed on.

## Current Behaviour
`find()` (`claude_viewer/app.py:171-183`) moves the cursor to the matching block and expands
it. Nothing in `render_line` (`app.py:97-105`) knows about the query, so the match itself
isn't marked. The query is stored on `SessionScreen.query_text`.

## Desired Behaviour
- After a search, every match in the visible lines has a highlight background. The match the
  cursor is on has a stronger one.
- The highlight follows the query from [RegexSearch](done-enh-RegexSearch.md), including
  smart case.
- An empty query or `Esc` in normal mode clears the highlights.
- Scrolling and toggling blocks keep the highlights without re-rendering blocks.
- Check: `/git` on the 37 MB session highlights every `git` on screen. Scrolling with `j`
  stays smooth.

## Design
### 1. Highlight per drawn line
In `render_line`, before the gutter is added:
1. Run the pattern over `strip.text`.
2. Convert character indexes to cells with `strip.index_to_cell_position`
   (`textual/strip.py:263`).
3. Cut with `strip.divide` (`strip.py:576`), `apply_style` the matched pieces (`strip.py:606`),
   and join with `Strip.join` (`strip.py:285`).

This costs one regex per visible line per repaint and never touches `_cache`. Limits:
- A match that wraps across lines isn't highlighted.
- A match in a collapsed body, or in tool input that isn't drawn, finds a block with
  nothing highlighted.

### 2. Highlight in the cached render
Apply `Text.highlight_regex` when the block is rendered. That handles wrapped matches, but a
new query clears and re-renders every block.

## Affected Code
- `src/claude-viewer/claude_viewer/app.py:97-105` (`render_line`)
- `src/claude-viewer/claude_viewer/app.py:254-265` (pass the query to the view)

## Priority
Medium

## Related Files
- [open-enh-RegexSearch.md](done-enh-RegexSearch.md)
