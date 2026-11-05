# Enhancement: Visual Mode Yank

## Goal
Select text in the view with vim keys and copy it to the Windows clipboard, so that a
command, a diff or a reply can be pasted somewhere else.

## Current Behaviour
The view has only a block cursor (`claude_viewer/app.py:52`), with no cell cursor and no
selection. `render_line` (`app.py:97-105`) takes the block's cached strip, adds the 2-cell
gutter and crops it. Textual's own mouse selection (`textual/widget.py:4213`
`get_selection`, `ctrl+c` at `textual/screen.py:272`) doesn't work on a custom
`render_line` widget unless `get_selection` is overridden.

## Desired Behaviour
- **Normal mode has a caret.** A cell cursor is always shown, as in vim. It starts on the
  first line of the session. The block cursor is the block the caret is in, so the status
  line, Enter and `e`/`c` act on that block.
- **Motions in normal mode:** `h` `j` `k` `l`, `w` `b`, `0` `^` `$`, `gg` `G`, `{` `}`,
  `ctrl+d`/`ctrl+u`. The view scrolls to keep the caret visible.
- `e` and `c` keep their meanings (expand and collapse the tool's calls), so vim's `e`
  motion is left out.
- `v` starts a character selection and `V` a line selection, from the caret. Motions extend
  the selection.
- `y` copies the selection and returns to normal mode. The status line reports how many
  lines were copied.
- Copied text is the rendered text without the gutter and without the block markers (`⏺ `,
  `  ⎿  `), with trailing spaces removed.
- `Esc` in visual mode returns to normal mode. Only an `Esc` in normal mode reaches
  `SessionScreen`'s close (`app.py:210`).
- When a block collapses under the caret, the caret moves to that block's first line.
- Check: select the three lines of a Bash command's output with `V` `j` `j` `y`, paste into
  Notepad, and get those three lines with no `⎿` and no padding.

## Design
### 1. A mode on `TranscriptView`, drawn per line
- **State.** Add a `mode` reactive (`normal`, `visual`, `line`), a caret `(line, col)` that
  exists in every mode, and an anchor for the selection. Derive `cursor` from the caret's
  line with `bisect_right(self._offsets, line) - 1`, so the status line and
  `enter`/`e`/`c` still work.
- **Drawing.** In `render_line`, split the strip with `strip.divide` and style the caret cell
  and the selection with `apply_style(Style(reverse=True))` (`textual/strip.py:576,606`).
  Offset by `GUTTER`. Draw this per line and never in `_cache`, so moving the caret doesn't
  re-render blocks.
- **Text.** `Strip.text` (`textual/strip.py:124`) gives a line's characters. Every block is a
  `marked()` grid (`render.py:72-77`) whose first column is `len(marker)` cells, so drop that
  many cells. Store the marker width per block next to `_cache`. Wrapped lines copy as
  separate lines, because the strips don't record soft wraps.
- **Keys.** Several keys already have meanings (`j` `k` `g` `G` `e` `c` `E` `C`). Bind each
  key once to an action that dispatches on `mode`, or bind both meanings and gate them with
  `check_action` (`textual/dom.py:1909`). The dispatch is simpler because no Footer shows the
  bindings. `gg` needs a pending-key state.
- **Clipboard.** Call `App.copy_to_clipboard` (OSC 52, `textual/app.py:1770-1786`). Under WSL
  (`WSL_DISTRO_NAME` set), also pipe the text to `/mnt/c/Windows/system32/clip.exe` as UTF-16
  LE with a BOM, so that `⏺`, `⎿` and other non-ASCII text survive. `wl-copy`, `xclip` and
  `xsel` are not installed.

### 2. Override Textual's mouse selection
Implement `get_selection` on `TranscriptView` and use Textual's drag-to-select with
`ctrl+c`. That gives mouse selection but no vim motions, which is what's asked for. It can be
added later alongside option 1.

## Affected Code
- `src/claude-viewer/claude_viewer/app.py:33-183` (`TranscriptView`: state, bindings,
  `render_line`)
- `src/claude-viewer/claude_viewer/app.py:186-275` (`SessionScreen`: Esc, status)
- `src/claude-viewer/claude_viewer/render.py:72-77` (`marked`, which sets the marker widths)

## Open Questions
- Does Windows Terminal accept OSC 52, and is there a size limit? This is untested. With
  `clip.exe` also used, OSC 52 is only a fallback, so this matters only off WSL.
- How do Markdown lists and code blocks copy? Settled: as rendered, with ` • ` bullets and
  their indentation kept, since the marker-width rule only drops the grid's first column.

## Priority
Medium

## Related Files
- [open-enh-LineScrollBlockMotions.md](done-enh-LineScrollBlockMotions.md), which sets the
  normal-mode meanings of `j` and `k`
- [open-enh-HalfPageScroll.md](done-enh-HalfPageScroll.md)
