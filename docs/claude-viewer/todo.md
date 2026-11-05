How these are worked: [workflow.md](../workflow.md#items).

Key:
Items are plain `- ` lines. Their status is not written here: the worktree working one claims
it with the `workflow` skill, and the startup survey reads the claims from every tree. No
marker is open, `~` in progress, `+` has update note, `x` confirmed and ready for `wf close`.

Reasoning is recorded here only while a fix is unconfirmed. Once confirmed it moves to
[project.md](project.md) and the line moves to [done.md](done.md), reduced to one entry.

<The person> will update with **note** or similar when an item is tested. Only they confirm
an item, and the claim moves to `x` on their word.

## defects:

Each open defect has a report in [issues/](issues/) carrying the reproduction, the root
cause and the candidate fixes. This list is the status; the report is the record.

None open.

## enhancements:

None open.

## back-burner:

Items that are real and not being worked: too large to scope yet, cosmetic and waiting on a
feature that would absorb them, or blocked on someone else. Each still says what it is and
why it is waiting, so it does not get rediscovered as a new item.
