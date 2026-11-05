# Enhancement: Half Page Scroll

## Goal
Move through a long session half a screen at a time with the vim keys, so the reader keeps
some context from the previous view.

## Current Behaviour
`TranscriptView` (`claude_viewer/app.py:33`) binds no ctrl keys (`app.py:40-50`). PgUp and
PgDn come from Textual's `ScrollableContainer` (`textual/containers.py:49-58`). They scroll
by a full `scrollable_content_region.height` (`textual/widget.py:3389`) and leave the block
cursor where it was, so the cursor can end up off screen.

## Desired Behaviour
- `ctrl+d` scrolls down by half the view height, and `ctrl+u` scrolls up by half.
- The block cursor moves with the scroll and keeps its screen row. The cursor block is the
  block under that row after the scroll.
- PgUp and PgDn scroll a full page and move the cursor the same way.
- The scroll clamps at the top and the bottom.
- While the find box has focus, `ctrl+u` and `ctrl+d` keep their `Input` meanings (delete
  left and delete right, `textual/widgets/_input.py:120,126`).
- Check: on the 37 MB session at 120x40, `ctrl+d` five times then `ctrl+u` five times
  returns to the same scroll offset and the same cursor block.

## Design
### 1. One scroll-by-rows action
Add `action_scroll_rows(rows)`:
1. Record the cursor's screen row.
2. Call `scroll_to(y=scroll_offset.y + rows, animate=False, immediate=True)`.
3. Set the cursor to `bisect_right(self._offsets, new_y + row) - 1`.

This is the same anchoring that `on_resize` uses (`app.py:90-95`). Bind `ctrl+d` and `ctrl+u`
to `±height // 2`, and PgDn and PgUp to `±height`. Textual binds only `ctrl+q` and `ctrl+c`
at the App level (`textual/app.py:455-463`), so these keys don't clash.

### 2. Textual's page actions plus a scroll watcher
Keep Textual's `page_down` and `page_up`, and add a `watch_scroll_y` that moves the cursor
into view. That doesn't give a half page, so `ctrl+d` and `ctrl+u` still need option 1. The
watcher is part of [LineScrollBlockMotions](done-enh-LineScrollBlockMotions.md).

## Affected Code
- `src/claude-viewer/claude_viewer/app.py:40-50` (bindings)
- `src/claude-viewer/claude_viewer/app.py:90-118` (`on_resize`, `_show_cursor` anchoring)
- `src/claude-viewer/claude_viewer/app.py:233` (status line, which shows the cursor)
- `docs/claude-viewer/project.md` (Keys)

## Priority
Medium

## Related Files
- `src/claude-viewer/tests/test_viewer.py`
- [open-enh-LineScrollBlockMotions.md](done-enh-LineScrollBlockMotions.md)
