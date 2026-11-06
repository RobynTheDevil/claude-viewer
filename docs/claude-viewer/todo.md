How these are worked: [workflow.md](../workflow.md#items).

Key:
Items are plain `- ` lines. Their status is not written here: the worktree working one claims
it with the `workflow` skill, and the startup survey reads the claims from every tree. No
marker is open, `~` in progress, `+` has update note, `x` confirmed and ready for `wf close`.

Reasoning is recorded here only while a fix is unconfirmed. Once confirmed it moves to
[project.md](project.md) and the line moves to [done.md](done.md), reduced to one entry.

Robyn will update with **note** or similar when an item is tested. Only they confirm
an item, and the claim moves to `x` on their word.

## defects:

Each open defect has a report in [issues/](issues/) carrying the reproduction, the root
cause and the candidate fixes. This list is the status; the report is the record.

None open.

## enhancements:

- [Usage Shown By Default](issues/open-enh-UsageShownByDefault.md)
    - Test: no usage lines on open; `U` shows them; `--usage` shows them from the start.
- [Status Line Crowded](issues/open-enh-StatusLineCrowded.md)
    - Test: the status line reads as asked, `O/X all[Bash read]` or `all[Bash write]` on a shell call, and `O`/`X` act on that half only; `?` expands the help at the bottom with filter, usage, times and scrollbar; Esc, `q` or `?` closes it; `ctrl+s` toggles the scrollbar, off at start.
- [Blocks Too Spaced](issues/open-enh-BlocksTooSpaced.md)
    - Test: one-column `▌` gutter; Bash reads `$ <command>` with a colored `$`; `• ` white for replies and thinking, dim for usage; long tool arguments wrap; a long command folds at the window edge with nothing cut; ` ⎿ ` elbow; a run of collapsed calls has no blank lines; a collapsed result shows only `> N lines`, level with the `$`; `y` copies without markers.

## back-burner:

Items that are real and not being worked: too large to scope yet, cosmetic and waiting on a
feature that would absorb them, or blocked on someone else. Each still says what it is and
why it is waiting, so it does not get rediscovered as a new item.
