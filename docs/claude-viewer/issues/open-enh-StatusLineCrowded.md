# Enhancement: Status Line Crowded

## Goal
A shorter status line with the common keys, and a `?` help screen with every key, the filter,
usage and times.

## Current Behaviour
`SessionScreen._update_status` (`app.py:683-699`) writes
`3/214 [tool]  ·  enter toggle  o/x block  O/X tool  f filter  U usage  - outline  / find  q back`,
with `ctrl+c quit` in place of `q back` for a session opened directly. No `?` key exists; the
full key list lives only in `project.md`.

## Desired Behaviour
- The status line reads
  `3/214 · enter toggle  o/x open/close  O/X all[tool]  - outline  / find  ctrl+c quit  ? help`,
  with the cursor block's group in the brackets.
- The visual-mode prefix, the filter name (`3/214 changes`) and a notice (`3 lines copied`,
  `not found`) still show, after the count.
- `?` opens a help screen listing every key, including `f`, `U` and `t`. Esc, `q` or `?`
  closes it.

## Design
### 1. Rewrite the hint, add a `ModalScreen`
The hint becomes one fixed string with the group in it. `HelpScreen(ModalScreen)` holds a
scrollable `Static` of the key table, pushed by a `question_mark` binding on `SessionScreen`.
No modal exists in the code yet; the outline is a docked `OptionList`, which suits a menu but
not a reference page.

## Affected Code
- `src/claude-viewer/claude_viewer/app.py:640-647`: `SessionScreen.BINDINGS`
- `src/claude-viewer/claude_viewer/app.py:683-699`: `_update_status`

## Priority
Medium

## Related Files
- `docs/claude-viewer/project.md`: the keys table
