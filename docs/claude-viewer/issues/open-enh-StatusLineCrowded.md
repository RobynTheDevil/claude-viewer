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
- `?` expands a help panel above the status line: the filter, usage, times and scrollbar
  state and every key, including `f`, `U`, `t` and `ctrl+s`. Esc, `q` or `?` closes it. `?`
  in the find box types a `?`.
- `ctrl+s` shows or hides the scrollbar, hidden by default.

## Design
### 1. Rewrite the hint, dock a help panel
The hint becomes one fixed string with the group in it. The help is a hidden `Static` docked
above the status line like the outline, opened from `SessionScreen.on_key` on the `?`
character. A first build pushed a `ModalScreen` from a `question_mark` binding; it passed the
pilot test and did nothing in Robyn's terminal, so the key is matched by character.

## Affected Code
- `src/claude-viewer/claude_viewer/app.py:640-647`: `SessionScreen.BINDINGS`
- `src/claude-viewer/claude_viewer/app.py:683-699`: `_update_status`

## Priority
Medium

## Related Files
- `docs/claude-viewer/project.md`: the keys table
