# Enhancement: Jump Between Prompts

## Goal
Step through a session one turn at a time, from one typed prompt to the next.

## Current Behaviour
The block cursor moves one block at a time (`claude_viewer/app.py:139`) or to the top or
bottom (`app.py:144`). Nothing knows where the prompts are. Textual has no key-sequence
support (`textual/binding.py`), so two-key bindings need code of their own.

## Desired Behaviour
- `]]` moves the cursor to the next `prompt` block and `[[` to the previous one. The view
  scrolls the prompt to the top of the screen.
- At the last prompt, `]]` does nothing and the status line says so. The same applies to
  `[[` at the first prompt.
- A single `[` or `]` followed by any other key, or by nothing for 1 s, does nothing.
- Check: in a session with 5 prompts, `]]` four times from the top reaches the fifth prompt,
  and `[[` goes back to the fourth.

## Design
### 1. A shared prefix-key handler
Add an `on_key` to `TranscriptView`. It runs before the widget's `BINDINGS`
(`textual/app.py:4136,4341`), so it can hold a first key:
1. A first `[` or `]` (`left_square_bracket` and `right_square_bracket`,
   `textual/keys.py:235-237`) sets `_pending`, starts `set_timer(1.0, ...)` to clear it,
   and stops the event.
2. A matching second key runs `action_prompt(±1)`.

Build a sorted list of prompt indexes in `__init__` and `bisect` the cursor into it. The same
handler serves `gg` and `gf` ([OpenFileAtLine](done-enh-OpenFileAtLine.md)).

### 2. Single keys
Bind `[` and `]` alone. This is simpler, but it isn't what vim does and it leaves no room for
other bracket motions later.

## Affected Code
- `src/claude-viewer/claude_viewer/app.py:33-60` (`TranscriptView` init and bindings)
- `src/claude-viewer/claude_viewer/app.py:139-147` (`action_move`, `action_jump`)
- `docs/claude-viewer/project.md` (Keys)

## Priority
High

## Related Files
- [open-enh-OutlinePanel.md](done-enh-OutlinePanel.md), which uses the same prompt index
