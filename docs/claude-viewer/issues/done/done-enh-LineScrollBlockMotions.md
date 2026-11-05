# Enhancement: Line Scroll Block Motions

## Goal
Make `j` and `k` scroll one line, as they do in less and vim, and move the
block-to-block step to `{` and `}`.

## Current Behaviour
`j`/`down` and `k`/`up` call `action_move(±1)` (`claude_viewer/app.py:41-42`). That moves the
block cursor one block and scrolls it into view with `_show_cursor` (`app.py:110-118`). The
gutter marker is drawn only on lines of the cursor block (`app.py:97-105`). When the
mouse wheel scrolls that block off screen, no marker shows and the status line still names
it.

## Desired Behaviour
- `j`/`down` and `k`/`up` move by one line. Neither animates. Once
  [VisualModeYank](done-enh-VisualModeYank.md) adds the normal-mode caret, they move the
  caret one line and the view scrolls when the caret reaches its edge, as in vim. Build
  this item's line step so the caret can take it over.
- `}` moves the cursor to the next block and `{` to the previous block, the old `j`/`k`
  behaviour.
- After any scroll by line, page or mouse wheel, the cursor block is on screen. If
  it would leave the view, the cursor moves to the first visible block when scrolling down,
  or to the last visible block when scrolling up.
- The session picker's `j`/`k` (`app.py:281-287`) still move one session.
- Check: on a block taller than the screen, `j` scrolls through it line by line and the
  cursor stays on it. `}` then goes to the block after it.

## Design
### 1. Own line-scroll actions and one scroll watcher
1. Bind `j,down` to `action_scroll_rows(1)` and `k,up` to `action_scroll_rows(-1)`, from
   [HalfPageScroll](done-enh-HalfPageScroll.md).
2. Bind `}` and `{` to the existing `move(±1)`. Textual turns the characters into
   `right_curly_bracket` and `left_curly_bracket` (`textual/binding.py:154-155`,
   `textual/keys.py:241,243`).
3. Clamp the cursor in a `watch_scroll_y` on `TranscriptView`. That covers keys, pages and
   the wheel in one place. Skip the clamp while `_show_cursor` is the one scrolling.

### 2. Textual's `scroll_down` and `scroll_up`
Bind `j` and `k` to Textual's actions (`textual/widget.py:3234,3312`). They animate by
default, which makes held keys lag behind. Option 1 is preferred.

## Affected Code
- `src/claude-viewer/claude_viewer/app.py:40-50` (bindings)
- `src/claude-viewer/claude_viewer/app.py:110-118` (`_show_cursor`)
- `src/claude-viewer/tests/test_viewer.py:72,80` (press `j` to move blocks; change to `}`)
- `docs/claude-viewer/project.md` (Keys)

## Priority
High

## Related Files
- [done-enh-HalfPageScroll.md](done-enh-HalfPageScroll.md)
- [done-enh-VisualModeYank.md](done-enh-VisualModeYank.md), which also binds `j` and `k`
