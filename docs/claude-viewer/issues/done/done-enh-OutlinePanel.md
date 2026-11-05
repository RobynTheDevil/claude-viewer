# Enhancement: Outline Panel

## Goal
See every prompt in a session at once and jump straight to one.

## Current Behaviour
`SessionScreen.compose` (`claude_viewer/app.py:220-226`) stacks the title, the view, the
status line and the find box vertically. Nothing lists the prompts.

## Desired Behaviour
- `-` opens a simple menu at the bottom of the screen, above the status line. It lists every
  prompt by its first line, at most 10 rows high, and scrolls when there are more.
- The menu takes focus when it opens and highlights the prompt that contains the cursor.
- `j`/`k` move in the menu. Enter jumps the view to that prompt, closes the menu and returns
  focus to the view.
- `Esc`, `q` or `-` closes the menu without moving, before anything closes the screen.
- Check: open the menu on the 37 MB session, pick the third prompt, and the view shows it at
  the top. Reopen the menu, and the third prompt is highlighted.

## Design
### 1. An OptionList docked at the bottom
- **Layout.** Add an `OptionList` (`#outline`, `display: none`, `max-height: 10`) to
  `SessionScreen.compose`, between the view and the status line.
- **Toggle.** Bind `minus` (`textual/keys.py:209`) on `SessionScreen` to show it, highlight
  the cursor's prompt, and focus it.
- **Keys.** Give it the `SessionList` `j`/`k` bindings (`app.py:281-287`).
- **Jump.** On `OptionList.OptionSelected`, call `view.action_jump(prompt_index[n])`, hide
  the menu and focus the view.
- **Close order.** `action_close` (`app.py:270`) hides the menu first.

The menu changes only the view's height. `_layout` (`app.py:79-88`) clears the cache only
when the width changes, so opening the menu re-uses every rendered block.

Robyn chose this over a side panel, which narrows the view and re-renders every block,
about 0.8 s on the largest session.

## Affected Code
- `src/claude-viewer/claude_viewer/app.py:186-275` (`SessionScreen`: CSS, compose,
  bindings, close)
- `src/claude-viewer/claude_viewer/app.py:79-95` (layout on resize)
- `src/claude-viewer/claude_viewer/app.py:281-287` (`SessionList` key bindings to reuse)

## Priority
Medium

## Related Files
- [done-enh-JumpBetweenPrompts.md](done-enh-JumpBetweenPrompts.md)
