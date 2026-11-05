# Enhancement: Outline Panel

## Goal
See every prompt in a session at once and jump straight to one.

## Current Behaviour
`SessionScreen.compose` (`claude_viewer/app.py:220-226`) stacks the title, the view, the
status line and the find box vertically. Nothing lists the prompts.

## Desired Behaviour
- `-` toggles a panel on the left, about 32 columns wide, that lists every prompt by its
  first line.
- When the panel opens, it takes focus and highlights the prompt that contains the cursor.
- `j`, `k` and Enter work in the panel. Enter jumps the view to that prompt and returns focus
  to the view. The panel stays open.
- While the panel is open, moving the cursor in the view moves the panel's highlight.
- `Esc` or `q` closes the panel before it closes the screen.
- Check: open the panel on the 37 MB session, pick the third prompt, and the view shows it
  at the top. Close and reopen the panel, and the third prompt is still highlighted.

## Design
### 1. An OptionList beside the view
- **Layout.** Put `TranscriptView` and an `OptionList` (`#outline`, `display: none`) in a
  `Horizontal` with height `1fr`.
- **Toggle.** Bind `minus` (`textual/keys.py:209`) on `SessionScreen` to show or hide it.
- **Jump.** On `OptionList.OptionSelected`, call `view.action_jump(prompt_index[n])`.
- **Sync.** Keep the highlight in step through the existing cursor watch (`app.py:233`).
- **Close order.** `action_close` (`app.py:270`) hides the panel first.

Opening the panel changes the view's width. That runs `on_resize` → `_layout`
(`app.py:79-95`), which clears and re-renders every block: about 0.8 s on the largest
session. To avoid it, render at the narrower width once and keep it, or overlay the panel
without resizing.

### 2. An overlay
Show the outline as a modal `Screen` over the view. The view's width doesn't change, so
there is no re-render, but the view isn't visible beside the list.

## Affected Code
- `src/claude-viewer/claude_viewer/app.py:186-275` (`SessionScreen`: CSS, compose,
  bindings, close)
- `src/claude-viewer/claude_viewer/app.py:79-95` (layout on resize)

## Open Questions
- Is a re-render of about 0.8 s on opening acceptable, or should the panel be an overlay?
  Settled by trying the side panel on the largest session.

## Priority
Medium

## Related Files
- [open-enh-JumpBetweenPrompts.md](open-enh-JumpBetweenPrompts.md)
